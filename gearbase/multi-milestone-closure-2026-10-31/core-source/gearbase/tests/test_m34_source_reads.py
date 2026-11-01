"""Stored-source projections are trusted; caller provenance claims are not."""
import copy
from pathlib import Path
import tempfile
import unittest

from gearmath.gear import math_source as MS
from gearmath.tools import ai_tools as AI, design_store as DS

ROOT=Path(__file__).resolve().parents[1]
READS=(('gear_rate',{}),('gear_explain',{'quantity':'S_H_1'}),
       ('gear_sensitivity',{'quantity':'S_H_1','wrt':['b']}))


class TestSourceOwnedReads(unittest.TestCase):
    def setUp(self):
        AI.reset_state()
        self.addCleanup(AI.reset_state)

    def assert_reads(self,doc):
        DS.commit_source(AI._STORE,'owned',doc,'real stored source read regression')
        head=AI._STORE.head('owned')
        model=MS.build_model(doc)
        source_eval=model.evaluate(['S_H_1'],wrt=['b'])
        got=AI.call('gear_get_design',{'design':'owned'})
        self.assertEqual(got['status'],'ok',got.get('errors'))
        for section in ('inputs','evidence','constraints'):
            for name,row in doc[section].items():
                self.assertEqual(got['parameters'][name]['provenance'],row['provenance'])
                self.assertEqual(got['parameters'][name]['value'],row['value'])
        rate=AI.call('gear_rate',{'design':'owned'})
        self.assertEqual(rate['status'],MS.receipt_of(model)['status'],rate.get('errors'))
        for tool,args in READS[1:]:
            out=AI.call(tool,{'design':'owned',**args})
            self.assertEqual(out['status'],source_eval.status,out.get('errors'))
            self.assertEqual(out['parameters'],got['parameters'])
            if tool=='gear_sensitivity':
                self.assertEqual(out['value'],source_eval.values['S_H_1'])
                self.assertEqual(out['sensitivities'][0]['d_quantity_d_input_canonical'],
                                 model.gradient(source_eval,'S_H_1','b'))
            else:
                self.assertTrue(out['chain'])
        self.assertEqual(AI._STORE.head('owned'),head,'reads must not alter owned source or chain')

    def test_imported_source_all_read_paths(self):
        self.assert_reads(MS.load_file())

    def test_real_optimizer_written_source_all_read_paths(self):
        # Existing optimizer-written artifact, imported unchanged as a source.
        doc=MS.load_file(ROOT/'output/m34/C001.opt-afcc042f.math-source.json')
        self.assertEqual(doc['inputs']['b']['provenance'],'optimizer')
        self.assert_reads(doc)

    def test_file_stored_source_reads_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            AI.configure_state(directory)
            self.assert_reads(MS.load_file())
            before=AI.call('gear_get_design',{'design':'owned'})
            AI.configure_state(directory)
            self.assertEqual(AI.call('gear_get_design',{'design':'owned'}),before)
            self.assertNotEqual(AI.call('gear_rate',{'design':'owned'})['status'],'blocked_invalid_inputs')

    def test_direct_caller_cannot_claim_trusted_provenance(self):
        DS.commit_source(AI._STORE,'owned',MS.load_file(),'source trust boundary')
        head=AI._STORE.head('owned')
        for provenance in ('optimizer','standard_constant'):
            params={'b':{'value':32,'unit':'mm','provenance':provenance}}
            for tool,args in READS:
                with self.subTest(tool=tool,provenance=provenance):
                    out=AI.call(tool,{'params':params,**args})
                    self.assertEqual(out['status'],'blocked_invalid_inputs')
                    self.assertIn('unknown_provenance',{e['code'] for e in out['errors']})
                    mixed=AI.call(tool,{'design':'owned','params':params,**args})
                    self.assertEqual(mixed['status'],'blocked_invalid_inputs')
            p=AI.call('gear_preview_edit',{'design':'owned','edit':{'params':params}})
            self.assertIsNone(p.get('preview_token'))
        self.assertEqual(AI._STORE.head('owned'),head)

    def test_reads_preserve_source_ownership_and_preview_token(self):
        DS.commit_source(AI._STORE,'owned',MS.load_file(),'initial')
        original=copy.deepcopy(AI._STORE.head('owned')['source'])
        edit={'params':{'b':{'value':31,'unit':'mm','provenance':'user'}}}
        preview=AI.call('gear_preview_edit',{'design':'owned','edit':edit})
        self.assertEqual(preview['status'],'preview')
        for tool,args in (('gear_get_design',{}),)+READS:
            out=AI.call(tool,{'design':'owned',**args})
            self.assertNotEqual(out['status'],'blocked_invalid_inputs',out.get('errors'))
        result=AI.call('gear_commit',{'design':'owned','edit':edit,'preview_token':preview['preview_token']})
        self.assertEqual(result['status'],'committed',result)
        head=AI._STORE.head('owned')
        self.assertEqual(head['version'],2)
        self.assertEqual(head['source']['evidence'],original['evidence'])
        self.assertEqual(head['source']['inputs']['b']['value'],31)
        self.assertEqual(AI.call('gear_get_design',{'design':'owned'})['status'],'ok')
        self.assertNotEqual(AI.call('gear_rate',{'design':'owned'})['status'],'blocked_invalid_inputs')


if __name__=='__main__': unittest.main()
