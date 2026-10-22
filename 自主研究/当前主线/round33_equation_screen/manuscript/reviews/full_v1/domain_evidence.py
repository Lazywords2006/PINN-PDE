"""Independent domain-review arithmetic/math probes, no training or project imports."""
from pathlib import Path
import hashlib
import json
import re
import statistics
import mpmath as mp

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUT = HERE / 'inputs/domain_phase2_input.md'
raw = INPUT.read_bytes()
paper = re.search(r'<paper>\r?\n(.*?)\r?\n</paper>', raw.decode('utf-8'), re.S).group(1)
sha256 = lambda data: hashlib.sha256(data).hexdigest()
assert sha256(raw) == '0810fb884f7bd41a46259dec3a7285150084c54ddc0016d50e2f965c3bf94365'
assert sha256(paper.encode('utf-8')) == '8c5a83cff08732ce8e548cd873faa4e55cede075c3340fe9799e9deae37d4fd3'

mp.mp.dps = 60
def q(y,t,c):
    eta = y / (2*mp.sqrt(t))
    return mp.exp(y/c+t/c**2)*mp.erfc(eta+mp.sqrt(t)/c)

def w(y,t,c):
    eta = y / (2*mp.sqrt(t))
    ii = mp.exp(-eta**2)/mp.sqrt(mp.pi)-eta*mp.erfc(eta)
    return c*(2*mp.sqrt(t)*ii-c*(mp.erfc(eta)-q(y,t,c)))

math_records = []
max_errors = {k:mp.mpf(0) for k in ['wt_Q','wyy_Q','wy_identity','boundary','decay_bulk','decay_boundary']}
for c in map(mp.mpf,['0.03','0.3','3']):
    for t in map(mp.mpf,['0.000001','0.001','0.05','0.5','1']):
        for mult in map(mp.mpf,['0','0.5','2','5']):
            y = mult*mp.sqrt(t)
            wt = mp.diff(lambda s:w(y,s,c),t)
            wy = mp.diff(lambda z:w(z,t,c),y)
            wyy = mp.diff(lambda z:w(z,t,c),y,2)
            errors = {'wt_Q':abs(wt-q(y,t,c)), 'wyy_Q':abs(wyy-q(y,t,c)),
                      'wy_identity':abs(wy-c*(q(y,t,c)-mp.erfc(y/(2*mp.sqrt(t)))))}
            if mult == 0:
                errors['boundary'] = abs(c*wt-wy-c)
            tau=mp.mpf('0.1')
            decay = mp.exp(-t/tau)
            vt = mp.diff(lambda s:mp.exp(-s/tau)*w(y,s,c),t)
            vyy = mp.diff(lambda z:decay*w(z,t,c),y,2)
            errors['decay_bulk']=abs(vt-vyy+decay*w(y,t,c)/tau)
            if mult == 0:
                vy=mp.diff(lambda z:decay*w(z,t,c),y)
                errors['decay_boundary']=abs(c*vt-vy-decay*(c-c*w(y,t,c)/tau))
            for k,v in errors.items(): max_errors[k]=max(max_errors[k],v)
            math_records.append({'C':str(c),'t':str(t),'y_over_sqrt_t':str(mult),'errors':{k:mp.nstr(v,12) for k,v in errors.items()}})
assert max(max_errors.values()) < mp.mpf('1e-45')

laplace=[]
for c,y,s in [(mp.mpf('.3'),mp.mpf('0'),mp.mpf('2')),(mp.mpf('.3'),mp.mpf('.2'),mp.mpf('3'))]:
    actual=mp.quad(lambda t:mp.exp(-s*t)*q(y,t,c),[0,mp.mpf('.1'),1,mp.inf])
    expected=mp.exp(-y*mp.sqrt(s))/(mp.sqrt(s)*(mp.sqrt(s)+1/c))
    laplace.append({'C':str(c),'y':str(y),'s':str(s),'absolute_error':mp.nstr(abs(actual-expected),12)})

