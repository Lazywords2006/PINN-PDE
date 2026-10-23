"""独立最终核验要求的单处术语精确化，冻结父稿不覆盖。"""
from pathlib import Path
import hashlib,json,difflib
OUT=Path(__file__).resolve().parent
MAN=OUT.parents[1]
OLD=MAN/'process/delivery_candidate2'
BASE=MAN/'drafts/delivery_candidate2.md'
DRAFT=MAN/'drafts/delivery_candidate2a.md'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
readj=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(n,o):(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not DRAFT.exists()
assert sha(BASE)=='59d1db8fd5c8c468783e98ba6db1bcde0e49e7f923e82afa6e2d9e6dbf383cd4'
manifest=OLD/'FROZEN_CANDIDATE2_MANIFEST.json'
assert sha(manifest)=='e7e2e0edfd06a2660cf336bce1dab13ab0e5453bc8f3b977ae3f9045e9883dbc'
protected=dict(readj(manifest)['files'])
protected[str(manifest)]=sha(manifest)
assert all(sha(Path(p))==h for p,h in protected.items())
save('protected_before.json',protected)
b=BASE.read_text(encoding='utf-8');t=b
changes=[
    {'id':'TERMINOLOGY-01','reason':'独立最终核验者要求避免将12个配置读作12类不同方程。',
     'old':'12种方程的参考解均新计算N48、N64与N96',
     'new':'12个方程、参数或初值配置的参考解均新计算N48、N64与N96'},
    {'id':'BINDING-01','reason':'简短引用表链接同步指向本派生稿的哈希和上下文附件。',
     'old':'../process/delivery_candidate2/citation_contexts.md',
     'new':'../process/delivery_candidate2a/citation_contexts.md'}]
for x in changes:
    assert t.count(x['old'])==1
    x['base_line']=b[:b.index(x['old'])].count('\n')+1
    t=t.replace(x['old'],x['new'])
    x['new_line']=t[:t.index(x['new'])].count('\n')+1
back=t
for x in reversed(changes):back=back.replace(x['new'],x['old'])
assert back==b
assert len(t.splitlines())==len(b.splitlines())
assert t.split('## 1 引言与相关工作',1)[1].split('## 参考文献',1)[0]==b.split('## 1 引言与相关工作',1)[1].split('## 参考文献',1)[0]
DRAFT.write_text(t,encoding='utf-8')
h=sha(DRAFT)
save('change_map.json',{'draft_sha256':h,'base_sha256':sha(BASE),'changes':changes,
    'scientific_numeric_change':False,'six_body_sections_byte_identical':True,
    'final_integrity_status':'PENDING_INDEPENDENT_FINAL_RECHECK'})
(OUT/'delivery_candidate2_to_candidate2a.diff').write_text(''.join(difflib.unified_diff(
    b.splitlines(keepends=True),t.splitlines(keepends=True),fromfile='drafts/delivery_candidate2.md',tofile='drafts/delivery_candidate2a.md')),encoding='utf-8')
print(json.dumps({'draft_sha256':h,'changed_lines':[x['new_line'] for x in changes],'body_cjk':11510}))
