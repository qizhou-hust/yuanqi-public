"""Finite source front acceptance, with authored software scenarios, not oil evidence."""
import copy
import hashlib
import pathlib
import tempfile
import unittest
from unittest import mock

from gearmath.gear import factor_recompute as FR
from gearmath.gear import math_source as MS
from gearmath.gear import source_frontier as SF
from gearmath.gear import source_optimize as SO
from gearmath.kernel import epsilon as EP
from gearmath.kernel import source_doc as SD


def fixture():
    doc = FR.load_doc("K01-spur.factors")
    decl = SO.load_declaration("K01-spur-recompute-local-kxauto")
    zeros = dict.fromkeys((v["name"] for v in decl["variables"]), 0.0)
    spec = {"source": "authored software test subset of existing K01 declaration; no new engineering evidence",
            "axes": {"z_1": [23, 24], "z_2": [68, 72], "m_n": [6.0], "b": [36.0, 44.0, 52.0], "x_1": [0.25]},
            "tolerance_scenarios": [
                {"id": "nominal", "source": "explicit nominal test scenario", "offsets": zeros},
                {"id": "low-width", "source": "authored test perturbation, not measured tolerance", "offsets": {**zeros, "b": -0.1, "x_1": -0.001}},
                {"id": "high-width", "source": "authored test perturbation, not measured tolerance", "offsets": {**zeros, "b": 0.1, "x_1": 0.001}}]}
    return doc, decl, spec


