"""Verify all four downloaded release archives against CATALOG.json (stdlib only)."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory', type=Path, nargs='?', default=Path.cwd())
parser.add_argument('--catalog', type=Path, default=Path(__file__).with_name('CATALOG.json'))
args = parser.parse_args()
catalog = json.loads(args.catalog.read_text(encoding='utf-8-sig'))
packages = catalog['packages']
if len(packages) != 4 or len({r['asset_name'] for r in packages}) != 4:
    raise SystemExit('FAIL: expected four distinct packages in catalog')
failures = 0
for row in packages:
    names = (row['asset_name'], row['filename'])
    if any(Path(n).name != n or n in ('.', '..') for n in names):
        raise SystemExit('FAIL: unsafe catalog filename')
    path = next((args.directory / n for n in names if (args.directory / n).is_file()), None)
    if path is None:
        print('MISSING', row['asset_name'])
        failures += 1
        continue
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    ok = path.stat().st_size == row['bytes'] and digest == row['sha256']
    print('PASS' if ok else 'FAIL', path.name, digest)
    failures += not ok
raise SystemExit(1 if failures else 0)
