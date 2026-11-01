import copy
import json
from pathlib import Path
import unittest

from gearmath.gear import backlash_din3967 as din, din3967_adapter as adapter, factor_recompute as fr
from gearmath.kernel.graph import InputError, InputSpec, Model

ROOT=Path(__file__).resolve().parents[1]

class DinGraphAdapterTests(unittest.TestCase):
    def one(self, diameter):
        fs, _=adapter.formulas({1:'d24',2:'d25'})
        m=Model([fs[0]],[InputSpec('d_1','mm'),InputSpec('root_mm','mm')],editions={'DIN 3967':'1978'})
        return m.set('d_1',diameter,'mm').set('root_mm',1,'mm')
    def test_every_bin_and_within_bin_gradient(self):
        lo=0
        for hi in din.D_LIMITS:
            d=(lo+hi)/2
            r=self.one(d).evaluate(['A_sn_i_1'],wrt=['d_1'])
            self.assertEqual(r.status,'ok')
            self.assertAlmostEqual(r.values['A_sn_i_1'],din.allowances(d=d,series='d',tolerance_series=24)['A_sni']/1000)
            self.assertEqual(r.duals['A_sn_i_1'].d.get('d_1',0),0)
            lo=hi
    def test_nondifferentiable_boundaries_and_domain(self):
        for d in din.D_LIMITS[:-1]:
            self.assertEqual(self.one(d).evaluate(['A_sn_i_1']).status,'out_of_domain')
            for d2 in (d-1e-6,d+1e-6):
                self.assertEqual(self.one(d2).evaluate(['A_sn_i_1']).status,'ok')
        for d in (-1,0,10000.01):
            self.assertEqual(self.one(d).evaluate(['A_sn_i_1']).status,'out_of_domain')
        for d in (float('nan'),float('inf'),True):
            with self.assertRaises(InputError): self.one(d)
    def test_explicit_designations(self):
        for codes in ({1:'d24'}, {1:'d24',2:'invalid'}, {1:'d24',2:True}):
            with self.assertRaises(ValueError): adapter.formulas(codes)
    def test_k02_optimized_current_geometry_propagation(self):
        p=ROOT/'output/m34/opt3/K02-helical.factors.opt-4ee0a4da.math-source.json'
        old=json.loads(p.read_text(encoding='utf8')); new=copy.deepcopy(old)
        for i,c in ((1,'d24'),(2,'d25')):
            new['selectors'][f'adapter.din3967_{i}']={'value':c,'source':'Explicit K02 diagnostic designation'}
            new['inputs'].pop(f'A_sn_i_{i}')
        new['inputs']['root_mm']={'value':1,'unit':'mm','provenance':'standard_constant','source':'Definition of millimetre'}
        new['editions']['DIN 3967']={'edition':'1978','source':'Explicit standard edition'}
        original=fr.build_model(old,'kisssoft_chain','K02-helical')
        current=fr.build_model(new,'kisssoft_chain','K02-helical')
        names=['d_1','d_2','A_sn_i_1','A_sn_i_2','xE_1','S_F_1']
        a=original.evaluate(names); b=current.evaluate(names)
        self.assertEqual(a.status,'ok');self.assertEqual(b.status,'ok')
        self.assertAlmostEqual(a.values['A_sn_i_1'],-.064)
        self.assertAlmostEqual(b.values['A_sn_i_1'],-.085)
        self.assertAlmostEqual(b.values['A_sn_i_2'],-.13)
        self.assertLess(b.values['xE_1'],a.values['xE_1'])
        # Independent unchanged optimized KISSsoft run; no coefficient or threshold fitted.
        fixture=ROOT/'data/kisssoft_v019/K02-additional.json'
        ks=json.loads(fixture.read_text(encoding='utf8'))['values']['ZPP[0].Fuss.SFnorm']
        self.assertLess(abs(b.values['S_F_1']-ks),abs(a.values['S_F_1']-ks))
        self.assertNotIn('adapter.din3967_1',old['selectors'])
