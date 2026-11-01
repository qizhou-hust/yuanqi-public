import copy,unittest
from gearmath.product import design_check as D
from tests.test_sys_design_check import _doc,_demo_system_input,L

def thermal():
    return {k:L(v,u) for k,v,u in [('method','equilibrium','-'),('A_c',2.,'m^2'),('k',.02,'kW/(m^2*K)'),('ambient_C',20.,'degC'),
      ('bracket_C',[40.,100.],'degC'),('temperature_tolerance_C',1e-8,'K'),('residual_tolerance_kW',1e-9,'kW'),
      ('max_iterations',100,'1'),('loss_model',{'fixed_kW':2.,'components':[]},'-'),('temperature_limit_C',75.,'degC')]}

class TestThermalProduct(unittest.TestCase):
    def run_case(self, t):
        si=_demo_system_input();si['thermal']=t;before=copy.deepcopy(si)
        r=D.check(_doc('C001'),si,['thermal']);self.assertEqual(si,before);self.assertEqual(D.validate_result(r),[])
        return r['checks']['thermal']
    def test_equilibrium_is_actual_temperature_check(self):
        r=self.run_case(thermal());self.assertEqual(r['status'],'pass')
        item=next(x for x in r['items'] if x['id']=='thermal.temperature_C');self.assertAlmostEqual(item['value'],70.,places=6)
        self.assertEqual((item['limit'],item['unit']),(75.,'degC'));self.assertIsNone(item['margin'])
        t=thermal();t['temperature_limit_C']=L(65.,'degC');self.assertEqual(self.run_case(t)['status'],'fail')
    def test_fail_closed_routes_units_and_missing_limits(self):
        for mutation in ('missing_limit','no_bracket','nonconvergence','wrong_unit','unknown_method'):
            t=thermal()
            if mutation=='missing_limit':del t['temperature_limit_C']
            if mutation=='no_bracket':t['bracket_C']=L([40.,50.],'degC')
            if mutation=='nonconvergence':t['max_iterations']=L(1,'1')
            if mutation=='wrong_unit':t['k']=L(.02,'W/(m^2*K)')
            if mutation=='unknown_method':t['method']=L('invented','-')
            with self.subTest(mutation=mutation):self.assertEqual(self.run_case(t)['status'],'blocked')
    def test_legacy_route_remains_unchanged(self):
        si=_demo_system_input();r=D.check(_doc('C001'),si,['thermal'])['checks']['thermal']
        self.assertEqual(r['items'][0]['id'],'thermal.P_T');self.assertEqual(r['status'],'fail')
        si['thermal']['method']=L(None,'-')
        self.assertEqual(D.check(_doc('C001'),si,['thermal'])['checks']['thermal']['status'],'blocked')
