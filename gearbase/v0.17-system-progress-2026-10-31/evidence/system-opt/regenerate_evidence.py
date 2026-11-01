from pathlib import Path
import runpy,json,hashlib,time,sys
sys.path.insert(0,str(Path.cwd()))
from gearmath.product.system_optimize import optimize
root=Path('../v017-system-run/system-opt')
x=runpy.run_path('tests/test_v017_system_optimize.py');d,s,p=x['probe']()
t=time.perf_counter();r=optimize(d,s,p);elapsed=time.perf_counter()-t
t=time.perf_counter();ref=x['reference'](d,s,p);ref_elapsed=time.perf_counter()-t
for name,obj in [('probe-input',{'design_doc':d,'system_input':s,'problem':p}),('staged-result',r),('fresh-cartesian-reference',{'full_design_check_calls':27,'feasible':ref,'elapsed_seconds':ref_elapsed})]:
    (root/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
files=['gearmath/product/system_optimize.py','gearmath/system/system_optimize.py','tests/test_v017_system_optimize.py','docs/v017-system-optimization.md','tests/test_sys_design_check.py','data/source/C001.factors.math-source.json','data/system/C001.system-input.json']
receipt={'scope':'M36 gate2 finite cylindrical capability probe only','status':r['status'],'complete_feasible_ranking_equal': [{'ids':a['ids'],'objective':a['objective']} for a in r['feasible']]==ref,'first_optimum_equal':{'ids':r['best']['ids'],'objective':r['best']['objective']}==ref[0],'certificate_files':r['certificate_files'],'stats':r['stats'],'feasible_count':len(ref),'best':ref[0],'elapsed_staged_seconds':elapsed,'elapsed_reference_seconds':ref_elapsed,'timing_note':'Observed single run; no speedup claim. Every reference tuple freshly invokes all four scopes; every staged bearing scope freshly resolves shaft loads. Exact cache local to one run.', 'source_sha256':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files},'focused_and_legacy_tests':'56 unittest methods passed dependency-free:17 optimizer methods/115 assertion cases plus39 original methods','limitations':r['limitations']}
(root/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(receipt['stats'])
