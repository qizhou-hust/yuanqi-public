import json,sys
from pathlib import Path
root=Path('D:/my_Works/Gears/gearbase-v020-work');sys.path.insert(0,str(root));from gearmath.tools import fea_ingest as i
base=Path('D:/my_Works/Gears/v020-closure-run/m37');pack=root/'data/m37_fea_pack';probe=Path('D:/my_Works/Gears/v017-system-run/fea-prepare');solver=Path('D:/my_Works/Gears/gearbase-v0.8-work/gearbase/vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23')
for stem,out in [('p01-raw.zip','ingest-p01.json'),('matrix-raw.zip','ingest-matrix.json')]:
 results,attachments,sha=i.load_results(base/stem);ev=i.ingest(results,pack,attachments,True,sha,verified_profile=(probe,solver));(base/out).write_text(json.dumps(ev,ensure_ascii=False,indent=2),encoding='utf8');print(stem,ev['verdict'],ev['checks']['strict_repost']['pass'])
