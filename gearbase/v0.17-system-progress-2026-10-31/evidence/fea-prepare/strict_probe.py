from pathlib import Path
from gearmath.tools import fea_prepare as P
base=Path('../v017-system-run/fea-prepare')
solver=Path('vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23')
inp=base/'L0_patch_CPE6_h0.inp'
r=P.verified_profile(base,solver)
st,report=P.deck_state.check_file(inp)
result=r.read_strict(inp.with_suffix('.dat').read_text(),inp.with_suffix('.sta').read_text(),st.strict_requests(),identity={'run_id':inp.stem,'input_sha256':P.sha(inp)},solver_version='2.23',**st.expectation())
print(result['record']['status'])
for f in result['record']['fields']:
    print(f['id'],f['coverage_observed'])
