"""Adapter contract fixtures below are synthetic software tests, never model evidence."""
import copy
import json
import pathlib
import tempfile
import unittest

from gearmath.tools import bench as B
from gearmath.tools import bench_closure as BC


class TestUnlabelledClosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = B.load_cases()
        cls.outputs = {c["id"]: B.rule_baseline(c["text_zh"]) for c in cls.doc["cases"]}

    def test_all_40_run_without_gold_or_mutation(self):
        before = B.BENCH.read_bytes()
        r, _ = BC.evaluate_outputs(self.outputs)
        self.assertEqual(r["cases"], 40)
        self.assertEqual(r["labeled_cases"], 0)
        self.assertEqual(r["metrics"]["numbers_checked"], 721)
        self.assertEqual(r["metrics"]["numbers_untraceable"], 0)
        self.assertEqual(r["metrics"]["clarification_inconsistent_cases"], [])
        self.assertIsNone(r["metrics"]["compile_accuracy"])
        self.assertEqual(sum(r["metrics"]["outcome_distribution"].values()), 40)
        for row in r["per_case"]:
            for field in row["field_sources"]:
                self.assertTrue(field["sources"], (row["id"], field))
        self.assertEqual(B.BENCH.read_bytes(), before)

    def test_invented_model_reply_is_reported_as_failure(self):
        outputs = copy.deepcopy(self.outputs)
        outputs["GAB-001"]["reply_text"] += "建议模数取123456.789毫米。"
        r, _ = BC.evaluate_outputs(outputs)
        self.assertEqual(r["metrics"]["hallucination_gate"], "FAIL")
        self.assertGreater(r["metrics"]["numbers_untraceable"], 0)
        self.assertGreater(r["metrics"]["hallucinated_number_rate"], 0)

    def test_forged_tool_report_and_hidden_fields_rejected(self):
        outputs = copy.deepcopy(self.outputs)
        outputs["GAB-001"]["compile_result"]["unapplied"][0]["reason"] = "invented numeric claim 98765"
        with self.assertRaisesRegex(ValueError, "differs"):
            BC.evaluate_outputs(outputs)
        outputs = copy.deepcopy(self.outputs)
        outputs["GAB-001"]["hidden_reason"] = "safety 98765"
        with self.assertRaisesRegex(ValueError, "only"):
            BC.evaluate_outputs(outputs)

    def test_direct_and_registered_sources_have_provenance(self):
        out = self.outputs["GAB-039"]
        row = next(c for c in self.doc["cases"] if c["id"] == "GAB-039")
        traces = {x["field"]: x for x in BC.field_sources(row["text_zh"], out)}
        self.assertTrue(any(s["kind"] == "registered_derivation" and s["formula_id"] == "w_to_kw" for s in traces["power_kW"]["sources"]))
        for s in traces["speed_rpm"]["sources"]:
            if s["kind"] == "input_text":
                self.assertEqual(row["text_zh"][slice(*s["span"])], s["quote"])

    def test_missing_case_not_scored_as_complete(self):
        outputs = dict(self.outputs)
        outputs.pop("GAB-040")
        with self.assertRaisesRegex(ValueError, "every benchmark"):
            BC.evaluate_outputs(outputs)

    def _fixture_file(self, tmp):
        """Synthetic adapter validation only; no real model run is claimed by this test."""
        receipt = tmp / "synthetic-test-only.receipt"
        receipt.write_text("SYNTHETIC SOFTWARE TEST ONLY; not external model evidence", encoding="utf-8")
        payload = {"schema": BC.MODEL_SCHEMA, "bench_sha256": BC.file_sha(B.BENCH),
                   "model": {"name": "synthetic-contract-fixture", "version": "test-only"},
                   "run": {"kind": "actual_model_run", "id": "synthetic-contract-test", "provider": "test-only",
                           "started_at": "2026-10-31T00:00:00Z", "completed_at": "2026-10-31T00:01:00Z",
                           "receipt": {"path": receipt.name, "sha256": BC.file_sha(receipt)}},
                   "cases": [{"id": cid, "output": {k: v for k, v in out.items() if k != "compile_result"}} for cid, out in self.outputs.items()]}
        return payload, receipt

    def test_receipt_bound_adapter_contract_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            payload, receipt = self._fixture_file(tmp)
            path = tmp / "fixture.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            report, _ = BC.evaluate_model_file(path)
            self.assertEqual(report["metrics"]["numbers_untraceable"], 0)
            self.assertEqual(report["system"]["output_file_sha256"], BC.file_sha(path))
            receipt.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "receipt"):
                BC.evaluate_model_file(path)

    def test_bad_model_metadata_coverage_and_bench_hash_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            payload, _ = self._fixture_file(tmp)
            for mutate in (lambda p: p["model"].pop("version"),
                           lambda p: p.update(bench_sha256="wrong"),
                           lambda p: p["run"].update(kind="mock"),
                           lambda p: p["run"].update(started_at="2026-10-31"),
                           lambda p: p["cases"].append(p["cases"][0]),
                           lambda p: p["cases"].pop()):
                bad = copy.deepcopy(payload)
                mutate(bad)
                path = tmp / "fixture.json"
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaises(ValueError):
                    BC.evaluate_model_file(path)


if __name__ == "__main__":
    unittest.main()
