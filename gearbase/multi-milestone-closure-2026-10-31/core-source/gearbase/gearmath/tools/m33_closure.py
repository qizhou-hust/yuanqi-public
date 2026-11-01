"""Reproducible M33 prototype inventory and C001 iteration diagnosis.

The nine-iteration model is diagnostic only: production formulas and tolerances
are untouched. This does not award TR30 E4 or product acceptance.
"""
import copy
import json
import math
from dataclasses import replace
from pathlib import Path

from gearmath.gear import factor_recompute as FR
from gearmath.gear.factor_methods import K01_FULL_FACTOR_SELECTORS
from gearmath.gear.kisssoft_case import build_model
from gearmath.gear.m31_case import RECEIPT_EVIDENCE, stage_model
from gearmath.tools.benchmarks import _RECEIPT


def prototype_inventory(remove_formula=None):
    model, _ = build_model(factor_selectors=K01_FULL_FACTOR_SELECTORS)
    names = ['K_A', *RECEIPT_EVIDENCE]
    evaluated = model.evaluate([n for n in RECEIPT_EVIDENCE if n not in ('Y_ST', remove_formula)])
    rows = []
    for name in names:
        f = None if name == remove_formula else model.formulas.get(name)
        exception = name in ('K_A', 'Y_ST')
        rows.append({'quantity': name, 'baseline': 'case input' if name == 'K_A' else list(RECEIPT_EVIDENCE[name]),
                     'status': 'input_exception' if exception else ('formula' if f else 'missing'),
                     'formula_id': f.id if f else None, 'reference': f.ref if f else None,
                     'evaluated_value': evaluated.values.get(name) if f else None})
    missing = [r['quantity'] for r in rows if r['status'] == 'missing']
    count = sum(r['status'] == 'formula' for r in rows)
    return {'source': 'gearmath.gear.m31_case.RECEIPT_EVIDENCE plus K_A; docs/分路设计报告/L2-formula-library.md table',
            'rows': rows, 'exceptions': ['K_A', 'Y_ST'], 'formula_count': count,
            'missing': missing, 'evaluation_status': evaluated.status,
            'passed': len(rows) == 22 and count >= 20 and not missing and evaluated.status == 'ok'}


def c001_comparison():
    model = FR.build_model(FR.load_doc('C001.factors'), 'pair_model')
    _, receipt = stage_model()
    targets = list(_RECEIPT)
    intermediate = [f'{x}_{i}' for i in (1, 2) for x in ('G', 'zn', 'H', 'theta', 'sFn', 'rhoF', 'hFe')]
    current = model.evaluate(targets + intermediate)
    if current.status != 'ok':
        raise RuntimeError(str(current.errors))
    diagnostic = copy.deepcopy(model)
    theta = []
    for i in (1, 2):
        g, zn, h = (current.values[f'{x}_{i}'] for x in ('G', 'zn', 'H'))
        x = math.pi / 6
        for _ in range(9):
            x = 2 * g / zn * math.tan(x) - h
        name = f'theta_{i}'
        old = diagnostic.formulas[name]
        f = replace(old, kind='explicit', expr=f'{x!r}*rad')
        diagnostic.formulas[name] = f
        diagnostic._exprs[name] = f.compiled()
        theta.append({'member': i, 'G': g, 'zn': zn, 'H': h, 'current': current.values[name], 'vendor_nine': x})
    legacy = diagnostic.evaluate(targets + intermediate)
    if legacy.status != 'ok':
        raise RuntimeError(str(legacy.errors))
    rows = []
    for name, (section, key) in _RECEIPT.items():
        ref = receipt[section][key]
        actual = current.values[name]
        approx = legacy.values[name]
        rows.append({'quantity': name, 'm31': ref, 'new': actual, 'delta': actual-ref,
                     'nine_iteration': approx, 'nine_minus_m31': approx-ref,
                     'cause': ('root theta iteration: vendor nine steps vs converged fixed point'
                               if name.startswith(('Y_F_', 'Y_S_', 'sigma_F_', 'S_F_'))
                               else 'same chain; floating point evaluation order')})
    # Independent receipt comparison, not a new acceptance tolerance: diagnostic
    # reconstruction must be at numerical precision, not a rounded reference.
    ok = all(math.isclose(r['nine_iteration'], r['m31'], rel_tol=1e-12, abs_tol=1e-12) for r in rows)
    return {'status': current.status, 'model_sha256': current.model_sha256, 'theta': theta,
            'intermediates': {k: {'new': current.values[k], 'nine_iteration': legacy.values[k]} for k in intermediate},
            'rows': rows, 'iteration_reproduction_passed': ok,
            'vendor_source': 'vendor/cad/vendor/python_gearbox_py/src/gearbox/standards/iso6336/bending.py::_tooth_root_geometry',
            'limits': 'C001.factors retains explicitly declared evidence factors and physical assumptions; no TR30 acceptance implied.'}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    args = p.parse_args()
    report = {'prototype22': prototype_inventory(), 'c001': c001_comparison()}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'prototype20': report['prototype22']['passed'], 'formula_count': report['prototype22']['formula_count'],
                      'c001_iteration_reproduction': report['c001']['iteration_reproduction_passed']}))
    return 0 if report['prototype22']['passed'] and report['c001']['iteration_reproduction_passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
