import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from gearmath.tools import fea_ingest, fea_prepare

PACK = Path(__file__).resolve().parents[1] / 'data' / 'm37_fea_pack'

class VerifiedProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.solver = Path(self.tmp.name) / 'solver'
        self.solver.write_bytes(b'unapproved solver')
        self.r = {'mode': 'full', 'solver': {'sha256': fea_prepare.sha(self.solver), 'version': '2.23', 'version_output': 'test'},
                  'inputs_sha256': {str(p.relative_to(PACK)).replace('\\', '/'): fea_prepare.sha(p) for folder in ('cases', 'expected', 'scripts') for p in (PACK / folder).glob('*.py' if folder == 'scripts' else '*.json')},
                  'jobs': [], 'field_read_protocol': {}}
    def invoke(self, results, attachments=None):
        with patch.object(fea_ingest, 'validate', return_value=[]):
            return fea_ingest.ingest(results, PACK, {} if attachments is None else attachments, True,
                                     verified_profile=(Path(self.tmp.name), self.solver))
    def test_unapproved_solver_fails_closed(self):
        with self.assertRaises(ValueError): self.invoke(self.r)
    def test_changed_probe_fails_closed(self):
        probe = Path(self.tmp.name) / 'probe.dat'
        probe.write_bytes(b'original')
        with patch.object(fea_prepare, 'SOLVER_HASH', fea_prepare.sha(self.solver)), patch.object(fea_prepare, 'PROBE_HASHES', {probe.name: fea_prepare.sha(probe)}):
            probe.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'probe identity changed'):
                fea_prepare.verified_profile(self.tmp.name, self.solver)
    @patch('gearmath.tools.fea_prepare.verified_profile', return_value=object())
    def test_version_or_solver_identity_fails(self, _):
        for key, value in [('version', '2.22'), ('sha256', '0'*64)]:
            r = copy.deepcopy(self.r); r['solver'][key] = value
            with self.assertRaises(ValueError): self.invoke(r)
    @patch('gearmath.tools.fea_prepare.verified_profile', return_value=object())
    def test_case_and_metadata_mismatch_fail(self, _):
        r = copy.deepcopy(self.r); r['inputs_sha256']['cases/L2_yfs_matrix.json'] = '0'*64
        with self.assertRaises(ValueError): self.invoke(r)
        r = copy.deepcopy(self.r); inp = b'deck'; meta = json.dumps({'case':'L2','point':{'id':'fake'},'level':0,'h':1}).encode()
        raw = b'raw'
        r['jobs'] = [{'id':'L2_P01_d8','case':'L2','group':'mesh','status':'solved','tags':{'point':'P01','level':0},'h':1,
                      'extracted':{'YFS_FE':1.0,'force_balance_rel':0.0},
                      'inp_sha256':fea_ingest.sha256_bytes(inp), 'dat_sha256':fea_ingest.sha256_bytes(raw),
                      'strict_read':{'identity':{'dat_sha256':fea_ingest.sha256_bytes(raw),'sta_sha256':fea_ingest.sha256_bytes(raw)}},
                      'run_identity':{'prepared':{'files':{'metadata':{'sha256':fea_ingest.sha256_bytes(meta)}}}}}]
        a = {'runs/L2/L2_P01_d8.inp': inp, 'runs/L2/L2_P01_d8.meta.json': meta, 'runs/L2/L2_P01_d8.dat':raw, 'runs/L2/L2_P01_d8.sta':raw}
        with self.assertRaisesRegex(ValueError, 'metadata mismatch'): self.invoke(r,a)
    @patch('gearmath.tools.fea_prepare.verified_profile', return_value=object())
    def test_requires_raw_repost(self, _):
        with patch.object(fea_ingest, 'validate', return_value=[]):
            with self.assertRaises(ValueError): fea_ingest.ingest(self.r, PACK, None, False, verified_profile=(Path(self.tmp.name),self.solver))
    @patch('gearmath.tools.fea_prepare.verified_profile', return_value=object())
    def test_rejects_omitted_force_balance(self, _):
        r = copy.deepcopy(self.r)
        r['jobs'] = [{'id':'L2_P01_d8','case':'L2','group':'mesh','status':'solved','extracted':{'YFS_FE':1.0}}]
        with self.assertRaisesRegex(ValueError, 'required extracted quantity'): self.invoke(r)
    @patch('gearmath.tools.fea_prepare.verified_profile', return_value=object())
    def test_rejects_changed_raw_bytes(self, _):
        r = copy.deepcopy(self.r); inp = b'deck'; meta = b'{}'; raw = b'raw'
        r['jobs'] = [{'id':'L2_P01_d8','case':'L2','group':'mesh','status':'solved',
            'extracted':{'YFS_FE':1.0,'force_balance_rel':0.0},
            'inp_sha256':fea_ingest.sha256_bytes(inp), 'dat_sha256':fea_ingest.sha256_bytes(raw),
            'strict_read':{'identity':{'dat_sha256':fea_ingest.sha256_bytes(raw),'sta_sha256':fea_ingest.sha256_bytes(raw)}},
            'run_identity':{'prepared':{'files':{'metadata':{'sha256':fea_ingest.sha256_bytes(meta)}}}}}]
        a = {'runs/L2/L2_P01_d8.inp':inp, 'runs/L2/L2_P01_d8.meta.json':meta,
             'runs/L2/L2_P01_d8.dat':raw+b'changed', 'runs/L2/L2_P01_d8.sta':raw}
        with self.assertRaisesRegex(ValueError, 'raw output identity mismatch'): self.invoke(r,a)

class SignedRichardsonTest(unittest.TestCase):
    def test_unequal_mesh_ratios_preserve_signed_order(self):
        hs = [1/18, 1/27, 1/40]
        for order in (2.0, -2.0):
            result = fea_ingest.richardson(hs, [50 + 3*h**order for h in hs])
            self.assertAlmostEqual(result['observed_order'], order, places=8)
            self.assertAlmostEqual(result['order_used'], 2.0, places=8)
            if order < 0:
                self.assertEqual(result['assumption_reason'], 'order_out_of_range_or_unresolved')
        result = fea_ingest.richardson(hs, [1, 1.2, 1.1])
        self.assertEqual(result['assumption_reason'], 'oscillatory')

if __name__ == '__main__': unittest.main()
