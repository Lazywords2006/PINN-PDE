from pathlib import Path
import urllib.request,json,hashlib,datetime
from concurrent.futures import ThreadPoolExecutor
import fitz
O=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen/manuscript/integrity/final_revised1');T=Path('D:/CodexRuntime/temp/r33_final_integrity');T.mkdir(parents=True,exist_ok=True)
urls={'rba_v1':'https://arxiv.org/pdf/2307.00379v1','rba_v2':'https://arxiv.org/pdf/2307.00379v2','chen2011':'https://global-sci.com/index.php/cicp/article/download/5794/11524/12754'}
def get(kv):
 k,u=kv
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=35) as r:b=r.read();status=r.status;url=r.url
  p=T/(k+'.pdf');p.write_bytes(b)
  doc=fitz.open(p); pages=[p.get_text() for p in doc]
  (T/(k+'.txt')).write_text('\n\n'.join(pages),encoding='utf-8')
  out=dict(key=k,url=u,final_url=url,status=status,sha256=hashlib.sha256(b).hexdigest(),pages=len(pages),local_temp=str(p),text_pages=pages)
 except Exception as e:out=dict(key=k,url=u,error=repr(e))
 return out
out=list(ThreadPoolExecutor(3).map(get,urls.items()));(O/'PRIMARY_PDF_FRESH.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
for x in out:
 print({k:v for k,v in x.items() if k!='text_pages'})
 if 'text_pages' in x:
  for i,p in enumerate(x['text_pages']):
   if 'Algorithm 1' in p or (x['key']=='chen2011' and ('Dirichlet' in p or 'S1' in p or 'time integral' in p)):print('PAGE',i+1,p[:10000])

