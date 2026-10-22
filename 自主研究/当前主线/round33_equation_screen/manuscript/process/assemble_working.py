"""Assemble only the writer's working draft and evidence; never edits experiment inputs."""
from pathlib import Path
import hashlib
import json
import re

PROCESS = Path(__file__).resolve().parent
MANUSCRIPT = PROCESS.parent
draft_path = MANUSCRIPT/'drafts/initial_working.md'
text = draft_path.read_text(encoding='utf-8')
tables = (PROCESS/'working_tables.md').read_text(encoding='utf-8')
for match in re.finditer(r'^## (\S+)\n\n(.*?)(?=^## |\Z)', tables, re.M|re.S):
    text = text.replace('<!-- TABLE:'+match[1]+' -->',match[2].strip())

# Use ordinary scientific numeric notation; Chinese character counts must not
# be inflated by spelling decimal quantities out as words.
replacements = {
 '三十点零六和五点九二':'30.06和5.92',
 '四十五点四七和八十一点六零':'45.47和81.60',
 '三十四点八三和五点九二':'34.83和5.92',
 '一点三六倍':'1.36倍',
 '二点六九':'2.69', '七点三四':'7.34',
 '十二点五三和六十九点九六':'12.53和69.96',
 '五点二一八五乘十的负四次方':'5.2185×10⁻⁴',
 '五点四零四八乘十的负四次方':'5.4048×10⁻⁴',
 '百分之三点五七':'3.57%',
 '二十二点六一和五点五二':'22.61和5.52',
 '十二点五一':'12.51','一点四七':'1.47',
 '零点零三到三':'0.03到3','零点一':'0.1','零点零五':'0.05',
 '零点七二三':'0.723','百分之三十八点三五':'38.35%',
 '五点九二降至五点零一':'5.92降至5.01',
 '千分之一点二':'1.2×10⁻³','千分之一点八九':'1.89×10⁻³',
 '百分之二点七三':'2.73%',
 '一千九百五十一至三千':'1951至3000',
 '三千一百九十六至三千七百五十一':'3196至3751',
 '三十八点二至一百零三点五分钟':'38.2至103.5分钟',
 '九十点四分钟':'90.4分钟','零点八三八':'0.838',
 '四个宽度为六十四的双曲正切隐藏层':'4个宽度为64的双曲正切隐藏层',
 '两万次 Adam 梯度调用':'20000次 Adam 梯度调用',
 '千分之一指数衰减至十万分之一':'10⁻³指数衰减至10⁻⁵',
 '名义上限三千次':'名义上限3000次',
 '四千零九十六个体点':'4096个体点',
 '每端二百五十六个边界点和二百五十六个初值点':'每端256个边界点和256个初值点',
 '体点八千一百九十二个，每端及初值各五百一十二个':'体点8192个，每端及初值各512个',
 '固定体点数为四千零九十六，少于普通方法的八千一百九十二':'固定体点数为4096，少于普通方法的8192',
 '三十二段':'32段','三个宽度为六十四':'3个宽度为64',
 '两万次梯度调用对应一万九千九百九十九次参数更新':'20000次梯度调用对应19999次参数更新',
 '参考分辨率六十四和二百个求积点':'参考分辨率64和200个求积点',
 '九十六和四百的设置':'96和400的设置',
 '八千一百九十二、一千零二十四及一千零二十四':'8192、1024及1024',
 '万分之一至一之间':'10⁻⁴至1之间',
 '一百七十六份结果记录':'176份结果记录',
 '独立编号一百和一百零一':'独立编号100和101',
}
for old,new in replacements.items():
    text=text.replace(old,new)
text=text.replace('体—面耦合','体表耦合').replace('修订1—5','修订1至5')
text=text.replace('关键词：物理信息神经网络；动态边界条件；初始相容性；角点层；解析修正',
                  '关键词：物理信息神经网络，动态边界条件，初始相容性，角点层，解析修正')
# Split long prose clauses; bibliography punctuation is handled separately.
pre_ref,post_ref=text.split('## 参考文献',1)
text=pre_ref.replace('；','。')+'## 参考文献'+post_ref

