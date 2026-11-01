"""ISO/TS6336-22:2018 clauses11.4–11.9, image-checked helical XY.

Source: micropitting.SOURCE_SHA256, PDF30–34 / printed22–26. Equations
60–77 are implemented directly; no fitted KISSsoft XY values are used.
Unloaded endpoints carry zero pressure and undefined film safety, not a clamp.
The original spur-only API and full micropitting rate remain unchanged.
"""
import math
from . import micropitting as M
from .tribology_common import formula_registry,choice,num,pos,nonneg,OutOfDomain
FORMULAS={}
_formula=formula_registry(FORMULAS,M.P,'New image-checked implementation; external branch qualification not yet registered')
PROFILES=('unmodified','modified_both','modified_wheel','modified_pinion')

@_formula('iso6336_22.eq60_66',M.P+' 11.4 式(60)–(66) 局部支撑因子；C=0.2mm（PDF30/印22 原图已核）')
def buttressing(*,g_Y,g_alpha,eps_beta,beta_b):
    g,ga,eb,bb=nonneg('g_Y',g_Y),pos('g_alpha',g_alpha),pos('eps_beta',eps_beta),pos('beta_b',beta_b)
    if g>ga or bb>=math.pi/2:raise OutOfDomain('buttressing','0≤gY≤gα and0<βb<π/2 required')
    width=.2*math.sin(bb)
    if width<=0 or 2*width>ga:raise OutOfDomain('g_alpha','buttressing end intervals must not overlap')
    peak=1.3 if eb>=1 else 1+.3*eb
    if g<=width:return peak-g/width*(peak-1)
    if g>=ga-width:return peak-(ga-g)/width*(peak-1)
    return 1.

def _geometry(g_Y,g_B,g_D,g_alpha,eps_alpha):
    g,gb,gd,ga,ea=nonneg('g_Y',g_Y),pos('g_B',g_B),pos('g_D',g_D),pos('g_alpha',g_alpha),pos('eps_alpha',eps_alpha)
    if not (1<ea<=2 and 0<=g<=ga and gb<=gd<ga):raise OutOfDomain('geometry','method B requires1<εα≤2 and ordered contact points')
    if not math.isclose(ga/gd,ea,rel_tol=1e-9) or not math.isclose(gb,ga-gd,rel_tol=1e-9,abs_tol=1e-12):raise OutOfDomain('geometry','gB=gα−pet, gD=pet and εα=gα/pet must agree')
    return g,gb,gd,ga,ea

@_formula('iso6336_22.eq50_59',M.P+' 11.3 式(50)–(59) 单端修形直齿分配，供11.6低重合度斜齿引用（PDF29/印21 原图已核）')
def _spur_one_end(profile,g,gb,gd,ga):
    gab,gde=gb/2,(ga+gd)/2
    if profile=='modified_wheel':
        if g<=gab:return g/gb
        if g<gb:return 1/3+g/(3*gb)
        if g<gd:return 1.
        if g<=gde:return (ga-g)/(ga-gd)
        return 1/3+(ga-g)/(3*(ga-gd))
    if g<=gab:return 1/3+g/(3*gb)
    if g<=gb:return g/gb
    if g<=gd:return 1.
    if g<=gde:return 1/3+(ga-g)/(3*(ga-gd))
    return (ga-g)/(ga-gd)

def _low(profile,g,gb,gd,ga,eb,bb,q):
    if profile=='unmodified':x=M.X_Y_spur_unmodified(g_Y=g,g_B=gb,g_D=gd,g_alpha=ga,tolerance_class=q)
    elif profile=='modified_both':x=M.X_Y_spur_modified_both(g_Y=g,g_B=gb,g_D=gd,g_alpha=ga)
    else:x=_spur_one_end(profile,g,gb,gd,ga)
    return x*buttressing(g_Y=g,g_alpha=ga,eps_beta=eb,beta_b=bb)

