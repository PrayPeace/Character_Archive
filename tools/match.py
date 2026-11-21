import json, re, sys, difflib
D = sys.argv[1]
P = json.load(open(D + '/parsed.json', encoding='utf-8'))
over, chars = P['over'], P['chars']
PREF = r'^(KP1920|1890|1920|1930|1970|1980|현대|미래|근미래|1시간|CC_|TA|트라이앵글 에이전시|트라이앵글|피아스코|너냐|저녁노을|UW|언월 7대미궁|언월|시노비가미|던월|조선아곤|아곤|둘수사|인세인|에모크로아|델타그린|무협_|탐공사|\[졸업\]|\[[^\]]+\])\s*'
def tabname(t):
    s = re.sub(PREF, '', t)
    s = re.sub(r'\((숨김|로스트|완전로스트|완전 로스트|모험불가|미완|경성 펄프|펄프|P\.P|프)\)', '', s)
    s = s.replace('의 사본', '').replace('_PrayPeace(V0.2)', '')
    return s.strip()
def key(s):
    s = re.sub(r'\(.*?\)|\[.*?\]|Dr\.|[\s\'"’]', '', s or '')
    return s
for c in chars:
    c['name'] = tabname(c['tab'])
# fixups by hand
FIX = {'일진스님': '일진 법사', 'EN003(Third)': 'Third', '세리아': '세리아 로체', '배태랑': '배태랑'}
for c in chars:
    for a, b in FIX.items():
        if c['name'].startswith(a): c['name'] = b if a != 'EN003(Third)' else 'Third(EN003)'
used = set()
okeys = [key(o['name']) for o in over]
for c in chars:
    k = key(c['name'])
    if c['name'].startswith('Third'): k = 'Third'
    cand = [i for i, ok in enumerate(okeys) if ok == k]
    if not cand:
        m = difflib.get_close_matches(k, okeys, n=1, cutoff=0.6)
        cand = [okeys.index(m[0])] if m else []
        # prefer same-source duplicates (e.g. 란체스터 in 둘수사 vs 현대)
    if len(cand) > 1:
        want = '그외' if c['rule'] != 'CoC' else None
        cc = [i for i in cand if (over[i]['src'] == '그외') == (want == '그외')]
        cand = cc or cand
    c['over'] = cand[0] if cand else None
    if cand: used.add(cand[0])
json.dump(P, open(D + '/parsed.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('--- tabs without overview row')
for c in chars:
    if c['over'] is None: print(c['tab_no'], c['tab'], '->', c['name'])
print('--- fuzzy matches')
for c in chars:
    if c['over'] is not None and key(over[c['over']]['name']) != key(c['name']): print(c['tab'], '=>', over[c['over']]['name'])
print('--- overview rows without tab')
for i, o in enumerate(over):
    if i not in used: print(o['src'], o['group'], o['name_raw'])
