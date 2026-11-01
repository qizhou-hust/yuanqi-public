"""Acceptance checks for a counting experiment, independent of gearmath/CAD/FE."""
import importlib.util
from pathlib import Path
import unittest


RUNNER = Path(__file__).with_name("run_enumeration.py")
if RUNNER.exists():
    SPEC = importlib.util.spec_from_file_location("library_enumeration", RUNNER)
    ENUM = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(ENUM)
else:
    ENUM = None


class EnumerationAcceptance(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ENUM, "The requested counting runner is not implemented")

    def test_geometric_count_four_and_six_letters(self):
        self.assertEqual(ENUM.geometric_sum(4, 4), 340)
        self.assertEqual(ENUM.geometric_sum(6, 4), 1554)
        self.assertEqual(len(list(ENUM.words(ENUM.FOUR, 4))), 340)
        self.assertEqual(len(list(ENUM.words(ENUM.SIX, 4))), 1554)

    def test_weight_two_macro_coefficients(self):
        self.assertEqual([ENUM.weighted_count(4, n) for n in range(1, 5)], [4, 17, 72, 305])
        self.assertEqual([ENUM.weighted_count(6, n) for n in range(1, 5)], [6, 37, 228, 1405])

    def test_duplicate_macro_is_an_alias(self):
        macros = {"M": ("P", "P"), "M_ALIAS": ("P", "P")}
        direct = ENUM.evaluate(("P", "P"), macros=macros)
        for expression in [("M",), ("M_ALIAS",)]:
            self.assertEqual(ENUM.evaluate(expression, macros=macros)["semantic_signature"], direct["semantic_signature"])
        four_planetaries = ENUM.evaluate(("P", "P", "P", "P"))
        self.assertEqual(ENUM.evaluate(("M", "M"))["semantic_signature"], four_planetaries["semantic_signature"])

    def test_reverse_order_must_not_collapse(self):
        hw, wh = ENUM.evaluate(("H", "W")), ENUM.evaluate(("W", "H"))
        self.assertNotEqual(hw["semantic_signature"], wh["semantic_signature"])
        self.assertEqual(hw["decision"], "abstract_candidate")
        self.assertEqual(wh["decision"], "abstract_candidate")
        self.assertEqual(ENUM.evaluate(("H", "W"), profile="worm_terminal")["reasons"], [])
        self.assertEqual(ENUM.evaluate(("W", "H"), profile="worm_terminal")["reasons"], ["WORM_NOT_TERMINAL"])

    def test_budget_counts_expanded_physical_stages(self):
        self.assertEqual(ENUM.evaluate(("M", "M"))["physical_stage_count"], 4)
        for expr, expanded in [(("M", "M", "P"), 5), (("M",) * 4, 8)]:
            result = ENUM.evaluate(expr)
            self.assertEqual(result["physical_stage_count"], expanded)
            self.assertIn("PHYSICAL_STAGE_BUDGET_EXCEEDED", result["reasons"])

    def test_all_reasons_survive_no_first_failure_short_circuit(self):
        result = ENUM.evaluate(("W", "W", "P", "M"), profile="worm_terminal")
        self.assertEqual(result["reasons"], ["PHYSICAL_STAGE_BUDGET_EXCEEDED", "WORM_MULTIPLICITY_LIMIT", "WORM_NOT_TERMINAL"])

    def test_planetary_roles_are_distinct_semantics(self):
        roles = ENUM.PLANETARY_ROLES
        self.assertEqual(len({r["semantic_id"] for r in roles}), 6)
        self.assertEqual(len({(r["fixed"], r["input"], r["output"]) for r in roles}), 6)
        self.assertTrue(all(r["physical_stage_weight"] == 1 for r in roles))

    def test_spur_and_helical_share_topology_parent(self):
        self.assertEqual(ENUM.ATOMS["H"]["geometry_subfamilies"], ["spur", "parallel_helical"])
        self.assertEqual(ENUM.ATOMS["I"]["plugin_family"], ENUM.ATOMS["H"]["plugin_family"])
        self.assertNotEqual(ENUM.ATOMS["I"]["semantic_id"], ENUM.ATOMS["H"]["semantic_id"])

    def test_port_admission_is_not_spatial_assembly(self):
        result = ENUM.evaluate(("H", "W", "B", "X"))
        self.assertEqual(result["port_admission"], "admitted")
        self.assertEqual(result["decision"], "abstract_candidate")
        self.assertEqual(result["spatial_embeddability"], "OPEN")
        self.assertEqual(ENUM.port_reasons([("rotation", "translation"), ("rotation", "rotation")]), ["PORT_TYPE_MISMATCH:1->2"])

    def test_domain_audit_conserves_all_raw_expressions(self):
        for alphabet, canonical, raw, accepted in [(ENUM.FOUR, 340, 780, 398), (ENUM.SIX, 1554, 2800, 1676)]:
            result = ENUM.enumerate_domain(alphabet)
            self.assertEqual(len(result["canonical"]), canonical)
            self.assertEqual(result["counts"]["macro_expression_domain_before_budget"], raw)
            self.assertEqual(result["counts"]["weighted_macro_expressions_admitted"], accepted)
            self.assertEqual(len(result["rejected"]) + accepted, raw)

    def test_optional_policy_is_disclosed_and_not_a_base_rule(self):
        four = ENUM.enumerate_domain(ENUM.FOUR)
        six = ENUM.enumerate_domain(ENUM.SIX)
        self.assertEqual(four["counts"]["worm_terminal_policy"]["admitted"], 160)
        self.assertEqual(six["counts"]["worm_terminal_policy"]["admitted"], 936)
        self.assertEqual(six["counts"]["plain_ordered_sequences"], 1554)

    def test_unknown_token_is_rejected(self):
        self.assertEqual(ENUM.evaluate(("UNKNOWN",))["reasons"], ["UNKNOWN_TOKEN:UNKNOWN"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
