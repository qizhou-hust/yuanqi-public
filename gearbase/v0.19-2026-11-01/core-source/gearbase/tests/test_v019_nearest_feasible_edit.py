"""Exact categorical nearest-feasible edits; real finite joint capability probe."""
import copy
import importlib.util
import itertools
import json
import pathlib
import subprocess
import sys
import unittest
from fractions import Fraction

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('edit_probe', ROOT / 'tests/test_v017_system_optimize.py')
probe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_module)


def request():
    return {'target': {'gear': 'original', 'shaft': 'weak', 'bearing': 'low'},
            'metric': {'kind': 'weighted_hamming',
                       'weights': {'gear': '1', 'shaft': '2', 'bearing': '0.1'}},
            'constraints': {'pass_scopes': ['gear_rating', 'shaft', 'bearing', 'key']},
            'source': 'Authored test request; no real engineering selection'}


class TestNearestFeasibleEdit(unittest.TestCase):
    def test_feature_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('gearmath.product.nearest_feasible_edit'))

    def test_full_enumeration_independently_matches_exact_distance_and_ties(self):
        from gearmath.product.nearest_feasible_edit import propose
        from gearmath.product import design_check as DC
        doc, si, domain = probe_module.probe()
        req = request()
        before = copy.deepcopy((doc, si, domain, req))
        expected = []
        for g, s, b in itertools.product(domain['gear'], domain['shaft'], domain['bearing']):
            d, system = copy.deepcopy((doc, si))
            d['inputs'].update(g['inputs'])
            system.update(shafts=s['shafts'], keys=s['keys'], bearings=b['bearings'])
            checked = DC.check(d, system, req['constraints']['pass_scopes'])
            if all(checked['checks'][scope]['status'] == 'pass' for scope in req['constraints']['pass_scopes']):
                ids = [g['id'], s['id'], b['id']]
                distance = sum((Fraction(req['metric']['weights'][axis])
                                for axis, candidate in zip(('gear', 'shaft', 'bearing'), ids)
                                if candidate != req['target'][axis]), Fraction())
                expected.append((distance, ids))
        expected.sort()
        got = propose(doc, si, domain, req)
        self.assertEqual(got['status'], 'completed', got)
        self.assertEqual([(Fraction(r['distance']), r['ids']) for r in got['feasible']], expected)
        self.assertEqual(got['nearest'], got['feasible'][0])
        self.assertEqual([r['ids'] for r in got['ties']], [ids for dist, ids in expected if dist == expected[0][0]])
        self.assertGreater(len(got['ties']), 1)
        self.assertFalse(got['target_feasible'])
        self.assertEqual(before, (doc, si, domain, req))
        self.assertTrue(got['read_only'])

    def test_zero_distance_target_and_stale_identity(self):
        from gearmath.product.nearest_feasible_edit import propose
        d, s, p = probe_module.probe()
        req = request()
        first = propose(d, s, p, req)
        req['target'] = dict(zip(('gear', 'shaft', 'bearing'), first['nearest']['ids']))
        second = propose(d, s, p, req)
        self.assertEqual(second['nearest']['distance'], '0')
        self.assertTrue(second['target_feasible'])
        self.assertNotEqual(first['problem_sha256'], second['problem_sha256'])
        stale = propose(d, s, p, req, expected_problem_sha256=first['problem_sha256'])
        self.assertEqual(stale['status'], 'rejected_stale_proposal')
        self.assertIsNone(stale['nearest'])
        same = propose(d, s, p, req, expected_problem_sha256=second['problem_sha256'])
        self.assertEqual(same, second)

    def test_missing_unknown_or_invalid_request_never_supplies_defaults(self):
        from gearmath.product.nearest_feasible_edit import propose
        d, s, p = probe_module.probe()
        for mutate in (lambda r: r.pop('metric'),
                       lambda r: r['target'].update(gear='unknown'),
                       lambda r: r['target'].update(gear=True),
                       lambda r: r['target'].update(gear=2),
                       lambda r: r['target'].update(gear='2'),
                       lambda r: r['target'].update(gear=[]),
                       lambda r: r['metric']['weights'].update(gear='0'),
                       lambda r: r['metric']['weights'].update(gear=True),
                       lambda r: r['metric']['weights'].update(gear='NaN'),
                       lambda r: r['constraints'].update(pass_scopes=['gear_rating']),
                       lambda r: r.update(source=''),
                       lambda r: r.update(apply=True)):
            req = request()
            mutate(req)
            with self.subTest(request=req):
                result = propose(d, s, p, req)
                self.assertEqual(result['status'], 'blocked', result)
                self.assertIsNone(result['nearest'])

    def test_no_feasible_domain_and_missing_certificate_are_distinct(self):
        from gearmath.product.nearest_feasible_edit import propose
        d, s, p = probe_module.probe()
        p['gear'] = p['gear'][:1]
        req = request()
        req['target']['gear'] = 'thin'
        result = propose(d, s, p, req)
        self.assertEqual(result['status'], 'completed', result)
        self.assertIsNone(result['nearest'])
        self.assertEqual(result['feasible'], [])
        d['evidence'][next(iter(d['evidence']))].pop('certificate', None)
        result = propose(d, s, p, req)
        self.assertEqual(result['status'], 'blocked', result)
        self.assertIsNone(result['nearest'])

    def test_source_domain_and_certificate_changes_reject_previous_proposal(self):
        from gearmath.product.nearest_feasible_edit import propose
        d, s, p = probe_module.probe()
        first = propose(d, s, p, request())
        d['inputs']['b']['source'] += ' changed source provenance'
        changed = propose(d, s, p, request(), expected_problem_sha256=first['problem_sha256'])
        self.assertEqual(changed['status'], 'rejected_stale_proposal')
        p['bearing'][1]['source'] += ' changed'
        result = propose(d, s, p, request(), expected_problem_sha256=first['problem_sha256'])
        self.assertEqual(result['status'], 'rejected_stale_proposal')
        p['bearing'].append(copy.deepcopy(p['bearing'][1]))
        result = propose(d, s, p, request())
        self.assertEqual(result['status'], 'blocked', result)
        self.assertIsNone(result['nearest'])
        p['bearing'].pop()
        cert = next(v['certificate'] for v in d['evidence'].values() if v['certificate']['kind'] == 'file')
        cert['sha256'] = '0' * 64
        result = propose(d, s, p, request(), expected_problem_sha256=first['problem_sha256'])
        self.assertEqual(result['status'], 'blocked', result)
        self.assertIsNone(result['nearest'])

    def test_registered_readonly_real_tool_call_and_stdio(self):
        from gearmath.tools import ai_tools
        d, s, p = probe_module.probe()
        args = {'design_doc': d, 'system_input': s, 'domain': p, 'request': request()}
        tool = next(t for t in ai_tools.TOOLS if t['name'] == 'nearest_feasible_edit')
        self.assertTrue(tool['annotations']['readOnlyHint'])
        self.assertFalse(tool['inputSchema']['additionalProperties'])
        result = ai_tools.call('nearest_feasible_edit', args)
        self.assertEqual(result['status'], 'completed', result)
        rpc = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
               'params': {'name': 'nearest_feasible_edit', 'arguments': args}}
        proc = subprocess.run([sys.executable, '-I', '-S', str(ROOT / 'mcp_server.py')],
                              input=json.dumps(rpc)+'\n', capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        response = json.loads(proc.stdout.splitlines()[-1])
        self.assertEqual(json.loads(response['result']['content'][0]['text']), result)


if __name__ == '__main__':
    unittest.main()
