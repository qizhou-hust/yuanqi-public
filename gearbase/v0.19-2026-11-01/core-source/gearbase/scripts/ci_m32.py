"""Isolated UTF-8 M32 acceptance runner (stdlib gates; pytest for old regression); never installs/runs solvers."""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def commands():
    prefix = [sys.executable, '-X', 'utf8', '-I']
    load = "import sys,unittest;sys.path.insert(0,'.');s=unittest.defaultTestLoader.loadTestsFromNames({names!r});r=unittest.TextTestRunner(verbosity=2).run(s);sys.exit(not r.wasSuccessful())"
    def tests(*names):
        return prefix + ['-c', load.format(names=list(names))]
    return {
        'architecture': prefix + ['gearmath/tools/architecture_guard.py', '--json'],
        'negative-proof': prefix + ['tests/test_m32_architecture_guard.py'],
        'prototype21': tests('tests.test_gearmath'),
        'adapter-regression': prefix + ['gearmath/tools/m31_regression.py', '--json'],
        'dimensions': tests('tests.test_inputs_editions', 'tests.test_kernel_ext', 'tests.test_registry'),
        'units': prefix + ['-c', "import sys,unittest;sys.path.insert(0,'.');s=unittest.defaultTestLoader.discover('tests',top_level_dir='.');r=unittest.TextTestRunner(verbosity=2).run(s);sys.exit(not r.wasSuccessful())"],
    }


def _valid_numeric_profiles(provenance):
    if not isinstance(provenance,list) or not all(isinstance(row,dict) for row in provenance):
        return False
    events=[row for row in provenance if row.get('event')=='numeric_profile']
    if not events:
        return False
    for row in events:
        filename=row.get('kernel_file')
        if not isinstance(filename,str) or not filename:
            return False
        path=pathlib.Path(filename)
        if (row.get('profile_id')!='binary64-ordered-fma-v1'
                or row.get('backend') not in {'math.fma','stdlib.Fraction-single-rounding'}
                or type(row.get('pid')) is not int or row['pid']<=0
                or not path.is_absolute() or path.parts[-4:]!=('src','gearmath','kernel','floating.py')):
            return False
    return True


def valid_report(gate, report):
    """A zero exit status alone cannot prove a JSON-producing acceptance gate."""
    if not isinstance(report, dict):
        return False
    if gate == 'architecture':
        return (report.get('schema') == 'gearbase.architecture-gate/1'
                and report.get('passed') is True
                and type(report.get('files_checked')) is int and report['files_checked'] > 0
                and report.get('violations') == [])
    if gate == 'adapter-regression':
        counts, integrity = report.get('counts'), report.get('source_integrity')
        if not isinstance(counts, dict) or not isinstance(integrity, dict):
            return False
        keys = ('collected', 'passed', 'skipped', 'failed', 'errors')
        return (all(type(counts.get(k)) is int for k in keys)
                and counts['collected'] >= 636 and counts['passed'] == counts['collected']
                and counts['skipped'] == counts['failed'] == counts['errors'] == 0
                and report.get('status') == 'passed' and type(report.get('exit_code')) is int and report['exit_code'] == 0
                and report.get('test_modules') == integrity.get('test_modules') == 73
                and integrity.get('mismatches') == []
                and _valid_numeric_profiles(report.get('provenance'))
                and report.get('invalid_provenance') == [] and isinstance(report.get('output'), str))
    return False


def compile_all():
    failures = []
    paths = sorted(p for p in ROOT.rglob('*.py') if not any(x in {'.git', '__pycache__', '.venv', '.m32-ci'} for x in p.relative_to(ROOT).parts))
    for p in paths:
        try:
            compile(p.read_text(encoding='utf-8-sig'), str(p), 'exec')
        except (SyntaxError, UnicodeError) as exc:
            failures.append({'path': p.relative_to(ROOT).as_posix(), 'error': str(exc)})
    return {'passed': not failures, 'files_checked': len(paths), 'failures': failures}


def negative_proof():
    """Launch real guard processes on independent sabotage trees and a generic control."""
    cases = {
        'geometry': ('product/bad.py', 'def f(m_n,z1):\n return m_n*z1\n', 1),
        'strength': ('tools/bad.py', 'sigma_H = Z_H*(F_t/(b*d_1))**0.5\n', 1),
        'optimizer': ('kernel/new_optimizer.py', 'def f(teeth):\n return teeth*2\n', 1),
        'generic': ('kernel/new_optimizer.py', 'def f(x,y):\n return (x*x+y*y)**0.5\n', 0),
    }
    results = []
    for name, (path, source, expected) in cases.items():
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / 'gearmath' / path
            p.parent.mkdir(parents=True)
            p.write_text(source, encoding='utf-8')
            cmd = [sys.executable, '-X', 'utf8', '-I', str(ROOT / 'gearmath/tools/architecture_guard.py'), '--root', td, '--json']
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=60)
            report = json.loads(r.stdout)
            results.append({'case': name, 'exit_code': r.returncode, 'expected_exit_code': expected, 'passed': r.returncode == expected and report['passed'] == (expected == 0), 'report': report})
    return {'passed': all(r['passed'] for r in results), 'cases': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate', choices=['all', 'stdlib', 'compile', *commands()], default='all')
    parser.add_argument('--out', type=pathlib.Path, default=ROOT / 'output/m32-ci')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    selected = ['compile', *commands()] if args.gate in {'all', 'stdlib'} else [args.gate]
    if args.gate == 'stdlib':
        selected.remove('adapter-regression')
    for name in selected:
        start = time.monotonic()
        print(f'Running {name}', flush=True)
        try:
            if name == 'compile':
                row = compile_all()
            elif name == 'negative-proof':
                row = negative_proof()
                # Unit fixtures exercise additional relative imports, DSL and positives.
                r = subprocess.run(commands()[name], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=300)
                row['fixture_exit_code'] = r.returncode
                row['passed'] &= r.returncode == 0
                (args.out / (name + '.log')).write_text(r.stdout + r.stderr, encoding='utf-8')
            else:
                env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
                r = subprocess.run(commands()[name], cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', timeout=1800)
                (args.out / (name + '.log')).write_text(r.stdout + r.stderr, encoding='utf-8')
                row = {'passed': r.returncode == 0, 'exit_code': r.returncode, 'command': commands()[name]}
                if name in {'architecture', 'adapter-regression'}:
                    try:
                        row['report'] = json.loads(r.stdout)
                        if not valid_report(name, row['report']):
                            row['passed'] = False
                            row['error'] = 'incomplete or unsuccessful gate report'
                    except json.JSONDecodeError:
                        row['passed'] = False
                        row['error'] = 'expected machine-readable JSON stdout'
        except Exception as exc:
            row = {'passed': False, 'error': f'{type(exc).__name__}: {exc}'}
        row.update(gate=name, seconds=round(time.monotonic() - start, 3))
        reports.append(row)
        (args.out / (name + '.json')).write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{name}: {'PASS' if row['passed'] else 'FAIL'}", flush=True)
    report = {'schema': 'gearbase.m32-ci/1', 'passed': all(r['passed'] for r in reports), 'gates': reports}
    (args.out / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
