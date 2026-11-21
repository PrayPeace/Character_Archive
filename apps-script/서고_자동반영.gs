/**
 * ◈프레이피스 캐릭터 서고 자동 반영
 * 이 코드는 원본 시트 "◈프레이피스 캐릭터 모음집"의 Apps Script(확장 프로그램 → Apps Script)에 붙여 넣습니다.
 *
 * 하는 일
 *  1) 모든 탭(숨김 포함)의 글자를 가려서(SYNC_KEY 없으면 못 읽음) sync/dump.bin 으로 깃허브에 올림
 *  2) 사이트에 아직 없는 새 탭이면, 그 탭에서 가장 큰 셀 그림을 sync/img/<탭이름>.png 로 올림
 *  3) 깃허브가 알아서 캐릭터 목록(characters.json)과 그림을 고치고 사이트에 반영 (몇 분 걸림)
 *  4) 요약 시트(v5)의 '캐릭터' 탭도 사이트 목록에 맞춰 다시 씀
 *
 * 처음 한 번만
 *  - 프로젝트 설정(톱니바퀴) → 스크립트 속성: GITHUB_TOKEN(깃허브 토큰), SYNC_KEY(깃허브 저장소 비밀값과 같은 값), LOG_PASSWORD(세션 로그 비밀번호)
 *  - 시트를 새로고침하면 위쪽 메뉴에 "📚 서고"가 생김 → "매일 자동 보내기 켜기"
 */
const REPO = 'PrayPeace/Character_Archive';
const BRANCH = 'main';
const SUMMARY_ID = '1dauOCIxwd8xORReChEVdK7RoYzZ3vBp6pTSah2dAC30'; // 요약 시트 v5

function onOpen() {
  SpreadsheetApp.getUi().createMenu('📚 서고')
    .addItem('지금 사이트로 보내기', 'syncToSite')
    .addItem('요약 시트 지금 맞추기', 'updateSummarySheet')
    .addItem('세션 한글 파일 링크 채우기', 'linkSessionFiles')
    .addSeparator()
    .addItem('매일 자동 보내기 켜기', 'installDailyTrigger')
    .addItem('매일 자동 보내기 끄기', 'removeDailyTrigger')
    .addToUi();
}

function installDailyTrigger() {
  removeDailyTrigger();
  ScriptApp.newTrigger('syncToSite').timeBased().everyDays(1).atHour(5).create();
  ScriptApp.newTrigger('updateSummarySheet').timeBased().everyDays(1).atHour(6).create();
  toast_('매일 새벽 5시에 사이트로 보내고, 6시에 요약 시트를 맞춰요.');
}
function removeDailyTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (['syncToSite', 'updateSummarySheet'].includes(t.getHandlerFunction())) ScriptApp.deleteTrigger(t);
  });
}

/* ---------- 1. 모음집 → 깃허브 ---------- */
function syncToSite() {
  const lock = LockService.getScriptLock(); if (!lock.tryLock(1000)) return;
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet(), sheets = ss.getSheets();
    const props = PropertiesService.getScriptProperties();
    const col = n => { let s = ''; n++; while (n) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = (n - m - 1) / 26; } return s; };

    // 글자 덤프 (예전 dumpAllTabs와 같은 형식)
    const out = [];
    sheets.forEach((sh, i) => {
      out.push(`\n===== [${i + 1}] ${sh.getName()}${sh.isSheetHidden() ? ' (숨김)' : ''} =====`);
      sh.getDataRange().getDisplayValues().forEach((row, r) => {
        const cells = [];
        row.forEach((v, c) => { if (String(v).trim()) cells.push(`${col(c)}${r + 1}: ${String(v).replace(/\n/g, ' / ')}`); });
        if (cells.length) out.push(cells.join(' | '));
      });
    });
    const dump = out.join('\n');
    const files = [];
    const hash = Utilities.base64Encode(Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, dump, Utilities.Charset.UTF_8));
    if (hash !== props.getProperty('lastDumpHash')) files.push({ path: 'sync/dump.bin', b64: Utilities.base64Encode(seal_(dump), Utilities.Charset.UTF_8) });

    // 사이트에 없는 탭의 그림
    const known = knownTabs_();
    const token = ScriptApp.getOAuthToken(), t0 = Date.now(), skipped = [];
    sheets.forEach((sh, i) => {
      if (i < 4) return;                          // 앞의 개요 탭 3개와 --- 탭
      const tab = sh.getName();
      if (known.has(tab) || Date.now() - t0 > 3 * 60 * 1000) return;
      let best = null;
      sh.getDataRange().getValues().forEach(row => row.forEach(v => {
        if (!(v && typeof v === 'object' && typeof v.getContentUrl === 'function')) return;
        try {
          const url = v.getContentUrl() || v.getUrl(); if (!url) return;
          const b = UrlFetchApp.fetch(url, { headers: { Authorization: 'Bearer ' + token } }).getBlob().getBytes();
          if (!best || b.length > best.length) best = b;
        } catch (e) { skipped.push(tab + ': ' + e.message); }
      }));
      if (best && best.length > 20000) files.push({ path: 'sync/img/' + safe_(tab) + '.png', b64: Utilities.base64Encode(best) });
    });

    if (!files.length) { toast_('바뀐 것이 없어요.'); return; }
    commit_(files, '모음집에서 보냄: ' + files.length + '개 파일');
    props.setProperty('lastDumpHash', hash);
    toast_('사이트로 보냈어요(' + files.length + '개). 몇 분 뒤 사이트에 보여요.' + (skipped.length ? ' 그림 못 읽은 탭: ' + skipped.length : ''));
  } finally { lock.releaseLock(); }
}

