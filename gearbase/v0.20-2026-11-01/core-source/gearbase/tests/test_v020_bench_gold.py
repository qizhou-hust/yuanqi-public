"""Synthetic labels only: never populate the actual forty-question gold file."""
import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from gearmath.tools import bench as B, bench_gold as G


def synthetic_doc():
    return {'schema': 'gearbase.agent-bench/1', 'version': 'synthetic-test-only',
            'cases': [{'id': f'TEST-{i:03}', 'text_zh': '未知需求。',
                       'gold': {'status': 'pending_engineer_label'}} for i in range(40)]}


def signed_synthetic(doc):
    form = G.template(doc)
    form['implementation_authors'] = ['Synthetic Implementer']
    form['independence_attested'] = True
    form['reviewer_role'] = 'gear_engineer'
    for row in form['cases']:
        row['gold'] = {'status': 'labeled', 'annotator': 'Synthetic Independent Engineer',
                       'labeled_at': '2026-11-01', 'expected_outcome': 'needs_clarification',
                       'expected_structured_requirement': {}, 'expected_questions': ['speed_rpm'],
                       'expected_key_points': 'Synthetic test, no actual engineer annotation', 'scoring_rule': None}
    return form


class GoldBenchTests(unittest.TestCase):
    def test_documented_compiled_outcome_matches_pending_confirmation(self):
        doc = {'version': 'synthetic-test-only', 'cases': [{'id': 'TEST', 'text_zh': '传动比2',
               'gold': {'status': 'labeled', 'expected_outcome': 'compiled',
                        'expected_structured_requirement': {'ratio': 2}, 'expected_questions': []}}]}
        out = B.evaluate(lambda text: {'parsed_requirement': {'ratio': 2},
            'compile_result': {'status': 'pass_pending_human_confirmation', 'questions': []}, 'reply_text': ''}, doc)
        self.assertEqual(out['metrics']['compile_accuracy'], 1)
        self.assertEqual(out['per_case'][0]['status'], 'pass_pending_human_confirmation')

    def test_blank_template_never_supplies_answers(self):
        before = B.BENCH.read_bytes()
        form = G.template()
        self.assertEqual(len(form['cases']), 40)
        self.assertIsNone(form['implementation_authors'])
        for row in form['cases']:
            self.assertEqual(row['gold']['status'], 'pending_engineer_label')
            self.assertIsNone(row['gold']['expected_structured_requirement'])
        with self.assertRaises(ValueError): G.apply(form)
        self.assertEqual(before, B.BENCH.read_bytes())

    def test_complete_signed_synthetic_import_and_metrics(self):
        doc = synthetic_doc(); before = copy.deepcopy(doc)
        annotated, receipt = G.apply(signed_synthetic(doc), doc)
        self.assertTrue(receipt['complete'])
        self.assertEqual(receipt['labeled_cases'], 40)
        self.assertEqual(doc, before)
        result = B.evaluate(lambda text: {'parsed_requirement': {}, 'compile_result': {
            'status': 'needs_clarification', 'questions': [{'field': 'speed_rpm', 'question': '请提供转速'}]}, 'reply_text': ''}, annotated)
        for name in ('compile_accuracy', 'clarification_precision', 'clarification_recall'):
            self.assertEqual(result['metrics'][name], 1)

    def test_missing_duplicate_stale_signature_or_custom_rule_is_rejected(self):
        doc = synthetic_doc(); base = signed_synthetic(doc)
        edits = [lambda f: f['cases'].pop(),
                 lambda f: f['cases'].__setitem__(1, copy.deepcopy(f['cases'][0])),
                 lambda f: f.update(benchmark_sha256='0'*64),
                 lambda f: f.update(independence_attested=False),
                 lambda f: f.update(implementation_authors=['Synthetic Independent Engineer']),
                 lambda f: f['cases'][0]['gold'].update(labeled_at=None),
                 lambda f: f['cases'][0]['gold'].update(annotator='   '),
                 lambda f: f['cases'][0]['gold'].update(scoring_rule={'ignore': 'numbers'}),
                 lambda f: f['cases'][0]['gold'].update(expected_structured_requirement={'ratio': float('nan')})]
        for edit in edits:
            form=copy.deepcopy(base);edit(form)
            with self.subTest(edit=edit), self.assertRaises(ValueError):G.apply(form, doc)

    def test_cli_synthetic_roundtrip_preserves_actual_benchmark(self):
        before=B.BENCH.read_bytes();doc=synthetic_doc()
        with tempfile.TemporaryDirectory() as td:
            folder=pathlib.Path(td);labels=folder/'submitted.json';out=folder/'result'
            labels.write_text(json.dumps(signed_synthetic(doc)),encoding='utf8')
            with patch.object(B,'load_cases',return_value=doc):
                self.assertEqual(G.main(['--labels',str(labels),'--out',str(out)]),0)
            self.assertEqual(json.loads((out/'result.json').read_text())['pending_engineer_label'],0)
            self.assertEqual(json.loads((out/'annotated-benchmark.json').read_text())['cases'][0]['id'],'TEST-000')
        self.assertEqual(before,B.BENCH.read_bytes())

    def test_blank_cli_cannot_overwrite_source(self):
        before=B.BENCH.read_bytes()
        with self.assertRaises(SystemExit):G.main(['--template',str(B.BENCH)])
        self.assertEqual(before,B.BENCH.read_bytes())


if __name__ == '__main__': unittest.main()
