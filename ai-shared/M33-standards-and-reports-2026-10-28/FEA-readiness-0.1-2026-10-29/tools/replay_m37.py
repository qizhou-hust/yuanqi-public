"""Read-only replay of existing native M37 inputs/results. Does not run FEA."""
import argparse
import copy
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fea_readiness.contracts import load_json,write_json,sha256
from fea_readiness.pipeline import prepare
from fea_readiness.review import review
from fea_readiness.runner import completion

def case(root,inp,label):
    meta=load_json(inp.with_suffix('.meta.json'))
    return {'case_id':label,'units':'N-mm-MPa','theory':{'kind':'nominal_spur',
        'inputs':{'z1':20,'z2':36,'module_mm':2.,'alpha_deg':20.,'face_width_mm':30.,'torque_Nm':25.,'s_mm':meta['s_ref']},
        'material':{'E1_MPa':206000.,'nu1':.3,'E2_MPa':206000.,'nu2':.3}},
        'native':{'profile':'m37_l3','asset_root':str(root),'input':str(inp)}}

def main():
    p=argparse.ArgumentParser();p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=a.asset_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for label,folder,phase,expected in [
        ('original_ph00','m37-results/runs/L3',0,False),
        ('repaired_ph00','m37-l3-periodic-diagnostic/runs/L3',0,True),
        ('repaired_ph10','preprocessing-work/m37-ph10-ph11-evidence/ph10',10,True)]:
        inp=root/folder/f'L3_C001_G1_ph{phase:02d}_d12.inp'
        spec=case(root,inp,label);write_json(out/(label+'.case.json'),spec)
        result=prepare(spec);write_json(out/(label+'.prepare.json'),result)
        row={'case':label,'expected_ready':expected,'actual_ready':result['ready_for_diagnostic_solve'],
             'matches':result['ready_for_diagnostic_solve']==expected}
        rows.append(row);print(row,flush=True)
    sys.path.insert(0,str(root/'preprocessing-work'))
    from extended_preflight import phase_audit
    raw=phase_audit(10);write_json(out/'ph10.raw-extraction.json',raw)
    inp=root/'preprocessing-work/m37-ph10-ph11-evidence/ph10/L3_C001_G1_ph10_d12.inp'
    record=load_json(inp.parent/'repeat-record.json');log=inp.with_suffix('.log').read_text(errors='replace')
    run=completion(inp.with_suffix(''),record['run']['returncode'],log,record['run']['timeout'])
    run['input_sha256']=record['input_sha256']
    eq=raw['actual_balance']
    residuals=[]
    for name in ['wheel_contact_force_residual_rel','wheel_contact_moment_residual_rel','pinion_contact_vs_input_torque_residual_rel']:
        force='force_residual' in name;wheel=name.startswith('wheel')
        residuals.append({'name':name,'value':eq[name],'limit':1e-4,'definition':eq['sign_convention']+' Diagnostic print-precision screen 1e-4; original mechanical gates unchanged.',
            'kind':'force' if force else 'moment','free_body':'wheel' if wheel else 'pinion_torque_only',
            'moment_origin_mm':[0,56,0] if wheel else [0,0,0],
            'scale':44.340740519829666 if force else abs(eq['wheel_RF_moment_Nmm']) if wheel else eq['input_torque_Nmm'],
            'extraction_id':'pinned_extended_preflight.phase_audit:CF_RF_final_step',
            'source_sha256':sha256(inp.with_suffix('.dat'))})
    sources=[inp,inp.with_suffix('.dat'),inp.with_suffix('.log'),inp.with_suffix('.sta'),inp.with_suffix('.meta.json'),inp.parent/'repeat-record.json']
    active_contact=[]
    for item in raw['active_pressure_elements']:
        item=dict(item);item['source_sha256']=sha256(inp.with_suffix('.dat'));active_contact.append(item)
    result={'schema':'fea-readiness.result/0.1','input_sha256':sha256(inp),'run':run,
        'sources':[{'path':str(p),'sha256':sha256(p)} for p in sources],
        'balance_residuals':residuals,'active_contact_elements':active_contact,
        'contact_mesh_trigger_ratio':2.,'mesh_study':None,
        'theory_comparison':{'actual':record['extracted']['p_max_MPa'],
            'predicted':load_json(out/'repaired_ph10.prepare.json')['theory']['contact']['p0_MPa'],
            'applicable':None,'tolerance':None,
            'definition':'UNKNOWN: global maximum includes neighboring tip contact; nominal single-pair Hertz cannot yet classify its peak'},
        'scope':'Historical actual solver results replayed; no new solve, no change to frozen numerical acceptance'}
    write_json(out/'ph10.result.json',result);reviewed=review(result);write_json(out/'ph10.review.json',reviewed)
    checks={r['check_id']:r['status'] for r in reviewed['checks']}
    assertions={'native_matrix':all(r['matches'] for r in rows),
        'actual_contact_mesh_flagged':checks['actual_contact_mesh']=='FAIL',
        'theory_unknown_not_failed_physics':checks['theory_comparison']=='UNKNOWN',
        'raw_sources_intact':checks['result_sources']=='PASS',
        'actual_run_complete':checks['run_completion']=='PASS',
        'actual_balance_passes':all(v=='PASS' for k,v in checks.items() if k.startswith('balance.'))}
    mutations=[]
    original=root/'m37-l3-periodic-diagnostic/runs/L3/L3_C001_G1_ph00_d12.inp'
    for mutation in ['nonzero_fixed_wheel','wrong_pair_point','wrong_phase','wrong_preload']:
        with tempfile.TemporaryDirectory(prefix='fea-readiness-negative-') as temp:
            p=Path(temp)/'negative.inp';text=original.read_text();m=load_json(original.with_suffix('.meta.json'))
            if mutation=='nonzero_fixed_wheel':
                assert 'WBORE,1,2' in text
                text=text.replace('WBORE,1,2','WBORE,1,2,1.0')
            if mutation=='wrong_pair_point':m['pairs'][1]['point'][0]+=1.
            if mutation=='wrong_phase':m['s_ref']+=.01
            if mutation=='wrong_preload':
                assert '-0.00036105411125' in text
                text=text.replace('-0.00036105411125','-0.00072210822250')
            p.write_text(text);write_json(p.with_suffix('.meta.json'),m)
            s=case(root,p,mutation);r=prepare(s)
            mutations.append({'mutation':mutation,'ready':r['ready_for_diagnostic_solve'],
                'checks':{x['check_id']:x['status'] for x in r['checks']}})
    write_json(out/'mutation-check.json',{'solver_invoked':False,'rows':mutations})
    assertions['all_four_semantic_mutations_blocked']=all(not r['ready'] for r in mutations)
    write_json(out/'replay-summary.json',{'cases':rows,'assertions':assertions,'all_pass':all(assertions.values()),'solver_invoked':False})
    print(assertions,flush=True)
    return 0 if all(assertions.values()) else 1

if __name__=='__main__':raise SystemExit(main())