function knownTabs_() {
  const list = JSON.parse(rawFile_('characters.json') || '[]');
  const s = new Set();
  list.forEach(c => { if (c['원본탭'] && c['원본탭'][0] !== '(') s.add(c['원본탭']); });
  return s;
}
// 공개 저장소라 글자를 그대로 올리지 않음: gzip 후 HMAC-SHA256 키스트림으로 XOR (깃허브 Actions가 tools/unseal.py로 품)
function seal_(text) {
  const key = Utilities.newBlob(PropertiesService.getScriptProperties().getProperty('SYNC_KEY') || '').getBytes();
  if (!key.length) throw new Error('스크립트 속성 SYNC_KEY 가 없어요.');
  const gz = Utilities.gzip(Utilities.newBlob(text, 'text/plain', 'd.txt')).getBytes();
  const nonce = Utilities.getUuid(), out = new Array(gz.length);
  for (let i = 0, c = 0; i < gz.length; c++) {
    const ks = Utilities.computeHmacSha256Signature(Utilities.newBlob(nonce + ':' + c).getBytes(), key);
    for (let j = 0; j < 32 && i < gz.length; j++, i++) out[i] = gz[i] ^ ks[j];
  }
  return nonce + '\n' + Utilities.base64Encode(out);
}
function safe_(t) { return t.replace(/[\\/:*?"<>|]/g, '_'); }

/* ---------- 2. 사이트 목록 → 요약 시트 ---------- */
function updateSummarySheet() {
  const list = JSON.parse(rawFile_('characters.json') || '[]');
  if (!list.length) return;
  const ORDER = ['CoC1920', 'CoC현대', 'UW', 'SG', 'TA', '저녁노을', '에모크로아', '아곤', '던전월드', '둘수사', '너냐', '인세인', '델타그린', '무협', '탐공사', '피아스코', '1시간히어로'];
  const NAME = { CoC1920: 'CoC 1920년대', CoC현대: 'CoC 현대', UW: '언리미티드 월드', SG: '시노비가미', TA: '트라이앵글 에이전시', 저녁노을: '저녁노을 어스름', 에모크로아: '에모크로아', 아곤: '아곤·조선 아곤', 던전월드: '던전 월드', 둘수사: '둘이서 수사', 너냐: '너냐?!', 인세인: '인세인', 델타그린: '델타 그린', 무협: '무협', 탐공사: '탐공사', 피아스코: '피아스코', '1시간히어로': '1시간 히어로' };
  list.sort((a, b) => ((ORDER.indexOf(a['서가']) + 100) % 100 - (ORDER.indexOf(b['서가']) + 100) % 100) || a.id.localeCompare(b.id));
  const sh = SpreadsheetApp.openById(SUMMARY_ID).getSheetByName('캐릭터');
  const old = sh.getDataRange().getValues(), head = old[0];
  const keep = {};  // 그림 원본 위치 칸(맨 뒤 4칸)은 원래 값 유지
  old.slice(1).forEach(r => { keep[r[0]] = r.slice(26, 30); });
  const rows = list.map(c => [c.id, c['이름'], c['원어/별명'], NAME[c['서가']] || c['서가'], c['룰'], c['시스템'], c['시대'], c['분류'], c['상태'], c['성별'], c['나이'], c['국적'], c['직업'], c['종족'], c['이성'], c['시나리오횟수'], (c['시나리오'] || []).join(' / '), c['한마디'], c['외견'], c['성격'], c['배경'], c['비고'], c['원본탭'], '', c['공개'] || 'O', c.img || '']
    .map(v => v == null ? '' : v).concat(keep[c.id] || ['', '', '', '']));
  sh.getRange(2, 1, Math.max(sh.getMaxRows() - 1, 1), head.length).clearContent();
  sh.getRange(2, 1, rows.length, 30).setValues(rows);
}

/* ---------- 깃허브 ---------- */
function gh_(method, path, body) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('스크립트 속성 GITHUB_TOKEN 이 없어요.');
  const res = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + path, {
    method: method, muteHttpExceptions: true, contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
    payload: body ? JSON.stringify(body) : undefined
  });
  const code = res.getResponseCode();
  if (code >= 300 && code !== 404) throw new Error('깃허브 ' + code + ': ' + res.getContentText().slice(0, 300));
  return code === 404 ? null : JSON.parse(res.getContentText() || '{}');
}
function rawFile_(path) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  const res = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/contents/' + path + '?ref=' + BRANCH, {
    muteHttpExceptions: true, headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github.raw+json' }
  });
  return res.getResponseCode() === 200 ? res.getContentText('UTF-8') : '';
}
// 여러 파일을 커밋 하나로 올림
function commit_(files, message) {
  const ref = gh_('get', '/git/ref/heads/' + BRANCH);
  const head = ref.object.sha;
  const base = gh_('get', '/git/commits/' + head).tree.sha;
  const tree = files.map(f => ({ path: f.path, mode: '100644', type: 'blob', sha: gh_('post', '/git/blobs', { content: f.b64, encoding: 'base64' }).sha }));
  const t = gh_('post', '/git/trees', { base_tree: base, tree: tree });
  const c = gh_('post', '/git/commits', { message: message, tree: t.sha, parents: [head] });
  gh_('patch', '/git/refs/heads/' + BRANCH, { sha: c.sha });
}
function toast_(m) { try { SpreadsheetApp.getActiveSpreadsheet().toast(m, '📚 서고', 8); } catch (e) { Logger.log(m); } }

