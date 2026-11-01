import copy
import json
from pathlib import Path
import unittest
from gearmath.gear import factor_recompute as fr
from gearmath.kernel.source_doc import SourceError
from gearmath.product import design_check

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'data/source/K02-helical.v019-diagnostic.math-source.json'
FIXTURE=ROOT/'data/kisssoft_v019/K02-additional.json'

class ActualSourcePipelineTests(unittest.TestCase):
    def setUp(self): self.doc=json.loads(DOC.read_text(encoding='utf8'))
    def test_derived_document_reproducible(self):
        parent=json.loads((ROOT/'output/m34/opt3/K02-helical.factors.opt-4ee0a4da.math-source.json').read_text(encoding='utf8'))
        keys=('method.life','method.root_factors','adapter.din3967_1','adapter.din3967_2','adapter.f_Hbeta5')
        sel={k:(self.doc['selectors'][k]['value'],self.doc['selectors'][k]['source']) for k in keys}
        input_names=('Rz_F_1','Rz_F_2','root_surface_intact_1','root_surface_intact_2','root_mm','root_um')
        rows=[(k,self.doc['inputs'][k]) for k in input_names]
        editions={k:(self.doc['editions'][k]['edition'],self.doc['editions'][k]['source']) for k in ('DIN 3967','ISO 1328-1')}
        actual=fr.derive_document(parent,'kisssoft_chain','K02-helical',selectors=sel,inputs=rows,editions=editions,
            doc_id=self.doc['id'],title=self.doc['title'])
        self.assertEqual(actual,self.doc)
    def test_source_pipeline_and_design_check(self):
        m=fr.build_model(self.doc,'kisssoft_chain','K02-helical')
        self.assertEqual(m.selectors['method.life'],'nitrided_085_long_life')
        self.assertEqual(m.selectors['method.root_factors'],'nitrided_reference')
        self.assertEqual(m.formulas['Y_drelT_1'].id,'nitrided.Y_drelT.1')
        self.assertIn('A_sn_i_1',m.formulas)
        vals=json.loads(FIXTURE.read_text(encoding='utf8'))['values']
        fields={f'S_H_{i}':f'ZPP[{i-1}].Flanke.SH' for i in (1,2)}
        fields.update({f'S_F_{i}':f'ZPP[{i-1}].Fuss.SFnorm' for i in (1,2)})
        r=m.evaluate(list(fields));self.assertEqual(r.status,'ok')
        for name,key in fields.items(): self.assertAlmostEqual(r.values[name],vals[key],delta=5e-4*max(1,abs(vals[key])))
        si=json.loads((ROOT/'data/system/K01-spur.system-input.json').read_text(encoding='utf8'))
        si['design_ref']['source_id']=self.doc['id'];si['design_ref']['model_family']='kisssoft_chain:K02-helical'
        checks=design_check.check(self.doc,si,['gear_rating'])['checks']['gear_rating']
        self.assertEqual(checks['status'],'pass')
        actual={x['quantity']:x['value'] for x in checks['items']}
        for name in fields: self.assertEqual(actual[name],r.values[name])
    def test_missing_physical_inputs_block(self):
        for name in ('Rz_F_1','Rz_F_2','root_surface_intact_1','root_surface_intact_2','root_mm','root_um'):
            d=copy.deepcopy(self.doc);d['inputs'].pop(name)
            m=fr.build_model(d,'kisssoft_chain','K02-helical')
            r=m.evaluate(['S_F_1','S_F_2'])
            self.assertEqual(r.status,'blocked_missing_inputs',msg=name)
            self.assertIn(name,r.missing)
    def test_invalid_surface_and_unsupported_override_rejected(self):
        for n,value in [('Rz_F_1',0),('root_surface_intact_1',.5)]:
            d=copy.deepcopy(self.doc);d['inputs'][n]['value']=value
            with self.assertRaises(SourceError): fr.build_model(d,'kisssoft_chain','K02-helical')
        d=copy.deepcopy(self.doc);d['selectors']['method.life']['value']='case_hardened_085_long_life'
        with self.assertRaises(SourceError): fr.build_model(d,'kisssoft_chain','K02-helical')
    def test_parent_document_unmodified(self):
        p=ROOT/'output/m34/opt3/K02-helical.factors.opt-4ee0a4da.math-source.json'
        parent=json.loads(p.read_text(encoding='utf8'))
        self.assertEqual(parent['selectors']['method.life']['value'],'external')
        self.assertEqual(parent['selectors']['method.root_factors']['value'],'external')
        m=fr.build_model(parent,'kisssoft_chain','K02-helical')
        self.assertNotIn('Y_drelT_1',m.formulas)
        self.assertEqual(m.evaluate(['S_F_1']).status,'ok')
