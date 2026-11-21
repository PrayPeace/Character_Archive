"""비공개('공개'가 O가 아닌) 캐릭터를 공개 저장소에서 뺀다.
- characters.json 에는 {id, 공개:'X', 원본탭해시} 껍데기만 남김(이름·글·그림 없음). 다음 자동 반영 때 같은 탭이 새 캐릭터로 다시 생기지 않게 하려고 해시만 둠.
- 그 캐릭터의 대표 그림과 앨범 그림 파일도 지움.
- 다시 공개하려면 껍데기를 지우면 됨(다음 반영 때 원본 탭에서 새로 만들어짐).
사용: python3 privatize.py <저장소 루트>"""
import hashlib, json, os, re, shutil, sys
ROOT = sys.argv[1]
CJ = os.path.join(ROOT, 'characters.json')
chars = json.load(open(CJ, encoding='utf-8'))
def th(t): return hashlib.sha256(t.encode('utf-8')).hexdigest()[:24]
out, n = [], 0
for c in chars:
    if (c.get('공개') or 'O') == 'O' or set(c) <= {'id', '공개', '원본탭해시'}:
        out.append(c); continue
    stub = {'id': c['id'], '공개': 'X'}
    if c.get('원본탭') and not c['원본탭'].startswith('('): stub['원본탭해시'] = th(c['원본탭'])
    for t in c.get('다른탭') or []: stub.setdefault('다른탭해시', []).append(th(t))
    for t in [c.get('원본탭', '')] + (c.get('다른탭') or []):   # 새 탭 그림 원본(sync/img)도 지움
        q = os.path.join(ROOT, 'sync', 'img', re.sub(r'[\\/:*?"<>|]', '_', t) + '.png')
        if t and os.path.exists(q): os.remove(q)
    if c.get('img') and os.path.exists(os.path.join(ROOT, c['img'])): os.remove(os.path.join(ROOT, c['img']))
    shutil.rmtree(os.path.join(ROOT, 'img', 'album', c['id']), ignore_errors=True)
    out.append(stub); n += 1
json.dump(out, open(CJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('privatized', n)
