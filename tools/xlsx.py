import json, re, sys
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
D, OUT = sys.argv[1], sys.argv[2]
P = json.load(open(D + '/parsed.json', encoding='utf-8'))
over, chars = P['over'], P['chars']
def split(v): return [x.strip() for x in (v or '').split(' / ') if x.strip()]
GROUP_SYS = {'아곤':'아곤','조선아곤':'조선 아곤','피아스코':'피아스코','둘이서 수사':'둘이서 수사','인세인':'인세인','너냐?!':'너냐?!',
 '던전월드':'던전 월드','언리미티드 월드':'언리미티드 월드','언리미티드 월드 7대미궁':'언리미티드 월드','에모크로아':'에모크로아','시노비가미':'시노비가미',
 '저녁 노을 어스름':'저녁 노을 어스름','델타그린':'델타 그린','크툴루 컨피덴셜':'크툴루 컨피덴셜'}
import os
IDS = json.load(open(D + '/drive_img_ids.json', encoding='utf-8')) if os.path.exists(D + '/drive_img_ids.json') else {}
BYTAB = json.load(open(D + '/drive_by_tab.json', encoding='utf-8')) if os.path.exists(D + '/drive_by_tab.json') else {}
TABS = {n: b for n, _, b in json.load(open(D + '/tabs.json', encoding='utf-8'))}
def img_for(o):
    if o['src'] == '그외':
        if ('B%d: ' % o['row'] + o['name_raw']) not in TABS[3]: return ''
    fid = IDS.get('%s__C%d.png' % (o['src'], o['row']))
    return 'https://drive.google.com/file/d/%s/view' % fid if fid else ''
def from_over(o):
    r = {}
    r['이름'] = o['name'].strip(' /')
    extras = o['name_extra']
    stat = [x for x in extras if re.search(r'로스트|모험불가|격리', x)]
    seq = [x for x in extras if '후속작' in x]
    nat = [x for x in extras if x not in stat and x not in seq]
    r['상태메모'] = ', '.join(x.strip('()') for x in stat)
    r['국적'] = ' / '.join(x for x in nat)
    if o['src'] == '그외':
        r['직업'] = o['d'].replace(' / ', ', ')
        e = split(o['e'])
        ages = [x for x in e if re.search(r'\d', x)]
        r['종족'] = ', '.join(x for x in e if x not in ages)
        r['나이'] = ', '.join(ages)
    else:
        d = split(o['d'])
        if d and re.match(r'^\d+', d[0]): r['나이'] = d[0]; d = d[1:]
        r['직업'] = ', '.join(d)
    r['이성'] = o['san'].replace(' / ', ' ')
    r['시나리오횟수'] = o['cnt']
    r['시나리오'] = split(o['scen'])
    r['비고'] = o['note'].replace(' /  / ', ' / ')
    r['분류'] = o['group'] if o['src'] != '그외' else ''
    r['_img'] = img_for(o)
    if seq: r['비고'] = ('후속작 있음 / ' + r['비고']).strip(' /')
    return r

rows = []
for c in chars:
    o = over[c['over']] if c['over'] is not None else None
    r = from_over(o) if o else {'이름': c['name'], '시나리오': []}
    f = c['f']
    def pick(k, fk=None):
        if not r.get(k): r[k] = f.get(fk or k, '')
    if not o: r['이름'] = c['name']
    pick('나이'); pick('직업'); pick('종족')
    if not r.get('국적'): r['국적'] = f.get('국적') or f.get('출신', '')
    r['원어/별명'] = f.get('이름', '') if f.get('이름') and re.sub(r'\s', '', f.get('이름')) != re.sub(r'\s', '', r['이름']) and f.get('이름') not in ('기간',) and not f.get('이름','').isdigit() else ''
    r['성별'] = f.get('성별', '')
    r['한마디'] = '' if re.search(r'시나리오 제목|캐릭터 한마디', f.get('한마디', '')) else f.get('한마디', '').strip('"『』 “”')
    r['외견'] = f.get('외견', ''); r['성격'] = f.get('성격', ''); r['배경'] = f.get('배경', '') if len(f.get('배경', '')) > 3 else ''
    st = c['status'] or ''
    if r.get('상태메모') and r['상태메모'].replace(' ','') not in st: st = (st + ', ' + r['상태메모']).strip(', ')
    if not st and re.search(r'사망|먹힘', r.get('비고', '')): st = '사망?'
    r['상태'] = st or '생존'
    rule, sysn = c['rule'], c['system']
    if o and o['src'] == '그외' and o['group'] in GROUP_SYS and rule == 'ETC' and not sysn: sysn = GROUP_SYS[o['group']]
    if o and o['group'] == '크툴루 컨피덴셜': sysn = '크툴루 컨피덴셜'
    if o and o['group'] == '니알라토텝의 가면들': r['캠페인'] = '니알라토텝의 가면들'
    L = BYTAB.get(c['tab'], [])
    r['_tabimg'] = 'https://drive.google.com/file/d/%s/view' % L[0]['id'] if L and L[0]['size'] > 20000 else ''
    r.update(룰=rule, 시스템=sysn, 시대=c['era'], 원본탭=c['tab'], 숨김='예' if c['hidden'] else '', tab_no=c['tab_no'], text=c['text'])
    if not r.get('시나리오') and f.get('시나리오기록'): r['시나리오'] = split(f['시나리오기록'])
    if not r.get('시나리오횟수') and r['시나리오']: r['시나리오횟수'] = str(len(r['시나리오']))
    rows.append(r)
