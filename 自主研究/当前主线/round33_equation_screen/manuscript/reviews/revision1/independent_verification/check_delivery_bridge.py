"""Verify only the allowed status-line bridge; do not certify the final gate."""
from pathlib import Path
import datetime
import hashlib
import json

OUT=Path(__file__).resolve().parent
MAN=OUT.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p):return json.loads(Path(p).read_text('utf-8-sig'))
base=MAN/'drafts/complete_revised1a.md'
candidate=MAN/'drafts/delivery_candidate.md'
a,b=base.read_bytes(),candidate.read_bytes()
assert sha(base)=='398c2a44f2f9fd959b62564ddc599b123a3dd5de168ad0257a8572e188bf92e8'
assert sha(candidate)=='aef0c10a1bf19e8703a8066e1f0aaef75600b886777424b9f6545677ccc77eb0'
al,bl=a.splitlines(keepends=True),b.splitlines(keepends=True)
assert len(al)==len(bl)
changed=[i+1 for i,(x,y) in enumerate(zip(al,bl)) if x!=y]
assert changed==[5]
assert al[:4]+al[5:]==bl[:4]+bl[5:]
# Re-check protected input bindings at report completion.
integrity=js(OUT/'input_integrity.json')
assert all(sha(r['path'])==r['actual'] for r in integrity['bindings'])
res=js(OUT/'VERIFICATION_RESULTS.json')
assert len(res['items'])==25 and len({r['id'] for r in res['items']})==25
assert sum(r['priority']=='P1' and r['independent_status']=='FULLY_ADDRESSED' for r in res['items'])==14
assert sum(r['priority']=='P2' and bool(r['author_claim']) for r in res['items'])==11
evidence=dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base=str(base),base_sha256=sha(base),candidate=str(candidate),candidate_sha256=sha(candidate),changed_lines=changed,old_line=al[4].decode('utf-8').rstrip(),new_line=bl[4].decode('utf-8').rstrip(),all_other_bytes_identical=True,scientific_content_identical=True,protected_bindings_rechecked=len(integrity['bindings']),review_items_count=25,scope='Byte bridge only. The ordinary re-review remains bound to revision1a; no final gate, render, external peer review or journal acceptance certified.')
(OUT/'delivery_candidate_bridge.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report=OUT/'VERIFICATION_REPORT_CN.md'
text=report.read_text('utf-8')
assert '## 交付候选的限定字节桥接' not in text
text+='''
## 交付候选的限定字节桥接

复核后另收到交付候选`delivery_candidate.md`，SHA256为`aef0c10a1bf19e8703a8066e1f0aaef75600b886777424b9f6545677ccc77eb0`。本次独立按原始字节比较：仅第5行将待核验的版本状态句改为中性的“完整中文论文初稿、未投稿、实际审查范围见交付说明、不等同于外部同行评审或录用”；其余所有字节与本报告绑定的1a一致。因此候选稿的科学正文、公式、数据表、图引用、参考文献、附录及全部25项修订内容均与已核验版本相同。

这只是限定的版本对应确认，普通re-review仍绑定原1a；不对正在另行进行的final gate、HTML/PDF或最终交付状态提前背书。报告完成时再次核对原89项输入绑定，全部保持一致。详见[delivery_candidate_bridge.json](delivery_candidate_bridge.json)。
'''
report.write_text(text,encoding='utf-8')
manifest=OUT/'REVIEW_DELIVERY_MANIFEST.json'
oldmanifest=js(manifest)
oldmanifest['finalized_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
oldmanifest['delivery_candidate_bridge_sha256']=sha(OUT/'delivery_candidate_bridge.json')
oldmanifest['files']={str(p):sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!=manifest.name}
manifest.write_text(json.dumps(oldmanifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(candidate_sha256=sha(candidate),changed_lines=changed,all_other_bytes_identical=True,protected_bindings_match=89,report_sha256=sha(report),results_sha256=sha(OUT/'VERIFICATION_RESULTS.json'),manifest_sha256=sha(manifest)),ensure_ascii=False,indent=2))
