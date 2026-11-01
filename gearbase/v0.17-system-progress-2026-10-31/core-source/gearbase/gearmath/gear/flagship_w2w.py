"""M31 SPEC §2-C/D, §3 W→W stage-0 synthesis; not a strength rating."""
import hashlib
import json
import math

M_SERIES = (1., 1.25, 1.5, 2., 2.5, 3., 4., 5., 6., 8., 10.)
Q_SERIES = (8., 9., 10., 11.2, 12.5, 14., 16., 20.)
REQUIRED = frozenset(('a1_mm','a2_mm','n1_rpm','target_ratio','rho_v_deg','t_out_nm','z1_options','ratio_band','k_w_m2k','area_m2','t_oil_max_c','t_amb_c','max_candidates'))

def _stage(a,m,q,z,rho,n):
    s=2*a/m
    if abs(s-round(s))>1e-6 or abs(round(s)-q-round(round(s)-q))>1e-6: return None
    z2=int(round(round(s)-q))
    if not 20<=z2<=80 or z2%z or m*z2>1.6*a+1e-9: return None
    gamma=math.degrees(math.atan(z/q)); eta=math.tan(math.radians(gamma))/math.tan(math.radians(gamma+rho))
    vs=math.pi*q*m*n/60000/math.cos(math.radians(gamma)); warns=[]
    if vs>4.5: warns.append('v_s>4.5 m/s: high sliding — scuffing/wear domain check required')
    if vs<0.3: warns.append('v_s<0.3 m/s: boundary lubrication — real ρv higher than input')
    return dict(ok=True,a_mm=a,m_mm=m,q=q,z1=z,z2=z2,ratio=z2//z,gamma_deg=gamma,eta=eta,self_locking=gamma<=rho,d1_mm=q*m,d2_mm=m*z2,d2_over_a=m*z2/a,sliding_speed_m_s=vs,warnings=warns)

def _designs(a,zs,rho,n):
    rows={}; count=0
    for z in zs:
        for m in M_SERIES:
            for q in Q_SERIES:
                r=_stage(a,m,q,z,rho,n)
                if r: count+=1; rows.setdefault((m,q,z),r)
    return rows,count

def _validate(p):
    if not isinstance(p,dict) or set(p)!=REQUIRED: raise ValueError('Required and only supported inputs: '+', '.join(sorted(REQUIRED)))
    for k,v in p.items():
        if k=='z1_options': continue
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v): raise ValueError('invalid '+k)
    z=p['z1_options']
    if not isinstance(z,(list,tuple)) or not z or any(type(x)!=int or not 1<=x<=6 for x in z): raise ValueError('invalid z1_options')
    if any(p[k]<=0 for k in ('a1_mm','a2_mm','n1_rpm','t_out_nm','k_w_m2k','area_m2')) or p['target_ratio']<1 or not 0<p['rho_v_deg']<45 or p['ratio_band']<0 or p['t_oil_max_c']<=p['t_amb_c'] or type(p['max_candidates'])!=int or p['max_candidates']<1: raise ValueError('invalid input range')

def _run(parameters):
    _validate(parameters); p=parameters; a,b=p['a1_mm'],p['a2_mm']; n=p['n1_rpm']; rho=p['rho_v_deg']; z=p['z1_options']; target=p['target_ratio']; k=p['k_w_m2k']; area=p['area_m2']; dt=p['t_oil_max_c']-p['t_amb_c']
    d1,c1=_designs(a,z,rho,n); d2,_=_designs(b,z,rho,n); candidates=[]; examined=0; seen=0; capped=False
    for one in sorted(d1.values(),key=lambda x:(x['m_mm'],x['q'],x['z1'])):
        mid=n/one['ratio']; second,c2=_designs(b,z,rho,mid); seen+=c2
        for two in sorted(second.values(),key=lambda x:(x['m_mm'],x['q'],x['z1'])):
            examined+=1
            if examined>1000000: capped=True; break
            ratio=one['ratio']*two['ratio']; err=abs(ratio-target)/target
            if err>p['ratio_band'] or not 0<one['eta']<=1 or not 0<two['eta']<=1: continue
            eta=one['eta']*two['eta']; out=n/ratio; pout=p['t_out_nm']*2*math.pi*out/60; pin=pout/eta; loss=pin-pout
            qloss=(pin/1000.0)*1000.0*(1-math.sqrt(eta)**2); req=qloss/(k*dt); actual=qloss/(k*area); levers=[f'forced cooling K≈25 → A_req≈{qloss/(25*dt):.3f} m²']
            thermal=dict(ok=area>=req,eta_total=math.sqrt(eta)**2,q_loss_w=qloss,area_required_m2=req,area_provided_m2=area,dt_actual_k=actual,t_oil_est_c=p['t_amb_c']+actual,levers=levers)
            candidates.append(dict(i_total=ratio,ratio_error_rel=err,eta_total=eta,n_mid_rpm=out*two['ratio'],n_out_rpm=out,p_out_w=pout,p_in_w=pin,q_loss_w=loss,thermal_ok=thermal['ok'],area_required_m2=req,area_provided_m2=area,dt_actual_k=actual,t_oil_est_c=thermal['t_oil_est_c'],thermal=thermal,cooling_levers=levers,stage1=dict(one,n_in_rpm=n,area_required_natconv_m2=loss/(12*60)),stage2=dict(two,n_in_rpm=mid),self_locking_stages=[name for name,rec in (('stage1',one),('stage2',two)) if rec['self_locking']],warnings=sorted(set(one['warnings'])|set(two['warnings']))))
        if capped: break
    candidates.sort(key=lambda c:(-c['eta_total'],c['ratio_error_rel'],*(c['stage1'][x] for x in ('m_mm','q','z1')),*(c['stage2'][x] for x in ('m_mm','q','z1'))))
    shown=candidates[:p['max_candidates']]
    return dict(status='ok' if shown else 'no_candidate',scope='stage0',inputs=dict(p),inputs_sha256=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),candidates=shown,search=dict(enumerated=c1+seen,feasible=len(candidates),pairs_examined=examined,stage1_designs=len(d1),stage2_designs=len(d2),truncated=len(candidates)>len(shown),pair_cap_hit=capped),assumptions=['M31 SPEC §2-D constant friction efficiency; §2-C convection; sliding warnings advisory'],unsupported_rating=['strength','wear','scuffing','bearing','shaft'],reason=None if shown else 'No in-band feasible worm pair')

def run(parameters):
    """Run stage 0, rejecting arithmetic overflow, underflow and nonfinite results."""
    try:
        _validate(parameters)
        dt = parameters['t_oil_max_c'] - parameters['t_amb_c']
        denominators = (parameters['k_w_m2k'] * parameters['area_m2'], parameters['k_w_m2k'] * dt)
        if not math.isfinite(dt) or any(not math.isfinite(x) or x <= 0 for x in denominators):
            raise ValueError('invalid thermal denominator')
        result = _run(parameters)
        def check(value):
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError('nonfinite computed value')
            if isinstance(value, dict):
                for v in value.values(): check(v)
            elif isinstance(value, (list, tuple)):
                for v in value: check(v)
        check(result)
        return result
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError('input produces invalid numerical result') from exc

def verify(parameters,candidate):
    """Re-enumerate and compare against the independently recomputed returned candidate."""
    result=run(parameters)
    return {'ok':candidate in result['candidates'], 'scope':'stage0', 'unsupported_rating':result['unsupported_rating']}