used = {c['over'] for c in chars}
for i, o in enumerate(over):
    if i in used: continue
    r = from_over(o)
    rule = 'CoC' if o['src'] != '그외' else ('UW' if '언리미티드' in o['group'] else 'ETC')
    era = '1920s' if o['src'] == '1920년대 캐릭터' else ('현대' if o['src'] == '현대 캐릭터' else '')
    r.update(룰=rule, 시스템='크툴루의 부름' if rule == 'CoC' else ('언리미티드 월드' if rule == 'UW' else GROUP_SYS.get(o['group'], o['group'])), 시대=era,
             원본탭='(시트 탭 없음, 개요 탭에만 있음)', 숨김='', tab_no=999, text='', 원어별명='', 성별='', 한마디='', 외견='', 성격='', 배경='')
    if o['group'] == '니알라토텝의 가면들': r['캠페인'] = '니알라토텝의 가면들'
    r['상태'] = r.get('상태메모') or ('사망?' if re.search(r'사망', r.get('비고','')) else '생존')
    rows.append(r)

ORDER = {'CoC': 0, 'UW': 1, 'SG': 2, 'TA': 3, 'ETC': 4}
ERA = {'1890s':0,'1920s':1,'1930s':2,'1940s':3,'1970s':4,'1980s':5,'현대':6,'근미래':7,'미래':8,'':9}
rows.sort(key=lambda r: (ORDER[r['룰']], ERA.get(r['시대'], 9), r['tab_no']))
cnt = {}
for r in rows:
    p = r['룰'].lower(); cnt[p] = cnt.get(p, 0) + 1
    r['id'] = f"{p}-{cnt[p]:03d}"

import os
if os.path.exists(D + '/img_map.json'):
    IM = json.load(open(D + '/img_map.json', encoding='utf-8'))
    for r in rows: r.update(IM.get(r['id'], {}))
wb = Workbook()
H = Font(bold=True, color='FFFFFF'); FILL = PatternFill('solid', fgColor='3A3A5A')
def sheet(ws, header, data, widths):
    ws.append(header)
    for cell in ws[1]: cell.font = H; cell.fill = FILL; cell.alignment = Alignment(vertical='center')
    for d in data: ws.append(d)
    for i, w in enumerate(widths): ws.column_dimensions[ws.cell(1, i + 1).column_letter].width = w
    ws.freeze_panes = 'C2'
    for row in ws.iter_rows(min_row=2):
        for cell in row: cell.alignment = Alignment(wrap_text=True, vertical='top')

