import unittest
from fea_readiness.review import balance_check, convergence_check, theory_check, contact_check,review

ID={'quantity':'peak_pressure','unit':'MPa','support_region':'smooth_interior','extraction':'peak_unaveraged','load_state':'final_full_load'}
IDS={'actual':ID,'predicted':ID}

class ReviewTests(unittest.TestCase):
    def test_balance_needs_scale_and_common_origin(self):
        loads=[{'force_N':[10,0,0],'point_mm':[0,3,0]}, {'force_N':[-10,0,0],'point_mm':[0,3,0]}]
        r=balance_check(loads,[0,0,0],10,30,1e-5,1e-5)
        self.assertEqual(r['status'],'PASS')
        loads[1]['point_mm']=[0,0,0]
        self.assertEqual(balance_check(loads,[0,0,0],10,30,1e-5,1e-5)['status'],'FAIL')
        with self.assertRaises(ValueError):balance_check(loads,[0,0,0],0,30,1e-5,1e-5)

    def test_convergence_identity_monotonic_and_order(self):
        rows=[{'physics_id':'p',**ID,'h_mm':h,'value':v} for h,v in [(1,104),(.5,101),(.25,100.25)]]
        r=convergence_check(rows,.01)
        self.assertEqual(r['status'],'PASS');self.assertAlmostEqual(r['measured']['observed_order'],2)
        rows[2]['physics_id']='other'
        self.assertEqual(convergence_check(rows,.01)['status'],'UNKNOWN')
        rows[2]['physics_id']='p';rows[2]['value']=102
        self.assertEqual(convergence_check(rows,.01)['status'],'UNKNOWN')
        rows[2]['value']=95
        self.assertEqual(convergence_check(rows,.01)['status'],'FAIL')
        self.assertEqual(convergence_check(rows[:2],.01)['status'],'UNKNOWN')

    def test_theory_requires_same_definition_and_eligibility(self):
        self.assertEqual(theory_check(100,100,None,.05,'same')['status'],'UNKNOWN')
        self.assertEqual(theory_check(100,100,True,.05,'')['status'],'UNKNOWN')
        self.assertEqual(theory_check(120,100,True,.05,'same p0',IDS)['status'],'FAIL')
        self.assertEqual(theory_check(101,100,True,.05,'same p0',IDS)['status'],'PASS')
        self.assertEqual(theory_check(100,100,True,.05,' ',IDS)['status'],'UNKNOWN')
        self.assertEqual(theory_check(100,100,True,.05,'same p0')['status'],'UNKNOWN')

    def test_incomplete_scalar_balance_cannot_substitute_free_body(self):
        r=review({'balance_residuals':[{'name':'ideal_ratio','value':0,'limit':.01,'definition':''}]})
        self.assertIn('balance',r['unknown'])

    def test_mesh_different_region_is_not_convergence(self):
        rows=[{'physics_id':'p',**ID,'h_mm':h,'value':v} for h,v in [(1,104),(.5,101),(.25,100.25)]]
        rows[1]['support_region']='tooth_root'
        self.assertEqual(convergence_check(rows,.01)['status'],'UNKNOWN')

    def test_contact_uses_actual_support(self):
        self.assertEqual(contact_check([],2)['status'],'UNKNOWN')
        r=contact_check([{'element':7779,'side':3,'source_sha256':'abc','edge_chord_over_contact_target_h':40.34}],2)
        self.assertEqual(r['status'],'FAIL')
        self.assertIn('convergence',r['message'])

if __name__=='__main__':unittest.main()
