import sys, unittest
from pathlib import Path
from unittest.mock import patch
from gearmath.tools import m33_geometry_replay as replay
from gearmath.tools import m33_native_geometry as native
class GeometryReplayTest(unittest.TestCase):
    def test_current_eight(self):
        r=replay.run(); self.assertEqual(len(r['rows']),8); self.assertEqual(r['status'],'numeric_candidate'); self.assertTrue(all(not x['strict_pass'] for x in r['rows'])); self.assertFalse(r['original_2_of_6_identified'])
    def test_missing_and_duplicate_identity_rejected(self):
        for specs in (replay.SPECS[:-1],replay.SPECS[:-1]+[replay.SPECS[0]]):
            with patch.object(replay,'SPECS',specs), self.assertRaises(ValueError): replay.run()
    def test_reference_tampering_rejected(self):
        with patch.dict(replay.PINS,{7:'0'*64}), self.assertRaises(ValueError): replay.run()
    def test_model_identity_missing_rejected(self):
        specs=list(replay.SPECS); c,k,i,_=specs[0]; specs[0]=(c,k,i,'not_a_quantity')
        with patch.object(replay,'SPECS',specs), self.assertRaises(ValueError): replay.run()
    def test_stale_model_hash_rejected(self):
        r=replay.run(); self.assertTrue(replay.receipt_is_current(r)); r['model_source_hashes']['gearmath/gear/tr30_full58.py']='0'*64; self.assertFalse(replay.receipt_is_current(r))
    def test_producer_stale_rejected(self):
        r=replay.run(); r['producer_sha256']='0'*64; self.assertFalse(replay.receipt_is_current(r))
    def test_native_all_mapped_geometry(self):
        r=native.run(); self.assertEqual(len(r['rows']),64); self.assertEqual(r['unique_counts'],{'formula':50,'input':4,'numerical_method':2}); self.assertEqual(sum(x['status']=='missing_model' for x in r['rows']),0); self.assertEqual(sum(x['status']=='numerical_method' for x in r['rows']),4); self.assertEqual(len({x['quantity'] for x in r['rows'] if x['status']=='numerical_method'}),2); self.assertTrue(all(x.get('relative_error',0)<.01 for x in r['rows'] if x.get('relative_error') is not None)); self.assertTrue(native.receipt_is_current(r)); r['producer_sha256']='0'*64; self.assertFalse(native.receipt_is_current(r))
    def test_native_evidence_tamper(self):
        with patch.dict(native.PINS,{'ex8-native-run.json':'0'*64}), self.assertRaises(ValueError): native.run()
    def test_receipt_integrity(self):
        r=replay.run(); self.assertTrue(replay.verify_receipt(r)); r['rows'][0]['relative_error']=0; self.assertFalse(replay.verify_receipt(r)); r=replay.run(); r['limit']=.1; self.assertFalse(replay.verify_receipt(r)); r=replay.run(); r['rows'][-1]=r['rows'][0]; self.assertFalse(replay.verify_receipt(r))
    def test_mapping_tamper_rejected(self):
        with patch.dict(native.PINS,{'ex7-map.csv':'0'*64}), self.assertRaises(ValueError): native.run()
