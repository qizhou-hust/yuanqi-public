import copy
import json
import tempfile
import unittest
from pathlib import Path
from tests.test_fea_gates_step_state import build
from gearmath.tools import fea_prepare as P

class PrepareTests(unittest.TestCase):
    def test_serialized_contact_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            inp,_=build('L0c',td)
            manifest=json.loads(json.dumps(P.prepare(inp,'2.21')))
            self.assertTrue(P.verify(inp,manifest))
    def test_bundled_modules_preserve_zero_dependency_guard(self):
        from gearmath.tools import doctor
        self.assertTrue(doctor.check_zero_deps()[0])
        self.assertEqual(Path(P.deck_state.__file__).resolve(),(P.PACK/'scripts/deck_state.py').resolve())
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'scripts').mkdir()
            for name in ('ccx_strict','deck_state'):
                (root/'scripts'/(name+'.py')).write_bytes((P.PACK/'scripts'/(name+'.py')).read_bytes())
            with patch.object(P,'PACK',root):
                P._bundled_module('deck_state');P._bundled_module('ccx_strict')
            self.assertEqual(list(root.rglob('*.pyc')),[])
    def test_block_and_edited_input(self):
        with tempfile.TemporaryDirectory() as d:
            inp, _ = build('L0', d)
            m = P.prepare(inp)
            self.assertEqual(m['registration'], 'blocked')
            self.assertTrue(P.verify(inp, m))
            inp.write_text(inp.read_text() + '\n** edited\n')
            with self.assertRaises(ValueError): P.verify(inp, m)
    def test_missing_face_and_unregistered_type(self):
        with tempfile.TemporaryDirectory() as d:
            inp, _ = build('L0c', d)
            m = P.prepare(inp, '2.21')
            altered = copy.deepcopy(m)
            face = next(r for r in altered['requests'] if r['coverage']['mode']=='rows_within_faces')
            face['coverage']['faces'] = []
            with self.assertRaises(ValueError): P.verify(inp, altered)
            face['coverage']['element_types'] = {'1':'UNREGISTERED'}
            face['coverage']['faces'] = [[1,1]]
            errors, _ = P.ccx_strict._validate_request(face, '2.21')
            self.assertTrue(any(x['code']=='registry_missing' for x in errors))
    def test_optin_identity_and_unknowns(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            names = list(P.PROBE_HASHES)
            for name in names: (base / name).write_text(name)
            solver = base / 'solver'; solver.write_text('solver')
            hashes = {name: P.sha(base / name) for name in names}
            with patch.object(P, 'PROBE_HASHES', hashes), patch.object(P, 'SOLVER_HASH', P.sha(solver)):
                inp, _ = build('L0', base / 'deck')
                with self.assertRaises(ValueError):
                    P.prepare(inp, '2.21', probe_dir=base, solver_path=solver)
                reader = P.verified_profile(base, solver)
                self.assertEqual(reader.IP_REGISTRY[('2.23', 'CPE6')], 9)
                self.assertNotIn(('2.23', 'CPE6'), P.ccx_strict.IP_REGISTRY)
                req = reader.field_request('stresses','X',('elem','integ.pnt.','sxx','syy','szz','sxy','sxz','syz'), {'mode':'elements_ip_registered','element_groups':{'CPE6':[1]}})
                self.assertFalse(reader._validate_request(req, '2.23')[0])
                self.assertTrue(reader._validate_request(req, '9.9')[0])
                req['coverage']['element_groups']={'UNKNOWN':[1]}
                self.assertTrue(reader._validate_request(req, '2.23')[0])
                (base / names[0]).write_text('changed')
                with self.assertRaises(ValueError): P.verified_profile(base, solver)
