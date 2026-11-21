import json, re, sys, difflib
D = sys.argv[1]
tabs = json.load(open(D + '/tabs.json', encoding='utf-8'))
CELL = re.compile(r'([A-Z]+)(\d+): ')

def colnum(c):
    n = 0
    for ch in c: n = n * 26 + ord(ch) - 64
    return n

def parse_cells(body):
    cells = {}
    for line in body.split('\n'):
        # split on ' | ' followed by an address
        parts = re.split(r' \| (?=[A-Z]+\d+: )', line)
        for p in parts:
            m = CELL.match(p)
            if not m: continue
            cells[(int(m.group(2)), colnum(m.group(1)))] = p[m.end():].strip()
    return cells

def split(v): return [x.strip() for x in v.split(' / ') if x.strip()] if v else []

# ---------- overview ----------
over = []
def add(src, group, name, a, b, san, cnt, scen, note, row):
    if not name or name in ('이름',): return
    over.append(dict(src=src, group=group, name_raw=name, d=a, e=b, san=san, cnt=cnt, scen=scen, note=note, row=row))

for n, tname, body in tabs:
    if n in (1, 2):
        c = parse_cells(body)
        rows = sorted({r for r, _ in c})
        for r in rows:
            g = lambda col: c.get((r, col), '')
            add(tname, g(1), g(2), g(4), '', g(5), g(6), g(7), g(8), r)
    if n == 3:
        c = parse_cells(body)
        rows = sorted({r for r, _ in c})
        gl = gr = ''
        for r in rows:
            g = lambda col: c.get((r, col), '')
            if g(1): gl = g(1)
            if g(10): gr = g(10)
            add(tname, gl, g(2), g(4), g(5), '', g(6), g(7), g(8), r)
            add(tname, gr, g(11), g(13), g(14), '', g(15), g(16), g(17), r)

def key(s):
    s = re.sub(r'\(.*?\)|\[.*?\]|Dr\.|[\s\'"’]', '', s)
    return s

for o in over:
    parts = split(o['name_raw'])
    o['name'] = parts[0] if parts else ''
    o['name_extra'] = parts[1:]

# ---------- per tab ----------
LABELS_RIGHT = {
 '이름':'이름','성별':'성별','나이':'나이','연령':'나이','국적':'국적','출신':'출신','출생지':'출신','거주지':'거주지',
 '직업':'직업','직업 유형':'직업','클래스':'직업','시대':'시대','키 / 몸무게':'키몸무게','키/몸무게':'키몸무게','신장':'키몸무게',
 '종족':'종족','정체':'종족','별호':'별호','혈통':'혈통','가치관':'가치관','좋아하는 것':'좋아하는것','싫어하는 것':'싫어하는것',
 '패션 특징':'외견','PL명':'PL',
}
LABELS_BELOW = {
 '겉보기':'외견','외견적 특징':'외견','10. 외관 묘사':'외견','성격':'성격','기타 배경 및 설정':'배경','캐릭터 설정':'배경2',
 '이상한 경험':'시나리오기록','기타 사항':'기타사항','17. 에이전투 세부사항 및 메모':'배경','메모':'메모',
}
NOISE = re.compile(r'^(TRUE|FALSE|#REF!|#N/A|#VALUE!|#ERROR!|✖|0|[■□○●\s/]+|\(\s*\)|\(　+\)|\( 　\))$')

def clean_text(body):
    out = []
    for line in body.split('\n'):
        if 'cc<=' in line or '&{template' in line or line.startswith('A') and re.match(r'^A\d+: (1d|\d+d\d)', line): continue
        vals = []
        for p in re.split(r' \| (?=[A-Z]+\d+: )', line):
            m = CELL.match(p)
            v = p[m.end():].strip() if m else p.strip()
            if not v or NOISE.match(v): continue
            if v.startswith('&{template') or 'Copyright' in v: continue
            vals.append(v)
        if vals: out.append(' | '.join(vals))
    return '\n'.join(out)

