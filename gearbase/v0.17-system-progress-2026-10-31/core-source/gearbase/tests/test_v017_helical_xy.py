import math,unittest
from gearmath.gear import micropitting_helical as H, micropitting as M, m39_demo as D

class TestHelicalXY(unittest.TestCase):
    def inputs(self):
        return dict(profile='modified_both',g_B=2.,g_D=4.,g_alpha=6.,eps_alpha=1.5,eps_beta=1.,beta_b=.2,tolerance_class=6)

    def test_interpolation_and_profile_boundaries(self):
        p=self.inputs();high=1/1.5+(.5)/(1.5*2.5)
        self.assertAlmostEqual(H.X_Y_helical(g_Y=3.,**p),(1+high)/2)
        for eps in (.2,.8,1.,1.2,2.):
            for profile in H.PROFILES:
                q={**p,'profile':profile,'eps_beta':eps}
                vals=[H.X_Y_helical(g_Y=g,**q) for g in (0.,1.,2.,3.,4.,5.,6.)]
                self.assertTrue(all(math.isfinite(v) and v>=0 for v in vals))
                if profile=='modified_both':self.assertEqual((vals[0],vals[-1]),(0.,0.))
        for eps in (.8,1.2):
            q={**p,'eps_beta':eps};base=H.X_Y_helical(g_Y=1.,**q)
            for nearby in (eps-1e-9,eps+1e-9):self.assertAlmostEqual(H.X_Y_helical(g_Y=1.,**{**q,'eps_beta':nearby}),base,places=7)

    def test_buttressing_and_invalid_inputs(self):
        p=self.inputs();self.assertAlmostEqual(H.buttressing(g_Y=0.,g_alpha=6.,eps_beta=.5,beta_b=.2),1.15)
        self.assertEqual(H.buttressing(g_Y=3.,g_alpha=6.,eps_beta=2.,beta_b=.2),1.)
        for delta in ({'eps_alpha':2.1},{'beta_b':0.},{'eps_beta':float('nan')},{'profile':'invented'},{'tolerance_class':6.5},{'g_B':-1.}):
            with self.subTest(delta=delta),self.assertRaises((ValueError,M.OutOfDomain)):H.X_Y_helical(g_Y=1.,**{**p,**delta})

    def test_printed_one_end_high_overlap_coefficients_and_boundaries(self):
        p={**self.inputs(),'eps_beta':1.2};ea=p['eps_alpha']
        weak=1/ea-(ea-1)/(2*ea*(ea+1));plateau=1/ea+(ea-1)/(2*ea*(ea+1))
        self.assertAlmostEqual(H.X_Y_helical(g_Y=5.5,**{**p,'profile':'modified_pinion'}),weak*.5)
        end=6.-.2*math.sin(p['beta_b'])
        self.assertEqual(H.X_Y_helical(g_Y=end,**{**p,'profile':'modified_wheel'}),plateau)
        self.assertLess(H.X_Y_helical(g_Y=math.nextafter(end,math.inf),**{**p,'profile':'modified_wheel'}),plateau)
        self.assertEqual(H.X_Y_helical(g_Y=4.,**{**p,'profile':'modified_pinion','eps_beta':.8}),1.)

    def test_k02_seven_points_and_unloaded_endpoints(self):
        d=D.load_p3('P3-K02-helical');i={k:v['v'] for k,v in d['inputs'].items()};er=M.E_r(E1=i['E1'],E2=i['E2'],nu1=i['nu1'],nu2=i['nu2'])
        args={k:i[k] for k in ('g_alpha','p_et','d_a1','d_a2','d_b1','d_b2','alpha_wt','alpha_t','F_t','K_A','K_gamma','K_v','K_Halpha','K_Hbeta','eps_alpha','eps_beta','beta_b')}
        rows=H.p_dyn_points_method_B_helical(profile='modified_both',b=i['b_min'],E_r=er,tolerance_class=6,**args)
        for p,ref in d['outputs']['iso6336_22']['points'].items():
            self.assertAlmostEqual(rows[p]['X_Y'],ref['XY'],delta=1e-12)
            if p in ('A','E'):
                self.assertEqual(rows[p]['status'],'unloaded');self.assertEqual(rows[p]['p_dyn'],0.)
                self.assertIsNone(rows[p]['lambda_GF'])
            else:
                self.assertEqual(rows[p]['status'],'loaded')
                self.assertAlmostEqual(rows[p]['p_H'],ref['pHYB'],delta=1e-12*abs(ref['pHYB']))
                self.assertAlmostEqual(rows[p]['p_dyn'],ref['phidynYB'],delta=1e-12*abs(ref['phidynYB']))