@_formula('iso6336_22.eq67_76',M.P+' 11.7–11.8 式(67)–(76) εβ≥1.2斜齿分配（PDF32–34/印24–26 原图已核）')
def _high(profile,g,gb,gd,ga,ea,eb,bb):
    if profile=='unmodified':return buttressing(g_Y=g,g_alpha=ga,eps_beta=eb,beta_b=bb)/ea
    gab,gde=gb/2,(ga+gd)/2
    if profile=='modified_both':
        plateau=1/ea+(ea-1)/(ea*(ea+1))
        if g<=gab:return plateau*g/gab
        if g<=gde:return plateau
        return plateau*(ga-g)/(ga-gde)
    plateau=1/ea+(ea-1)/(2*ea*(ea+1));weak=1/ea-(ea-1)/(2*ea*(ea+1));width=.2*math.sin(bb)
    if profile=='modified_wheel':
        if g<=gab:return plateau*g/gab
        if g<=ga-width:return plateau
        return weak*buttressing(g_Y=g,g_alpha=ga,eps_beta=eb,beta_b=bb)
    if g<=width:return weak*buttressing(g_Y=g,g_alpha=ga,eps_beta=eb,beta_b=bb)
    if g<=gde:return plateau
    return weak*(ga-g)/(ga-gde)

@_formula('iso6336_22.eq77',M.P+' 11.9 式(77) εβ在0.8与1.2边界分配因子间线性插值（PDF34/印26 原图已核）')
def X_Y_helical(*,profile,g_Y,g_B,g_D,g_alpha,eps_alpha,eps_beta,beta_b,tolerance_class):
    choice('profile',profile,PROFILES)
    g,gb,gd,ga,ea=_geometry(g_Y,g_B,g_D,g_alpha,eps_alpha)
    eb,bb=pos('eps_beta',eps_beta),pos('beta_b',beta_b);q=num('tolerance_class',tolerance_class)
    if bb>=math.pi/2 or not q.is_integer() or not 1<=q<=11:raise OutOfDomain('helical','0<βb<π/2 and integer accuracy1..11 required')
    # Validate buttressing geometry even for profiles whose endpoint factor is0.
    buttressing(g_Y=g,g_alpha=ga,eps_beta=eb,beta_b=bb)
    if eb<=.8:return _low(profile,g,gb,gd,ga,eb,bb,q)
    if eb>=1.2:return _high(profile,g,gb,gd,ga,ea,eb,bb)
    low=_low(profile,g,gb,gd,ga,.8,bb,q);high=_high(profile,g,gb,gd,ga,ea,1.2,bb)
    return low*(1.2-eb)/.4+high*(eb-.8)/.4

def p_dyn_points_method_B_helical(*,profile,g_alpha,p_et,d_a1,d_a2,d_b1,d_b2,alpha_wt,alpha_t,F_t,b,E_r,
                                  K_A,K_gamma,K_v,K_Halpha,K_Hbeta,eps_alpha,eps_beta,beta_b,tolerance_class):
    """Seven pressure points. Unloaded points have λGF=None; no film fiction."""
    gY=M.contact_points(g_alpha=g_alpha,p_et=p_et,d_a1=d_a1,d_b1=d_b1,alpha_wt=alpha_wt)
    out={}
    for name,g in gY.items():
        xy=X_Y_helical(profile=profile,g_Y=g,g_B=gY['B'],g_D=gY['D'],g_alpha=g_alpha,eps_alpha=eps_alpha,eps_beta=eps_beta,beta_b=beta_b,tolerance_class=tolerance_class)
        geo=M.local_geometry(g_Y=g,g_alpha=g_alpha,d_a1=d_a1,d_a2=d_a2,d_b1=d_b1,d_b2=d_b2,beta_b=beta_b)
        row={'g_Y':g,'X_Y':xy,'rho_nY':geo['rho_nY'],'status':'unloaded' if xy==0 else 'loaded'}
        if xy==0:row.update(p_H=0.,p_dyn=0.,lambda_GF=None,note='Zero load: film/safety undefined; excluded by no implicit policy')
        else:
            row['p_H']=M.p_H_Y_B(F_t=F_t,X_Y=xy,b=b,rho_nY=geo['rho_nY'],alpha_t=alpha_t,E_r=E_r)
            row['p_dyn']=M.p_dyn_B(p_H_Y_B=row['p_H'],K_A=K_A,K_gamma=K_gamma,K_v=K_v,K_Halpha=K_Halpha,K_Hbeta=K_Hbeta,eps_alpha=eps_alpha)
        out[name]=row
    return out
