"""Reproduce bounded joint optimization versus independent fresh enumeration.

Inputs are explicit authored capability fixtures, not real C001 engineering data.
"""
import argparse,copy,hashlib,itertools,json,pathlib
from ..product import design_check as DC, system_optimize as OPT
from ..gear import math_source as MS, source_optimize as SO
from ..system.system_optimize import total_volume_mm3
from ..kernel import units as U
from .m36_identity import implementation_sha256

def report(inputs):
    doc,si,p=(inputs[k] for k in ('design_doc','system_input','problem'))
    result=OPT.optimize(doc,si,p)
    if result['status']!='completed':raise ValueError('Optimization blocked: '+str(result['errors']))
    rows=[];feasible=[]
    for g,sh,b in itertools.product(p['gear'],p['shaft'],p['bearing']):
        d=copy.deepcopy(doc);d['inputs'].update(g['inputs'])
        s=copy.deepcopy(si);s.update(shafts=sh['shafts'],keys=sh['keys'],bearings=b['bearings'])
        checked=DC.check(d,s,OPT.SCOPES)
        statuses={scope:checked['checks'][scope]['status'] for scope in OPT.SCOPES}
        if any(v not in ('pass','fail') for v in statuses.values()):raise ValueError('Full reference blocked: '+str(statuses))
        row={'ids':[g['id'],sh['id'],b['id']],'status':'pass' if all(v=='pass' for v in statuses.values()) else 'fail','checks':checked}
        if row['status']=='pass':
            model=SO.build_family_model(d,'pair_model')
            volume=U.from_canonical(model.evaluate(['V_blank']).values['V_blank'],'mm^3')
            row['objective']=total_volume_mm3(gear_blank_mm3=volume,shafts=sh['shafts'])
            feasible.append({'ids':row['ids'],'objective':row['objective']})
        rows.append(row)
    if MS.verify_certificates(doc):raise ValueError('Certificate changed during reference replay')
    feasible.sort(key=lambda r:(r['objective'],r['ids']))
    actual=[{'ids':r['ids'],'objective':r['objective']} for r in result['feasible']]
    return {'schema':'gearbase.m36-system-closure/1','system_optimization_passed':actual==feasible,
            'full_reference_combinations':len(rows),'feasible_count':len(feasible),'optimized':result,'fresh_reference':rows,
            'implementation_sha256':implementation_sha256(),'input_sha256':hashlib.sha256(json.dumps(inputs,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest(),
            'limits':['Finite authored cylindrical demo only; real C001 source inputs remain incomplete.','Objective excludes bearing envelopes, keys, housings and feedback of shaft deflection into KHbeta.','Original Stage0 regressions are separate from full-system worm/planet ratings; M40 remains frozen.']}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--inputs',type=pathlib.Path,required=True);ap.add_argument('--out',type=pathlib.Path,required=True);args=ap.parse_args()
    inputs=json.loads(args.inputs.read_text(encoding='utf8'));r=report(inputs)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'closure.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(json.dumps({k:r[k] for k in ('system_optimization_passed','full_reference_combinations','feasible_count','implementation_sha256')}))
    return 0 if r['system_optimization_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
