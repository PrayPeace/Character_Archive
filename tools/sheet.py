"""캐릭터 시트 탭에서 '상세 시트' 섹션(특성치·기능·무기·소지품)을 뽑아 characters.json 의 '시트' 칸에 넣는다.
지금은 크툴루의 부름(CoC·델타 그린 등 cc<= 채팅 팔레트가 있는 시트)만 읽는다. 플레이어 이름 같은 칸은 읽지 않는다.
사용: python3 sheet.py <작업폴더(tabs.json)> <저장소 루트>"""
import json, os, re, sys

D, ROOT = sys.argv[1], sys.argv[2]
tabs = json.load(open(os.path.join(D, 'tabs.json'), encoding='utf-8'))
CJ = os.path.join(ROOT, 'characters.json')
chars = json.load(open(CJ, encoding='utf-8'))
CELL = re.compile(r'([A-Z]+)(\d+): ')
STATS = [('근력', 'STR'), ('건강', 'CON'), ('크기', 'SIZ'), ('민첩', 'DEX'), ('외모', 'APP'),
         ('교육', 'EDU'), ('지능', 'INT'), ('정신력', 'POW'), ('행운', 'LUK')]
STATNAME = re.compile(r'^(근력|건강|크기|민첩|외모|교육|지능|정신력|정신|행운|이성|체력|마력|아이디어|지식|운|STR|CON|SIZ|DEX|APP|EDU|INT|POW|LUK|SAN)(\s|\(|$)', re.I)
DERIVED = ['체력', '마력', '피해 보너스', '체구', '이동력']


def colnum(c):
    n = 0
    for ch in c: n = n * 26 + ord(ch) - 64
    return n


def grid(body):
    rows = {}
    for line in body.split('\n'):
        for p in re.split(r' \| (?=[A-Z]+\d+: )', line):
            m = CELL.match(p)
            if m: rows.setdefault(int(m.group(2)), []).append((colnum(m.group(1)), p[m.end():].strip()))
    for r in rows: rows[r].sort()
    return rows


NUM = re.compile(r'^-?\d+$')


def after(row, i):
    """같은 줄에서 i번째 칸 다음에 오는 첫 값"""
    for _, v in row[i + 1:]:
        if v: return v
    return ''


def parse(body):
    if 'cc<=' not in body and not re.search(r'\bSTR\b', body): return None
    g = grid(body)
    out = {}
    # 특성치: '근력 STR' 또는 '근력' 칸 오른쪽 첫 숫자
    st = {}
    for r in sorted(g):
        row = g[r]
        for i, (_, v) in enumerate(row):
            for ko, en in STATS:
                if en in st: continue
                if v in (ko, en, ko + ' ' + en, ko + '(' + en + ')', en + ' ' + ko) or re.fullmatch(ko + r'\s*\(?' + en + r'\)?', v):
                    nx = after(row, i)
                    if NUM.match(nx): st[en] = (ko, int(nx))
    if len(st) >= 5:
        out['특성치'] = [[ko + ' ' + en, st[en][1]] for ko, en in STATS if en in st]
    # 파생치: 체력·마력 등 (값이 있는 것만)
    dv = []
    for r in sorted(g):
        row = g[r]
        for i, (_, v) in enumerate(row):
            if v in DERIVED and v not in [k for k, _ in dv]:
                nx = after(row, i)
                if nx and len(nx) <= 12 and not re.search(r'[가-힣]{3,}', nx): dv.append([v, nx])
    if dv: out['파생'] = dv
    # 기능: cc<=값 이름 (채팅 팔레트). 같은 이름은 처음 것만, 0과 이름 없는 줄은 뺌
    sk, seen = [], set()
    for m in re.finditer(r'(?:^|\| )[A-Z]+\d+: cc<=(\d+)\s+([^|\n]+)', body, re.M):
        val, nm = int(m.group(1)), re.sub(r'\(\s*\)$', '', m.group(2).strip()).strip()
        if not nm or val <= 0 or nm in seen or STATNAME.match(nm): continue
        seen.add(nm); sk.append([nm, val])
    if sk:
        sk.sort(key=lambda x: -x[1])
        out['기능'] = sk
    # 무기: '피해'·'사거리' 머리줄 아래 줄들
    for r in sorted(g):
        vals = [v for _, v in g[r]]
        if '피해' in vals and ('사거리' in vals or '보통' in vals):
            cols = {v: c for c, v in g[r]}
            wc, pc = g[r][0][0], cols['피해']
            ws = []
            for rr in range(r + 1, r + 12):
                row = dict(g.get(rr, []))
                name = row.get(wc, '')
                if not name: break
                hit = row.get(cols.get('보통', -1), '')
                ws.append([name, hit, row.get(pc, ''), row.get(cols.get('사거리', -1), '')])
            if ws: out['무기'] = ws
            break
    # 소지품: '소지품' 머리칸 아래 몇 줄, 옆 머리칸(관계 등) 앞까지
    for r in sorted(g):
        row = g[r]
        hit = [(c, v) for c, v in row if v in ('소지품', '소지품 목록', '장비', '소지품/장비')]
        if not hit: continue
        c0 = hit[0][0]
        right = [c for c, v in row if c > c0 and v]
        c1 = right[0] if right else 999
        items = []
        for rr in range(r + 1, r + 6):
            for c, v in g.get(rr, []):
                if c0 <= c < c1 and v and v != '#REF!': items += [x.strip() for x in v.split(' / ') if x.strip()]
        if items: out['소지품'] = items[:30]
        break
    return out or None


by_tab = {}
for n, name, body in tabs:
    by_tab[re.sub(r' \(숨김\)$', '', name).strip()] = body
n = 0
for c in chars:
    body = by_tab.get(c.get('원본탭', ''))
    s = parse(body) if body else None
    if s:
        if c.get('시트') != s: c['시트'] = s; n += 1
    elif '시트' in c and body is not None:
        del c['시트']; n += 1
json.dump(chars, open(CJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('sheet sections updated', n, 'with sheet', sum(1 for c in chars if c.get('시트')))