def extract(body):
    c = parse_cells(body)
    f = {}
    for (r, col), v in sorted(c.items()):
        lab = v.strip()
        if lab in LABELS_RIGHT and LABELS_RIGHT[lab] not in f:
            for cc in range(col + 1, col + 12):
                w = c.get((r, cc), '').strip()
                if w and not NOISE.match(w):
                    if w in LABELS_RIGHT or w in LABELS_BELOW: break
                    f[LABELS_RIGHT[lab]] = w; break
        if lab in LABELS_BELOW:
            for rr in range(r + 1, r + 4):
                w = c.get((rr, col), '').strip()
                if w in LABELS_BELOW: break
                if w in LABELS_RIGHT: break
                if w and not NOISE.match(w) and not w.endswith('?'):
                    k = LABELS_BELOW[lab]
                    pri = 1 if any(c.get((r, x), '') in ('겉보기', '외견적 특징') for x in range(1, 80)) else 0
                    old = f.get(k + '#', (-1, 0))
                    if (pri, len(w)) > old: f[k] = w; f[k + '#'] = (pri, len(w))
                    break
    if not f.get('배경') and f.get('배경2') and f.get('배경2') != f.get('외견'): f['배경'] = f['배경2']
    f.pop('배경2', None)
    for k in [k for k in f if k.endswith('#')]: f.pop(k)
    for (r, col), v in sorted(c.items()):
        if r <= 3 and (v.startswith('"') or v.startswith('『') or v.startswith('“')) and len(v) > 4 and '캐릭터 한마디' not in v and '한마디' != v.strip('" '):
            f['한마디'] = v.strip(); break
    return f

def tab_meta(tname):
    t = tname.replace(' (숨김)', '')
    hidden = '(숨김)' in tname
    status = ''
    for s in ['완전 로스트', '완전로스트', '로스트', '모험불가', '미완', '졸업']:
        if s in t: status = s.replace(' ', ''); break
    rule, sysname, era = 'ETC', '', ''
    m = re.match(r'^(KP)?(1890|1920|1930|1970|1980)\s', t)
    if m: rule, sysname, era = 'CoC', '크툴루의 부름', m.group(2) + 's'
    elif t.startswith('현대'): rule, sysname, era = 'CoC', '크툴루의 부름', '현대'
    elif t.startswith('미래'): rule, sysname, era = 'CoC', '크툴루의 부름', '미래'
    elif t.startswith('근미래'): rule, sysname, era = 'CoC', '크툴루의 부름', '근미래'
    elif t.startswith('1시간'): sysname = '1시간 히어로'
    elif t.startswith('TA') or t.startswith('트라이앵글'): rule, sysname = 'TA', '트라이앵글 에이전시'
    elif t.startswith('피아스코'): sysname = '피아스코'
    elif t.startswith('너냐'): sysname = '너냐?!'
    elif t.startswith('CC_'): rule, sysname, era = 'CoC', '크툴루 컨피덴셜', '1940s'
    elif t.startswith('UW') or t.startswith('언월'): rule, sysname = 'UW', '언리미티드 월드'
    elif t.startswith('시노비가미'): rule, sysname = 'SG', '시노비가미'
    elif t.startswith('던월'): sysname = '던전 월드'
    elif t.startswith('조선아곤') or t.startswith('일진스님'): sysname = '조선 아곤'
    elif t.startswith('아곤'): sysname = '아곤'
    elif t.startswith('둘수사'): sysname = '둘이서 수사'
    elif t.startswith('인세인'): sysname = '인세인'
    elif t.startswith('에모크로아'): sysname = '에모크로아'
    elif t.startswith('델타그린'): sysname = '델타 그린'
    elif t.startswith('무협'): sysname = '무협'
    elif t.startswith('탐공사'): sysname = '탐공사'
    elif t.startswith('저녁노을'): sysname = '저녁 노을 어스름'
    elif t.startswith('['): sysname = '저녁 노을 어스름'
    if 'KP' in t[:2]: status = status or 'KP용 NPC'
    if '(경성 펄프)' in t: sysname = '크툴루의 부름(경성 펄프)'
    if '(펄프)' in t: sysname = '크툴루의 부름(펄프)'
    return t, hidden, status, rule, sysname, era

chars = []
for n, tname, body in tabs:
    if n <= 4: continue
    t, hidden, status, rule, sysname, era = tab_meta(tname)
    f = extract(body)
    chars.append(dict(tab_no=n, tab=t, hidden=hidden, status=status, rule=rule, system=sysname, era=era, f=f, text=clean_text(body)))

json.dump(dict(over=over, chars=chars), open(D + '/parsed.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(over), len(chars))
for ch in chars[:0]:
    print(ch['tab_no'], ch['tab'], '|', ch['f'].get('이름'), '|', ch['f'].get('나이'), ch['f'].get('직업'), '| 한마디:', (ch['f'].get('한마디') or '')[:30], '| 배경:', len(ch['f'].get('배경','')), '| text', len(ch['text']))
