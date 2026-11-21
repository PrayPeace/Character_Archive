"""모음집에서 새로 읽은 rows.json 을 사이트 characters.json 에 합친다.
- 이미 있는 캐릭터(원본 탭 이름으로 찾음): 시트에서 바뀔 수 있는 칸만 새 값으로 바꿈.
  손으로 고친 서가·룰·시스템·그림·공개·비고는 그대로 둠. "고정": true 인 캐릭터는 아예 안 건드림.
- 끝에 dedupe.py로 중복 캐릭터(이름+서가 같음)를 하나로 합침. 합쳐 지운 탭은 '다른탭'에 남아 다시 안 생김.
- 처음 보는 탭: 새 캐릭터로 추가(서가는 룰·시대로 자동), 그림은 sync/img/<탭이름>.png 를 webp로.
사용: python3 merge.py <작업폴더> <저장소 루트>"""
import json, os, re, sys
from PIL import Image
D, ROOT = sys.argv[1], sys.argv[2]
rows = json.load(open(D + '/rows.json', encoding='utf-8'))
CJ = os.path.join(ROOT, 'characters.json')
chars = json.load(open(CJ, encoding='utf-8'))
LIVE = ['이성', '시나리오', '시나리오횟수', '나이', '직업', '한마디', '외견', '성격', '배경', '국적', '성별', '종족', '원어/별명']
def safe(t): return re.sub(r'[\\/:*?"<>|]', '_', t)
def shelf(r):
    if r['룰'] == 'CoC':
        return 'CoC현대' if r['시대'] in ('현대', '근미래', '미래', '') else 'CoC1920'
    if r['룰'] in ('UW', 'TA', 'SG'): return r['룰']
    M = {'저녁 노을 어스름': '저녁노을', '에모크로아': '에모크로아', '던전 월드': '던전월드', '아곤': '아곤', '조선 아곤': '아곤', '둘이서 수사': '둘수사',
         '너냐?!': '너냐', '인세인': '인세인', '델타 그린': '델타그린', '무협': '무협', '탐공사': '탐공사', '피아스코': '피아스코', '1시간 히어로': '1시간히어로'}
    return M.get(r['시스템'], '기타')
by_tab = {c['원본탭']: c for c in chars if not c['원본탭'].startswith('(')}
by_name = {c['이름']: c for c in chars if c['원본탭'].startswith('(')}
merged_tabs = {t for c in chars for t in (c.get('다른탭') or [])}  # 중복으로 합쳐 지운 탭: 다시 만들지 않음
def next_id(rule):
    p = {'CoC': 'coc', 'UW': 'uw', 'SG': 'sg', 'TA': 'ta'}.get(rule, 'etc')
    n = max([int(c['id'].split('-')[1]) for c in chars if c['id'].startswith(p + '-')] + [0]) + 1
    return '%s-%03d' % (p, n)
added, changed = [], []
for r in rows:
    tab = r['원본탭']
    if tab in merged_tabs: continue
    c = by_tab.get(tab) if not tab.startswith('(') else by_name.get(r['이름'])
    if c:
        if c.get('고정'): continue
        for k in LIVE:
            v = r.get(k)
            if v not in (None, '', []) and c.get(k) != v:
                c[k] = v; changed.append((c['id'], k))
        continue
    if tab.startswith('('): continue  # 개요에만 있는 새 줄은 시트 탭이 생기면 그때 추가
    nid = next_id(r['룰'])
    c = {k: r.get(k, '') for k in ['이름', '원어/별명', '룰', '시스템', '시대', '분류', '상태', '성별', '나이', '국적', '직업', '종족', '이성', '시나리오횟수', '한마디', '외견', '성격', '배경', '비고']}
    c.update(id=nid, 시나리오=r.get('시나리오') or [], 원본탭=tab, 서가=shelf(r), 공개='O', 새로추가=True)
    src = os.path.join(ROOT, 'sync', 'img', safe(tab) + '.png')
    if os.path.exists(src):
        im = Image.open(src); im.seek(0); im = im.convert('RGBA'); im.thumbnail((520, 720))
        im.save(os.path.join(ROOT, 'img', nid + '.webp'), 'WEBP', quality=80); c['img'] = 'img/%s.webp' % nid
    chars.append(c); by_tab[tab] = c; added.append((nid, c['이름'], c['서가']))
# 그림만 나중에 올라온 경우
for c in chars:
    if not c.get('img') and not c['원본탭'].startswith('('):
        src = os.path.join(ROOT, 'sync', 'img', safe(c['원본탭']) + '.png')
        if os.path.exists(src):
            im = Image.open(src); im.seek(0); im = im.convert('RGBA'); im.thumbnail((520, 720))
            im.save(os.path.join(ROOT, 'img', c['id'] + '.webp'), 'WEBP', quality=80); c['img'] = 'img/%s.webp' % c['id']; changed.append((c['id'], 'img'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedupe import dedupe
merged = dedupe(chars, ROOT)
json.dump(chars, open(CJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('added', added); print('merged', merged); print('changed', len(changed), changed[:40])
