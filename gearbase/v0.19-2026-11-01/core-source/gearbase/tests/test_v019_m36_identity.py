import hashlib, pathlib, shutil, tempfile, unittest
from gearmath.gear.math_source import verify_certificates
from gearmath.tools.m36_identity import implementation_sha256

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ScopedIdentityTests(unittest.TestCase):
    def test_relevant_unrelated_and_dynamic_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            shutil.copytree(ROOT / 'gearmath', root / 'gearmath', ignore=shutil.ignore_patterns('__pycache__'))
            for name in ('data/source/gears.math-source-2.schema.json', 'data/schema/gears.system-input-1.schema.json', 'data/schema/gears.design-check-result-1.schema.json', 'data/registry/formulas-v1.json'):
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, dest)
            baseline = implementation_sha256(root)
            unrelated = root / 'gearmath' / 'tools' / 'fea_prepare.py'
            unrelated.write_bytes(unrelated.read_bytes() + b'\n# unrelated\n')
            self.assertEqual(baseline, implementation_sha256(root))
            relevant = root / 'gearmath' / 'tools' / 'system_closure.py'
            new_dep = root / 'gearmath' / 'gear' / 'profile_added.py'
            new_dep.write_text('VALUE = 1\n', encoding='utf-8')
            relevant.write_bytes(relevant.read_bytes() + b'\nfrom gearmath.gear import profile_added\n')
            added = implementation_sha256(root)
            self.assertNotEqual(baseline, added)
            new_dep.write_text('VALUE = 2\n', encoding='utf-8')
            self.assertNotEqual(added, implementation_sha256(root))
            relevant.write_bytes(relevant.read_bytes() + b'\n# relevant\n')
            self.assertNotEqual(baseline, implementation_sha256(root))
            relevant.write_bytes(relevant.read_bytes() + b'\n__import__("anything")\n')
            with self.assertRaises(ValueError): implementation_sha256(root)

    def test_certificate_missing_and_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'certificate'
            path.write_bytes(b'approved')
            doc = {'evidence': {'x': {'certificate': {'kind': 'file', 'ref': 'certificate', 'sha256': hashlib.sha256(b'approved').hexdigest()}}}}
            self.assertEqual([], verify_certificates(doc, root=tmp))
            path.write_bytes(b'tampered')
            self.assertEqual('certificate_hash', verify_certificates(doc, root=tmp)[0]['code'])
            path.unlink()
            self.assertEqual('certificate_missing', verify_certificates(doc, root=tmp)[0]['code'])
