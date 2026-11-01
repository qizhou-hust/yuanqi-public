import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('data/m37_fea_pack/scripts').resolve()))
import study
pack=Path('data/m37_fea_pack')
case=json.loads((pack/'cases/L3_C001_G1.json').read_text(encoding='utf-8'))
exp=json.loads((pack/'expected/L3_C001_G1.json').read_text(encoding='utf-8'))
wd=Path('../v017-system-run/fea-prepare/jobs_utf8/runs/L3').resolve()
jobs=study.jobs_L3(case, exp, wd, {'coord':True}, {'mortar':False})
job=next(j for j in jobs if j['tags'].get('phase') == 10)
print(job['id'], flush=True)
job['build']()
