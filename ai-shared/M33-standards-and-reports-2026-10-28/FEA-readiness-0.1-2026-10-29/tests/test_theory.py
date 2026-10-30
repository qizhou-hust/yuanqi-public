import math
import unittest
from fea_readiness.theory import hertz_line, spur_pair, rectangular_cantilever
from fea_readiness.contracts import eligible, rule, resultant

class TheoryTests(unittest.TestCase):
    def test_frozen_m37_pitch(self):
        g=spur_pair(20,36,2,20,30,25)
        h=hertz_line(g['full_load_q_N_per_mm'],g['rho1_mm'],g['rho2_mm'],206000,.3,206000,.3)
        self.assertAlmostEqual(g['contact_ratio'],1.6246424030581257,12)
        self.assertAlmostEqual(h['half_width_mm'],.0468335081991751,13)
        self.assertAlmostEqual(h['p0_MPa'],602.7349481549439,9)
        self.assertAlmostEqual(g['torque_per_1mm_Nmm'],833.3333333333334,10)

    def test_hertz_scaling_and_integral(self):
        a=hertz_line(10,10,20,210000,.3,210000,.3)
        b=hertz_line(40,10,20,210000,.3,210000,.3)
        for key in ['half_width_mm','p0_MPa']:self.assertAlmostEqual(b[key]/a[key],2)
        self.assertAlmostEqual(a['integrated_line_load_N_per_mm'],10)
        self.assertEqual(a,hertz_line(10,20,10,210000,.3,210000,.3))

    def test_invalid_domains(self):
        for q in [-1,float('nan'),float('inf'),True]:
            with self.subTest(q=q), self.assertRaises(ValueError):hertz_line(q,10,10,200000,.3,200000,.3)
        with self.assertRaises(ValueError):hertz_line(10,-10,10,200000,.3,200000,.3)
        with self.assertRaises(ValueError):hertz_line(10,10,10,200000,.5,200000,.3)
        self.assertEqual(hertz_line(0,10,10,200000,.3,200000,.3)['p0_MPa'],0.)
        with self.assertRaises(ValueError):spur_pair(20,36,2,20,30,25,s_mm=100)
        with self.assertRaises((ValueError,OverflowError,ZeroDivisionError)):hertz_line(1e308,1e308,1e308,1e308,.3,1e308,.3)

    def test_beam_independent_and_scaling(self):
        a=rectangular_cantilever(100,50,10,5,200000,.3)
        b=rectangular_cantilever(200,50,10,5,200000,.3)
        self.assertAlmostEqual(a['nominal_root_bending_MPa'],120)
        self.assertAlmostEqual(a['bending_displacement_mm'],.2)
        self.assertAlmostEqual(b['total_displacement_mm'],2*a['total_displacement_mm'])

    def test_moment_origin(self):
        loads=[{'force_N':[10,0,0],'point_mm':[0,3,0]}]
        self.assertEqual(resultant(loads,[0,0,0])['moment_Nmm'],[0,0,-30])
        self.assertEqual(resultant(loads,[0,2,0])['moment_Nmm'],[0,0,-10])

    def test_no_vacuous_pass(self):
        for rs in [[],[rule('x','PASS','',required=False)],[rule('x','UNKNOWN','')],[rule('x','NOT_APPLICABLE','')]]:
            self.assertFalse(eligible(rs))
        self.assertTrue(eligible([rule('x','PASS','')]))

if __name__=='__main__':unittest.main()
