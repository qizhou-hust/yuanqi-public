"""Independent-review counterexamples: no shared oracle or blank provenance."""
import copy
import json
import pathlib
import unittest
from unittest.mock import patch

from gearmath.product import flagship_system as F
from gearmath.product.nearest_feasible_edit import propose

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReviewRegressions(unittest.TestCase):
    def test_corrupt_production_force_cannot_validate_itself(self):
        case = F._edits()['H2'][0]
        self.assertTrue(F.edit_case('H2', case)['ok'])
        with patch.object(F.FK, 'tangential_force', lambda torque, diameter: 200 * torque / diameter):
            result = F.edit_case('H2', case)
        self.assertFalse(result['ok'], result)
        self.assertNotEqual(result['observed'], result['independent'])

    def test_blank_gear_leaf_provenance_blocks_nearest_edit(self):
        inputs = json.loads((ROOT / 'data/system-optimization/v017-capability-probe.json').read_text(encoding='utf8'))
        req = {'target': {'gear': 'original', 'shaft': 'economy', 'bearing': 'original'},
               'metric': {'kind': 'weighted_hamming', 'weights': {'gear': '1', 'shaft': '1', 'bearing': '1'}},
               'constraints': {'pass_scopes': ['gear_rating', 'shaft', 'bearing', 'key']},
               'source': 'Independent review counterexample'}
        for source in ('', '   ', '\t\n'):
            p = copy.deepcopy(inputs['problem'])
            for gear in p['gear']:
                for leaf in gear['inputs'].values():
                    leaf['source'] = source
            result = propose(inputs['design_doc'], inputs['system_input'], p, req)
            self.assertEqual(result['status'], 'blocked', result)
            self.assertIsNone(result['nearest'])


if __name__ == '__main__':
    unittest.main()
