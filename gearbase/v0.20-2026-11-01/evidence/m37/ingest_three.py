import sys,json,zipfile,platform,os,datetime
from pathlib import Path
root=Path('D:/my_Works/Gears/gearbase-v020-work'); pack=root/'data/m37_fea_pack'; sys.path[:0]=[str(root),str(pack/'scripts')]
from gearmath.tools import fea_ingest as ing, fea_prepare as prep
import run_m37
base=Path('D:/my_Works/Gears/v020-closure-run/m37'); probe=Path('D:/my_Works/Gears/v017-system-run/fea-prepare'); solver=Path('D:/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23'); entries=json.loads((base/'three-level-summary.json').read_text(encoding='utf8')); jobs=[]; attachments={}
for e in entries:
 name=e['id']; d=base/('canonical_d'+name.split('_d')[-1]); meta=json.loads((d/(name+'.meta.json')).read_text(encoding='utf8')); inp=d/(name+'.inp')
 j={'id':name,'case':'L2','group':'mesh','tags':{'point':meta['point']['id'],'level':meta['level']},'status':'solved','warnings':e['warnings'],'h':meta['h'],'inp_sha256':prep.sha(inp),'dat_sha256':prep.sha(inp.with_suffix('.dat')),'step_check':e['step_check'],'run_identity':e['run_identity'],'strict_read':e['strict_read'],'extracted':e['extracted']}
 jobs.append(j)
 for suffix in ('.inp','.meta.json','.dat','.sta','.frd'): attachments[f'runs/L2/{name}{suffix}']=(d/(name+suffix)).read_bytes()
results={'schema':'m37.fea-results/v1','pack_version':run_m37.PACK_VERSION,'generated_utc':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'mode':'full','machine':{'platform':platform.platform(),'cpu_count':os.cpu_count(),'python':platform.python_version(),'gmsh_version':'4.15.2 (source deck metadata)'},'solver':{'path':str(solver),'version':'2.23','version_output':'CalculiX Version 2.23, Copyright(C) 1998-2025 Guido Dhondt','sha256':prep.sha(solver),'threads':1},'coord_supported':True,'total_wall_s':max((base/('canonical_d'+e['id'].split('_d')[-1])/'evidence.json').stat().st_mtime for e in entries)-min((base/('canonical_d'+e['id'].split('_d')[-1])/(e['id']+'.inp')).stat().st_mtime for e in entries),'inputs_sha256':{str(p.relative_to(pack)).replace('\\','/'):prep.sha(p) for folder in ('cases','expected','scripts') for p in (pack/folder).glob('*.py' if folder == 'scripts' else '*.json')},'cases':[],'jobs':jobs,'warnings':['Subset: L2 P01 only; lower ladder levels and other matrix points not run. total_wall_s is estimated from file timestamps, not exact duration.'],'field_read_protocol':run_m37.FIELD_READ_PROTOCOL}
(base/'results-p01.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
with zipfile.ZipFile(base/'p01-raw.zip','w',zipfile.ZIP_DEFLATED) as z:
 z.writestr('results.json',json.dumps(results,ensure_ascii=False,indent=2)); [z.writestr(k,v) for k,v in attachments.items()]
ev=ing.ingest(results,pack,attachments,True,prep.sha(base/'p01-raw.zip'),verified_profile=(probe,solver)); (base/'ingest-p01.json').write_text(json.dumps(ev,ensure_ascii=False,indent=2),encoding='utf8');print('verdict',ev['verdict']); print('checks',[(k,v.get('pass')) for k,v in ev['checks'].items()]);print('ladder',ev.get('summary'));print('P01',[r for r in ev.get('records',[]) if r.get('quantity')=='YFS_root'][:1])
