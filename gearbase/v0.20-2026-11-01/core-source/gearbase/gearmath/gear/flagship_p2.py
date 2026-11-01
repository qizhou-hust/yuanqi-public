"""L2 P→P Stage0: original NGW integer geometry and Pareto reporting.

No archive imports, strength sizing, efficiency or thermal model. All engineering
inputs are caller supplied. Constants below are the original SPEC §2-B / solver
contract, including its floating point Pareto epsilon and rounded tie identity.
The search is finite domain enumeration, not a general optimization engine.
"""
from __future__ import annotations

from collections import Counter
import copy
import math

MAX_CHECKS = 200_000
MAX_PAIRS = 6_000_000
PARETO_EPSILON = 1e-12
BACKLASH_NOTE = ('exact concentricity + full zero shift ⇒ theoretical backlash 0 at BOTH meshes; '
                 'profile shift is mandatory for an assemblable design (SPEC §2-B, V4 correction C2)')
REQUIRED = frozenset(('n1_rpm','target_total_ratio','np_options','zs_range','zp_range',
                      'm_series','i_tol','top_k'))
SCOPE = 'stage0_integer_geometry_only'


def _number(x):
    try:
        return type(x) in (int,float) and math.isfinite(x)
    except OverflowError:
        return False


def _validate(inputs):
    if not isinstance(inputs,dict) or set(inputs) != REQUIRED:
        raise ValueError('P2 requires exactly: '+', '.join(sorted(REQUIRED)))
    p = copy.deepcopy(inputs)
    for k in ('n1_rpm','target_total_ratio','i_tol'):
        if not _number(p[k]): raise ValueError(k+' must be a finite number')
    if p['n1_rpm'] <= 0 or p['target_total_ratio'] < 1 or p['i_tol'] < 0:
        raise ValueError('positive speed, ratio >= 1 and tolerance >= 0 required')
    if type(p['top_k']) is not int or p['top_k'] < 1:
        raise ValueError('top_k must be a positive integer')
    for k in ('zs_range','zp_range'):
        v=p[k]
        if not isinstance(v,(list,tuple)) or len(v)!=2 or any(type(x) is not int or x<1 for x in v) or v[0]>v[1]:
            raise ValueError(k+' must be an inclusive positive integer range')
        p[k]=list(v)
    for k in ('np_options','m_series'):
        v=p[k]
        if not isinstance(v,(list,tuple)) or not v:
            raise ValueError(k+' must be a nonempty sequence')
        if any((type(x) is not int or x<1) if k=='np_options' else (not _number(x) or x<=0) for x in v):
            raise ValueError(k+' contains invalid values')
        p[k]=list(v)
    count = len(p['np_options'])*len(p['m_series'])*(p['zs_range'][1]-p['zs_range'][0]+1)*(p['zp_range'][1]-p['zp_range'][0]+1)
    if count > MAX_CHECKS:
        raise ValueError('stage domain exceeds original 200000 check cap; partial search unsupported')
    try:
        if not all(math.isfinite(m*(p['zs_range'][1]+2*p['zp_range'][1]+4)) for m in p['m_series']):
            raise ValueError('geometry outside finite arithmetic range')
    except OverflowError as e:
        raise ValueError('geometry outside finite arithmetic range') from e
    return p


def _stage(s,z,n,m):
    """SPEC §2-B: concentricity, assembly/phasing, adjacency and tip clearance."""
    ring=s+2*z
    chord=m*(s+z)*math.sin(math.pi/n)
    need=m*(z+2.0)
    clearance=m*(1.25-1.0)
    if (s+ring)%n or chord<=need or clearance < .2*m-1e-12:
        return None
    return dict(zs=s,zp=z,zr=ring,n_p=n,ratio=1.0+ring/s,chord_mm=chord,
                needed_mm=need,radial_clearance_mm=clearance,
                backlash_note=BACKLASH_NOTE,m_options=[])


def _candidate(row,p,ties):
    err,mx,a,b,total=row
    mid=p['n1_rpm']/a['ratio']
    return dict(i_total=total,ratio_error_rel=err,max_stage_ratio=mx,
                min_stage_ratio=min(a['ratio'],b['ratio']),
                identical_stages=(a['zs'],a['zp'],a['n_p'])==(b['zs'],b['zp'],b['n_p']),
                ties=ties[(round(err,9),round(mx,9))],n_mid_rpm=mid,n_out_rpm=mid/b['ratio'],
                stage1=copy.deepcopy(a),stage2=copy.deepcopy(b))


