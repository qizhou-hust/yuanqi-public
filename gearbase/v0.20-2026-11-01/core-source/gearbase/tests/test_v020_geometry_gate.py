import copy
import unittest
from gearmath.tools import milestones as M, m33_geometry_replay as R


class GeometryGateIntegration(unittest.TestCase):
    def test_user_scoped_numeric_gate_preserves_e4_limits(self):
        receipt = R.run()
        state = M.m33_geometry_numeric_gate(receipt)
        self.assertTrue(state['passed'])
        self.assertEqual(state['scope'], 'example7/8_geometry_user_identified')
        self.assertFalse(state['full_E4'])
        self.assertFalse(state['original_2_of_6_reconstructed'])

    def test_forged_or_stale_geometry_receipt_does_not_close_gate(self):
        receipt = R.run()
        for edit in (lambda r: r.update(limit=.1),
                     lambda r: r['rows'][0].update(relative_error=0),
                     lambda r: r['rows'].pop(),
                     lambda r: r.update(producer_sha256='0'*64)):
            bad=copy.deepcopy(receipt);edit(bad)
            self.assertFalse(M.m33_geometry_numeric_gate(bad)['passed'])


if __name__ == '__main__': unittest.main()
