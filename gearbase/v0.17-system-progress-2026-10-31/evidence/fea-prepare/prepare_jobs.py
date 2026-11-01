import json
from pathlib import Path
from gearmath.tools.fea_prepare import prepare, verify
base=Path('../v017-system-run/fea-prepare/jobs_utf8/runs')
for inp in base.rglob('*.inp'):
    m=prepare(inp); verify(inp,m)
    inp.with_suffix('.prepare.json').write_text(json.dumps(m,indent=1,ensure_ascii=False),encoding='utf-8')
    print(inp.name, m['registration'], len(m['registration_problems']))
