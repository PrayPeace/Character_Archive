"""캐릭터 시트 탭에서 '상세 시트' 섹션을 뽑아 characters.json 의 '시트' 칸에 넣는다.
- CoC(델타 그린 포함): 특성치·체력/마력 등·기능·무기·소지품
- 그 밖의 룰: 레벨 등 기본 수치, 판정(채팅 팔레트·매크로), 가방, 시트에 적힌 내용(정리본)
플레이어 이름·템플릿 제작자·저작권 안내 칸은 읽지 않는다.
사용: python3 sheet.py <작업폴더(tabs.json)> <저장소 루트>"""
import time, base64, gzip, hashlib, hmac, json, os, re, sys

D, ROOT = sys.argv[1], sys.argv[2]
tabs = json.load(open(os.path.join(D, 'tabs.json'), encoding='utf-8'))
CJ = os.path.join(ROOT, 'characters.json')
chars = json.load(open(CJ, encoding='utf-8'))
CELL = re.compile(r'([A-Z]+)(\d+): ')
STATS = [('근력', 'STR'), ('건강', 'CON'), ('크기', 'SIZ'), ('민첩', 'DEX'), ('외모', 'APP'),
         ('교육', 'EDU'), ('지능', 'INT'), ('정신력', 'POW'), ('행운', 'LUK')]
STATALT = {'정신': 'POW', '운': 'LUK'}
STATNAME = re.compile(r'^(근력|건강|크기|민첩|외모|교육|지능|정신력|정신|행운|이성|체력|마력|아이디어|지식|운|STR|CON|SIZ|DEX|APP|EDU|INT|POW|LUK|SAN)(\s|\(|$)', re.I)
DERIVED = ['체력', '마력', '피해 보너스', '피해보너스', '체구', '이동력']
NUM = re.compile(r'^-?\d+$')
JUNK = re.compile(r'^(TRUE|FALSE|#REF!|#N/A|#VALUE!|#ERROR!|-|0|/|[\s/■□●○◆◇★☆▣▩◐◈♠♥♣♦※✖✔·.,()（）　]+|[●○]?\s*\(\s*\)|\(\s*[　\s]*\))$')
SKIPCELL = re.compile(r'Copyright|ⓒ|©|All rights|재배포|배포|posty\.pe|https?://|\bby\.|Based on|@\w|템플릿|제작·수정|제작 및 수정|시트 제작|API|\{"|설정해주세요|복사해|붙여넣|\[\[|&\{|@\{|cc<=|^x\d+ ', re.I)