def stage0(inputs: dict) -> dict:
    """Return full objective frontier and original top_k representative candidates.

    ValueError rejects incomplete/unsupported input or a domain over the original
    budgets. No engineering parameter is inferred and no truncated optimization
    is labeled complete. Module order controls dimensional reporting as before.
    """
    p=_validate(inputs)
    stages={}; checks=0
    for n in p['np_options']:
        for s in range(p['zs_range'][0],p['zs_range'][1]+1):
            for z in range(p['zp_range'][0],p['zp_range'][1]+1):
                for m in p['m_series']:
                    checks+=1
                    stage=_stage(s,z,n,float(m))
                    if stage is None: continue
                    d=stages.setdefault((s,z,n),stage)
                    if m not in d['m_options']: d['m_options'].append(float(m))
    stages=sorted(stages.values(),key=lambda d:(d['ratio'],d['zs'],d['zp'],d['n_p']))
    pair_count=len(stages)*(len(stages)+1)//2
    if pair_count>MAX_PAIRS:
        raise ValueError('stage pairs exceed original 6000000 pair cap; partial search unsupported')
    rows=[]
    for i,a in enumerate(stages):
        for b in stages[i:]:
            total=a['ratio']*b['ratio']
            err=abs(total-p['target_total_ratio'])/p['target_total_ratio']
            if err<=p['i_tol']: rows.append((err,max(a['ratio'],b['ratio']),a,b,total))
    # Original stable identity order, strict epsilon improvement, rounded tie
    # buckets are P2's reporting contract. Generic kernel.pareto has different
    # equal-point semantics; replacing this scan would change the flagship.
    rows.sort(key=lambda r:(r[0],r[1],r[2]['zs'],r[2]['zp'],r[2]['n_p'],
                            r[3]['zs'],r[3]['zp'],r[3]['n_p']))
    ties=Counter((round(r[0],9),round(r[1],9)) for r in rows)
    front=[]; best=math.inf
    for row in rows:
        if row[1]<best-PARETO_EPSILON:
            front.append(_candidate(row,p,ties)); best=row[1]
    candidates=copy.deepcopy(front[:p['top_k']])
    return dict(ok=bool(candidates),family='P→P',scope=SCOPE,inputs=p,
                candidates=candidates,frontier=front,
                search=dict(enumerated=checks,feasible=len(stages),pairs_examined=pair_count,
                            in_tolerance_pairs=len(rows),pareto_points=len(front),complete=True,
                            top_k_truncated=len(front)>len(candidates),
                            stage_space_partial=False,pair_scan_partial=False,
                            caps=dict(stage_checks=MAX_CHECKS,stage_pairs=MAX_PAIRS)),
                reason=None if candidates else 'no two-stage pairing satisfies the declared domain and ratio tolerance',
                assumptions=['sun input / carrier output / ring fixed; i = 1 + zr/zs',BACKLASH_NOTE],
                spec_constants=dict(ha_planet=1.0,hf_ring=1.25,minimum_radial_clearance_factor=.2,
                                    pareto_epsilon=PARETO_EPSILON,tie_round_digits=9),
                strength=dict(status='not_implemented',hold='No planetary ISO 6336 rating or manufacturing release at Stage0'),
                efficiency=dict(status='not_implemented'),thermal=dict(status='not_implemented'))


def verify(inputs: dict, candidate: dict) -> dict:
    """Independent local candidate check; does not certify rank/tie multiplicity.

    Reconstruct equations directly, without stage0/_stage calls. Search/frontier
    completeness is separately checked by frozen oracle and small enumeration.
    """
    p=_validate(inputs); issues=[]; ratios=[]
    try:
        if not isinstance(candidate,dict): raise ValueError('candidate must be an object')
        for name in ('stage1','stage2'):
            d=candidate[name]; s,z,n=(d[k] for k in ('zs','zp','n_p'))
            if any(type(x) is not int for x in (s,z,n)): raise ValueError('integer stage identity required')
            if not (p['zs_range'][0]<=s<=p['zs_range'][1] and p['zp_range'][0]<=z<=p['zp_range'][1] and n in p['np_options']):
                raise ValueError('stage outside declared domain')
            ring=s+2*z
            if d['zr']!=ring or (s+ring)%n: raise ValueError('concentricity or phasing failed')
            allowed=[]
            for m in p['m_series']:
                chord=m*(s+z)*math.sin(math.pi/n); need=m*(z+2.0)
                if chord>need and .25*m >= .2*m-1e-12 and m not in allowed: allowed.append(float(m))
            if not allowed or d['m_options']!=allowed: raise ValueError('adjacency/clearance/module options failed')
            m=allowed[0]; ratio=1.0+ring/s; ratios.append(ratio)
            expected=dict(ratio=ratio,chord_mm=m*(s+z)*math.sin(math.pi/n),
                          needed_mm=m*(z+2.0),radial_clearance_mm=.25*m)
            for k,v in expected.items():
                if not _number(d[k]) or d[k]!=v: issues.append(name+'.'+k)
            if d['backlash_note']!=BACKLASH_NOTE: issues.append(name+'.backlash_note')
        a,b=ratios; total=a*b; err=abs(total-p['target_total_ratio'])/p['target_total_ratio']
        if err>p['i_tol']: issues.append('ratio tolerance')
        for k,v in dict(i_total=total,ratio_error_rel=err,max_stage_ratio=max(a,b),
                        min_stage_ratio=min(a,b),n_mid_rpm=p['n1_rpm']/a,
                        n_out_rpm=p['n1_rpm']/a/b).items():
            if not _number(candidate[k]) or candidate[k]!=v: issues.append(k)
        same=all(candidate['stage1'][k]==candidate['stage2'][k] for k in ('zs','zp','n_p'))
        if type(candidate['identical_stages']) is not bool or candidate['identical_stages']!=same: issues.append('identical_stages')
        if type(candidate['ties']) is not int or candidate['ties']<1: issues.append('ties')
    except (KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError) as e:
        issues.append(str(e))
    return dict(ok=not issues,issues=issues,scope=SCOPE,rank_verified=False,tie_multiplicity_verified=False,
                strength_status='not_implemented')


run = stage0
