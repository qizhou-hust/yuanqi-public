"""Bounded before-solve wrapper checks. Writes own fixtures/results only."""
from pathlib import Path
import ast,json,math,types
import numpy as np
import independent_preflight_checks as base

OUT=Path(__file__).resolve().parent
WRAPPER=OUT.parent/'preprocessing-work/check_before_solve.py'

def main():
    sem=base.functions_only(base.SEM,{'np':np,'math':math,'json':json,'Path':Path,'BASE':base.BASE,'TRI':base.TRI,'SHA':base.sha})
    ext=base.functions_only(base.EXT,{'np':np,'sp':types.SimpleNamespace(TRI=base.TRI)})
    tree=ast.parse(WRAPPER.read_text(encoding='utf-8-sig'))
    allowed=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ALLOWED' for t in n.targets))
    attrs=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ATTRS' for t in n.targets))
    env=base.functions_only(WRAPPER,{'Path':Path,'json':json,'math':math,'sp':types.SimpleNamespace(**sem),
        'jacobian_check':ext['jacobian_check'],'ALLOWED':allowed,'ATTRS':attrs})
    fixture=OUT/'fixtures'; source=fixture/'baseline.inp'
    text=source.read_text(); meta=source.with_suffix('.meta.json').read_bytes()
    # FIXED is a documented CalculiX BOUNDARY parameter: freezes the previous
    # step deformation, or zero in step 1. It changes the intended closure step.
    lines=text.splitlines(); step=0; changed=0
    for i,line in enumerate(lines):
        if line.upper().startswith('*STEP'):step+=1
        if step==1 and line.upper().startswith('*BOUNDARY'):
            lines[i]=line+',FIXED';changed+=1
    assert changed==1
    p=fixture/'fixed_closure_step.inp';p.write_text('\n'.join(lines)+'\n',encoding='utf-8');p.with_suffix('.meta.json').write_bytes(meta)
    rows=[]
    for name in ['baseline','reversed_torque','wrong_second_material','missing_material_reference','fixed_closure_step']:
        path=fixture/(name+'.inp');r=env['check'](path)
        rows.append({'fixture':name,'input_sha256':base.sha(path),'ready_for_diagnostic_solve':bool(r['ready_for_diagnostic_solve']),
                     'profile_errors':r['supported_profile_errors'],'input_pass':bool(r['input_checks']['pass']),
                     'mesh_pass':bool(r['mesh']['pass'])})
    assert rows[0]['ready_for_diagnostic_solve'] and all(not r['ready_for_diagnostic_solve'] for r in rows[1:])
    result={'schema':'m37.independent-profile-checks/v1','source_sha256':{str(p.relative_to(base.BASE)):base.sha(p) for p in [WRAPPER,base.SEM,base.EXT]},
        'scope':'Independent AST-loaded calls on copied local fixtures. No solver. Unknown BOUNDARY FIXED is a real physical step mutation.',
        'rows':rows,'no_acceptance_change':True}
    out=OUT/'INDEPENDENT-PROFILE-CHECKS.json';out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
