"""Run unchanged M31 tests in a staged tree with kernel-backed shims."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / 'archive' / 'm31'
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from gearmath.tools.m31_runtime import prepare_stage, stage_environment

def inventory():
    return sorted(str(p.relative_to(ARCHIVE)) for d in ('tests', 'cadbench_tests') for p in (ARCHIVE / d).rglob('test_*.py'))

def gate_counts(counts):
    return (counts['collected'] >= 636 and counts['passed'] == counts['collected']
            and counts['skipped'] == counts['failed'] == counts['errors'] == 0)

def pytest_sessionfinish(session, exitstatus):
    result_path = os.environ.get('M31_PYTEST_COUNTS')
    if not result_path:
        return
    stats = session.config.pluginmanager.getplugin('terminalreporter').stats
    counts = {'collected':session.testscollected, 'passed':len(stats.get('passed',[])),
              'skipped':len(stats.get('skipped',[]))+len(stats.get('xfailed',[])),
              'failed':len(stats.get('failed',[]))+len(stats.get('xpassed',[])),
              'errors':len(stats.get('error',[]))}
    Path(result_path).write_text(json.dumps(counts), encoding='utf-8')
    if not gate_counts(counts): session.exitstatus = 1

def _run():
    files = inventory()
    if len(files) != 73:
        return {'status':'invalid_inventory', 'test_modules':len(files), 'expected_modules':73, 'exit_code':1}
    with tempfile.TemporaryDirectory(prefix='m31-regression-') as temp:
        stage = Path(temp)
        stage_report = prepare_stage(stage, ROOT)
        env = stage_environment(stage)
        env['M31_PYTEST_COUNTS'] = str(stage / 'pytest-counts.json')
        result = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'gearmath.tools.m31_regression', '-q', '--continue-on-collection-errors', 'tests', 'cadbench_tests'], cwd=stage, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        log = stage / 'provenance.jsonl'
        provenance = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
        alias_events = [row for row in provenance if row.get('event') == 'alias_import']
        adapter_root = (stage/'src'/'gearmath'/'compat'/'m31').resolve()
        kernel_root = (stage/'src'/'gearmath'/'kernel').resolve()
        invalid = [row for row in alias_events if not Path(row['adapter_file']).resolve().is_relative_to(adapter_root) or not all(Path(p).resolve().is_relative_to(kernel_root) for p in row['kernel_files'])]
        if set(row['alias'] for row in alias_events) != {'cadbench.math_calculator','cadbench.math_optimizer','gears.graph'}: invalid.append({'error':'missing alias provenance'})
        numeric_events = [row for row in provenance if row.get('event') == 'numeric_profile']
        if not numeric_events:
            invalid.append({'error':'missing actual deterministic numerical profile provenance'})
        for row in numeric_events:
            if (row.get('profile_id') != 'binary64-ordered-fma-v1'
                    or row.get('backend') not in {'math.fma', 'stdlib.Fraction-single-rounding'}
                    or Path(row.get('kernel_file','')).resolve() != kernel_root / 'floating.py'):
                invalid.append({'error':'invalid deterministic numerical profile provenance','event':row})
        counts_path = stage / 'pytest-counts.json'
        counts = json.loads(counts_path.read_text(encoding='utf-8')) if counts_path.exists() else None
        ok = result.returncode == 0 and bool(provenance) and not invalid and counts is not None and gate_counts(counts)
        return {'status':'passed' if ok else 'failed', 'test_modules':len(files), 'exit_code':result.returncode or (0 if ok else 1), 'source_integrity':stage_report['source_integrity'], 'counts':counts, 'provenance':provenance, 'invalid_provenance':invalid, 'output':result.stdout + result.stderr}


def run():
    try:
        return _run()
    except Exception as exc:
        return {'status':'error', 'exit_code':1, 'error':f'{type(exc).__name__}: {exc}'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = run()
    print(json.dumps(result, ensure_ascii=False) if args.json else result.get('output', str(result)))
    return result['exit_code'] or (0 if result['status']=='passed' else 1)

if __name__ == '__main__':
    sys.exit(main())
