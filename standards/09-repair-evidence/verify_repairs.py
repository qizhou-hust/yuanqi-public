"""Reproducible repair checks; engineering aid, NOT an ISO compliance engine."""
from pathlib import Path
import csv
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parent
rows = [
    (1, 1000, 103600, .89, .12, 1.01, 105.6),
    (2, 1000, 103600, .89, .67, 1.56, 163.1),
    (3, 224.5, 23260, .42, 1.53, 1.95, 45.84),
    (4, 224.5, 23260, .42, .83, 1.25, 29.39),
    (5, 55.43, 5740, .45, 3.41, 3.85, 22.38),
    (6, 55.43, 5740, .45, 1.86, 2.31, 13.42),
    (7, 13.69, 1420, .56, 4.03, 4.59, 6.58),
    (8, 13.69, 1420, .56, 8.00, 8.56, 12.28),
]
with (ROOT/'Table12_recovered.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f)
    w.writerow(['bearing','n_rpm_from_table11','nu_times_n_as_printed','T0_Nm','T1_Nm','Ttotal_Nm','P_W_as_printed'])
    w.writerows(rows)

def fin_heat(k, area, perimeter, h, length, delta_T, tip_h=0):
    """Uniform fin, constant properties, lateral h, tip_h over area; SI units."""
    if min(k,area,perimeter,h,length) <= 0 or tip_h < 0:
        raise ValueError('Positive geometry/material/h and nonnegative tip_h required')
    m=math.sqrt(h*perimeter/(k*area))
    b=tip_h/(k*m)
    return k*area*m*delta_T*(math.tanh(m*length)+b)/(1+b*math.tanh(m*length))

def finite_volume_fin(k,area,perimeter,h,length,delta_T,tip_h=0,N=300):
    """Independent cell-centred energy-balance discretization."""
    dx=length/N; g=k*area/dx; side=h*perimeter*dx
    a=np.zeros((N,N)); b=np.zeros(N)
    for i in range(N):
        a[i,i]=side
        if i:
            a[i,i]+=g; a[i,i-1]=-g
        else:
            a[i,i]+=2*g; b[i]=2*g*delta_T
        if i<N-1:
            a[i,i]+=g; a[i,i+1]=-g
        elif tip_h:
            a[i,i]+=1/(dx/(2*k*area)+1/(tip_h*area))
    t=np.linalg.solve(a,b)
    return 2*g*(delta_T-t[0])

def housing_example(T_oil=60,T_amb=25):
    # This example uses T_wall = T_oil, exactly the printed approximation.
    T_wall=T_oil+273.; T_inf=T_amb+273.
    alpha_rad=.23e-6*.9*((T_wall+T_inf)/2)**3
    alpha_free=18*.662**(-.1)*((T_wall-T_inf)/T_inf)**.3
    alpha=alpha_rad+alpha_free
    U=1/(1/200+.01/50+1/alpha)
    area=2*(.662*.925+.662*.370)+.925*.370
    Q=U*area*(T_oil-T_amb)
    return dict(alpha_rad=alpha_rad,alpha_free=alpha_free,alpha_air=alpha,U=U,area=area,Q_W=Q)

def run():
    checks=[]
    def check(name, actual, expected, abs_tol):
        actual=float(actual); expected=float(expected); abs_tol=float(abs_tol)
        passed=bool(abs(actual-expected)<=abs_tol)
        checks.append(dict(name=name,actual=actual,expected=expected,abs_tol=abs_tol,passed=passed))
    check('Table12 printed sum W',sum(r[-1] for r in rows),398.6,.02)
    for b,n,_,t0,t1,t,p in rows:
        # Published torques are rounded to 0.01 Nm; do not force equality.
        check(f'bearing {b}: P=2*pi*n*T/60',2*math.pi*n*t/60,p,.01*max(p,1))
        check(f'bearing {b}: torque rounded consistency',t0+t1,t,.011)
    # eq26/27, independently confirmed as Nmm in Palmgren, converted to Nm.
    t0=1e-10*6*(103.6*1000)**(2/3)*87.5**3
    check('bearing1 no-load torque Nm',t0,.886,.002)
    check('bearing7 low-speed torque Nm',1.6e-8*6*180**3,.560,.001)
    result=housing_example()
    check('sample radiation coefficient',result['alpha_rad'],6.5,.05)
    check('sample natural convection coefficient',result['alpha_free'],9.9,.06)
    check('sample total coefficient',result['U'],15.1,.1)
    check('sample housing heat W: printed rounding allowance',result['Q_W'],1085,6)
    next_T=(1075/(15.1*2.06)+25+60)/2
    check('sample one oil-temperature iteration',next_T,59.8,.05)
    # Do not claim the final 59.7 C is independently replayed: full viscosity/loss
    # recalculation is not implemented here.
    for tip_h in [0,15,100]:
        args=(45,3e-4,.08,18,.12,35)
        q=fin_heat(*args,tip_h=tip_h)
        qfv=finite_volume_fin(*args,tip_h=tip_h)
        check(f'fin analytical vs finite volume tip_h={tip_h}',q,qfv,abs(q)*.0001)
    sigma=5.670374419e-8;tw=333.;ta=298.;eps=.9
    exact=eps*sigma*(tw+ta)*(tw*tw+ta*ta)
    check('radiation mean-temperature approximation vs Stefan-Boltzmann',result['alpha_rad'],exact,.15)
    check('DIN official correction table1 mass kg/1000',7850*2*2*20*1e-6,.628,1e-12)
    check('DIN official correction table2 mass kg/1000',7850*45*25*360*1e-6,3180,1)
    # Sensitivity demonstration, not a validation tolerance for an actual product.
    sens=[]
    for loss_scale in [.8,1,1.2]:
        for ua_scale in [.8,1,1.2]:
            sens.append(dict(loss_scale=loss_scale,UA_scale=ua_scale,
                             equilibrium_C_linear=25+1075*loss_scale/(15.1*2.06*ua_scale)))
    record=dict(status='passed' if all(c['passed'] for c in checks) else 'failed',
                checks=checks,sample=result,next_temperature_C=next_T,
                sensitivity_illustration=sens,
                NOT_verified=['Full ISO compliance','Full table11 to table12 recalculation',
                              'Final 59.7 C fixed-point result','Product temperature prediction',
                              'DIN full corrected edition','Finned housing empirical area weighting'])
    (ROOT/'verification_results.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))
    assert record['status']=='passed'

if __name__=='__main__':run()
