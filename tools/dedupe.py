"""중복 캐릭터를 하나로 합친다. (이름(띄어쓰기 무시) + 서가)가 같으면 같은 캐릭터로 본다.
- 남길 쪽: 실제 시트 탭이 있는 쪽 > 시트 내용이 많은 쪽 > 앨범·이야기가 많은 쪽 > id가 앞선 쪽.
- 지우는 쪽의 앨범·연대기·시나리오는 남길 쪽에 더하고, 빈 칸은 채움. 지운 쪽 원본탭은 '다른탭'에 적어
  다음 자동 반영 때 새 캐릭터로 다시 생기지 않게 함(merge.py가 '다른탭'은 건너뜀).
- 서로 다른 룰·서가의 같은 이름(예: 란체스터 리베르타 CoC/둘수사)은 다른 캐릭터로 둔다.
사용: python3 dedupe.py <저장소 루트>  (merge.py도 끝에서 부름)"""
import json, os, re, sys


def key(c):
    return (re.sub(r'\s+', '', c.get('이름', '')), c.get('서가', ''))


def score(c):
    real = not c.get('원본탭', '(').startswith('(')
    return (real, len(json.dumps(c.get('시트', ''), ensure_ascii=False)),
            len(c.get('앨범') or []) + len(c.get('이야기') or ''), [-ord(ch) for ch in c['id']])


def dedupe(chars, root):
    groups = {}
    for c in chars:
        groups.setdefault(key(c), []).append(c)
    gone, log = set(), []
    for g in groups.values():
        if len(g) < 2:
            continue
        g.sort(key=score, reverse=True)
        keep = g[0]
        for o in g[1:]:
            for k, v in o.items():
                if k in ('id', '원본탭', 'img', '앨범', '연대기', '시나리오', '다른탭', '새로추가'):
                    continue
                if v not in (None, '', [], {}) and keep.get(k) in (None, '', [], {}):
                    keep[k] = v
            al = keep.setdefault('앨범', [])
            seen = {a[0] for a in al}
            if o.get('img') and o['img'] != keep.get('img') and os.path.exists(os.path.join(root, o['img'])):
                # 지우는 쪽 대표 그림이 남길 쪽과 다르면 앨범으로 옮김
                same = keep.get('img') and os.path.exists(os.path.join(root, keep['img'])) and \
                    open(os.path.join(root, o['img']), 'rb').read() == open(os.path.join(root, keep['img']), 'rb').read()
                if not same:
                    n = 1
                    while os.path.exists(os.path.join(root, 'img', 'album', keep['id'], '%d.webp' % n)):
                        n += 1
                    dst = 'img/album/%s/%d.webp' % (keep['id'], n)
                    os.makedirs(os.path.dirname(os.path.join(root, dst)), exist_ok=True)
                    os.replace(os.path.join(root, o['img']), os.path.join(root, dst))
                    al.append([dst, ''])
                    seen.add(dst)
            for a in o.get('앨범') or []:
                if a[0] not in seen:
                    al.append(a); seen.add(a[0])
            if not al:
                keep.pop('앨범')
            ch = keep.setdefault('연대기', [])
            for x in o.get('연대기') or []:
                if x not in ch:
                    ch.append(x)
            if not ch:
                keep.pop('연대기')
            if isinstance(keep.get('시나리오'), list) and isinstance(o.get('시나리오'), list):
                for s in o['시나리오']:
                    if s not in keep['시나리오']:
                        keep['시나리오'].append(s)
            tabs = keep.setdefault('다른탭', [])
            for t in [o.get('원본탭', '')] + (o.get('다른탭') or []):
                if t and not t.startswith('(') and t not in tabs:
                    tabs.append(t)
            if not tabs:
                keep.pop('다른탭')
            if o.get('img') and o['img'] != keep.get('img'):
                p = os.path.join(root, o['img'])
                if os.path.exists(p):
                    os.remove(p)
            gone.add(o['id'])
            log.append((o['id'], '→', keep['id'], keep['이름']))
    chars[:] = [c for c in chars if c['id'] not in gone]
    return log


if __name__ == '__main__':
    ROOT = sys.argv[1]
    CJ = os.path.join(ROOT, 'characters.json')
    chars = json.load(open(CJ, encoding='utf-8'))
    log = dedupe(chars, ROOT)
    json.dump(chars, open(CJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('merged', log)
