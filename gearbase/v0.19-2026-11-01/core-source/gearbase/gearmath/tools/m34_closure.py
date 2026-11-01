"""Fresh M34 evidence: archived Stage0 baseline versus same-problem H2 pruning.

Run: python -m gearmath.tools.m34_closure --out output/m34/closure
Archived files are imported read-only under an isolated package name.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import inspect
import json
import math
from pathlib import Path
import sys
import types
import tempfile
from datetime import datetime, timezone

from ..gear import h2_flagship as H2

ROOT = Path(__file__).resolve().parents[2]


def _reference():
    package = '_m34_archived_reference'
    directory = ROOT/'archive/m31/src/gears'
    if package not in sys.modules:
        module = types.ModuleType(package)
        module.__path__ = [str(directory)]
        sys.modules[package] = module
    name = package+'.solver'
    spec = importlib.util.spec_from_file_location(name,directory/'solver.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signature(c):
    return list(H2.stage0_rank(c))


def compare_h2(ratio_splits=None):
    old = _reference()
    domains, verifier_calls, pair_calls = [], 0, 0
    original_space, original_verifier = old._helical_design_space, old.enumerate_helical_options
    def capture(*args):
        result = original_space(*args)
        domains.append(sorted(result[0]))
        return result
    def verifier(*args, **kwargs):
        nonlocal verifier_calls
        verifier_calls += 1
        return original_verifier(*args, **kwargs)
    old._helical_design_space, old.enumerate_helical_options = capture, verifier
    lines, start = inspect.getsourcelines(old.synthesize_h2)
    evaluation_line = start+next(i for i,line in enumerate(lines) if 'i_total = one[' in line)
    def trace(frame,event,arg):
        nonlocal pair_calls
        if frame.f_code is old.synthesize_h2.__code__ and event == 'line' and frame.f_lineno == evaluation_line:
            pair_calls += 1
        return trace
    previous_trace = sys.gettrace()
    try:
        sys.settrace(trace)
        baseline = old.synthesize_h2(80.,100.,10.,(2.,2.5,3.),ratio_splits=ratio_splits,beta_range=(8.,30.))
    finally:
        sys.settrace(previous_trace)
    new = H2.search_seed_domain(ratio_splits=ratio_splits)
    strict = all(H2.verify_stage0_geometry(candidate,80.,100.,10.,(8.,30.),.03)
                 for candidate in new['candidates'])
    old_candidates = [signature(c) for c in baseline['candidates']]
    new_candidates = [signature(c) for c in new['candidates']]
    return dict(same_candidates=old_candidates == new_candidates,
                same_stage_domain=domains == new['stage_domains'],
                strict_independent_checks=bool(strict and new['candidates']),
                old_pair_evaluations=pair_calls, old_verifier_calls=verifier_calls,
                old_reported_pairs=baseline['search']['pairs_examined'],
                new_pair_evaluations=new['pair_evaluations'],
                pair_boxes_rejected=new['pair_boxes_rejected'],
                feasible_old=baseline['search']['feasible'], feasible_new=new['feasible'],
                old_candidates=old_candidates,new_candidates=new_candidates,
                first_assignment={f'stage{i}':{k:new['candidates'][0][f'stage{i}'][k]
                                             for k in ('mn_mm','z1','z2','beta_deg')} for i in (1,2)},
                reference_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (ROOT/'archive/m31/src/gears/solver.py',ROOT/'archive/m31/src/gears/verifiers.py')})


def gradient_matrix():
    from ..gear import factor_recompute as FR, source_optimize as SO
    rows = json.loads((ROOT/'tests/theta_iteration_forward_baseline.json').read_text(encoding='utf-8'))
    evidence = []
    for row in rows:
        ev = SO.SourceEvaluator(FR.load_doc(row['document']),SO.load_declaration(row['declaration']))
        x = row['x']
        names = [n for n,v in ev.vars.items() if v['kind']=='continuous']
        ad = ev.point(x,wrt=names)
        worst, count = 0., 0
        for name in names:
            h = 1e-6*max(1,abs(x[name]))
            up, dn = dict(x),dict(x)
            up[name] += h
            dn[name] -= h
            vu, vd = ev.point(up)['values'],ev.point(dn)['values']
            for q in ad['values']:
                exact = ad['derivatives'][q][name]
                fd = (vu[q]-vd[q])/(2*h)
                worst = max(worst,abs(exact-fd)/max(1,abs(exact),abs(fd)))
                count += 1
        evidence.append(dict(case=row['case'],point=row['point'],comparisons=count,
                             max_scaled_error=worst,passed=worst <= 1e-6))
    return evidence


def ownership_checks():
    """Exercise both public append backends, not a document inventory."""
    from . import design_store as DS
    from ..gear import math_source as MS
    checks = []
    with tempfile.TemporaryDirectory() as directory:
        for store in (DS.MemoryStore(),DS.FileStore(directory)):
            DS.commit_source(store,'owned',MS.load_file(),'M34 acceptance')
            before = store.head('owned')
            record = DS.make_record('owned',before,{'baseline':'none','params':{}},None,{},[],None)
            rejected = False
            try:
                store.append('owned',record)
            except DS.SourceOwnershipError:
                rejected = True
            checks.append(dict(backend=store.mode,projection_only_write_rejected=rejected,
                               state_unchanged=store.head('owned')==before))
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=ROOT/'output/m34/closure')
    args = parser.parse_args()
    report = dict(generated_at=datetime.now(timezone.utc).isoformat(),
                  h2=compare_h2(),gradient_matrix=gradient_matrix(),source_ownership=ownership_checks())
    a = H2.search_seed_domain(mn_series=(2.,),ratio_splits=[2.5,4.],prune=True)
    b = H2.search_seed_domain(mn_series=(2.,),ratio_splits=[2.5,4.],prune=False)
    report['small_domain'] = dict(same_candidates=a['candidates']==b['candidates'],
                                exhaustive_evaluations=b['pair_evaluations'],pruned_evaluations=a['pair_evaluations'])
    h2 = report['h2']
    report['passed'] = (h2['same_candidates'] and h2['same_stage_domain'] and h2['strict_independent_checks']
                        and h2['new_pair_evaluations'] < h2['old_pair_evaluations']
                        and report['small_domain']['same_candidates'] and all(r['passed'] for r in report['gradient_matrix'])
                        and all(r['projection_only_write_rejected'] and r['state_unchanged'] for r in report['source_ownership']))
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'closure.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='h2'}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
