from pathlib import Path
import json,re,hashlib,datetime,urllib.request,urllib.error,difflib,collections
R=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen')
O=R/'manuscript/integrity/final_revised1'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v): (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
draft=R/'manuscript/drafts/complete_revised1a.md'
lines=draft.read_text(encoding='utf-8-sig').splitlines()
refs=[]
for i,s in enumerate(lines,1):
 m=re.match(r'^\[(\d+)\] (.+)',s)
 if m:
  u=re.search(r'\]\((https?[^)]+)\)',s).group(1)
  refs.append(dict(id=int(m[1]),line=i,text=s,url=u))
old=(R/'manuscript/drafts/complete_v1.md').read_text(encoding='utf-8-sig')
paras=[]; section='首页'; ine=False
for i,s in enumerate(lines,1):
 if s.startswith('#'): section=s.lstrip('# ').strip(); continue
 if s=='\\[': ine=True; continue
 if s=='\\]': ine=False; continue
 if not s.strip() or ine or s.startswith('|') or s.startswith('![') or re.match(r'^\[\d+\]',s): continue
 if section.startswith(('参考文献','数据与论据')): continue
 if i in (3,5,11,17) or s.startswith('关键词') or s.startswith('Keywords') or len(s)<21: continue
 paras.append(dict(id=f'P{len(paras)+1:03}',line=i,section=section,text=s,changed=s not in old))
for p in paras:
 p['selected_originality']=p['changed'] or p['line']<219 or p['section'].startswith(('5','6')) or p['line'] in [295,312,318,572,608,621]
write('INVENTORY.json',dict(created=datetime.datetime.now().astimezone().isoformat(),draft=str(draft),sha256=sha(draft),references=refs,paragraphs=paras,paragraph_count=len(paras),changed_count=sum(p['changed'] for p in paras),selected_originality=sum(p['selected_originality'] for p in paras)))
runs=[]
for p in sorted((R/'runs').rglob('*.json')):
 d=json.loads(p.read_text(encoding='utf-8-sig')); runs.append(dict(path=str(p),sha256=sha(p),data=d))
write('RAW_JSON_INDEPENDENT.json',runs)
print(json.dumps(dict(refs=len(refs),paras=len(paras),changed=sum(p['changed'] for p in paras),originality_selected=sum(p['selected_originality'] for p in paras),runs=len(runs),tags=collections.Counter(Path(x['path']).relative_to(R/'runs').parts[0] for x in runs)),ensure_ascii=False,indent=2))
ids=[]
for r in refs:
 u=r['url']
 if 'doi.org/' in u: ids.append('DOI:'+u.split('doi.org/')[1])
 elif 'arxiv.org/abs/' in u: ids.append('ARXIV:'+u.split('/abs/')[1].split('v')[0])
 else: ids.append('URL:'+u)
req=urllib.request.Request('https://api.semanticscholar.org/graph/v1/paper/batch?fields=title,authors,year,venue,publicationVenue,journal,externalIds,url',data=json.dumps({'ids':ids}).encode(),headers={'Content-Type':'application/json','User-Agent':'R33-integrity-audit/1.0'},method='POST')
try:
 with urllib.request.urlopen(req,timeout=25) as resp: ans={'status':resp.status,'body':json.load(resp)}
except Exception as e:
 ans={'status':'API_UNAVAILABLE','error':repr(e)}
 if isinstance(e,urllib.error.HTTPError): ans['body']=e.read().decode(errors='replace')[:3000]
write('A0_SEMANTIC_SCHOLAR.json',dict(time=datetime.datetime.now().astimezone().isoformat(),ids=ids,result=ans,protocol_missing='C:/Users/LazyM/.codex/skills/deep-research/references/semantic_scholar_api_protocol.md'))
print('S2',ans)
