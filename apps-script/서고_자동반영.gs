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
const LOG_ID = '1zdev6RtZC5djIrsiWkl6hgVspXODLBwL-x2hEPipBo8';     // 세션 로그 (비공개)

function onOpen() {
  SpreadsheetApp.getUi().createMenu('📚 서고')
    .addItem('지금 사이트로 보내기', 'syncToSite')
    .addItem('요약 시트 지금 맞추기', 'updateSummarySheet')
    .addItem('세션 한글 파일 링크 채우기', 'linkSessionFiles')
    .addItem('새 회의록으로 세션 로그 쓰기', 'autoSessionLog')
    .addSeparator()
    .addItem('매일 자동 보내기 켜기', 'installDailyTrigger')
    .addItem('매일 자동 보내기 끄기', 'removeDailyTrigger')
    .addToUi();
}

function installDailyTrigger() {
  removeDailyTrigger();
  ScriptApp.newTrigger('syncToSite').timeBased().everyDays(1).atHour(5).create();
  ScriptApp.newTrigger('updateSummarySheet').timeBased().everyDays(1).atHour(6).create();
  ScriptApp.newTrigger('autoSessionLog').timeBased().everyDays(1).atHour(7).create();
  toast_('매일 새벽 5시에 사이트로 보내고, 6시에 요약 시트를, 7시에 세션 로그를 맞춰요.');
}
function removeDailyTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (['syncToSite', 'updateSummarySheet', 'autoSessionLog'].includes(t.getHandlerFunction())) ScriptApp.deleteTrigger(t);
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
      if (known.has(tab) || known.has(tabHash_(tab)) || Date.now() - t0 > 3 * 60 * 1000) return;
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
  list.forEach(c => {
    if (c['원본탭'] && c['원본탭'][0] !== '(') s.add(c['원본탭']);
    [c['원본탭해시']].concat(c['다른탭해시'] || [], c['다른탭'] || []).forEach(h => { if (h) s.add(h); });   // 비공개로 뺀 탭(해시), 합쳐 지운 탭
  });
  return s;
}
function tabHash_(t) {   // tools/privatize.py 와 같은 해시(sha256 앞 24자리)
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, t, Utilities.Charset.UTF_8)
    .map(b => ('0' + (b & 255).toString(16)).slice(-2)).join('').slice(0, 24);
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

/* ---------- 3. 비공개 세션 로그·즐겨찾기·대표 이미지 (웹 앱) ----------
 * 배포: 배포 → 웹 앱, 실행: 나, 액세스: 모든 사용자. 주소는 사이트 LOG_URL. (GitHub Actions '서고 스크립트 배포'가 새 버전으로 바꿔 줌)
 * 비밀번호: 스크립트 속성 LOG_PASSWORD. 비밀번호는 로그인 때 한 번만 POST 본문으로 받고, 그 뒤로는 만료되는 표(토큰)만 씀.
 *  - GET  ?op=covers                      대표 이미지 목록 (누구나)
 *  - POST {op:'login', pw}                → {ok, token, exp}  (10분에 10번 틀리면 15분 잠금)
 *  - POST {op:'sessions'|'fav'|'favset'|'coverset'|'pickset'|'logout', token, ...}
 * 세션 로그에는 친구 닉네임이 있어 깃허브에는 안 올림.
 */
