import copy
import tempfile
import unittest

from gearmath.gear import h2_flagship as H2, math_source as MS
from gearmath.tools import design_store as DS


class TestM34Closure(unittest.TestCase):
    def test_seed_domain_and_rank_match_old_solver(self):
        from gearmath.tools.m34_closure import compare_h2
        for splits in (None, [2.5, 4], [2, 3, 5]):
            r = compare_h2(ratio_splits=splits)
            self.assertTrue(r['same_candidates'])
            self.assertTrue(r['same_stage_domain'])
            self.assertTrue(r['strict_independent_checks'])
            self.assertLess(r['new_pair_evaluations'], r['old_pair_evaluations'])

    def test_pruning_matches_exhaustive_small_domain(self):
        a = H2.search_seed_domain(mn_series=(2,), ratio_splits=[2.5, 4], prune=True)
        b = H2.search_seed_domain(mn_series=(2,), ratio_splits=[2.5, 4], prune=False)
        self.assertEqual(a['candidates'], b['candidates'])
        self.assertLess(a['pair_evaluations'], b['pair_evaluations'])

    def test_source_owned_chain_rejects_projection_only_write(self):
        for store in (DS.MemoryStore(), DS.FileStore(tempfile.mkdtemp())):
            DS.commit_source(store, 'owned', MS.load_file(), 'initial')
            head = store.head('owned')
            rec = DS.make_record('owned', head, {'baseline':'none','params':{}}, None, {}, [], None)
            with self.assertRaises(DS.SourceOwnershipError):
                store.append('owned', rec)
            self.assertEqual(store.head('owned'), head)

    def test_store_checks_source_hash_before_mutation(self):
        store = DS.MemoryStore()
        rec = DS.import_record('owned', None, MS.load_file(), 'initial')
        rec['source']['inputs']['b']['value'] += 1
        with self.assertRaises(DS.SourceOwnershipError):
            store.append('owned', rec)
        self.assertIsNone(store.head('owned'))

    def test_source_only_change_invalidates_preview_token(self):
        from gearmath.tools import ai_tools as AI
        AI.configure_state(None)
        doc = MS.load_file()
        DS.commit_source(AI._STORE,'owned',doc,'initial')
        edit = {'params':{'b':{'value':31,'unit':'mm','provenance':'user'}}}
        preview = AI.call('gear_preview_edit',{'design':'owned','edit':edit})
        changed = copy.deepcopy(doc)
        changed['note'] = 'new provenance review'
        DS.commit_source(AI._STORE,'owned',changed,'metadata changed')
        result = AI.call('gear_commit',{'design':'owned','edit':edit,'preview_token':preview['preview_token']})
        self.assertEqual(result['status'],'rejected_invalid_token')
        self.assertEqual(AI._STORE.head('owned')['version'],2)
        AI.configure_state(None)

    def test_imported_source_edits_do_not_fall_back_to_baseline(self):
        from gearmath.tools import ai_tools as AI
        AI.configure_state(None)
        doc = MS.load_file()
        doc['inputs']['z_1']['value'] = 23
        DS.commit_source(AI._STORE,'imported',doc,'initial')
        edit = {'params':{'b':{'value':doc['inputs']['b']['value']+1,'unit':'mm','provenance':'user'}}}
        preview = AI.call('gear_preview_edit',{'design':'imported','edit':edit})
        self.assertEqual(preview['status'],'preview',preview)
        result = AI.call('gear_commit',{'design':'imported','edit':edit,'preview_token':preview['preview_token']})
        self.assertEqual(result['status'],'committed',result)
        new = AI._STORE.head('imported')['source']
        self.assertEqual(new['inputs']['z_1'],doc['inputs']['z_1'])
        self.assertEqual(new['evidence'],doc['evidence'])
        self.assertNotEqual(MS.source_sha256(doc),MS.source_sha256(new))
        AI.configure_state(None)


if __name__ == '__main__':
    unittest.main()
