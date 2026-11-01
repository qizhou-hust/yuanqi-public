import copy
import json
from pathlib import Path
import unittest
from gearmath.gear import factor_recompute as fr
from gearmath.gear.factor_methods import compile_factors
from gearmath.kernel.graph import Model
from gearmath.kernel import units as U

ROOT=Path(__file__).resolve().parents[1]

class K02CompositeDiagnostic(unittest.TestCase):
    def test_same_input_all_enabled_branches(self):
        doc=json.loads((ROOT/'output/m34/opt3/K02-helical.factors.opt-4ee0a4da.math-source.json').read_text(encoding='utf8'))
        doc=copy.deepcopy(doc)
        for k,v in [('adapter.din3967_1','d24'),('adapter.din3967_2','d25'),('adapter.f_Hbeta5','iso1328_grade5')]:
            doc['selectors'][k]={'value':v,'source':'K02 explicit diagnostic'}
        for n in ('A_sn_i_1','A_sn_i_2','f_Hbeta5'):
            doc['inputs'].pop(n,None);doc['evidence'].pop(n,None)
        for n,u in [('root_mm','mm'),('root_um','um')]:
            doc['inputs'][n]={'value':1,'unit':u,'provenance':'standard_constant','source':'unit definition'}
        for n,edition in [('DIN 3967','1978'),('ISO 1328-1','2013')]:
            doc['editions'][n]={'edition':edition,'source':'Explicit standard edition'}
        base=fr.build_model(doc,'kisssoft_chain','K02-helical')
        sel={'method.Z_LVR':'external','method.life':'nitrided_085_long_life','method.root_factors':'nitrided_reference'}
        compiled,table,missing=compile_factors(sel);self.assertFalse(missing)
        outputs={f'{s}_{i}' for s in ('Z_NT','Y_NT','Y_drelT','Y_RrelT','Y_X') for i in (1,2)}|{'Y_X'}
        formulas=list(base.formulas.values())+[f for f in compiled if f.output in outputs]
        specs=[s for s in base.specs.values() if s.name not in outputs]; have={s.name for s in specs}
        extras={'Rz_F_1','Rz_F_2','root_surface_intact_1','root_surface_intact_2'}
        specs += [s for s in table if s.name in extras and s.name not in have]
        m=Model(formulas,specs,editions=base.editions); m.selectors={**base.selectors,'method.life':sel['method.life'],'method.root_factors':sel['method.root_factors']}
        for n,v in base.inputs.items():
            if n in m.specs:m.set(n,U.from_canonical(v.value,v.unit),v.unit,v.provenance,v.source)
        # Reported Rz 20 µm; intact surface is an explicit diagnostic assumption.
        for i in (1,2):
            m.set(f'Rz_F_{i}',20,'um','user','K02 report RzF')
            m.set(f'root_surface_intact_{i}',1,'1','assumption','Root surface meets ISO 14.1')
        fixture=json.loads((ROOT/'data/kisssoft_v019/K02-additional.json').read_text(encoding='utf8'))
        self.assertEqual(fixture['run_sha256'],'bc9ccc436c40c436f8c026be155f3f0db3062f4e845f5d4f630bcf8b4b925b78')
        self.assertTrue(fixture['calculate_return'] and fixture['reload_calculate_return'] and fixture['source_unchanged'])
        self.assertFalse(fixture['reload_differences']);self.assertFalse(fixture['edits'])
        values=fixture['values']
        mapping={}
        for i in (1,2):
            j=i-1
            mapping.update({f'S_H_{i}':f'ZPP[{j}].Flanke.SH',f'S_F_{i}':f'ZPP[{j}].Fuss.SFnorm',
                f'Y_F_{i}':f'ZPP[{j}].Fuss.YF',f'Y_S_{i}':f'ZPP[{j}].Fuss.YS',
                f'Y_drelT_{i}':f'ZPP[{j}].Fuss.Ydrel',f'Y_RrelT_{i}':f'ZR[{j}].Fuss.YR',
                f'Z_NT_{i}':f'ZR[{j}].Flanke.ZNT',f'Y_NT_{i}':f'ZR[{j}].Fuss.YNT',
                f'A_sn_i_{i}':f'ZR[{j}].As.i',f'd_{i}':f'ZR[{j}].d'})
        r=m.evaluate(list(mapping)+['f_Hbeta5']);self.assertEqual(r.status,'ok')
        for n,key in mapping.items():
            # Geometry and direct material factors are tight; YF/YS and resulting safety
            # include known independent commercial-model residuals.
            tol=5e-4 if n.startswith(('S_H','S_F','Y_F','Y_S')) else 2e-8
            self.assertAlmostEqual(r.values[n],values[key],delta=tol*max(abs(values[key]),1),msg=n)
        self.assertAlmostEqual(U.from_canonical(r.values['f_Hbeta5'],'um'),values['ZP[0].KHdat.fHb5'])
