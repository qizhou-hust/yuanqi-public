import csv, hashlib, json, sys
from pathlib import Path
base = Path('D:/my_Works/Gears/parallel-v09-2026-10-29/m33-return/variants')
rows = []
for case, variant in [(7, 'ex7-base-native'), (8, 'ex8-Rz2.3')]:
    path = base / variant / 'v09-original-table.csv'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for r in csv.DictReader(stream):
            if r['stage'] == 'geometry' and r['numeric_within_limit'] == 'False':
                ref, value = float(r['kisssoft']), float(r['v09'])
                err = abs(value-ref)/abs(ref)
                assert abs(err-float(r['relative_error'])) < 1e-14
                rows.append(dict(case=case, variant=variant, row=r['model_quantity'], model=value, reference=ref, unit=r['unit'], error=err, source=str(path), sha256=digest, template_row=r['template_row']))
assert len([r for r in rows if r['case']==7]) == 2
assert len([r for r in rows if r['case']==8]) == 6
assert all(1e-6 < r['error'] < .01 for r in rows)
result = dict(status='BLOCKED_ORIGINAL_GATE_IDENTITY', original_user_gate_identified=False, original_six=[], diagnostic_rows=rows, reason='No source establishes that these diagnostic rows are the six from the user independent gate; counts differ.', strict_diagnostic_limit=1e-6, milestone_limit=.01)
Path(__file__).with_name('gate-evidence.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
print('BLOCKED: original gate identity unavailable; diagnostic 2 + 6 rows verified, not substituted')
sys.exit(2)