def load_nicks():
    """sync/nicks.bin: 친구 닉네임 목록(SYNC_KEY로 가림). 이 이름이 들어간 칸은 사이트에 안 올림"""
    p, key = os.path.join(ROOT, 'sync', 'nicks.bin'), os.environ.get('SYNC_KEY', '').encode()
    if not key or not os.path.exists(p): return None
    nonce, b64 = open(p, encoding='ascii').read().split('\n', 1)
    data = base64.b64decode(b64.strip()); buf = bytearray(len(data))
    for c in range((len(data) + 31) // 32):
        ks = hmac.new(key, f'{nonce}:{c}'.encode(), hashlib.sha256).digest()
        for j in range(min(32, len(data) - c * 32)): buf[c * 32 + j] = data[c * 32 + j] ^ ks[j]
    names = [x for x in gzip.decompress(bytes(buf)).decode('utf-8').split('\n') if x.strip()]
    return re.compile('(?<![가-힣A-Za-z])(' + '|'.join(map(re.escape, sorted(names, key=len, reverse=True))) + ')(?![가-힣A-Za-z])') if names else None


NICK = load_nicks()
PLLABEL = re.compile(r'^(PL|PL명|플레이어|플레이어명|Player|PL 이름|작성자)$', re.I)


def colnum(c):
    n = 0
    for ch in c: n = n * 26 + ord(ch) - 64
    return n


def grid(body):
    rows = {}
    for line in body.split('\n'):
        for p in re.split(r' \| (?=[A-Z]+\d+: )', line):
            m = CELL.match(p)
            if not m: continue
            v = p[m.end():].strip()
            if NICK and NICK.search(v.replace('님', ' ')): continue
            rows.setdefault(int(m.group(2)), []).append((colnum(m.group(1)), v))
    for r in rows: rows[r].sort()
    return rows


def norm(v): return re.sub(r'[\s/]', '', v)


def after(row, i):
    for _, v in row[i + 1:]:
        if v: return v
    return ''


def below(g, r, c):
    """바로 아래 줄(최대 2줄)에서 같은 칸 근처의 첫 값"""
    for rr in (r + 1, r + 2):
        for cc, v in g.get(rr, []):
            if c <= cc <= c + 2 and v: return v
    return ''


def stat_key(v):
    n = norm(v)
    for ko, en in STATS:
        if n in (ko, en, ko + en, en + ko, ko + '(' + en + ')'): return en
    return STATALT.get(n)


def parse_coc(body, g):
    out = {}
    st = {}
    for r in sorted(g):
        row = g[r]
        for i, (c, v) in enumerate(row):
            en = stat_key(v)
            if not en or en in st: continue
            nx = after(row, i)
            if not NUM.match(nx): nx = below(g, r, c)
            if NUM.match(nx) and int(nx) > 0: st[en] = int(nx)
    if len(st) >= 5:
        out['특성치'] = [[ko + ' ' + en, st[en]] for ko, en in STATS if en in st]
    dv = []
    for r in sorted(g):
        row = g[r]
        for i, (c, v) in enumerate(row):
            k = v.replace('피해보너스', '피해 보너스')
            if v in DERIVED and k not in [x for x, _ in dv]:
                nx = after(row, i)
                if not nx or re.search(r'[가-힣]{2,}', nx): nx = below(g, r, c)
                if nx and len(nx) <= 12 and not re.search(r'[가-힣]{3,}', nx): dv.append([k, nx])
    if dv: out['파생'] = dv
    sk, seen = [], set()
    for m in re.finditer(r'(?:^|\| )[A-Z]+\d+: cc<=(\d+)\s+([^|\n]+)', body, re.M):
        val, nm = int(m.group(1)), re.sub(r'\(\s*\)$', '', m.group(2).strip()).strip()
        if not nm or val <= 0 or nm in seen or STATNAME.match(nm): continue
        seen.add(nm); sk.append([nm, val])
    if not sk:
        # 팔레트가 없는 시트: '이름 기본 … 합계 절반 1/5' 줄에서 합계를 찾음
        for r in sorted(g):
            row = g[r]
            for i, (c, v) in enumerate(row):
                if NUM.match(v) or JUNK.match(v) or len(v) > 16 or STATNAME.match(v): continue
                nums = []
                for _, w in row[i + 1:i + 8]:
                    if NUM.match(w): nums.append(int(w))
                    elif w in ('TRUE', 'FALSE'): break
                    else: break
                for j in range(len(nums) - 2):
                    x = nums[j]
                    if x > 0 and nums[j + 1] == x // 2 and nums[j + 2] == x // 5:
                        nm = re.sub(r'\(\s*\)$', '', v).strip()
                        if nm not in seen: seen.add(nm); sk.append([nm, x])
                        break
    if sk:
        sk.sort(key=lambda x: -x[1])
        out['기능'] = sk
    for r in sorted(g):
        vals = [v for _, v in g[r]]
        if '피해' in vals and ('사거리' in vals or '보통' in vals) and any(v in ('무기', '무기 이름', '무기명') for v in vals) or ('피해' in vals and '보통' in vals):
            cols = {v: c for c, v in g[r]}
            wc, pc = g[r][0][0], cols['피해']
            ws = []
            for rr in range(r + 1, r + 12):
                row = dict(g.get(rr, []))
                name = row.get(wc, '')
                if not name or NUM.match(name): break
                hit = row.get(cols.get('보통', -1), '')
                if not hit:
                    hit = next((w for c, w in sorted(row.items()) if wc < c < pc and NUM.match(w)), '')
                ws.append([name, hit, row.get(pc, ''), row.get(cols.get('사거리', -1), '')])
            if ws: out['무기'] = ws
            break
    items = []
    for r in sorted(g):
        row = g[r]
        heads = [(c, v) for c, v in row if v in ('소지품', '소지품 목록', '장비', '소지품/장비')]
        if not heads: continue
        for c0, _ in heads:
            right = [c for c, v in row if c > c0 and v]
            c1 = right[0] if right else 999
            for rr in range(r + 1, r + 6):
                for c, v in g.get(rr, []):
                    if c0 <= c < c1 and v and not JUNK.match(v) and not SKIPCELL.search(v):
                        items += [x.strip() for x in v.split(' / ') if x.strip()]
        break
    if items: out['소지품'] = list(dict.fromkeys(items))[:30]
    return out


MACRO = re.compile(r'^(?:x\d+\s+)?(\d*[dD]\d+(?:\s*[+-]\s*\d+)*)\s*(?:[<>]=?\s*\d+\s*)?([^\[\]{}<>=]{1,24})$')


def macros(g):
    res, seen = [], set()
    for r in sorted(g):
        for c, v in g[r]:
            m = MACRO.match(v.replace(' / ', ' ').strip())
            if not m: continue
            nm = re.sub(r'\s+', ' ', m.group(2)).strip()
            if not nm or not re.search(r'[가-힣A-Za-z]', nm) or nm in seen: continue
            if re.fullmatch(r'피해\(무기\d+\)', nm): continue
            seen.add(nm); res.append([nm, re.sub(r'\s+', '', m.group(1)).replace('+0', '') or m.group(1)])
    return res


def bag(g):
    """UW: '물품 이름 | 개수 | 무게 | 태그' 표"""
    for r in sorted(g):
        cols = {v: c for c, v in g[r]}
        if '물품 이름' in cols:
            c0 = cols['물품 이름']
            cn = next((cols[k] for k in ('개수',) if k in cols and cols[k] > c0), None)
            ct = next((cols[k] for k in ('태그', '태그/효과') if k in cols and cols[k] > c0), None)
            items = []
            for rr in range(r + 1, r + 30):
                row = dict(g.get(rr, []))
                nm = row.get(c0, '')
                if not nm: continue
                if nm in ('생활수준', '재산', '무게', '백금화', '실버', '한달 고정수입'): break
                if JUNK.match(nm): continue
                items.append([nm, row.get(cn, '') if cn else '', row.get(ct, '') if ct else ''])
            if items: return items[:30]
    return None


def basic(g):
    out = []
    for lab in ('LV', 'EXP', '레벨', 'HP', 'MP', '재산'):
        for r in sorted(g):
            row = g[r]
            for i, (c, v) in enumerate(row):
                if norm(v) == lab and lab not in [k for k, _ in out]:
                    nx = after(row, i)
                    if not nx or not re.search(r'\d', nx) or len(nx) > 14: nx = below(g, r, c)
                    if nx and re.search(r'\d', nx) and len(nx) <= 14: out.append([lab, nx])
    return out


def text_blocks(g, skip_cols=None):
    """시트에 적힌 글을 줄 단위로 정리. 빈 줄이 2줄 이상이면 덩어리를 나눔"""
    blocks, cur, last = [], [], None
    for r in sorted(g):
        cells, drop_next = [], False
        for c, v in g[r]:
            if drop_next: drop_next = False; continue
            if PLLABEL.match(v.strip()): drop_next = True; continue
            if JUNK.match(v) or SKIPCELL.search(v) or NUM.match(v) and len(v) > 4: continue
            if re.fullmatch(r'\d*[dD]\d+.*', v) and len(v) < 30: continue
            if re.fullmatch(r'(\S /){3,}\s*\S?', v): continue   # 세로로 쓴 장식 글자
            cells.append(v.replace(' / ', ' '))
        if not cells: continue
        if last is not None and r - last > 2 and cur: blocks.append(cur); cur = []
        cur.append(' · '.join(cells)); last = r
    if cur: blocks.append(cur)
    out = []
    for b in blocks:
        b = [x for x in b if len(x) > 1 and x not in ('당신',)]
        if b: out.append(b[:40])
    return out[:20]


def parse_other(body, g, uw):
    out = {}
    b = basic(g)
    if b: out['기본'] = b
    m = macros(g)
    if m: out['판정'] = m[:60]
    if uw:
        bg = bag(g)
        if bg: out['가방'] = bg
    else:
        t = text_blocks(g)
        if t: out['내용'] = t
    return out


def is_coc(body):
    return 'cc<=' in body or re.search(r'\bSTR\b', body) or 'Call of Cthulhu' in body or '탐사자' in body


def parse(body, shelf):
    g = grid(body)
    if is_coc(body) and shelf not in ('UW', 'SG', '인세인', '저녁노을', '에모크로아'):
        out = parse_coc(body, g)
    else:
        out = parse_other(body, g, shelf == 'UW' or 'UNLIMITED' in body.replace(' / ', '').replace(' ', '').upper())
    return out or None


by_tab = {}
for n, name, body in tabs:
    by_tab[re.sub(r' \(숨김\)$', '', name).strip()] = body
n = 0
for c in chars:
    body = by_tab.get(c.get('원본탭', ''))
    s = parse(body, c.get('서가', '')) if body else None
    if s:
        if c.get('시트') != s:
            if c.get('시트'):   # 예전 시트는 성장 기록으로 남김(최근 8개)
                c['시트이력'] = (c.get('시트이력') or [])[-7:] + [{'날짜': time.strftime('%Y-%m-%d'), '시트': c['시트']}]
            c['시트'] = s; n += 1
    elif '시트' in c and body is not None:
        del c['시트']; n += 1
json.dump(chars, open(CJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('sheet sections updated', n, 'with sheet', sum(1 for c in chars if c.get('시트')))
