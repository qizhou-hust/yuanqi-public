import unittest
from unittest.mock import patch
from gearmath.tools import m33_closure as C

class ClosureTest(unittest.TestCase):
    def test_original_22_inventory_and_formula_gate(self):
        r = C.prototype_inventory()
        self.assertEqual(len(r['rows']), 22)
        self.assertEqual(set(r['exceptions']), {'K_A', 'Y_ST'})
        self.assertTrue(r['passed'])
    def test_missing_formula_blocks_gate(self):
        r = C.prototype_inventory(remove_formula='Z_L')
        self.assertFalse(r['passed'])
        self.assertIn('Z_L', r['missing'])
    def test_c001_iteration_reproduces_legacy_receipt(self):
        r = C.c001_comparison()
        self.assertEqual(len(r['rows']), 18)
        self.assertTrue(r['iteration_reproduction_passed'])
        self.assertNotEqual(r['theta'][0]['current'], r['theta'][0]['vendor_nine'])

    def test_corrupted_receipt_does_not_pass_iteration_diagnosis(self):
        model, receipt = C.stage_model()
        receipt['root']['tooth_root_stress_pinion'] += 1
        with patch.object(C, 'stage_model', return_value=(model, receipt)):
            self.assertFalse(C.c001_comparison()['iteration_reproduction_passed'])
