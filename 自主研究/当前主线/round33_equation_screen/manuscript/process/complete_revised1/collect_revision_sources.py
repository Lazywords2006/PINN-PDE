"""第一轮修订的定向只读来源核查；不导入研究模块或加载模型。"""
from pathlib import Path
from statistics import median
import hashlib
import json
import math
import re

OUT=Path(__file__).resolve().parent
MAN=OUT.parents[1]
ROOT=MAN.parent
BASE=MAN/'drafts/complete_v1.md'
BASE_SHA='8c5a83cff08732ce8e548cd873faa4e55cede075c3340fe9799e9deae37d4fd3'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
readj=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert sha(BASE)==BASE_SHA
assert not (OUT/'source_evidence.json').exists(),'来源初核已存在，拒绝无条件覆盖。'
frozen=readj(MAN/'process/complete_v1/FROZEN_DELIVERY_MANIFEST.json')
assert all(sha(Path(p))==digest for p,digest in frozen['files'].items())
protected=dict(frozen['files'])
extra=[MAN/'process/complete_v1/FROZEN_DELIVERY_MANIFEST.json',MAN/'PAPER_CONFIGURATION.json',MAN/'OUTLINE_AND_EVIDENCE.md',
       MAN/'process/writer_phase4a.md',MAN/'process/writer_contract.json',MAN/'drafts/working_revised1.md',MAN/'drafts/initial_working.md']
protected.update({str(p):sha(p) for p in extra})
save('protected_before.json',protected)

source_names=['pinn1d.py','problems.py','stage5_support.py','SCREEN_PROTOCOL.md','E4_PROTOCOL.md']
source={name:(ROOT/name).read_text(encoding='utf-8-sig') for name in source_names}
assert 'torch.sqrt(t.clamp_min(1e-30))' in source['pinn1d.py']
assert 'rng = np.random.default_rng(330500)' in source['stage5_support.py']
assert 'rng.uniform(0, 1, 8192), rng.uniform(1e-4, 1, 8192)' in source['stage5_support.py']
assert 'rng.uniform(1e-4, 1, 1024), rng.uniform(1e-4, 1, 1024), rng.uniform(0, 1, 1024)' in source['stage5_support.py']
assert 'G=lambda u: kappa * (u - 1.0)' in source['problems.py']
assert 'D=0.1, kappa=1.0, gamma=1.0, V0=1.0' in source['problems.py']

old_hashes=readj(MAN/'process/complete_v1/numeric_checks.json')['json_sha256']
targeted=[]
for tag in ('e4screen','e4confirm','pirate'):
    for path in sorted((ROOT/'runs'/tag).glob('*/*.json')):
        rel=path.relative_to(ROOT).as_posix()
        assert sha(path)==old_hashes[rel],rel
        r=readj(path)
        assert r['metrics']['times']==[.05,.1,.25,.5,1.]
        assert all(math.isfinite(v) for key in ('vol','trace') for v in r['metrics'][key])
        assert max(r['metrics']['vol'])==r['max_vol'] and max(r['metrics']['trace'])==r['max_trace']
        targeted.append({'source':rel,'sha256':sha(path),'tag':r['tag'],'eq':r['eq'],'method':r['method'],'seed':r['seed'],
            'max_vol':r['max_vol'],'max_trace':r['max_trace'],'metrics':{'times':r['metrics']['times'],'vol':r['metrics']['vol'],'trace':r['metrics']['trace']},
            'config':r['config'],'env':r['env'],'resumed_at':r['history'].get('resumed_at',[]),'delta':r['delta']})
assert len(targeted)==32
e4groups=[]
for tag in ('e4screen','e4confirm'):
    for method in ('vanilla','hardic','rba','hardic+layer'):
        rows=sorted([r for r in targeted if r['tag']==tag and r['method']==method],key=lambda r:r['seed'])
        assert [r['seed'] for r in rows]==([0,1] if tag=='e4screen' else [0,1,2])
        assert all(r['delta']==-1.02 for r in rows)
        e4groups.append({'tag':tag,'method':method,'seeds':[r['seed'] for r in rows],
            'max_vol':[r['max_vol'] for r in rows],'max_trace':[r['max_trace'] for r in rows],
            'vol_median':median(r['max_vol'] for r in rows),'trace_median':median(r['max_trace'] for r in rows),
            'under_1e2':sum(r['max_vol']<=.01 for r in rows),'sources':[r['source'] for r in rows]})
