"""Independent bounded checks of local preflight code; no solver or third-party imports.

The functions under review are loaded with AST extraction. Independent polynomial
interpolation and dense evaluation check the TRI6 determinant implementation.
Only this research directory is written. No acceptance gate is modified.
"""
from pathlib import Path
import ast
import hashlib
import json
import math
import types
import numpy as np

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
SEM = BASE/'preprocessing-work/m37-preflight/semantic_preflight.py'
EXT = BASE/'preprocessing-work/extended_preflight.py'
TRI = ((0, 1, 3), (1, 2, 4), (2, 0, 5))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def functions_only(path, env):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    body = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), env)
    return env

def one_element(xy):
    return {'nodes': {i+1: list(p) for i, p in enumerate(xy)}, 'elements': {1: [1, 2, 3, 4, 5, 6]}}

REFERENCE = np.array([[0,0],[1,0],[0,1],[.5,0],[.5,.5],[0,.5]], dtype=float)
V = np.array([[1, r, s, r*r, r*s, s*s] for r, s in REFERENCE])

def independent_sample(xy, n=160):
    # Interpolate the coordinate polynomial, then differentiate it. This does not
    # reuse the explicit shape-function derivatives or candidate formulas under review.
    coef = np.linalg.solve(V, np.asarray(xy))
    rs = np.array([(i/n,j/n) for i in range(n+1) for j in range(n+1-i)])
    r, s = rs.T
    dr = coef[1] + 2*r[:,None]*coef[3] + s[:,None]*coef[4]
    ds = coef[2] + r[:,None]*coef[4] + 2*s[:,None]*coef[5]
    det = dr[:,0]*ds[:,1]-dr[:,1]*ds[:,0]
    k = np.argmin(det)
    return float(det[k]), rs[k].tolist(), float(det.max()), len(det)

def run_jacobian(ext):
    check = ext['jacobian_check']
    fixed = [('positive_affine', REFERENCE.copy(), 1., True),
             ('negative_affine', REFERENCE[:,::-1].copy(), -1., False),
             ('degenerate', np.zeros((6,2)), 0., False)]
    distorted = REFERENCE.copy(); distorted[3] = [.5, 1.]
    fixed.append(('midpoint_fold', distorted, -3., False))
    records=[]
    for name, xy, expected, passes in fixed:
        result=check(one_element(xy)); sampled=independent_sample(xy)
        assert abs(result['minimum_jacobian_mm2']-expected)<1e-12, (name,result)
        assert result['pass']==passes, (name,result)
        records.append({'name':name,'nodes':xy.tolist(),'expected_minimum':expected,'expected_pass':passes,
                        'actual':result,'independent_grid_minimum':sampled[0]})
    rng=np.random.default_rng(371029); rows=[]
    for k in range(100):
        xy=REFERENCE.copy(); xy[3:]+=rng.uniform(-.8,.8,(3,2))
        exact=check(one_element(xy)); sampled, point, maximum, count=independent_sample(xy)
        delta=sampled-exact['minimum_jacobian_mm2']
        assert delta>=-1e-12, (k,delta)
        assert delta<.002, (k,delta)
        if sampled < -1e-10: assert not exact['pass']
        rows.append({'id':k,'nodes':xy.tolist(),'candidate_minimum':exact['minimum_jacobian_mm2'],
                     'grid_minimum':sampled,'grid_argmin':point,'grid_minus_candidate':delta,'pass':exact['pass']})
    # Adjacent positive triangles with equal coordinates but different shared midpoint IDs.
    d={'nodes':{1:[0,0],2:[1,0],3:[0,1],4:[.5,0],5:[.5,.5],6:[0,.5],
                7:[1,1],8:[1,.5],9:[.5,1],10:[.5,.5]},
       'elements':{1:[1,2,3,4,5,6],2:[2,7,3,8,9,10]}}
    mismatch=check(d); assert mismatch['mismatched_shared_midside_nodes']==1 and not mismatch['pass']
    d['elements'][2][-1]=5
    shared=check(d); assert shared['pass']
    d['elements'][3]=d['elements'][2]
    nonmanifold=check(d); assert nonmanifold['nonmanifold_edges']==1 and not nonmanifold['pass']
    return {'fixed_fixtures':records,'random_seed':371029,'random_fixtures':rows,'sample_points_per_fixture':count,
            'maximum_grid_minus_candidate':max(r['grid_minus_candidate'] for r in rows),
            'shared_midpoint_mismatch_rejected':mismatch,'shared_midpoint_positive_control':shared,
            'nonmanifold_rejected':nonmanifold,
            'scope':'Independent polynomial interpolation/differentiation and finite grid checks; not interval arithmetic certification or proof for arbitrary floating-point conditioning.'}

