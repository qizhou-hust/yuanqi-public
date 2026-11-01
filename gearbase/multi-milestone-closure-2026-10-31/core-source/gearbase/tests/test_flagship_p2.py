"""P2 Stage0 regression against the frozen original, never a production dependency."""
import copy
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

from gearmath.gear import flagship_p2 as P2

ROOT = Path(__file__).resolve().parents[1]
INPUTS = dict(n1_rpm=1440.0, target_total_ratio=40.0, np_options=[3, 4],
              zs_range=[14, 30], zp_range=[18, 60], m_series=[2.0, 2.5, 3.0],
              i_tol=0.02, top_k=5)


def oracle(inputs):
    script = ('import json,sys; sys.path.insert(0,sys.argv[1]); '
              'from gears.solver import synthesize_p2; '
              'print(json.dumps(synthesize_p2(**json.loads(sys.argv[2]))))')
    return json.loads(subprocess.check_output(
        [sys.executable, '-c', script, str(ROOT/'archive/m31/src'), json.dumps(inputs)],
        text=True, encoding='utf-8'))


class TestP2Stage0(unittest.TestCase):
    def test_original_flagship_candidates_front_and_counts(self):
        old, new = oracle(INPUTS), P2.stage0(INPUTS)
        self.assertEqual(old['candidates'], new['candidates'])
        for k in ('enumerated', 'feasible', 'pairs_examined', 'in_tolerance_pairs', 'pareto_points'):
            self.assertEqual(old['search'][k], new['search'][k])
        self.assertEqual(new['frontier'], new['candidates'])
        self.assertTrue(new['search']['complete'])
        self.assertEqual(new['strength']['status'], 'not_implemented')
        for c in new['candidates']:
            self.assertTrue(P2.verify(INPUTS, c)['ok'])

    def test_small_domain_full_enumeration(self):
        p = dict(INPUTS, zs_range=[14, 17], zp_range=[18, 24],
                 target_total_ratio=25.0, i_tol=0.4, top_k=100)
        new, old = P2.stage0(p), oracle(p)
        self.assertEqual(new['candidates'], old['candidates'])
        stages = []
        for n, s, z in itertools.product(p['np_options'], range(14,18), range(18,25)):
            if (2*s+2*z) % n == 0 and (s+z)*math.sin(math.pi/n) > z+2:
                stages.append((s,z,n,1+(s+2*z)/s))
        rows = []
        for a,b in itertools.combinations_with_replacement(stages,2):
            err = abs(a[3]*b[3]-25)/25
            if err <= .4:
                rows.append((err,max(a[3],b[3])))
        self.assertEqual(new['search']['in_tolerance_pairs'],len(rows))
        # Independently compute nondominated objective points (strict dominance).
        front = sorted(set(x for x in rows if not any(
            y[0] <= x[0] and y[1] <= x[1] and y != x for y in rows)))
        self.assertEqual([(x['ratio_error_rel'],x['max_stage_ratio']) for x in new['frontier']],front)

    def test_top_k_and_module_order(self):
        for k in (1,2,9):
            p = dict(INPUTS, top_k=k, m_series=[3.0,2.0])
            r = P2.stage0(p)
            self.assertEqual(r['candidates'],oracle(p)['candidates'])
            self.assertEqual(r['candidates'],r['frontier'][:k])
            self.assertEqual(r['candidates'][0]['stage1']['m_options'],[3.0,2.0])

    def test_empty_feasible(self):
        p = dict(INPUTS, target_total_ratio=400.0,zs_range=[14,16],zp_range=[18,20])
        r = P2.stage0(p)
        self.assertFalse(r['ok'])
        self.assertTrue(r['reason'])
        self.assertEqual(r['candidates'],oracle(p)['candidates'])

    def test_strict_adjacency_boundary_zero_tolerance_and_pair_cap(self):
        # n_p=2, zs=2: chord equals the required diameter exactly; reject.
        p=dict(INPUTS,zs_range=[2,2],zp_range=[2,2],np_options=[2],m_series=[2.0])
        r=P2.stage0(p)
        self.assertEqual(r['search']['feasible'],0)
        self.assertEqual(r['candidates'],oracle(p)['candidates'])
        p=dict(INPUTS,i_tol=0.0)
        self.assertEqual(P2.stage0(p)['candidates'],oracle(p)['candidates'])
        # Stage-check budget is legal, but the feasible pair count exceeds cap.
        with self.assertRaisesRegex(ValueError,'pair cap'):
            P2.stage0(dict(INPUTS,zs_range=[14,180],zp_range=[18,180],
                          np_options=[3],m_series=[2.0]))

    def test_missing_unknown_invalid_fail_closed(self):
        for key in INPUTS:
            p = dict(INPUTS); del p[key]
            with self.assertRaises(ValueError): P2.stage0(p)
        bad = [('n1_rpm',0),('n1_rpm',True),('n1_rpm',float('nan')),
               ('target_total_ratio',.5),('i_tol',-1),('i_tol',float('inf')),
               ('zs_range',[1,2.5]),('zs_range',[20,14]),('zp_range',[0,5]),
               ('np_options',[0]),('np_options',[2.5]),('np_options',[]),
               ('m_series',[]),('m_series',[-2]),('m_series',[True]),
               ('top_k',0),('top_k',1.5),('alien',1),('zs_range',[1,1000000])]
        for key,value in bad:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                P2.stage0(dict(INPUTS,**{key:value}))

    def test_verify_tampering_out_of_domain_phasing_adjacency(self):
        c = P2.stage0(INPUTS)['candidates'][0]
        for path,value in [('zr',99),('n_p',5),('zs',1),('ratio',100),
                           ('chord_mm',0),('m_options',[99]),('zp',61)]:
            x=copy.deepcopy(c); x['stage1'][path]=value
            self.assertFalse(P2.verify(INPUTS,x)['ok'])
        for key in ('i_total','ratio_error_rel','n_mid_rpm','n_out_rpm'):
            x=copy.deepcopy(c); x[key]=float('nan')
            self.assertFalse(P2.verify(INPUTS,x)['ok'])
        for s,z,n in [(14,18,3),(14,60,4)]:
            x=copy.deepcopy(c); x['stage1'].update(zs=s,zp=z,zr=s+2*z,n_p=n)
            self.assertFalse(P2.verify(INPUTS,x)['ok'])


if __name__ == '__main__': unittest.main()