/* ---------- 3. 비공개 세션 로그 (사이트의 '세션 로그' 탭) ----------
 * 요약 시트의 '세션로그' 탭을 비밀번호가 맞을 때만 돌려줌. 친구 닉네임이 있어 깃허브에는 안 올림.
 * 배포: 배포 → 새 배포 → 유형 '웹 앱', 실행: 나, 액세스: 모든 사용자 → 나온 주소를 사이트 LOG_URL에.
 * 비밀번호: 스크립트 속성 LOG_PASSWORD
 */
function doGet(e) {
  const pw = (e && e.parameter && e.parameter.pw) || '';
  const want = PropertiesService.getScriptProperties().getProperty('LOG_PASSWORD');
  let body;
  if (!want || pw !== want) {
    Utilities.sleep(800);                       // 마구 넣어 보기 늦추기
    body = { ok: false };
  } else {
    const v = SpreadsheetApp.openById(SUMMARY_ID).getSheetByName('세션로그').getDataRange().getDisplayValues();
    const h = v[0];
    body = { ok: true, sessions: v.slice(1).filter(r => r.join('')).map(r => Object.fromEntries(h.map((k, i) => [k, r[i]]))) };
  }
  return ContentService.createTextOutput(JSON.stringify(body)).setMimeType(ContentService.MimeType.JSON);
}

/* 구글 드라이브 '세션 기록' 폴더에 한글 파일을 올려 두면, 파일 이름으로 찾아 '링크' 칸을 채움 (메뉴에서 실행) */
function linkSessionFiles() {
  const it = DriveApp.getFoldersByName('세션 기록');
  if (!it.hasNext()) { toast_("드라이브에 '세션 기록' 폴더가 없어요."); return; }
  const map = {};
  const walk = f => { const fi = f.getFiles(); while (fi.hasNext()) { const x = fi.next(); map[x.getName()] = x.getUrl(); } const fo = f.getFolders(); while (fo.hasNext()) walk(fo.next()); };
  walk(it.next());
  const sh = SpreadsheetApp.openById(SUMMARY_ID).getSheetByName('세션로그');
  const v = sh.getDataRange().getValues(), h = v[0], fi = h.indexOf('파일'), li = h.indexOf('링크');
  let n = 0;
  for (let r = 1; r < v.length; r++) { const u = map[v[r][fi]]; if (u && v[r][li] !== u) { sh.getRange(r + 1, li + 1).setValue(u); n++; } }
  toast_('한글 파일 링크 ' + n + '개를 채웠어요.');
}
