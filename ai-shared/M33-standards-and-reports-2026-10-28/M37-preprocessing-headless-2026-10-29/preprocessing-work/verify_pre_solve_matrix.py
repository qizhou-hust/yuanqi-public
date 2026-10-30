"""Run known negative and corrected positive fixtures, without invoking ccx."""
from pathlib import Path
import json
from check_before_solve import check
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent
rows=[]
for scope,folder in [('original','m37-results'),('periodic','m37-l3-periodic-diagnostic')]:
    for phase in range(16):
        path=BASE/folder/'runs/L3'/f'L3_C001_G1_ph{phase:02d}_d12.inp'
        result=check(path);expected=scope=='periodic' or phase>=10
        rows.append({'scope':scope,'phase':phase,'expected_ready':expected,'matches_expectation':result['ready_for_diagnostic_solve']==expected,'result':result})
        print(scope,phase,result['ready_for_diagnostic_solve'],result['supported_profile_errors'],flush=True)
out={'schema':'m37.pre-solve-regression/v1','all_match_expectations':all(r['matches_expectation'] for r in rows),'cases':rows,'accepted':False}
(ROOT/'pre-solve-matrix.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
assert out['all_match_expectations']
