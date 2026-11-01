import math
import unittest
from gearmath.system import thermal_balance as TB
from gearmath.gear import micropitting as MP
from gearmath.system import thermal_14179 as TH


def spec():
    return dict(A_c=2, k=.02, ambient_C=20, bracket_C=[40,100], temperature_tolerance_C=1e-8, residual_tolerance_kW=1e-9, max_iterations=100, loss_model=dict(fixed_kW=2, components=[]))

class ThermalBalanceTests(unittest.TestCase):
    def test_fixed_closed_form(self):
        r=TB.solve(spec())
        self.assertEqual(r['status'], 'converged')
        self.assertAlmostEqual(r['temperature_C'],70,places=6)
    def test_dependent_independent_root(self):
        s=spec(); s['loss_model']={'fixed_kW': 1, 'viscosity': {'nu_40':220,'nu_100':19}, 'components':[{'type':'mesh','K':5,'V':10,'T1':500,'n1':1500,'beta_w':0,'M':2}]}
        r=TB.solve(s); self.assertEqual(r['status'],'converged')
        def f(t):
            nu=MP.nu_theta(nu_40=220,nu_100=19,theta=t)
            return .04*(t-20)-1-TH.mesh_loss(f_m=TH.mesh_friction(nu=nu,K=5,V=10),T1=500,n1=1500,beta_w=0,M=2)
        lo,hi=40.,100.
        for _ in range(100):
            mid=(lo+hi)/2
            if f(mid)>0: hi=mid
            else: lo=mid
        self.assertAlmostEqual(r['temperature_C'],(lo+hi)/2,places=6)
    def test_failures(self):
        s=spec(); s['bracket_C']=[40,50]; self.assertEqual(TB.solve(s)['status'],'no_bracket')
        s=spec(); s['max_iterations']=1; self.assertEqual(TB.solve(s)['status'],'nonconvergence')
        s=spec(); s['k']=float('nan'); self.assertEqual(TB.solve(s)['status'],'invalid')
        s=spec(); del s['loss_model']; self.assertEqual(TB.solve(s)['status'],'invalid')
        s=spec(); s['loss_model']={'fixed_kW':0,'viscosity':{'nu_40':220,'nu_100':19},'components':[{'type':'mesh','K':5,'V':1,'T1':500,'n1':1500,'beta_w':0,'M':2}]}; self.assertEqual(TB.solve(s)['status'],'invalid')