refs=json.loads((MANUSCRIPT/'research/REFERENCES_VERIFIED.json').read_text(encoding='utf-8-sig'))['references']
bykey={r['key']:r for r in refs}
map_path=PROCESS/'writer_citation_map.json'
if re.search(r'\[@[^\]]+\]',text):
    ordered=list(dict.fromkeys(re.findall(r'\[@([^\]]+)\]',text)))
else:
    ordered=[r['key'] for r in json.loads(map_path.read_text(encoding='utf-8'))['references']]
number={key:i+1 for i,key in enumerate(ordered)}
assert all(k in bykey for k in ordered)
for key,n in number.items(): text=text.replace('[@'+key+']','['+str(n)+']')

entries=[]
for key in ordered:
    r=bykey[key]
    names=[]
    for a in r['authors']:
        names.append(a.get('literal') or (a['family']+', '+a['given']))
    authors='; '.join(names)
    title=r['title']
    if key=='Vyas2024SOAP':
        venue='arXiv:2409.11321v2，初次提交2024，v2修订于2025-01-31'
        url='https://arxiv.org/abs/2409.11321v2'
    elif key=='NISTDLMF':
        venue='在线参考，§7.2.2、§7.6.1、§7.14.4，访问日期2026-10-22'
        url='https://dlmf.nist.gov/7.14.E4'
    else:
        venue=f"{r['journal']}, {r['year']}, {r['volume']}"
        if r.get('number'): venue+='('+r['number']+')'
        venue+=': '+r['pages']
        url=r['url']
    entries.append(f"[{number[key]}] {authors}. [{title}]({url}). {venue}.")
text=text.replace('<!-- REFERENCES:verified -->','\n\n'.join(entries))
draft_path.write_text(text,encoding='utf-8')

contexts=[]
body=text.split('## 参考文献')[0]
section='front_matter'
for para in re.split(r'\n\s*\n',body):
    if para.startswith('## '): section=para.splitlines()[0][3:]
    if para.startswith('### '): section=para.splitlines()[0][4:]
    for m in re.finditer(r'\[(\d+)\]',para):
        n=int(m[1]); key=ordered[n-1]
        contexts.append({'number':n,'key':key,'section':section,'paragraph':para})
mapdata={'references':[{**bykey[k],'citation_number':number[k]} for k in ordered], 'contexts':contexts,
         'body_citation_occurrences':len(contexts),'unique_references':len(ordered)}
map_path.write_text(json.dumps(mapdata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

config=json.loads((MANUSCRIPT/'PAPER_CONFIGURATION.json').read_text(encoding='utf-8-sig'))
counts={}
for match in re.finditer(r'^## ([1-6] [^\n]+)\n(.*?)(?=^## [1-6] |^## 参考文献|\Z)',text,re.M|re.S):
    title,content=match[1],match[2]
    clean=title+'\n'+content
    clean=re.sub(r'\\\[.*?\\\]','',clean,flags=re.S)
    clean=re.sub(r'<!--.*?-->','',clean,flags=re.S)
    clean=re.sub(r'^\|.*$','',clean,flags=re.M)
    clean=re.sub(r'^图\d+.*$','',clean,flags=re.M)
    clean=re.sub(r'\[MATERIAL GAP.*?\]','',clean,flags=re.S)
    actual=len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]',clean))
    target=config['section_targets'][title]
    counts[title]={'actual_cjk':actual,'target_cjk':target,'deviation_percent':round(100*(actual-target)/target,2),
                   'within_15_percent':abs(actual-target)<=target*.15}
assert len(counts)==6
total=sum(x['actual_cjk'] for x in counts.values())
result={'definition':config['count_definition'],
 'implementation_notes':'包括六节标题及小节标题；排除全部Markdown表格行、显示公式、图题、HTML注释和工作稿MATERIAL GAP占位文本。',
 'sections':counts,'actual_body_cjk':total,'target_body_cjk':11000,
 'deviation_percent':round(100*(total-11000)/11000,2),'within_10_percent':abs(total-11000)<=1100,
 'material_gaps':re.findall(r'\[MATERIAL GAP.*?\]',text,re.S),
 'draft_sha256':hashlib.sha256(draft_path.read_bytes()).hexdigest()}
(PROCESS/'writer_word_counts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'count':result['actual_body_cjk'],'deviation_percent':result['deviation_percent'],
 'sections':counts,'gaps':len(result['material_gaps']),'references':len(ordered),'citations':len(contexts)},ensure_ascii=False,indent=2))