ws = wb.active; ws.title = '안내'
guide = [
 ['◈프레이피스 캐릭터 요약 (AI·사이트용)'],
 ['원본: ◈프레이피스 캐릭터 모음집 (숨김 탭 포함 165개 탭). 원본은 플레이용 시트 보관함이고, 이 파일은 그 내용을 읽기 쉽게 모은 요약본입니다.'],
 [''],
 ['탭', '내용'],
 ['캐릭터', '한 줄 = 캐릭터 한 명. id는 사이트 주소에 쓸 고유값이라 바꾸지 않습니다. 개요 탭(1920년대·현대·그외)의 정보를 우선 쓰고, 빈 칸은 각 캐릭터 시트에서 채웠습니다.'],
 ['참가기록', '한 줄 = 캐릭터 하나가 시나리오 하나를 한 기록. 같은 시나리오에 간 캐릭터를 묶어 볼 때 씁니다.'],
 ['시트원문', '각 캐릭터 시트 탭의 글자를 그대로 옮긴 것(빈칸·체크박스·주사위 매크로는 뺌). 능력치·기능·장비·설정 전체가 필요할 때 AI가 이 칸을 읽으면 됩니다.'],
 [''],
 ['칸', '설명'],
 ['룰', 'CoC(크툴루의 부름) / UW(언리미티드 월드) / SG(시노비가미) / TA(트라이앵글 에이전시) / ETC(그 외). 세부 룰은 시스템 칸.'],
 ['시대', 'CoC만: 1890s·1920s·1930s·1940s·1970s·1980s·현대·근미래·미래'],
 ['상태', '생존 / 로스트 / 완전로스트 / 모험불가 / 미완 / KP용 NPC 등. "사망?"은 비고에 사망이 적혀 있어 추정한 값.'],
 ['이성', 'CoC: 현재/초기 (예: 51/75 = 지금 51, 시작 75)'],
 ['원어/별명', '시트 이름 칸에 적힌 다른 표기'],
 ['공개', '사이트에 올려도 되면 O. 비워 두면 비공개로 봅니다.'],
 ['대표 이미지', '사이트에 쓸 그림 링크. 캐릭터 시트 그림이 있으면 그것, 없으면 개요 탭 그림.'],
 ['이미지(캐릭터 시트)', '각 캐릭터 시트 탭에서 가장 큰 그림(보통 사진 칸). 구글 드라이브 \'캐릭터 이미지\' 폴더 링크.'],
 ['이미지(개요 탭)', '1920년대·현대·그외 개요 탭에 넣어 둔 그림.'],
 ['포트레잇(PC)', '대표 그림 파일. 대장 PC의 바탕화면/티알피지/TRPG/캐릭 포트레잇 폴더 기준 경로. 자동으로 고른 것이라 이미지목록 탭에서 바꿀 수 있어요.'],
 ['이미지목록 탭', '캐릭터별 포트레잇 폴더의 그림 전체. 대표 칸에 표시된 것이 캐릭터 탭 이미지 칸에 들어간 그림.'],
]
for g in guide: ws.append(g)
ws['A1'].font = Font(bold=True, size=14)
for r in (4, 9):
    for cell in ws[r]: cell.font = H; cell.fill = FILL
ws.column_dimensions['A'].width = 14; ws.column_dimensions['B'].width = 110
for row in ws.iter_rows(min_row=2):
    for cell in row: cell.alignment = Alignment(wrap_text=True, vertical='top')

hdr = ['id','이름','원어/별명','룰','시스템','시대','캠페인/분류','상태','성별','나이','국적/출신','직업·역할','종족','이성(현재/초기)','시나리오 횟수','시나리오','한마디','외견','성격','배경','비고','원본 탭','원본에서 숨김','공개','대표 이미지','이미지(캐릭터 시트)','이미지(개요 탭)','포트레잇(PC)']
data = []
for r in rows:
    data.append([r['id'], r['이름'], r.get('원어/별명',''), r['룰'], r['시스템'], r['시대'], r.get('캠페인') or r.get('분류',''), r['상태'], r.get('성별',''), r.get('나이',''),
                 r.get('국적',''), r.get('직업',''), r.get('종족',''), r.get('이성',''), r.get('시나리오횟수',''), ' / '.join(r.get('시나리오', [])), r.get('한마디',''),
                 r.get('외견',''), r.get('성격',''), r.get('배경',''), r.get('비고',''), r['원본탭'], r['숨김'], '', r.get('_tabimg') or r.get('_img') or '', r.get('_tabimg',''), r.get('_img',''), r.get('이미지','')])
sheet(wb.create_sheet('캐릭터'), hdr, data, [9,18,18,6,14,8,14,10,5,6,12,20,10,10,8,36,30,24,20,40,36,24,8,6,30,30,30,30])
rec = []
for r in rows:
    for i, s in enumerate(r.get('시나리오', []), 1):
        rec.append([r['id'], r['이름'], i, s, '', '', ''])
sheet(wb.create_sheet('참가기록'), ['캐릭터 id','이름','순서','시나리오','날짜','결과','메모'], rec, [9,18,6,40,12,10,30])
img = []
for r in rows:
    for f in r.get('이미지목록', []): img.append([r['id'], r['이름'], '캐릭 포트레잇/' + f, '대표' if '캐릭 포트레잇/' + f == r.get('이미지') else ''])
sheet(wb.create_sheet('이미지목록'), ['캐릭터 id','이름','파일 (PC: 바탕화면/티알피지/TRPG/캐릭 포트레잇 기준)','대표'], img, [9,18,90,8])
raw = [[r['id'], r['이름'], r['원본탭'], r['text']] for r in rows if r['text']]
sheet(wb.create_sheet('시트원문'), ['캐릭터 id','이름','원본 탭','시트 내용'], raw, [9,18,24,140])
wb.save(OUT)
from collections import Counter
print(len(rows), len(rec), len(raw), Counter(r['룰'] for r in rows), Counter(r['상태'] for r in rows))
json.dump(rows, open(D + '/rows.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
