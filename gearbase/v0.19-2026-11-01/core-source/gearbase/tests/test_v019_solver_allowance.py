"""A11: exact-byte origin allowance; this verifier never executes a solver."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gearmath.tools import solver_allowance as S


class SolverAllowanceTests(unittest.TestCase):
    def test_recorded_origin_is_exact_and_not_fea_acceptance(self):
        record = S.record()
        self.assertEqual(record['solver_id'], 'calculix-ccx-2.23-linux-x86_64')
        self.assertEqual(record['executable_sha256'], S.BINARY_SHA256)
        self.assertEqual(record['archive_sha256'], S.ARCHIVE_SHA256)
        self.assertEqual(record['numerical_gear_qualification'], 'not_granted')
        self.assertFalse(record['origin_proof']['executed_during_origin_verification'])

    def test_wrong_binary_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'solver'; p.write_bytes(b'not an approved executable')
            with self.assertRaisesRegex(ValueError, 'binary hash'):
                S.verify(p)

    def test_hash_match_permits_only_the_registered_binary(self):
        real_sha = S._sha
        with patch.object(S, '_sha', side_effect=lambda p: S.BINARY_SHA256 if str(p) == 'never-executed' else real_sha(p)):
            r = S.verify('never-executed')
        self.assertTrue(r['allowed'])
        self.assertFalse(r['archive_rechecked'])
        self.assertFalse(r['solver_executed'])
        self.assertEqual(r['numerical_gear_qualification'], 'not_granted')

    def test_registry_and_proof_tamper_block(self):
        original = S.REGISTRY
        root = original.parent
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for p in root.iterdir():
                if p.is_file(): (base / p.name).write_bytes(p.read_bytes())
            reg = base / original.name
            with patch.object(S, 'REGISTRY', reg):
                self.assertEqual(S.record()['executable_sha256'], S.BINARY_SHA256)
                obj = json.loads(reg.read_text(encoding='utf8'))
                changed = copy.deepcopy(obj); changed['executable_sha256'] = '0' * 64
                reg.write_text(json.dumps(changed), encoding='utf8')
                with self.assertRaisesRegex(ValueError, 'identity'):
                    S.record()
                reg.write_text(json.dumps(obj), encoding='utf8')
                proof = base / obj['origin_proof_file']
                proof.write_bytes(proof.read_bytes() + b' ')
                with self.assertRaisesRegex(ValueError, 'proof hash'):
                    S.record()

    def test_wrong_archive_does_not_grant_allowance(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'archive'; p.write_bytes(b'not the official archive')
            real_sha = S._sha
            with patch.object(S, '_sha', side_effect=lambda path: S.BINARY_SHA256 if str(path) == 'never-executed' else real_sha(path)):
                with self.assertRaisesRegex(ValueError, 'archive hash'):
                    S.verify('never-executed', archive=p)

    def test_missing_binary_is_not_a_permission(self):
        with self.assertRaises(FileNotFoundError):
            S.verify(Path(tempfile.gettempdir()) / 'gearbase-definitely-missing-ccx')


if __name__ == '__main__':
    unittest.main()
