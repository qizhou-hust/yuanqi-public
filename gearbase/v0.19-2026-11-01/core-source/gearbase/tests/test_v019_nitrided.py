import unittest
import json
from pathlib import Path
from gearmath.kernel.graph import Model, InputSpec, InputError
from gearmath.kernel.expr import FormulaError
from gearmath.gear.inputs import full_input_table, input_specs
from gearmath.gear.life_factors import LIFE_INPUTS
from gearmath.gear.root_factors import ROOT_FACTOR_INPUTS
from gearmath.gear.nitrided_factors import LIFE, NOTCH, ROUGHNESS
from gearmath.gear.factor_methods import compile_factors
from gearmath.gear import kisssoft_multi
from gearmath.kernel import units as U
from gearmath.gear import backlash_din3967 as DIN

class NitridedTests(unittest.TestCase):
    def model(self, f):
        return Model([f], input_specs([f], full_input_table()+LIFE_INPUTS+ROOT_FACTOR_INPUTS+[InputSpec("qs_1", "1"), InputSpec("qs_2", "1")]), editions={"ISO 6336-2":"2019", "ISO 6336-3":"2019"})
    def test_endpoints_and_domains(self):
        for f in LIFE:
            lower = 2e6 if f.output.startswith('Z') else 3e6
            for n, expected in ((lower, 1), (1e10, .85)):
                r=self.model(f).set('N_L_'+f.output[-1], n, '1').evaluate([f.output])
                self.assertEqual(r.status, 'ok'); self.assertAlmostEqual(r.values[f.output], expected)
            for n in (lower*.99, 1.01e10):
                self.assertEqual(self.model(f).set('N_L_'+f.output[-1], n, '1').evaluate([f.output]).status, 'out_of_domain')
    def test_notch_reference(self):
        f=NOTCH[0]; m=self.model(f).set('N_L_1',3e6,'1').set('qs_1',2.5,'1')
        self.assertAlmostEqual(m.evaluate([f.output]).values[f.output],1)
    def test_long_life_endpoint_continuity(self):
        for f in LIFE:
            lower = 2e6 if f.output.startswith('Z') else 3e6
            for n,adjacent in ((lower,lower*(1+1e-9)),(1e10,1e10*(1-1e-9))):
                a=self.model(f).set('N_L_'+f.output[-1],n,'1').evaluate([f.output])
                b=self.model(f).set('N_L_'+f.output[-1],adjacent,'1').evaluate([f.output])
                self.assertLess(abs(a.values[f.output]-b.values[f.output]),1e-9)
    def test_nonfinite_boolean_and_negative(self):
        for val in (float('nan'), float('inf'), -float('inf'), True, False, 0, -1):
            with self.assertRaises(InputError):
                self.model(LIFE[0]).set('N_L_1', val, '1')
        for val in (float('nan'), float('inf'), True, -1, 0):
            with self.assertRaises(ValueError):
                DIN.tooth_thickness_tolerance(d=val, tolerance_series=25)
        for val in (True, 25.5, 20, 31):
            with self.assertRaises(ValueError):
                DIN.tooth_thickness_tolerance(d=100, tolerance_series=val)
    def test_roughness_and_notch_domains(self):
        f=ROUGHNESS[0]
        for rough, expected in ((0.5, 1.025), (10, 4.299-3.259*11**0.005)):
            m=self.model(f).set('N_L_1', 3e6, '1').set('Rz_F_1',rough,'um').set('root_um',1,'um').set('root_surface_intact_1',1,'1')
            self.assertAlmostEqual(m.evaluate([f.output]).values[f.output],expected)
        for val in (0.5, True, float('nan')):
            with self.assertRaises(InputError): self.model(ROUGHNESS[0]).set('root_surface_intact_1',val,'1')
        f=NOTCH[0]
        for q in (0.9,8):
            m=self.model(f).set('N_L_1',3e6,'1').set('qs_1',q,'1')
            self.assertEqual(m.evaluate([f.output]).status,'out_of_domain')
    def test_root_selector(self):
        sel={'method.Z_LVR':'external','method.life':'external','method.root_factors':'nitrided_reference'}
        fs, _, missing=compile_factors(sel)
        self.assertFalse(missing)
        self.assertTrue(any(f.id == 'nitrided.Y_drelT.1' for f in fs))
        self.assertTrue(any(f.id == 'nitrided.Y_RrelT.1' for f in fs))
    def test_bad_material_selectors(self):
        for value in (True, 1.5, 'nitrided', ''):
            with self.assertRaises(FormulaError):
                compile_factors({'method.Z_LVR':'external','method.life':value,'method.root_factors':'external'})
    def test_selector(self):
        sel={'method.Z_LVR':'external','method.life':'nitrided_085_long_life','method.root_factors':'external'}
        fs, _, missing=compile_factors(sel)
        self.assertFalse(missing)
        self.assertTrue(any(f.id == 'nitrided.Z_NT.1' for f in fs))

