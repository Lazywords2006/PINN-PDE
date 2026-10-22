"""仅刷新N04静态文义检查和来源哈希，不运行分析脚本或任何训练代码。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import ast
import hashlib
import json
import re
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
KEY = 'validation/stage6_analysis_20261022/analyze_stage6.py'
FROZEN_SHA = '7ca430d7911dda4507469099e493dc2563ef48dff0157b4df862e4ab8f3b3635'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(name): return json.loads((OUT/name).read_text(encoding='utf-8'))
def save(name, obj):
    assert (OUT/name).parent == OUT
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

audit = load('source_and_command_audit.json')
checks = load('reproducibility_checks.json')
partial = load('read_only_partial_snapshot.json')
observed = datetime.now(timezone(timedelta(hours=8))).isoformat()
changed = [k for k,v in audit['source_files'].items() if sha(Path(v['absolute_path'])) != v['sha256']]
assert set(changed) <= {KEY}, changed
source = ROOT/KEY
raw = source.read_bytes()
text = raw.decode('utf-8-sig')
tree = ast.parse(text)
declarations=[]
for node in ast.walk(tree):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('add_argument','add_parser'):
        names=[arg.value for arg in node.args if isinstance(arg,ast.Constant) and isinstance(arg.value,str)]
        if names:
            options={}
            for keyword in node.keywords:
                try: options[keyword.arg]=ast.literal_eval(keyword.value)
                except (ValueError,TypeError): options[keyword.arg]=ast.unparse(keyword.value)
            declarations.append({'line':node.lineno,'call':node.func.attr,'names':names,'options':options})
declarations=sorted(declarations,key=lambda x:x['line'])
old_cli=audit['cli_static_audit'][KEY]['declarations']
strip_line=lambda items:[{k:v for k,v in item.items() if k!='line'} for item in items]
assert strip_line(declarations)==strip_line(old_cli)
assert 'Adam/SOAP末次记录损失' in text
assert 'history.adam_gradient_calls在第一阶段成功完成后按cfg.adam_steps写入' in text
old_hash=audit['source_files'][KEY]['sha256']
new_hash=sha(source)
audit['source_files'][KEY].update(sha256=new_hash,bytes=len(raw))
audit['cli_static_audit'][KEY]={'source_sha256':new_hash,'declarations':declarations}
revision={'captured_local':observed,'purpose':'N04文义修订与分析report新源码绑定',
    'source':KEY,'previous_source_sha256':old_hash,'current_source_sha256':new_hash,
    'cli_declarations_unchanged_except_line_numbers':True,
    'original_partial_snapshot_captured_local':partial['captured_local'],
    'original_partial_snapshot_source_sha256':partial['source_sha256'],
    'partial_rerun':False,'training_runs':0,'torch_imported':False,
    'scope':'仅更新源文件哈希和静态CLI/文义检查；原状态及命令实测快照保持原时点，不冒充当前实测。'}
audit.setdefault('static_revisions',[]).append(revision)
checks['documents']=[]
for name in ['REPRODUCIBILITY_CN.md','DATA_DICTIONARY_CN.md','AI_USE_STATEMENT_N03_CN.md']:
    path=OUT/name
    body=path.read_text(encoding='utf-8')
    assert body.count('```')%2==0
    links=re.findall(r'\]\((E:/[^\n)]+)\)',body)
    assert all(Path(link).exists() for link in links)
    columns=None
    for line in body.splitlines():
        if line.startswith('|'):
            size=line.count('|')
            if columns is None: columns=size
            assert size==columns,(name,line)
        else: columns=None
    checks['documents'].append({'file':name,'sha256':sha(path),'local_links':len(links),
        'all_local_link_targets_exist':True,'code_fences_paired':True,'table_columns_consistent':True})
dictionary=(OUT/'DATA_DICTIONARY_CN.md').read_text(encoding='utf-8')
assert '第一阶段成功走完后由`cfg.adam_steps`写入的预算/调用数记录' in dictionary
assert '非独立逐步增量计数器或外部逐步观测' in dictionary
assert 'N04' in dictionary
assert sha(ROOT/'manuscript/drafts/working_revised1.md')==FROZEN_SHA
assert 'torch' not in sys.modules
assert all(sha(Path(v['absolute_path']))==v['sha256'] for v in audit['source_files'].values())
checks['n04_static_revision']=revision
save('source_and_command_audit.json',audit)
save('reproducibility_checks.json',checks)
print(json.dumps({'documents':checks['documents'],'current_analysis_sha256':new_hash,
    'sources_bound':len(audit['source_files']),'all_sources_match_current_files':True,
    'frozen_working_draft_unchanged':True,'torch_imported':False,'partial_rerun':False},ensure_ascii=False,indent=2))