const TOKEN_DAYS = 14;
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
function doGet(e) {
  const P = PropertiesService.getScriptProperties();
  if (e && e.parameter && e.parameter.op === 'covers') return json_({ ok: true, cover: JSON.parse(P.getProperty('COVER') || '{}'), picks: JSON.parse(P.getProperty('PICKS') || '[]') });
  return json_({ ok: false, error: 'old' });   // 비밀번호를 주소에 싣는 옛 방식은 막음
}
function tokens_(P) {
  const now = Date.now(), m = JSON.parse(P.getProperty('TOKENS') || '{}');
  Object.keys(m).forEach(k => { if (m[k] < now) delete m[k]; });
  return m;
}
function sha_(t) { return Utilities.base64EncodeWebSafe(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, t, Utilities.Charset.UTF_8)); }
function doPost(e) {
  let q = {};
  try { q = JSON.parse((e && e.postData && e.postData.contents) || '{}'); } catch (x) { return json_({ ok: false }); }
  const P = PropertiesService.getScriptProperties(), C = CacheService.getScriptCache();
  const lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    if (q.op === 'login') {
      if (C.get('locked')) return json_({ ok: false, error: 'locked' });
      const want = P.getProperty('LOG_PASSWORD');
      if (!want || String(q.pw || '') !== want) {
        Utilities.sleep(800);
        const n = +(C.get('fails') || 0) + 1; C.put('fails', String(n), 600);
        if (n >= 10) { C.put('locked', '1', 900); C.remove('fails'); }
        return json_({ ok: false });
      }
      C.remove('fails');
      const tok = Utilities.getUuid() + Utilities.getUuid().slice(0, 8), exp = Date.now() + TOKEN_DAYS * 864e5;
      const m = tokens_(P); m[sha_(tok)] = exp;
      const keys = Object.keys(m).sort((a, b) => m[b] - m[a]).slice(0, 20), mm = {}; keys.forEach(k => mm[k] = m[k]);
      P.setProperty('TOKENS', JSON.stringify(mm));
      return json_({ ok: true, token: tok, exp: exp });
    }
    const m = tokens_(P), th = sha_(String(q.token || ''));
    if (!q.token || !m[th]) return json_({ ok: false, error: 'auth' });
    if (q.op === 'logout') { delete m[th]; P.setProperty('TOKENS', JSON.stringify(m)); return json_({ ok: true }); }
    if (q.op === 'fav') return json_({ ok: true, fav: JSON.parse(P.getProperty('FAV') || '[]') });
    if (q.op === 'favset') {
      const ids = (Array.isArray(q.ids) ? q.ids : []).map(x => String(x).trim()).filter(x => /^[a-z]+-\d{3}$/.test(x)).slice(0, 500);
      P.setProperty('FAV', JSON.stringify(ids)); return json_({ ok: true, fav: ids });
    }
    if (q.op === 'pickset') {   // 서고지기의 추천 (첫 화면 전시, 최대 6명)
      const ids = (Array.isArray(q.ids) ? q.ids : []).map(x => String(x).trim()).filter(x => /^[a-z]+-\d{3}$/.test(x)).slice(0, 6);
      P.setProperty('PICKS', JSON.stringify(ids)); return json_({ ok: true, picks: ids });
    }
    if (q.op === 'coverset') {   // 대표 이미지 바꾸기 (src 빈 값이면 원래대로)
      const id = String(q.id || ''), src = String(q.src || ''), c = JSON.parse(P.getProperty('COVER') || '{}');
      if (!/^[a-z]+-\d{3}$/.test(id) || (src && !/^img\/(album\/[a-z]+-\d{3}\/\d+|[a-z]+-\d{3})\.webp$/.test(src))) return json_({ ok: false });
      if (src) c[id] = src; else delete c[id];
      P.setProperty('COVER', JSON.stringify(c)); return json_({ ok: true, cover: c });
    }
    if (q.op === 'sessions') {
      const v = SpreadsheetApp.openById(LOG_ID).getSheetByName('세션로그').getDataRange().getDisplayValues();
      const h = v[0].filter(k => k !== '머리말');   // 머리말(확인용)은 안 보냄
      return json_({ ok: true, exp: m[th], sessions: v.slice(1).filter(r => r.join('')).map(r => Object.fromEntries(h.map(k => [k, r[v[0].indexOf(k)]]))) });
    }
    return json_({ ok: false });
  } finally { lock.releaseLock(); }
}

/* 구글 드라이브 '세션 기록' 폴더에 한글 파일을 올려 두면, 파일 이름으로 찾아 '링크' 칸을 채움 (메뉴에서 실행) */
function linkSessionFiles() {
  const it = DriveApp.getFoldersByName('세션 기록');
  if (!it.hasNext()) { toast_("드라이브에 '세션 기록' 폴더가 없어요."); return; }
  const map = {};
  const walk = f => { const fi = f.getFiles(); while (fi.hasNext()) { const x = fi.next(); map[x.getName()] = x.getUrl(); } const fo = f.getFolders(); while (fo.hasNext()) walk(fo.next()); };
  walk(it.next());
  const sh = SpreadsheetApp.openById(LOG_ID).getSheetByName('세션로그');
  const v = sh.getDataRange().getValues(), h = v[0], fi = h.indexOf('파일'), li = h.indexOf('링크');
  let n = 0;
  for (let r = 1; r < v.length; r++) { const u = map[v[r][fi]]; if (u && v[r][li] !== u) { sh.getRange(r + 1, li + 1).setValue(u); n++; } }
  toast_('한글 파일 링크 ' + n + '개를 채웠어요.');
}

/* ---------- 4. 새 회의록 한글 파일 → 세션 로그 자동 쓰기 ----------
 * 드라이브 '세션 기록' 폴더(하위 폴더 포함)에서, 세션로그 '파일' 칸에 아직 없는 한글 파일을 찾아 한 줄씩 덧붙임.
 * .hwpx 는 안의 글을 읽어 제목·KP·PL·내 캐릭터를 뽑고, .hwp(옛 형식)는 파일 이름만으로 적음.
 * 내 캐릭터는 본문 앞부분에서 '프레이피스(이름)'·'이름(프레이피스)'·'이름(나)'를 찾고, 없으면 모음집 탭 이름과 맞춰 '(추정)'을 붙임.
 * 기존 줄은 건드리지 않음. 매일 7시(자동 켜기 시) 또는 메뉴에서 실행.
 */