class K02FrozenDiagnostic(unittest.TestCase):
    def test_new_selectors_on_frozen_inputs(self):
        old, case = kisssoft_multi.build_model('K02-helical')
        original = {k:(v.value,v.unit,v.provenance,v.source) for k,v in old.inputs.items()}
        selectors={'method.Z_LVR':'external', 'method.life':'nitrided_085_long_life', 'method.root_factors':'nitrided_reference'}
        compiled, table, missing = compile_factors(selectors)
        self.assertFalse(missing)
        wanted={f'{stem}_{i}' for stem in ('Z_NT','Y_NT','Y_drelT','Y_RrelT','Y_X') for i in (1,2)} | {'Y_X'}
        formulas=list(old.formulas.values()) + [f for f in compiled if f.output in wanted]
        specs=[spec for spec in old.specs.values() if spec.name not in wanted]
        have={spec.name for spec in specs}
        new_inputs={'Rz_F_1','Rz_F_2','root_surface_intact_1','root_surface_intact_2','root_mm','root_um'}
        specs += [spec for spec in table if spec.name in new_inputs and spec.name not in have]
        m=Model(formulas,specs,editions=case['editions'])
        for n,v in old.inputs.items():
            if n in m.specs: m.set(n,U.from_canonical(v.value,v.unit),v.unit,v.provenance,v.source)
        for i in (1,2):
            m.set(f'Rz_F_{i}',case['report']['Rz_F']['value'],'um')
            m.set(f'root_surface_intact_{i}',1,'1')
        m.set('root_mm',1,'mm'); m.set('root_um',1,'um')
        r=m.evaluate(sorted(wanted)); self.assertEqual(r.status,'ok')
        for n in wanted & set(old.inputs):
            self.assertAlmostEqual(r.values[n],old.inputs[n].value,delta=2e-14,msg=n)
        self.assertEqual(original,{k:(v.value,v.unit,v.provenance,v.source) for k,v in old.inputs.items()})
        self.assertEqual(m.formulas['Y_drelT_1'].id,'nitrided.Y_drelT.1')
        self.assertIn('qs_1',m.formulas)
        diameters=old.evaluate(['d_1','d_2']).values
        # Explicitly selected d24/d25 designations reproduce source allowances.
        for i,designation in ((1,'d24'),(2,'d25')):
            result=DIN.allowances(d=diameters[f'd_{i}'],**DIN.parse_designation(designation))
            self.assertAlmostEqual(result['A_sni']/1000,old.inputs[f'A_sn_i_{i}'].value)


class IndependentOptimizedK02(unittest.TestCase):
    def test_native_cycles_to_life_factors(self):
        path=Path(__file__).resolve().parents[1]/'data/kisssoft_v019/K02-additional.json'
        data=json.loads(path.read_text(encoding='utf8'))
        self.assertEqual(data['run_sha256'],'bc9ccc436c40c436f8c026be155f3f0db3062f4e845f5d4f630bcf8b4b925b78')
        self.assertEqual(data['edits'],[]); self.assertTrue(data['calculate_return'])
        for i in (1,2):
            for stem,field in (('Z_NT','Flanke.ZNT'),('Y_NT','Fuss.YNT')):
                f=next(f for f in LIFE if f.output==f'{stem}_{i}')
                m=Model([f],input_specs([f],LIFE_INPUTS),editions={'ISO 6336-2':'2019','ISO 6336-3':'2019'})
                m.set(f'N_L_{i}',data['values'][f'ZR[{i-1}].NL'],'1')
                r=m.evaluate([f.output]); self.assertEqual(r.status,'ok')
                self.assertAlmostEqual(r.values[f.output],data['values'][f'ZR[{i-1}].{field}'],delta=2e-14)
