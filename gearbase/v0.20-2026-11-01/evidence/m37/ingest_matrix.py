import sys,json,zipfile,platform,os,datetime,re
from pathlib import Path
root=Path('D:/my_Works/Gears/gearbase-v020-work'); pack=root/'data/m37_fea_pack'; sys.path[:0]=[str(root),str(pack/'scripts')]
from gearmath.tools import fea_ingest as ing, fea_prepare as prep
import run_m37
base=Path('D:/my_Works/Gears/v020-closure-run/m37'); d=base/'matrix'; solver=Path('D:/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23'); probe=Path('D:/my_Works/Gears/v017-system-run/fea-prepare'); jobs=[json.loads(p.read_text(encoding='utf8')) for p in sorted(d.glob('*.record.json'))]; attachments={}
for j in jobs:
 name=j['id']
 for suffix in ('.inp','.meta.json','.dat','.sta','.frd','.log'): attachments[f'runs/L2/{name}{suffix}']=(d/(name+suffix)).read_bytes()
inputs={str(p.relative_to(pack)).replace('\\','/'):prep.sha(p) for folder in ('cases','expected','scripts') for p in (pack/folder).glob('*.py' if folder=='scripts' else '*.json')}
results={'schema':'m37.fea-results/v1','pack_version':run_m37.PACK_VERSION,'generated_utc':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'mode':'full','machine':{'platform':platform.platform(),'cpu_count':os.cpu_count(),'python':platform.python_version(),'gmsh_version':'4.15.2'},'solver':{'path':str(solver),'version':'2.23','version_output':'CalculiX Version 2.23, Copyright(C) 1998-2025 Guido Dhondt','sha256':prep.sha(solver),'threads':1},'coord_supported':True,'total_wall_s':max((d/(j['id']+'.record.json')).stat().st_mtime for j in jobs)-min((d/(j['id']+'.inp')).stat().st_mtime for j in jobs),'inputs_sha256':inputs,'cases':[],'jobs':jobs,'warnings':['All available canonical L2 jobs; L0 and L1 not run. total_wall_s is elapsed interval estimated from file timestamps, not exact duration.'],'field_read_protocol':run_m37.FIELD_READ_PROTOCOL}
with zipfile.ZipFile(base/'matrix-raw.zip','w',zipfile.ZIP_DEFLATED) as z:
 z.writestr('results.json',json.dumps(results,ensure_ascii=False,indent=2)); [z.writestr(k,v) for k,v in attachments.items()]
ev=ing.ingest(results,pack,attachments,True,prep.sha(base/'matrix-raw.zip'),verified_profile=(probe,solver)); (base/'ingest-matrix.json').write_text(json.dumps(ev,ensure_ascii=False,indent=2),encoding='utf8'); print('jobs',len(jobs),'verdict',ev['verdict'],'ladder',ev.get('summary'));print('L2',json.dumps(ev.get('ladder',{}).get('L2',{}),ensure_ascii=True));print('checks',[(k,v.get('pass')) for k,v in ev['checks'].items()])
