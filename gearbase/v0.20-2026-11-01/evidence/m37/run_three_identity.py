import sys, json, shutil, subprocess, hashlib, os
from pathlib import Path
root=Path('D:/my_Works/Gears/gearbase-v020-work'); sys.path.insert(0,str(root)); sys.path.insert(0,str(root/'data/m37_fea_pack/scripts'))
from gearmath.tools import fea_prepare as p
import ccx_io, cases, run_m37
src=Path('D:/my_Works/Gears/v017-system-run/fea-prepare/jobs_utf8/runs/L2'); out=Path('D:/my_Works/Gears/v020-closure-run/m37'); solver=Path('D:/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23'); probe=Path('D:/my_Works/Gears/v017-system-run/fea-prepare')
reader=p.verified_profile(probe,solver); records=[]
for level in (8,12,18):
 name=f'L2_P01_d{level}'; folder=out/f'canonical_d{level}'; folder.mkdir(exist_ok=True)
 for suffix in ('.inp','.meta.json'): shutil.copyfile(src/(name+suffix),folder/(name+suffix))
 inp=folder/(name+'.inp'); meta=folder/(name+'.meta.json'); before={x.name:p.sha(x) for x in (inp,meta,solver)}; state,check,prepared=run_m37.preflight(inp,meta,solver); pre=run_m37.input_identity(inp,meta,solver)
 assert check['pass'] and not state.frd_requested() and before[solver.name]==p.SOLVER_HASH
 command=f'cd /mnt/d/my_Works/Gears/v020-closure-run/m37/canonical_d{level} && export LD_LIBRARY_PATH=/mnt/d/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/runtime/usr/lib/x86_64-linux-gnu:/mnt/d/my_Works/Gears/parallel-v09-2026-10-29/m37/runtime-ccx/root/usr/lib/x86_64-linux-gnu && sha256sum /mnt/d/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23 | grep -q ^{p.SOLVER_HASH} && OMP_NUM_THREADS=1 timeout 120s /mnt/d/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23 {name}'
 r=subprocess.run(['wsl','-d','Ubuntu','--','bash','-lc',command],capture_output=True,timeout=135); (folder/'solver.log').write_bytes(r.stdout+r.stderr)
 after={x.name:p.sha(x) for x in (inp,meta,solver)}; post=run_m37.input_identity(inp,meta,solver); assert before==after and not run_m37.identity_drift(prepared,pre) and not run_m37.identity_drift(prepared,post)
 rec,vals=reader.strict_record(inp.with_suffix('.dat').read_text(),inp.with_suffix('.sta').read_text(),state.strict_requests(),identity={'run_id':name,'input_sha256':before[inp.name]},frd_text=None,solver_version='2.23',**state.expectation())
 extracted,warnings=cases.post_L2(json.loads(meta.read_text(encoding='utf8')),ccx_io.parse_dat(inp.with_suffix('.dat')))
 result={'id':name,'returncode':r.returncode,'identity_before':before,'identity_after':after,'frd_requested':False,'step_check':check,'run_identity':{'version':run_m37.IDENTITY_VERSION,'prepared':prepared,'prelaunch':pre,'post':post,'consistent':True},'strict_read':rec,'extracted':extracted,'warnings':warnings,'output_sha256':{x.name:p.sha(x) for x in folder.iterdir() if x.is_file() and x.name not in ('evidence.json',)}}
 (folder/'evidence.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8'); records.append(result)
 print(name,'exit',r.returncode,'strict',rec['status'],'YFS_FE',extracted.get('YFS_FE'),'balance',extracted.get('force_balance_rel'),flush=True)
(out/'three-level-summary.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf8')