def ratio(a,b): return float(a/b)
ratios={
 'E1_default_hardic_over_layer':ratio(4.11144e-2,1.18038e-3),
 'E3_default_hardic_over_layer':ratio(2.31643e-3,3.91498e-4),
 'E1_new_hardic_over_layer':ratio(3.27036e-3,1.21485e-3),
 'E3_new_hardic_over_layer':ratio(3.96935e-3,5.40479e-4),
 'E1_pirate_hardic_over_layer':ratio(1.73954e-2,7.69442e-4),
 'E3_pirate_hardic_over_layer':ratio(5.73940e-4,1.04021e-4),
 'E1_soap_hardic_over_layer':ratio(4.43049e-2,1.47648e-4),
 'E3_soap_hardic_over_layer':ratio(2.49476e-3,8.09251e-5),
 'E1_tau_max_over_min':ratio(1.37334e-3,8.00404e-4),
 'E3_tau_max_over_min':ratio(4.85645e-4,3.39548e-4),
 'E3_new_seed0_increase_pct':100*(ratio(5.40479e-4,5.21850e-4)-1),
 'E3_k0.1_increase_pct':100*(ratio(5.04041e-4,3.64333e-4)-1),
}
mismatch={'E1_default':-(2+0.3*0.5)/0.3-2,
          'E3_default':-(-0.02-1)/0.3-(-0.02),
          'E3_k0.1':-(-0.02-0.1)/0.3-(-0.02),
          'E3_k3':-(-0.02-3)/0.3-(-0.02)}
body=re.search(r'## 1 引言与相关工作(.*?)## 参考文献',paper,re.S).group(1)
body_clean='\n'.join(line for line in body.splitlines() if not (line.startswith('|') or line.startswith('![') or re.match(r'^[图表]\d',line)))
section_counts={}
for section in re.split(r'(?=^## [1-6] )', '## 1 引言与相关工作'+body,flags=re.M):
    if section.strip():
        title=section.splitlines()[0]
        clean='\n'.join(line for line in section.splitlines() if not (line.startswith('|') or line.startswith('![') or re.match(r'^[图表]\d',line)))
        section_counts[title]=len(re.findall('[\u4e00-\u9fff]',clean))
files=[ROOT/'pinn1d.py',ROOT/'problems.py',ROOT/'manuscript/figures/analytic_layer.png',ROOT/'manuscript/figures/history_v2/historical_comparison.png',ROOT/'validation/stage6_analysis_20261022/complete_v2/tau_sensitivity.png',ROOT/'validation/stage6_analysis_20261022/complete_v2/default_six_arms.png']
source_hashes={str(p):sha256(p.read_bytes()) for p in files}
runtime=Path('D:/CodexRuntime/runs/r33_domain_full_v1')
pdf_hashes={str(p):sha256(p.read_bytes()) for p in [runtime/'rba_v1.pdf',runtime/'rba_v2.pdf']}
evidence={
 'scope':'Independent reviewer checks only; no training, no model replay, no reference solve, no other reviewer/evaluator/integrity conclusions read.',
 'input_sha256':sha256(raw), 'embedded_manuscript_sha256':sha256(paper.encode('utf-8')),
 'math_probe_precision_digits':mp.mp.dps,'math_probe_point_count':len(math_records),
 'math_probe_max_abs_errors':{k:mp.nstr(v,16) for k,v in max_errors.items()},'math_probe_records':math_records,
 'laplace_quadrature_probes':laplace,
 'math_limit':'Finite high-precision checks are implementation/arithmetic evidence, not a proof or a convergence theorem.',
 'ratios_from_rounded_manuscript_table_values':ratios,'mismatch_from_equation3_and_parameter_definitions':mismatch,
 'word_count_scope':'CJK U+4E00-U+9FFF, sections 1-6 only; excluded table rows, image syntax, figure/table captions; no prescribed per-section quota available.',
 'body_cjk_count':len(re.findall('[\u4e00-\u9fff]',body_clean)), 'section_cjk_counts':section_counts,
 'inspected_source_and_figure_sha256':source_hashes,'downloaded_primary_pdf_sha256':pdf_hashes,
 'known_reporting_gaps':[{'id':'DR1','where':'section 3.1; section 4.4/table5','detail':'The manuscript names reservoir strength but does not explicitly state G_kappa(u)=kappa*(u-1); current problems.py lines100-102 supplies it.'},{'id':'DR2','where':'section5.2; E09','detail':'E4 is mentioned quantitatively without equations, parameters or flux-layer formula in manuscript; detailed external protocol/code exist, so this is local reporting incompleteness rather than missing underlying source.'},{'id':'DR3','where':'Appendix A','detail':'N04 appears once but has no definition or resolvable label in the supplied full manuscript.'}]
}
out=HERE/'domain_evidence.json'
out.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'evidence':str(out),'input_sha256':evidence['input_sha256'],'manuscript_sha256':evidence['embedded_manuscript_sha256'],'max_errors':evidence['math_probe_max_abs_errors'],'ratios':ratios,'body_cjk_count':evidence['body_cjk_count'],'evidence_sha256':sha256(out.read_bytes())},ensure_ascii=False))
