import math
import sys
import unittest
from pathlib import Path
from gearmath.gear.flagship_w2w import run, verify

P = dict(a1_mm=100.,a2_mm=125.,n1_rpm=1440.,target_ratio=144.,rho_v_deg=5.,t_out_nm=800.,z1_options=[1,2,3,4,5,6],ratio_band=.02,k_w_m2k=12.,area_m2=.5,t_oil_max_c=90.,t_amb_c=30.,max_candidates=40)


def original(p):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'archive/m31/src'))
    try:
        from gears.solver import synthesize_w2w
        return synthesize_w2w(**p)
    finally:
        sys.path.pop(0)


def keys(c):
    return tuple(c[s][k] for s in ('stage1','stage2') for k in ('m_mm','q','z1'))


class TestFlagshipW2W(unittest.TestCase):
    def test_original_oracle(self):
        old=original(P); new=run(P)
        self.assertEqual(new['search']['feasible'],old['search']['feasible'])
        self.assertEqual(new['search']['pairs_examined'],old['search']['pairs_examined'])
        self.assertEqual(len(new['candidates']),len(old['candidates']))
        self.assertEqual(new['candidates'], old['candidates'])
        for a,b in zip(new['candidates'],old['candidates']):
            self.assertEqual(keys(a),keys(b))
            for k in ('eta_total','i_total','p_in_w','area_required_m2'):
                self.assertTrue(math.isclose(a[k],b[k],rel_tol=1e-14), k)
            self.assertEqual(a['thermal_ok'],b['thermal_ok'])
        self.assertFalse(new['candidates'][0]['thermal_ok'])
        self.assertTrue(verify(P,new['candidates'][0])['ok'])
        altered=dict(new['candidates'][0],thermal_ok=True)
        self.assertFalse(verify(P,altered)['ok'])

    def test_invalid(self):
        for key in P:
            p=dict(P); del p[key]
            with self.subTest(missing=key), self.assertRaises(ValueError): run(p)
        for p in (dict(P,extra=1),dict(P,area_m2=0),dict(P,z1_options=[7]),dict(P,n1_rpm=float('nan')),dict(P,k_w_m2k=float('inf')),dict(P,t_oil_max_c=30),dict(P,max_candidates=0),dict(P,ratio_band=-1)):
            with self.subTest(p=p), self.assertRaises(ValueError): run(p)

    def test_small_domain_against_original(self):
        p=dict(P,z1_options=[2,4],ratio_band=.5,max_candidates=10000)
        old=original(p); new=run(p)
        self.assertEqual(new['search']['feasible'],old['search']['feasible'])
        self.assertEqual(new['search']['pairs_examined'],old['search']['pairs_examined'])
        self.assertEqual([keys(c) for c in new['candidates']],[keys(c) for c in old['candidates']])

    def test_exact_thermal_boundary_and_underflow(self):
        p = dict(P, area_m2=1.669296396441226)
        old = original(p); new = run(p)
        self.assertEqual(new['candidates'], old['candidates'])
        self.assertFalse(old['candidates'][9]['thermal_ok'])
        self.assertFalse(new['candidates'][9]['thermal_ok'])
        with self.assertRaises(ValueError):
            run(dict(P, k_w_m2k=1e-300, area_m2=1e-300))

    def test_return_budget_reports_truncation(self):
        p=dict(P,max_candidates=1)
        result=run(p)
        self.assertEqual(len(result['candidates']),1)
        self.assertGreater(result['search']['feasible'],1)
        self.assertTrue(result['search']['truncated'])
        self.assertFalse(result['search']['pair_cap_hit'])

if __name__ == '__main__': unittest.main()
