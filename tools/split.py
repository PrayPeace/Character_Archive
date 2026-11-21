"""sync/dump.txt (앱 스크립트가 올린 전체 탭 글자) -> <작업폴더>/tabs.json"""
import json, re, sys
src, D = sys.argv[1], sys.argv[2]
tabs, cur = [], None
for line in open(src, encoding='utf-8').read().split('\n'):
    m = re.match(r'^===== \[(\d+)\] (.*) =====$', line)
    if m:
        cur = [int(m.group(1)), m.group(2), []]; tabs.append(cur)
    elif cur is not None:
        cur[2].append(line)
json.dump([[n, t, '\n'.join(b)] for n, t, b in tabs], open(D + '/tabs.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('tabs', len(tabs))