class TestSourceFrontier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc, cls.decl, cls.spec = fixture()
        cls.report = SF.finite_frontier(cls.doc, cls.decl, cls.spec)

    def test_full_finite_coverage_and_fresh_check(self):
        self.assertEqual(self.report["coverage"]["finite_candidates"], 12)
        self.assertGreater(self.report["coverage"]["feasible"], 0)
        self.assertGreater(len(self.report["front"]), 1)
        for p in self.report["points"]:
            self.assertEqual(SD.sha256_of(p["document"]), p["document_sha256"])
            ver = SO.verify_writeback(p["document"], self.decl)
            self.assertEqual(p["status"] == "pass", ver["all_confirmed"])
            self.assertEqual(p["verification"]["objective"], ver["objective"])

    def test_front_exact_dominance_and_no_infeasible_leak(self):
        points = self.report["points"]
        expected = [p["index"] for p in points if p["status"] == "pass" and not any(
            q["status"] == "pass" and EP.dominates(q, p, SF.SENSES) for q in points)]
        self.assertEqual(expected, self.report["front"])
        # Removing center-distance from the comparison must not silently define this report.
        self.assertEqual(set(self.report["senses"]), {"volume_mm3", "center_distance_mm", "safety_min"})
        self.assertGreater(len({points[i]["center_distance_mm"] for i in expected}), 1)

    def test_tolerance_denominator_and_nominal_identity(self):
        for p in self.report["points"]:
            t = p["tolerance"]
            self.assertEqual(t["total"], 3)
            self.assertEqual(sum(t["counts"].values()), 3)
            self.assertEqual(t["feasible_fraction"], t["counts"]["pass"] / 3)
            self.assertEqual(t["scenarios"][0]["status"], p["status"])
            self.assertEqual(t["scenarios"][0].get("volume_mm3"), p.get("volume_mm3"))

    def test_source_spec_declaration_and_implementation_invalidation(self):
        self.assertTrue(SF.is_current(self.report, self.doc, self.decl, self.spec))
        for i, key in ((0, "title"), (1, "description"), (2, "source")):
            args = copy.deepcopy([self.doc, self.decl, self.spec])
            args[i][key] += " changed"
            self.assertFalse(SF.is_current(self.report, *args))
        report = copy.deepcopy(self.report)
        report["identity"]["implementation_sha256"] = "0" * 64
        self.assertFalse(SF.is_current(report, self.doc, self.decl, self.spec))

    def test_missing_limits_not_replaced_and_bad_scenario_counted(self):
        d, dec, s = fixture()
        s["axes"] = {n: [v[0]] for n, v in s["axes"].items()}
        s["tolerance_scenarios"][1]["offsets"]["b"] = -100  # intentional invalid software fixture
        result = SF.finite_frontier(d, dec, s)
        t = result["points"][0]["tolerance"]
        self.assertEqual(t["total"], 3)
        self.assertGreater(t["counts"]["blocked"], 0)
        self.assertFalse(t["all_scenarios_feasible"])
        self.assertLess(t["feasible_fraction"], 1)
        del dec["parameters"]["document_limits"]
        with self.assertRaises(SO.OptimizeBlocked):
            SF.finite_frontier(d, dec, s)

    def test_malformed_specs_rejected_before_enumerating(self):
        for mutation in (lambda s: s.pop("source"), lambda s: s["axes"]["b"].append(float("nan")),
                         lambda s: s["axes"].pop("z_1"), lambda s: s["axes"].update(b=[44.05]),
                         lambda s: s["tolerance_scenarios"][0]["offsets"].pop("b"),
                         lambda s: s["tolerance_scenarios"].append(s["tolerance_scenarios"][0])):
            spec = copy.deepcopy(self.spec)
            mutation(spec)
            with self.assertRaises(ValueError):
                SF.finite_frontier(self.doc, self.decl, spec)

    def test_parent_document_unchanged(self):
        doc, decl, spec = fixture()
        self.assertEqual(self.doc, doc)
        self.assertEqual(self.decl, decl)
        self.assertEqual(self.spec, spec)

    def test_invalid_registered_certificates_block_before_scoring_and_cannot_be_current(self):
        # Temporary certificate copies only: original evidence/reference bytes stay untouched.
        for fault, code in (("expected_hash", "certificate_hash"), ("missing_file", "certificate_missing"),
                            ("changed_bytes", "certificate_hash")):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as td:
                doc, decl, spec = fixture()
                cert = next(r["certificate"] for r in doc["evidence"].values() if r["certificate"]["kind"] == "file")
                original = pathlib.Path(MS.ROOT) / cert["ref"]
                local = pathlib.Path(td) / "certificate.json"
                local.write_bytes(original.read_bytes())
                cert["ref"] = str(local)
                self.assertEqual(MS.verify_certificates(doc), [])
                if fault == "expected_hash":
                    cert["sha256"] = "0" * 64
                elif fault == "missing_file":
                    local.unlink()
                else:
                    local.write_bytes(local.read_bytes() + b"\nchanged certificate bytes\n")
                self.assertIn(code, {e["code"] for e in MS.verify_certificates(doc)})
                # Even a report with freshly copied actual identity must fail the
                # registered expected-hash contract, not merely detect hash drift.
                matching_identity = {"identity": SF.identity(doc, decl, spec)}
                self.assertFalse(SF.is_current(matching_identity, doc, decl, spec))
                with mock.patch.object(SF, "_evaluate") as scorer:
                    with self.assertRaises(SO.OptimizeBlocked) as cm:
                        SF.finite_frontier(doc, decl, spec)
                    self.assertIn(code, {e["code"] for e in cm.exception.errors})
                    scorer.assert_not_called()

    def test_valid_certificate_copy_preserves_holds_and_current_report(self):
        with tempfile.TemporaryDirectory() as td:
            doc, decl, spec = fixture()
            cert = next(r["certificate"] for r in doc["evidence"].values() if r["certificate"]["kind"] == "file")
            local = pathlib.Path(td) / "certificate.json"
            local.write_bytes((pathlib.Path(MS.ROOT) / cert["ref"]).read_bytes())
            cert["ref"] = str(local)
            self.assertEqual(hashlib.sha256(local.read_bytes()).hexdigest(), cert["sha256"])
            spec["axes"] = {n: [v[0]] for n, v in spec["axes"].items()}
            before = copy.deepcopy(doc)
            report = SF.finite_frontier(doc, decl, spec)
            self.assertEqual(report["status"], "ok")
            self.assertTrue(SF.is_current(report, doc, decl, spec))
            self.assertEqual(doc, before)
            for point in report["points"]:
                self.assertEqual(point["document"]["evidence"], before["evidence"])
                self.assertEqual(MS.verify_certificates(point["document"]), [])
                self.assertEqual(SF._evaluate(point["document"], decl)["status"], "pass")
            local.write_bytes(local.read_bytes() + b"changed")
            self.assertFalse(SF.is_current(report, doc, decl, spec))
            # A stored candidate must also fail if evaluated directly after evidence drift.
            checked = SF._evaluate(report["points"][0]["document"], decl)
            self.assertEqual(checked["status"], "blocked")
            self.assertIn("certificate_hash", {e["code"] for e in checked["certificate_errors"]})


if __name__ == "__main__":
    unittest.main()
