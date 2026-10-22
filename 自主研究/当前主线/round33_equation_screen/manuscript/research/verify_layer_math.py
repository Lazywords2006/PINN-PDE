"""Independent high-precision identity audit; no training or result selection."""
import json
from pathlib import Path
import mpmath as m
m.mp.dps = 70

def w(y,t,C):
    eta=y/(2*m.sqrt(t))
    I=m.exp(-eta**2)/m.sqrt(m.pi)-eta*m.erfc(eta)
    q=m.exp(y/C+t/C**2)*m.erfc(eta+m.sqrt(t)/C)
    return C*(2*m.sqrt(t)*I-C*(m.erfc(eta)-q))

def q(y,t,C):
    return m.exp(y/C+t/C**2)*m.erfc(y/(2*m.sqrt(t))+m.sqrt(t)/C)

rows=[]
for C in map(m.mpf,['0.05','0.7','3']):
 for t in map(m.mpf,['1e-8','0.0001','0.03','0.7']):
  for eta in map(m.mpf,['0','0.25','1','3']):
   y=2*eta*m.sqrt(t)
   wt=m.diff(lambda z:w(y,z,C),t)
   wy=m.diff(lambda z:w(z,t,C),y)
   wyy=m.diff(lambda z:w(z,t,C),y,2)
   row={'C':float(C),'t':float(t),'eta':float(eta),
        'pde_absolute':float(abs(wt-wyy)),
        'wt_q_absolute':float(abs(wt-q(y,t,C)))}
   if not eta: row['boundary_absolute']=float(abs(C*wt-wy-C))
   rows.append(row)
inverse=[]
for C,t,eta in [('0.05','0.001','0.5'),('0.7','0.02','0'),('3','0.7','2')]:
 C,t,eta=map(m.mpf,(C,t,eta)); y=2*eta*m.sqrt(t)
 inv=m.invertlaplace(lambda s:C*m.exp(-m.sqrt(s)*y)/(s*(C*s+m.sqrt(s))),t,method='dehoog')
 true=w(y,t,C)
 integ=m.quad(lambda r:q(y,r,C),[0,t])
 inverse.append({'C':float(C),'t':float(t),'eta':float(eta),
    'inverse_relative':float(abs(inv-true)/abs(true)),
    'integral_relative':float(abs(integ-true)/abs(true))})
physical=[]
for D,c in [('0.01','0.2'),('0.3','1.1'),('4','0.07')]:
 D,c=map(m.mpf,(D,c));C=c/m.sqrt(D);x=m.mpf('.9');t=m.mpf('.01')
 U=lambda x,t:w((1-x)/m.sqrt(D),t,C)
 pde=m.diff(lambda z:U(x,z),t)-D*m.diff(lambda z:U(z,t),x,2)
 bc=c*m.diff(lambda z:U(m.mpf(1),z),t)+D*m.diff(lambda z:U(z,t),m.mpf(1))-c
 physical.append({'D':float(D),'c':float(c),'pde_absolute':float(abs(pde)),'boundary_absolute':float(abs(bc))})
asymptotic=[]
C=m.mpf('.7')
for t in map(m.mpf,['1e-4','1e-6','1e-8','1e-10']):
 v=w(m.mpf(0),t,C)
 # w=t-4 t^(3/2)/(3 sqrt(pi) C)+t^2/(2C^2)+O(t^(5/2)).
 coefficient=(v-t)/t**m.mpf('1.5')
 target=-4/(3*m.sqrt(m.pi)*C)
 asymptotic.append({'t':float(t),'w_over_t':float(v/t),'coefficient':float(coefficient),'limit':float(target)})
result={'precision_decimal_digits':m.mp.dps,'differential_points':rows,'inverse_and_integral':inverse,'physical_scaling':physical,'boundary_asymptotic':asymptotic,
 'summary':{'pde_max_abs':max(r['pde_absolute'] for r in rows),'wt_q_max_abs':max(r['wt_q_absolute'] for r in rows),'boundary_max_abs':max(r.get('boundary_absolute',0) for r in rows),'inverse_max_relative':max(r['inverse_relative'] for r in inverse),'integral_max_relative':max(r['integral_relative'] for r in inverse)}}
Path(__file__).with_name('MATH_NUMERICAL_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result['summary'],indent=2))
