"""Prepare a bound case without invoking a solver."""
from pathlib import Path
from .contracts import digest, eligible, rule, sha256
from .theory import precalculate

def native_check(spec):
    native=spec.get('native',{})
    if native.get('profile')!='m37_l3':
        return {'checks':[rule('native_profile','UNKNOWN','No supported native adapter; theory alone cannot authorize a solve')],'files':[]}
    from .adapters.m37 import check
    return check(spec)

def prepare(spec):
    checks=[rule('case_id','PASS' if isinstance(spec.get('case_id'),str) and spec['case_id'].strip() else 'FAIL','Explicit case identity'),
            rule('units','PASS' if spec.get('units')=='N-mm-MPa' else 'FAIL','Supported unit system is N-mm-MPa; torque_Nm fields convert explicitly')]
    theory={};native={};files=[]
    try:
        theory=precalculate(spec['theory'])
        checks.append(rule('analytical_domain','PASS','Transparent estimate computed; physical applicability remains a separate comparison requirement'))
    except (ValueError,KeyError,TypeError,OverflowError,ZeroDivisionError) as e:
        checks.append(rule('analytical_domain','FAIL',str(e)))
    try:
        native=native_check(spec);checks.extend(native['checks']);files=native['files']
    except Exception as e:
        checks.append(rule('native_profile','UNKNOWN',f'{type(e).__name__}: {e}'))
    identity=None
    try:
        # Bind own implementation as well as native dependencies and model inputs.
        package=Path(__file__).parent
        code={str(p.relative_to(package)):sha256(p) for p in sorted(package.rglob('*')) if p.suffix in {'.py','.json'}}
        identity={'case_sha256':digest(spec),'code':code,'files':{str(Path(p).resolve()):sha256(p) for p in files}}
        identity['binding_sha256']=digest(identity)
    except (OSError,ValueError,TypeError) as e:
        checks.append(rule('input_identity','FAIL',str(e)))
    return {'schema':'fea-readiness.prepare/0.1','case_id':spec.get('case_id'),'checks':checks,'theory':theory,
            'native':native,'identity':identity,'ready_for_diagnostic_solve':identity is not None and eligible(checks),
            'engineering_accepted':False,'scope':'Enumerated diagnostic checks only; not complete engineering validation'}
