from pathlib import Path
import hashlib,json,re,datetime,collections
R=Path('E:/PINN-PDE/自主研究/当前主线/round33_equation_screen')
O=R/'manuscript/integrity/final_numeric_completion_20261023'
P=R/'manuscript/process/delivery_candidate2a'
D=R/'manuscript/drafts/delivery_candidate2a.md'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(label,okay,detail=None):checks.append(dict(label=label,passed=bool(okay),detail=detail))
lines=D.read_text(encoding='utf-8-sig').splitlines();old=(R/'manuscript/drafts/delivery_candidate.md').read_text(encoding='utf-8-sig').splitlines()
check('2a_exact_draft',sha(D)=='741b88925f6248050c9de3f5fa590f2abf8a8496f4194dd6c35990038a3343ce')
for q in read(R/'manuscript/integrity/final_revised1/FILE_BINDINGS.json')['files']:
    f=Path(q['path']);check('retained_prior_source_or_figure:'+q['path'],f.exists() and sha(f)==q['sha256'])
oldfig={q['path']:q['sha256'] for q in read(R/'manuscript/process/complete_revised1a/figure_retention_checks.json')['figures']}
for q in read(P/'figure_retention_checks.json')['figures']:
    check('current_figure:'+q['path'],sha(Path(q['path']))==q['sha256']==oldfig[q['path']])
for m,expected,n in [('DELIVERY_BINDING_INDEX.json','f304f32b5cd25ed8dff94ec2853123f582ac1aec9a8178882f8a08aa9da12df4',21),('FROZEN_CANDIDATE2A_MANIFEST.json','cc2d57034e6d6cdfa2019ccd8a0a1e19f4e0ec0f9557e58182a4794f47c64a6a',19)]:
    data=read(P/m);check('manifest_identity:'+m,sha(P/m)==expected and len(data['files'])==data['file_count']==n)
    for f,h in data['files'].items():check('bound:'+f,sha(Path(f))==h)
c=read(P/'citation_contexts.json')
check('citation_draft_binding',c['draft_sha256']==sha(D))
check('bibliography_13_unchanged',[s for s in lines if re.match(r'^\[\d+\]',s)]==[s for s in old if re.match(r'^\[\d+\]',s)] and len(c['references'])==13)
actual=[(n,int(x),t) for n,t in enumerate(lines,1) if not re.match(r'^\[\d+\]',t) for x in re.findall(r'\[(\d+)\]',t)]
check('18_external_occurrences',len(actual)==18)
for q in c['contexts']:
    check('citation_context:'+str(q['line'])+':'+str(q['numbers']),lines[q['line']-1]==q['paragraph'] and all((q['line'],n,q['paragraph']) in actual for n in q['numbers']) and q['paragraph'] in old)
check('all_18_contexts_mapped',collections.Counter((q['line'],n,q['paragraph']) for q in c['contexts'] for n in q['numbers'])==collections.Counter(actual))
for q in c['data_evidence_contexts']:
    check('data_context:'+str(q['line']),lines[q['line']-1]==q['paragraph'])
links=[];link_math=False
for n,t in enumerate(lines,1):
    if t=='\\[':link_math=True;continue
    if t=='\\]':link_math=False;continue
    if link_math:continue
    for label,url in re.findall(r'\[([^\]]*)\]\(([^)]+)\)',t):
        if url.startswith(('http://','https://','#')):continue
        local=Path(url) if re.match(r'^[A-Za-z]:/',url) else D.parent/url
        check('local_link:'+str(n)+':'+label,local.exists(),str(local.resolve()))
        links.append(dict(line=n,label=label,target=str(local.resolve()),exists=local.exists()))
bridge=read(P/'prior_25_items_location_bridge.json');anchors=[]
check('25_prior_items',len(bridge['items'])==25)
check('prior_independent_report_binding',sha(Path(bridge['prior_report']))==bridge['prior_report_sha256']=='845b28cd6a6c662d4df0fc14ad93e33d67ceacb6d2b62868ef695300bc2b51e7')
for item in bridge['items']:
    for q in item['current_locations']:
        f=Path(q['file']);fl=f.read_text(encoding='utf-8-sig').splitlines();passed=sha(f)==q['sha256']
        if 'exact_anchor' in q:passed=passed and q['exact_anchor'] in fl[q['line']-1]
        check('prior_location:'+item['id']+':'+str(q.get('line','file_hash')),passed);anchors.append(dict(id=item['id'],line=q.get('line'),type='text_anchor' if 'exact_anchor' in q else 'file_hash',passed=passed))
check('84_prior_anchors',len(anchors)==84)
# Independent count under the supplied six-section Han-only definition.
section=None;math=False;counts=collections.Counter()
for t in lines:
    if t.startswith('## '):
        section=t[3:] if re.match(r'^## [1-6] ',t) else None
    if section is None:continue
    if t=='\\[':math=True;continue
    if t=='\\]':math=False;continue
    if math or t.startswith(('|','![')) or re.match(r'^图\s*\d',t):continue
    counts[section]+=len(re.findall(r'[\u4e00-\u9fff]',t))
w=read(P/'word_counts.json')
check('body_count',sum(counts.values())==w['actual_body_cjk']==11510,dict(counts))
for name,d in w['sections'].items():check('section_count:'+name,counts[name]==d['actual_cjk'])
out=dict(created=datetime.datetime.now().astimezone().isoformat(),draft_sha256=sha(D),checks=checks,check_count=len(checks),failures=[x for x in checks if not x['passed']],local_links=links,prior_anchor_count=len(anchors),body_counts=dict(counts),scope='Hashes, local links, exact retained citation contexts and response-anchor placement; historical re-review is not presented as current final approval.')
(O/'PROCESS_AND_LINK_CHECK.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:out[k] for k in ['check_count','failures','prior_anchor_count','body_counts']},ensure_ascii=False))
