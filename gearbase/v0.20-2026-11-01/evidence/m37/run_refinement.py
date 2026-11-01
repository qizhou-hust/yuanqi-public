import sys,json,subprocess,traceback
from pathlib import Path
root=Path('D:/my_Works/Gears/gearbase-v020-work'); pack=root/'data/m37_fea_pack'; sys.path[:0]=[str(root),str(pack/'scripts')]
from gearmath.tools import fea_prepare as p
import study, cases, ccx_io, run_m37
out=Path('D:/my_Works/Gears/v020-closure-run/m37/refinement'); out.mkdir(exist_ok=True); probe=Path('D:/my_Works/Gears/v017-system-run/fea-prepare'); solver=Path('D:/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23'); reader=p.verified_profile(probe,solver)
case=json.loads((pack/'cases/L2_yfs_matrix.json').read_text(encoding='utf8')); exp=json.loads((pack/'expected/L2_yfs_matrix.json').read_text(encoding='utf8'))
failed=[r['point'] for r in json.loads((out.parent/'ingest-matrix.json').read_text(encoding='utf8'))['ladder']['L2']['rows'] if r.get('converged') is False]
case['mesh']['root_divisions'] += [27,40]
(out/'derived-case.json').write_text(json.dumps(case,indent=2,ensure_ascii=False),encoding='utf8')
for sp in study.jobs_L2(case,exp,out,{'coord':True},{'l2_points':failed}):
 if sp['tags']['level'] < 3: continue
 name=sp['id']; print('BUILD',name,flush=True)
 try:
  inp,meta=sp['build'](); inp=Path(inp); mp=inp.with_suffix('.meta.json'); state,check,prepared=run_m37.preflight(inp,mp,solver); pre=run_m37.input_identity(inp,mp,solver)
  if not check['pass'] or state.frd_requested() or run_m37.identity_drift(prepared,pre): raise ValueError('preflight failed')
  command=f'cd /mnt/d/my_Works/Gears/v020-closure-run/m37/refinement && export LD_LIBRARY_PATH=/mnt/d/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/runtime/usr/lib/x86_64-linux-gnu:/mnt/d/my_Works/Gears/parallel-v09-2026-10-29/m37/runtime-ccx/root/usr/lib/x86_64-linux-gnu && sha256sum /mnt/d/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23 | grep -q ^{p.SOLVER_HASH} && OMP_NUM_THREADS=1 timeout 120s /mnt/d/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23 {name}'
  r=subprocess.run(['wsl','-d','Ubuntu','--','bash','-lc',command],capture_output=True,timeout=135); inp.with_suffix('.log').write_bytes(r.stdout+r.stderr); post=run_m37.input_identity(inp,mp,solver)
  if r.returncode or run_m37.identity_drift(prepared,post): raise ValueError('solver or identity failed')
  rec,values=reader.strict_record(inp.with_suffix('.dat').read_text(),inp.with_suffix('.sta').read_text(),state.strict_requests(),identity={'run_id':name,'input_sha256':p.sha(inp)},solver_version='2.23',**state.expectation())
  if rec['status']!='accepted': raise ValueError(str(rec['reasons']))
  ex,warn=cases.post_L2(meta,ccx_io.parse_dat(inp.with_suffix('.dat')))
  j={'id':name,'case':'L2','group':'mesh','tags':sp['tags'],'status':'solved','warnings':warn,'h':meta['h'],'mesh':meta['mesh'],'element_types':meta['element_types'],'inp_sha256':p.sha(inp),'dat_sha256':p.sha(inp.with_suffix('.dat')),'step_check':check,'run_identity':{'version':run_m37.IDENTITY_VERSION,'prepared':prepared,'prelaunch':pre,'post':post,'consistent':True},'strict_read':rec,'extracted':ex}
  inp.with_suffix('.record.json').write_text(json.dumps(j,indent=2,ensure_ascii=False),encoding='utf8'); print('OK',name,'YFS',ex['YFS_FE'],flush=True)
 except Exception:
  inp_path=out/(name+'.failure.txt'); inp_path.write_text(traceback.format_exc(),encoding='utf8'); print('FAILED',name,flush=True)