def run_semantic(sem):
    source=BASE/'m37-l3-periodic-diagnostic/runs/L3/L3_C001_G1_ph00_d12.inp'
    original=source.read_text(); fixture=OUT/'fixtures'; fixture.mkdir(exist_ok=True)
    meta=source.with_suffix('.meta.json').read_bytes()
    def audit(name,text):
        p=fixture/(name+'.inp');p.write_text(text,encoding='utf-8');p.with_suffix('.meta.json').write_bytes(meta)
        result=sem['audit'](p,'independent-negative-fixture',0,export=False)
        return {'fixture':str(p.relative_to(OUT)),'sha256':sha(p),'pass':bool(result['pass']),
                'load':result['load'],'units':result['units']}
    baseline=audit('baseline',original); assert baseline['pass']
    lines=original.splitlines(); inside=False; reversed_lines=[]; count=0
    for line in lines:
        if line.startswith('*'): inside=line.upper().startswith('*CLOAD')
        elif inside and line.strip():
            v=line.split(',');v[2]=str(-float(v[2]));line=','.join(v);count+=1
        reversed_lines.append(line)
    negative=audit('reversed_torque','\n'.join(reversed_lines)+'\n')
    assert count>0 and not negative['load']['pass'] and not negative['pass']
    # Add a material and actually reference it from the wheel section.
    altered=[]; changed=0
    for line in lines:
        if line.upper().startswith('*SOLID SECTION') and 'WHEEL' in line.upper():
            terms=line.split(',');terms=[('MATERIAL=AUDIT_WRONG' if t.strip().upper().startswith('MATERIAL=') else t) for t in terms]
            line=','.join(terms);changed+=1
        altered.append(line)
    assert changed>0
    pos=next(i for i,l in enumerate(altered) if l.upper().startswith('*STEP'))
    altered[pos:pos]=['*MATERIAL, NAME=AUDIT_WRONG','*ELASTIC','1.0, 0.1']
    second=audit('wrong_second_material','\n'.join(altered)+'\n')
    assert not second['units']['pass'] and not second['pass']
    missing=audit('missing_material_reference',original.replace('MATERIAL=STEEL','MATERIAL=AUDIT_ABSENT'))
    assert not missing['units']['pass'] and not missing['pass']
    return {'source':str(source.relative_to(BASE)),'source_sha256':sha(source),'baseline':baseline,
            'reversed_torque_rejected':negative,'wrong_second_material_rejected':second,
            'missing_material_reference_rejected':missing,
            'scope':'Actual current audit function on own-directory input mutations. Known baseline passes and the three negative fixtures are rejected. This is bounded validation, not a universal parser claim.'}

def main():
    sem=functions_only(SEM,{'np':np,'math':math,'json':json,'Path':Path,'BASE':BASE,'TRI':TRI,'SHA':sha})
    before=json.loads((OUT/'INDEPENDENT-PREFLIGHT-CHECKS-BEFORE.json').read_text(encoding='utf-8'))
    reuse=before['reviewed_source_sha256'][str(EXT.relative_to(BASE))]==sha(EXT)
    jac=before['jacobian'] if reuse else run_jacobian(functions_only(EXT,{'np':np,'sp':types.SimpleNamespace(TRI=TRI)}))
    result={'schema':'m37.independent-preflight-checks/v1','reviewed_source_sha256':{str(SEM.relative_to(BASE)):sha(SEM),str(EXT.relative_to(BASE)):sha(EXT)},
            'no_solver_runs':True,'no_acceptance_change':True,'jacobian':jac,'semantic':run_semantic(sem),
            'jacobian_evidence_reused_on_identical_source_hash':reuse,
            'before_evidence_sha256':sha(OUT/'INDEPENDENT-PREFLIGHT-CHECKS-BEFORE.json')}
    out=OUT/'INDEPENDENT-PREFLIGHT-CHECKS.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'file':str(out),'sha256':sha(out),'jacobian_fixtures':104,
        'max_grid_difference':result['jacobian']['maximum_grid_minus_candidate'],
        'reversed_torque_rejected':not result['semantic']['reversed_torque_rejected']['pass'],
        'wrong_second_material_rejected':not result['semantic']['wrong_second_material_rejected']['pass'],
        'missing_material_reference_rejected':not result['semantic']['missing_material_reference_rejected']['pass']},indent=2))

if __name__=='__main__':main()
