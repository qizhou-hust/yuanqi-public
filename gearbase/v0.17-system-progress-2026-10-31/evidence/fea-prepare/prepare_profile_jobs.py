import json
from pathlib import Path
from gearmath.tools.fea_prepare import prepare, verify
base=Path('../v017-system-run/fea-prepare')
solver=Path('vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23')
for inp in (base/'jobs_utf8/runs').rglob('*.inp'):
    m=prepare(inp,probe_dir=base,solver_path=solver)
    verify(inp,m,probe_dir=base,solver_path=solver)
    inp.with_suffix('.v017-prepare.json').write_text(json.dumps(m,indent=1,ensure_ascii=False),encoding='utf-8')
    print(inp.name, m['registration'], len(m['registration_problems']))