e4final={r['method']:r for r in e4groups if r['tag']=='e4confirm'}
ratio=e4final['vanilla']['vol_median']/e4final['hardic+layer']['vol_median']
assert format(ratio,'.3f')=='0.838'
pirate=[r for r in targeted if r['tag']=='pirate']
for r in pirate:
    expected='2.14.1+cpu' if r['eq']=='E1_heat' and r['seed'] in (0,1) else '2.14.1+cu130'
    assert r['env']['torch']==expected
    r['execution_category']='历史检查点在本机完成' if expected.endswith('+cpu') else '历史云端完成'

# 复现两种计数口径；审稿的表/图行前缀筛除会同时删除以“表N”开头的正文说明。
t=BASE.read_text(encoding='utf-8')
config=readj(MAN/'PAPER_CONFIGURATION.json')
counts=[]
for title,target in config['section_targets'].items():
    block=t.split('## '+title+'\n',1)[1].split('\n## ',1)[0]
    block=re.sub(r'\\\[.*?\\\]','',block,flags=re.S)
    block=re.sub(r'<!--.*?-->','',block,flags=re.S)
    original=[line for line in block.splitlines() if not line.startswith(('|','图','!['))]
    alternative=[line for line in block.splitlines() if not line.startswith(('|','![')) and not re.match(r'^[图表]\s*\d',line)]
    han=lambda x:len(re.findall(r'[\u4e00-\u9fff]',x))
    original_n=han(title+'\n'+'\n'.join(original)); alternative_n=han('\n'.join(alternative))
    removed=[{'text':line,'cjk':han(line),'kind':'table_caption' if re.match(r'^表\d+\s',line) else 'table_note' if re.match(r'^表\d+注',line) else 'body_prose'}
             for line in original if re.match(r'^表\s*\d',line)]
    assert original_n-alternative_n==han(title)+sum(r['cjk'] for r in removed)
    counts.append({'section':title,'configured_target':target,'original_rule_cjk':original_n,'prefix_filter_rule_cjk':alternative_n,
        'chapter_title_cjk':han(title),'removed_table_prefixed_lines':removed})
assert [r['original_rule_cjk'] for r in counts]==[1695,2180,2245,2762,1789,763]
assert [r['prefix_filter_rule_cjk'] for r in counts]==[1688,2170,2204,1606,1784,761]
save('count_definition_comparison.json',{'base_sha256':BASE_SHA,'configuration_sha256':sha(MAN/'PAPER_CONFIGURATION.json'),
    'original_rule_total':sum(r['original_rule_cjk'] for r in counts),'reviewer_prefix_rule_total':sum(r['prefix_filter_rule_cjk'] for r in counts),
    'explanation':'原口径计章/节标题、表题、表注和以表号开头的正文，排除表格行/图题/图片/显示公式。审稿10213口径排除章标题及所有表号开头整行，故也排除多段结果论述；此差异不是稿件被删改。保留原配置与原口径，不据替代口径追改配额。',
    'sections':counts})
review_files=[MAN/'reviews/full_v1'/name for name in ('method_phase2.md','domain_phase2.md','da_phase2.md')]
save('source_evidence.json',{'base_sha256':BASE_SHA,'status':'三份审稿已读；待EIC及跨学科审稿完成后补全响应，不最终冻结',
    'sources':{str(ROOT/name):sha(ROOT/name) for name in source_names},'reviews_read':{str(p):sha(p) for p in review_files},
    'raw_records_targeted':32,'targeted_raw_records':targeted,'e4_groups':e4groups,
    'e4_vanilla_over_corrected_median_ratio':ratio,'e4_scope':'体与迹已有历史复算；不读取或发布表面变量历史误差为可复现证据。',
    'pirate_execution_map':pirate,'clamp':{'expression':'torch.sqrt(t.clamp_min(1e-30))','constant':1e-30,
        'analytic_limit_scope':'理想解析式按t=0连续延拓；截断分支的自动微分极限不是命题1的对象。'},
    'heldout':{'generator':'numpy.random.default_rng(330500)','draw_order':['x_f','t_f','t_left','t_right','x_initial'],
        'sizes':[8192,8192,1024,1024,1024],'spatial_interval':[0.,1.],'time_interval':[.0001,1.],
        'residual_component_counts':{'pde':8192,'left_neumann':1024,'right_dynamic':1024,'initial':1024}},
    'operations':{'training':0,'model_load':0,'reference_integration':0,'torch_import':0,'git_mutation':0}})
print(json.dumps({'raw_targeted':32,'e4_ratio':ratio,'original_count':11434,'alternative_count':10213,
    'protected_files':len(protected),'reviewers_read':3,'final_freeze_pending':True},ensure_ascii=False,indent=2))
