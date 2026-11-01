"""Strict caller-input adapter to the original H2 Stage0 sampled problem."""
import copy,math
from . import h2_flagship as H2
REQUIRED=frozenset(('a1_mm','a2_mm','total_ratio','mn_series','ratio_splits','beta_range','tol','max_candidates'))

def _validate(p):
    if not isinstance(p,dict) or set(p)!=REQUIRED:raise ValueError('H2 requires exactly '+', '.join(sorted(REQUIRED)))
    def num(v):return type(v) in (int,float) and math.isfinite(v)
    if any(not num(p[k]) or p[k]<=0 for k in ('a1_mm','a2_mm','total_ratio','tol')):raise ValueError('positive finite scalars required')
    if p['total_ratio']<1 or type(p['max_candidates'])!=int or p['max_candidates']<1:raise ValueError('invalid ratio/output budget')
    if not isinstance(p['mn_series'],(tuple,list)) or not p['mn_series'] or any(not num(v) or v<=0 for v in p['mn_series']):raise ValueError('invalid module series')
    if not isinstance(p['beta_range'],(tuple,list)) or len(p['beta_range'])!=2 or not all(num(v) for v in p['beta_range']) or not 0<p['beta_range'][0]<=p['beta_range'][1]<45:raise ValueError('invalid helix band')
    if p['ratio_splits'] is not None:
        if not isinstance(p['ratio_splits'],(list,tuple)) or not p['ratio_splits']:raise ValueError('invalid seed policy')
        for row in p['ratio_splits']:
            values=row if isinstance(row,(list,tuple)) else [row]
            if not values or any(not num(v) or v<1 for v in values):raise ValueError('invalid seed ratio')
    return copy.deepcopy(p)

def run(parameters):
    p=_validate(parameters)
    out=H2.search_seed_domain(a1=p['a1_mm'],a2=p['a2_mm'],total_ratio=p['total_ratio'],mn_series=p['mn_series'],ratio_splits=p['ratio_splits'],beta_range=p['beta_range'],tol=p['tol'],max_candidates=p['max_candidates'])
    out.update(scope='stage0_sampled_geometry_only',inputs=p,unsupported_rating=['strength','shaft','bearing','thermal'])
    return out

def verify(parameters,candidate):
    result=run(parameters)
    return {'ok':candidate in result['candidates'],'kind':'fresh_sampled_domain_membership','scope':'stage0_sampled_geometry_only'}
