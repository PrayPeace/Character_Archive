"""자동 반영 결과를 올리기 전에 검사한다. 문제가 있으면 1로 끝나서 GitHub Actions가 커밋하지 않음
(= 사이트는 직전의 정상 데이터를 그대로 씀. 예전 판은 git 기록에 남아 있어 되돌릴 수 있음).
사용: python3 validate.py <저장소 루트> [이전 characters.json]"""
import json, os, re, sys
ROOT = sys.argv[1]
err = []
try:
    chars = json.load(open(os.path.join(ROOT, 'characters.json'), encoding='utf-8'))
except Exception as e:
    print('::error::characters.json 을 읽지 못함:', e); sys.exit(1)
if not isinstance(chars, list) or not chars: err.append('목록이 비었거나 형식이 다름')
ids = [c.get('id') for c in chars]
if len(ids) != len(set(ids)): err.append('id가 겹침: %s' % sorted({i for i in ids if ids.count(i) > 1}))
pub = [c for c in chars if (c.get('공개') or 'O') == 'O']
for c in chars:
    if not re.fullmatch(r'[a-z]+-\d{3}', str(c.get('id', ''))): err.append('id 형식: %r' % c.get('id'))
for c in pub:
    if not str(c.get('이름', '')).strip(): err.append('%s 이름 없음' % c['id'])
    if not c.get('서가'): err.append('%s 서가 없음' % c['id'])
    for p in [c.get('img')] + [a[0] for a in c.get('앨범') or []]:
        if p and not os.path.exists(os.path.join(ROOT, p)): err.append('%s 그림 파일 없음: %s' % (c['id'], p))
for c in chars:
    if (c.get('공개') or 'O') != 'O' and set(c) - {'id', '공개', '원본탭해시', '다른탭해시'}: err.append('%s 비공개인데 내용이 남음' % c['id'])
if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
    prev = json.load(open(sys.argv[2], encoding='utf-8'))
    pp = sum(1 for c in prev if (c.get('공개') or 'O') == 'O')
    if pp and len(pub) < pp * 0.9: err.append('공개 인물이 %d명 → %d명으로 10%% 넘게 줄어듦' % (pp, len(pub)))
    lost = [k for k in ('이야기', '앨범', '연대기') if sum(1 for c in pub if c.get(k)) < sum(1 for c in prev if (c.get('공개') or 'O') == 'O' and c.get(k)) - 3]
    if lost: err.append('손으로 넣은 기록이 많이 사라짐: %s' % lost)
for e in err[:40]: print('::error::' + e)
print('검사: 공개 %d명, 문제 %d개' % (len(pub), len(err)))
sys.exit(1 if err else 0)