function autoSessionLog() {
  const it = DriveApp.getFoldersByName('세션 기록');
  if (!it.hasNext()) { toast_("드라이브에 '세션 기록' 폴더가 없어요."); return; }
  const files = [];
  const walk = f => { const fi = f.getFiles(); while (fi.hasNext()) { const x = fi.next(); if (/\.hwpx?$/i.test(x.getName())) files.push(x); } const fo = f.getFolders(); while (fo.hasNext()) walk(fo.next()); };
  walk(it.next());

  const sh = SpreadsheetApp.openById(LOG_ID).getSheetByName('세션로그');
  const v = sh.getDataRange().getValues(), h = v[0];
  const col = k => h.indexOf(k);
  const have = new Set(v.slice(1).map(r => String(r[col('파일')] || '').trim()).filter(Boolean));
  const tabs = SpreadsheetApp.getActiveSpreadsheet().getSheets().map(s => s.getName().trim()).filter(n => n.length >= 2);
  const ME = /(프레이피스|PrayPeace|\bPP\b)/i;

  const add = [];
  files.sort((a, b) => a.getDateCreated() - b.getDateCreated()).forEach(f => {
    const name = f.getName();
    if (have.has(name)) return;
    have.add(name);
    let lines = [];
    if (/\.hwpx$/i.test(name)) { try { lines = hwpxLines_(f.getBlob()); } catch (e) { Logger.log(name + ': ' + e); } }
    const base = name.replace(/\.hwpx?$/i, '');
    const num = (base.match(/^(\d+)\s*[.\s]/) || [])[1] || '';
    const title = (lines[0] || base.replace(/^\d+\s*\.?\s*/, '')).trim();
    const top = lines.slice(0, 10);
    const roleLine = top.find(l => /(키퍼|KP|GM|마스터)\s*[:;：]|PL\s*[:;：]/i.test(l)) || '';
    const kp = ((roleLine.match(/(?:키퍼|KP|GM|마스터)\s*[:;：]\s*([^/|]+)/i) || [])[1] || '').trim();
    const pls = ((roleLine.match(/(?:PL|PC)\s*[:;：]\s*(.+)$/i) || [])[1] || '')
      .split(/[,，、]/).map(x => x.trim()).filter(x => x && !ME.test(x)).join(',');
    add.push(rowFor_(h, {
      번호: num, 시나리오: title, 룰: ruleOf_(base + ' ' + title), KP: kp, PL: pls,
      대장PC: myPc_(top, tabs, ME),
      날짜: Utilities.formatDate(f.getLastUpdated(), 'Asia/Seoul', 'yyyy-MM-dd') + ' (파일)',
      파일: name, 링크: f.getUrl(), 머리말: lines.slice(0, 8).join(' / ').slice(0, 400)
    }));
  });
  if (add.length) sh.getRange(sh.getLastRow() + 1, 1, add.length, h.length).setValues(add);
  linkSessionFiles();
  toast_('새 세션 ' + add.length + '개를 세션 로그에 적었어요.');
}

function hwpxLines_(blob) {
  const parts = Utilities.unzip(blob.setContentType('application/zip'))
    .filter(b => /^Contents\/section\d+\.xml$/.test(b.getName()))
    .sort((a, b) => a.getName().localeCompare(b.getName(), 'en', { numeric: true }));
  const out = [];
  parts.forEach(b => {
    const x = b.getDataAsString('UTF-8');
    (x.match(/<hp:p\b[\s\S]*?<\/hp:p>/g) || []).forEach(p => {
      const t = (p.match(/<hp:t\b[^>]*>[\s\S]*?<\/hp:t>/g) || []).map(s => s.replace(/<[^>]+>/g, '')).join('')
        .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&amp;/g, '&').trim();
      if (t) out.push(t);
    });
  });
  return out;
}

function ruleOf_(t) {
  const R = [[/1시간\s*히어로/, '1시간히어로'], [/탐공사/, '탐공사'], [/무협/, '무협'], [/트라이앵글|\bTA\b/i, 'TA'], [/CoC|크툴루/i, 'CoC'], [/\bUW\b|언월|언리미티드/i, 'UW'], [/에모크로아/, '에모크로아'], [/시노비가미|\bSG\b/i, 'SG'],
    [/저녁노을/, '저녁노을'], [/아곤/, '아곤'], [/던전\s*월드/, '던전월드'], [/둘이서\s*수사/, '둘수사'],
    [/너냐/, '너냐'], [/인세인/, '인세인'], [/델타\s*그린/, '델타그린']];
  const m = R.find(([re]) => re.test(t));
  return m ? m[1] : '기타';
}

function myPc_(top, tabs, ME) {
  const txt = top.join('\n');
  let m = txt.match(/(?:프레이피스|PrayPeace|PP)\s*\(([^)]+)\)/i);          // 프레이피스(이름)
  if (m) return m[1].trim();
  m = txt.match(/([^\s,/()]+(?: [^\s,/()]+)?) *\((?:프레이피스|PrayPeace|PP|나)\)/i);   // 이름(프레이피스) / 이름(나)
  if (m) return m[1].trim();
  const hit = tabs.filter(n => txt.includes(n));
  return hit.length ? hit[0] + ' (추정)' : '';
}

function rowFor_(h, o) { return h.map(k => (o[k] === undefined ? '' : o[k])); }

