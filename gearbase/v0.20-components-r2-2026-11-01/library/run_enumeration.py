"""Reproducible, stdlib-only ABSTRACT topology counting experiment.

This is report evidence, not a transmission selector, CAD or rating service.
It imports nothing from the frozen source tree and only reads its Git state.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
from math import comb
from pathlib import Path
import subprocess


GRAMMAR_ID = "serial-reducer-abstract-v1.0.0"
SOURCE_ROOT = Path("D:/my_Works/Gears/gearbase-v020-work")
FROZEN_COMMIT = "80117283778cf8732b5557fa15c2e41f626f92fc"
BUDGET = 4
FOUR = ("P", "H", "B", "W")
SIX = FOUR + ("I", "X")
MACROS = {"M": ("P", "P")}
TECHNICAL_REFERENCES = [
    {"id": "mathworks-planetary-gear", "url": "https://www.mathworks.com/help/sdl/ref/planetarygear.html", "accessed_date": "2026-11-01", "supports": "C/R/S rotational ports; (1+q)*omega_C=omega_S+q*omega_R; q>1", "does_not_support": "Existence or viability of any enumerated industrial assembly"},
    {"id": "cmu-mechanisms-ch7", "url": "https://www.cs.cmu.edu/~rapidproto/mechanisms/chpt7.html", "accessed_date": "2026-11-01", "supports": "Gear classification by parallel, intersecting, and neither-parallel-nor-intersecting axes", "does_not_support": "Spatial assembly, strength or industrial precedent of any generated chain"},
    {"id": "khk-gear-types", "url": "https://khkgears.net/korea/types-of-gears.html", "accessed_date": "2026-11-01", "supports": "Physical distinction of external/internal mesh and examples of gear categories", "does_not_support": "This report's six-atom vocabulary being exhaustive"},
]

# Stage weight means a serial ratio transformation, not a tooth-contact count.
# All axes, sizes, teeth, helix hands, loads and supports remain unbound.
ATOMS = {
    "P": {"semantic_id": "planetary.simple.fixed_R.in_S.out_C.v1", "plugin_family": "planetary_simple", "name_zh": "单排行星：齿圈固定、太阳轮输入、行星架输出", "axis_relation": "coaxial", "geometry_subfamilies": ["unbound"], "reaction": "ring_grounded"},
    "H": {"semantic_id": "cylindrical.parallel.external_pair.v1", "plugin_family": "cylindrical_parallel", "name_zh": "平行轴外啮合圆柱齿轮副", "axis_relation": "parallel_offset", "geometry_subfamilies": ["spur", "parallel_helical"], "reaction": "housing_support_required"},
    "B": {"semantic_id": "bevel.intersecting_pair.v1", "plugin_family": "bevel", "name_zh": "相交轴锥齿轮副", "axis_relation": "intersecting", "geometry_subfamilies": ["unbound"], "reaction": "housing_support_required"},
    "W": {"semantic_id": "worm.in_worm.out_wheel.v1", "plugin_family": "worm", "name_zh": "蜗杆输入、蜗轮输出齿轮副", "axis_relation": "skew", "geometry_subfamilies": ["unbound"], "reaction": "housing_support_required"},
    "I": {"semantic_id": "cylindrical.parallel.internal_pair.v1", "plugin_family": "cylindrical_parallel", "name_zh": "平行轴内啮合圆柱齿轮副", "axis_relation": "parallel_offset", "geometry_subfamilies": ["spur", "parallel_helical"], "reaction": "housing_support_required"},
    "X": {"semantic_id": "cylindrical.crossed_helical_pair.v1", "plugin_family": "cylindrical_crossed", "name_zh": "交错轴斜齿轮副", "axis_relation": "skew", "geometry_subfamilies": ["crossed_helical"], "reaction": "housing_support_required"},
}
for _atom in ATOMS.values():
    _atom.update({"input_port": "rotation", "output_port": "rotation", "physical_stage_weight": 1, "definition_evidence": "ASSUMED", "industrial_precedent": "OPEN"})

# Six fixed/input/output permutations are NOT deduplicated by the parent family.
# q=z_R/z_S>1. Signed i=omega_input/omega_output, common positive axis convention.
PLANETARY_ROLES = [
    {"fixed": "R", "input": "S", "output": "C", "signed_ratio": "1+q", "reduction_magnitude_gt_1": True},
    {"fixed": "R", "input": "C", "output": "S", "signed_ratio": "1/(1+q)", "reduction_magnitude_gt_1": False},
    {"fixed": "S", "input": "R", "output": "C", "signed_ratio": "(1+q)/q", "reduction_magnitude_gt_1": True},
    {"fixed": "S", "input": "C", "output": "R", "signed_ratio": "q/(1+q)", "reduction_magnitude_gt_1": False},
    {"fixed": "C", "input": "S", "output": "R", "signed_ratio": "-q", "reduction_magnitude_gt_1": True},
    {"fixed": "C", "input": "R", "output": "S", "signed_ratio": "-1/q", "reduction_magnitude_gt_1": False},
]
for _role in PLANETARY_ROLES:
    _role.update({"semantic_id": f"planetary.simple.fixed_{_role['fixed']}.in_{_role['input']}.out_{_role['output']}.v1", "physical_stage_weight": 1, "industrial_precedent": "OPEN"})


def geometric_sum(k: int, max_stages: int) -> int:
    return max_stages if k == 1 else (k ** (max_stages + 1) - k) // (k - 1)


def words(alphabet, max_tokens):
    for length in range(1, max_tokens + 1):
        yield from itertools.product(alphabet, repeat=length)


def weighted_count(k: int, physical_stages: int, macro_types: int = 1) -> int:
    """Coefficient of x^n in 1/(1-k*x-m*x^2), independent of enumeration."""
    n = physical_stages
    return sum(comb(n - j, j) * k ** (n - 2 * j) * macro_types ** j for j in range(n // 2 + 1))


def port_reasons(stage_ports):
    return [f"PORT_TYPE_MISMATCH:{i + 1}->{i + 2}" for i in range(len(stage_ports) - 1) if stage_ports[i][1] != stage_ports[i + 1][0]]


def evaluate(tokens, *, macros=None, profile=None):
    """Expand flat, explicitly declared macros; retain ALL applicable reasons.

    The only optional policy is a hypothetical worm-at-terminal application
    contract. A policy rejection does not assert physical impossibility.
    """
    macros = MACROS if macros is None else macros
    reasons, expanded = [], []
    if not tokens:
        reasons.append("EMPTY_CHAIN")
    for token in tokens:
        if token in ATOMS:
            expanded.append(token)
        elif token in macros:
            for child in macros[token]:
                if child in ATOMS:
                    expanded.append(child)
                else:
                    reasons.append(f"NON_ATOMIC_MACRO_CHILD:{token}:{child}")
        else:
            reasons.append(f"UNKNOWN_TOKEN:{token}")
    fully_expanded = not any(r.startswith(("UNKNOWN_TOKEN:", "NON_ATOMIC_MACRO_CHILD:")) for r in reasons)
    if len(expanded) > BUDGET:
        reasons.append("PHYSICAL_STAGE_BUDGET_EXCEEDED")
    interface_reasons = port_reasons([(ATOMS[x]["input_port"], ATOMS[x]["output_port"]) for x in expanded])
    reasons.extend(interface_reasons)
    if profile == "worm_terminal":
        if expanded.count("W") > 1:
            reasons.append("WORM_MULTIPLICITY_LIMIT")
        if any(x == "W" and i != len(expanded) - 1 for i, x in enumerate(expanded)):
            reasons.append("WORM_NOT_TERMINAL")
    elif profile is not None:
        raise ValueError(f"Undeclared profile: {profile}")
    return {
        "expression": list(tokens), "expanded_atom_word": expanded,
        "semantic_signature": " > ".join(ATOMS[x]["semantic_id"] for x in expanded) if fully_expanded else None,
        "family_order_signature": " > ".join(ATOMS[x]["plugin_family"] for x in expanded) if fully_expanded else None,
        "physical_stage_count": len(expanded) if fully_expanded else None,
        "port_admission": "admitted" if fully_expanded and not interface_reasons else "not_admitted",
        "decision": "rejected_by_declared_rules" if reasons else "abstract_candidate",
        "spatial_embeddability": "OPEN", "reasons": reasons,
    }


def enumerate_domain(alphabet):
    canonical, rejected = {}, []
    by_weight = Counter()
    for expression in words(tuple(alphabet) + tuple(MACROS), BUDGET):
        result = evaluate(expression)
        if result["reasons"]:
            rejected.append(result)
            continue
        signature = result["semantic_signature"]
        if signature not in canonical:
            canonical[signature] = {**result, "representations": []}
        canonical[signature]["representations"].append(list(expression))
        by_weight[result["physical_stage_count"]] += 1
    k = len(alphabet)
    expected = geometric_sum(k, BUDGET)
    weighted = [weighted_count(k, n) for n in range(1, BUDGET + 1)]
    assert len(canonical) == expected
    assert [by_weight[n] for n in range(1, BUDGET + 1)] == weighted
    pure_atom_signatures = {evaluate(w)["semantic_signature"] for w in words(alphabet, BUDGET)}
    assert set(canonical) == pure_atom_signatures
    optional_rejected, optional_counts = [], Counter()
    for candidate in canonical.values():
        result = evaluate(candidate["expanded_atom_word"], profile="worm_terminal")
        if result["reasons"]:
            optional_rejected.append(result)
            optional_counts.update(result["reasons"])
    # Closed form for either no W or precisely one terminal W.
    optional_expected = sum((k - 1) ** n + (k - 1) ** (n - 1) for n in range(1, BUDGET + 1))
    assert expected - len(optional_rejected) == optional_expected
    raw = geometric_sum(k + len(MACROS), BUDGET)
    assert raw == sum(weighted) + len(rejected)
    return {
        "canonical": canonical, "rejected": rejected, "optional_rejected": optional_rejected,
        "counts": {
            "alphabet": list(alphabet), "semantic_atom_count": k,
            "plugin_family_count": len({ATOMS[x]["plugin_family"] for x in alphabet}),
            "plain_by_physical_stages": {str(n): k ** n for n in range(1, BUDGET + 1)},
            "plain_ordered_sequences": expected,
            "geometric_closed_form": f"({k}^5-{k})/({k}-1)",
            "geometric_closed_form_result": expected,
            "macro_expression_domain_before_budget": raw,
            "weighted_macro_expressions_by_physical_stages": {str(n): weighted[n - 1] for n in range(1, BUDGET + 1)},
            "weighted_macro_expressions_admitted": sum(weighted),
            "stage_budget_rejected_expressions": len(rejected),
            "expanded_unique_semantic_topologies": len(canonical),
            "macro_alias_expressions_beyond_canonical": sum(weighted) - len(canonical),
            "family_order_groups_not_semantic_dedup": len({c["family_order_signature"] for c in canonical.values()}),
            "first_release_at_most_two_physical_stages": geometric_sum(k, 2),
            "at_most_three_physical_stages": geometric_sum(k, 3),
            "worm_terminal_policy": {
                "active_in_base_grammar": False, "evidence_state": "ASSUMED",
                "meaning": "Hypothetical application contract: at most one W and W only at the final expanded physical stage.",
                "admitted": optional_expected, "rejected": len(optional_rejected),
                "reason_occurrences_overlap": dict(sorted(optional_counts.items())),
            },
        },
    }


def negative_probes():
    direct = evaluate(("P", "P"))
    duplicate_alias = evaluate(("M_ALIAS",), macros={"M_ALIAS": ("P", "P")})
    hw, wh = evaluate(("H", "W")), evaluate(("W", "H"))
    over = evaluate(("M", "M", "P"))
    all_reasons = evaluate(("W", "W", "P", "M"), profile="worm_terminal")
    probes = [
        {"id": "duplicate_macro_cannot_create_new_topology", "passed": direct["semantic_signature"] == evaluate(("M",))["semantic_signature"] == duplicate_alias["semantic_signature"], "observed": [direct, evaluate(("M",)), duplicate_alias], "alias_classification": "DUPLICATE_CANONICAL_SIGNATURE"},
        {"id": "macro_boundaries_cannot_create_new_topology", "passed": evaluate(("M", "P"))["semantic_signature"] == evaluate(("P", "M"))["semantic_signature"], "observed": [evaluate(("M", "P")), evaluate(("P", "M"))]},
        {"id": "reverse_order_cannot_collapse", "passed": hw["semantic_signature"] != wh["semantic_signature"], "observed": [hw, wh]},
        {"id": "two_macros_fit_exactly_four_physical_stages", "passed": evaluate(("M", "M"))["physical_stage_count"] == 4 and not evaluate(("M", "M"))["reasons"], "observed": evaluate(("M", "M"))},
        {"id": "three_modules_can_exceed_four_physical_stages", "passed": over["physical_stage_count"] == 5 and over["reasons"] == ["PHYSICAL_STAGE_BUDGET_EXCEEDED"], "observed": over},
        {"id": "four_macros_are_eight_not_four_physical_stages", "passed": evaluate(("M",) * 4)["physical_stage_count"] == 8 and "PHYSICAL_STAGE_BUDGET_EXCEEDED" in evaluate(("M",) * 4)["reasons"], "observed": evaluate(("M",) * 4)},
        {"id": "all_rejection_reasons_retained", "passed": all_reasons["reasons"] == ["PHYSICAL_STAGE_BUDGET_EXCEEDED", "WORM_MULTIPLICITY_LIMIT", "WORM_NOT_TERMINAL"], "observed": all_reasons},
        {"id": "type_mismatch_is_rejected", "passed": port_reasons([("rotation", "translation"), ("rotation", "rotation")]) == ["PORT_TYPE_MISMATCH:1->2"], "observed": port_reasons([("rotation", "translation"), ("rotation", "rotation")])},
        {"id": "abstract_admission_cannot_claim_spatial_assembly", "passed": evaluate(("H", "W", "B", "X"))["spatial_embeddability"] == "OPEN" and evaluate(("H", "W", "B", "X"))["decision"] == "abstract_candidate", "observed": evaluate(("H", "W", "B", "X"))},
        {"id": "unknown_token_rejected", "passed": evaluate(("UNKNOWN",))["reasons"] == ["UNKNOWN_TOKEN:UNKNOWN"], "observed": evaluate(("UNKNOWN",))},
    ]
    assert all(p["passed"] for p in probes), probes
    return probes


def frozen_source_state():
    def git(*args):
        return subprocess.run(["git", "-C", str(SOURCE_ROOT), *args], check=True, capture_output=True, text=True).stdout.strip()
    state = {"root": str(SOURCE_ROOT.resolve()), "head": git("rev-parse", "HEAD"), "porcelain": git("status", "--porcelain=v1")}
    if state["head"] != FROZEN_COMMIT:
        raise RuntimeError(f"Frozen source HEAD changed: {state['head']}")
    return state


def json_write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_write(path, rows, columns):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def build_artifacts(output_dir):
    output_dir = output_dir.resolve()
    if output_dir == SOURCE_ROOT.resolve() or SOURCE_ROOT.resolve() in output_dir.parents:
        raise RuntimeError("Output must stay outside the frozen source tree")
    before = frozen_source_state()
    domains = {"four_atom": enumerate_domain(FOUR), "six_atom": enumerate_domain(SIX)}
    probes = negative_probes()
    role_counts = {"four_atom_with_all_six_planetary_roles": {"semantic_atom_count": 9, "ordered_sequences_le_4": geometric_sum(9, 4)}, "six_atom_with_all_six_planetary_roles": {"semantic_atom_count": 11, "ordered_sequences_le_4": geometric_sum(11, 4)}, "four_atom_with_only_three_reducing_planetary_roles": {"semantic_atom_count": 6, "ordered_sequences_le_4": geometric_sum(6, 4)}, "six_atom_with_only_three_reducing_planetary_roles": {"semantic_atom_count": 8, "ordered_sequences_le_4": geometric_sum(8, 4)}}
    for name, values in role_counts.items():
        values.update({"grammar_extension_id": "serial-reducer-three-planetary-roles-v1.0.0" if "three_reducing" in name else "serial-ratio-chain-six-planetary-roles-v1.0.0", "materialization": "count_only_not_in_the_1554_entry_library", "reducer_only": "three_reducing" in name})
    # These are a separate subtype-assignment metric, never new canonical IDs.
    subtype_metric = {"four_atom_H_spur_or_helical_assignment_count": geometric_sum(5, 4), "six_atom_H_and_I_spur_or_helical_assignment_count": geometric_sum(8, 4), "adds_canonical_topologies": 0, "assignment_domain_evidence": "ASSUMED", "note": "Two labels per cylindrical parallel stage, without binding beta or proving manufacturability."}
    macro_alias_probe = {}
    for alphabet in (FOUR, SIX):
        aliases = {"M": ("P", "P"), "M_ALIAS": ("P", "P")}
        admitted = [result for expr in words(alphabet + tuple(aliases), BUDGET) if not (result := evaluate(expr, macros=aliases))["reasons"]]
        unique = {result["semantic_signature"] for result in admitted}
        expected_raw = sum(weighted_count(len(alphabet), n, 2) for n in range(1, 5))
        assert len(admitted) == expected_raw
        assert len(unique) == geometric_sum(len(alphabet), BUDGET)
        macro_alias_probe[str(len(alphabet))] = {"two_weight_two_alias_definitions_raw_admitted": len(admitted), "expanded_unique_unchanged": len(unique), "verification": "full_enumeration_equals_weighted_closed_form"}
    after = frozen_source_state()
    assert before == after, "Read-only source boundary changed during the experiment"
    provenance = {"expected_frozen_commit": FROZEN_COMMIT, "source_before": before, "source_after": after, "source_state_unchanged": before == after, "runner_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "grammar_evidence": "ASSUMED: explicitly controlled vocabulary", "count_evidence": "VERIFIED: enumeration, closed forms, and negative probes", "technical_references": TECHNICAL_REFERENCES, "industrial_precedent": "OPEN: no vendor, patent or product examples asserted"}
    counts = {"schema": "abstract-transmission-enumeration-counts/1", "grammar_id": GRAMMAR_ID, "physical_stage_budget": BUDGET, "zero_stage_identity_included": False, "provenance": provenance, "domains": {name: result["counts"] for name, result in domains.items()}, "planetary_role_extension": role_counts, "geometry_subfamily_assignment_metric": subtype_metric, "duplicate_macro_definition_probe": macro_alias_probe, "negative_probes_passed": len(probes), "universe_claim": "Finite only inside this declared grammar; not an exhaustive census of industrial transmissions."}
    entries, summary, group_rows, rejection_rows = [], [], [], []
    groups = Counter()
    for candidate in sorted(domains["six_atom"]["canonical"].values(), key=lambda c: (c["physical_stage_count"], c["expanded_atom_word"])):
        atom_word = candidate["expanded_atom_word"]
        n = candidate["physical_stage_count"]
        signature = candidate["semantic_signature"]
        candidate_id = "T-" + hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
        policy = evaluate(atom_word, profile="worm_terminal")
        subtype_slots = sum(x in ("H", "I") for x in atom_word)
        entry = {
            "candidate_id": candidate_id, "letter_word": atom_word,
            "physical_stage_count": n, "semantic_signature": signature,
            "family_order_signature": candidate["family_order_signature"],
            "axis_relation_word": [ATOMS[x]["axis_relation"] for x in atom_word],
            "module_representations": candidate["representations"],
            "representation_count": len(candidate["representations"]),
            "geometry_subfamily_assignment_count_metric": 2 ** subtype_slots,
            "parameter_domain_refs_in_order": [f"parameter-domain:{x}" for x in atom_word],
            "parameter_instance_signature": None, "layout_variant_signature": None,
            "base_four_atom_member": all(x in FOUR for x in atom_word),
            "initial_library_le_2_member": n <= 2,
            "port_admission": "admitted", "decision": "abstract_candidate",
            "spatial_embeddability": "OPEN", "rating_evidence": "OPEN", "load_path_evidence": "OPEN", "thermal_evidence": "OPEN", "industrial_precedent": {"state": "OPEN", "source_refs": []},
            "source_status": "controlled_grammar_generated_not_industrial_case",
            "optional_worm_terminal_policy": {"decision": policy["decision"], "reasons": policy["reasons"]},
        }
        entries.append(entry)
        summary.append({"candidate_id": candidate_id, "physical_stages": n, "letter_word": ">".join(atom_word), "semantic_signature": signature, "family_order_signature": candidate["family_order_signature"], "module_representation_count": len(candidate["representations"]), "axis_relation_word": ">".join(entry["axis_relation_word"]), "geometry_subfamily_assignment_count_metric": 2 ** subtype_slots, "base_four_atom_member": entry["base_four_atom_member"], "initial_library_le_2_member": n <= 2, "decision": "abstract_candidate", "spatial_embeddability": "OPEN", "industrial_precedent": "OPEN", "optional_policy_decision": policy["decision"], "optional_policy_reasons": "|".join(policy["reasons"])})
        groups[(n, candidate["family_order_signature"])] += 1
    assert len({e["candidate_id"] for e in entries}) == len(entries)
    assert sum(e["representation_count"] for e in entries) == 1676
    for (n, family_signature), count in sorted(groups.items()):
        group_rows.append({"physical_stages": n, "family_order_signature": family_signature, "distinct_atomic_semantic_topologies": count, "grouping_is_not_dedup": True})
    for name, result in domains.items():
        for profile_name, rows in [("base_physical_budget", result["rejected"]), ("optional_worm_terminal", result["optional_rejected"])]:
            for row in rows:
                rejection_rows.append({"domain": name, "profile": profile_name, "expression": ">".join(row["expression"]), "expanded_atoms": ">".join(row["expanded_atom_word"]), "expanded_physical_stages": row["physical_stage_count"], "all_reason_codes": "|".join(row["reasons"]), "physical_impossibility_claimed": False})
    parameter_domains = {f"parameter-domain:{x}": {"evidence": "ASSUMED", "ratio_magnitude_domain": "i_abs > 2; i_abs=1+z_R/z_S and z_R/z_S>1" if x == "P" else "i_abs>1 by controlled reducer-only domain; no numerical upper bound supplied", "ratio_is_topology_entry": False, "bound_values": None, "required_unbound_parameters": ["tooth_counts_or_starts", "module_or_pitch", "ratio", "geometry_subfamily", "shaft_geometry", "material", "efficiency_model", "load_spectrum", "bearing_support", "lubrication", "housing"], "manufacturable_ratio_domain": "OPEN"} for x in SIX}
    library = {"schema": "abstract-transmission-topology-library/1", "grammar_id": GRAMMAR_ID, "provenance": provenance, "scope": {"ordered": True, "single_exposed_input_output": True, "physical_stage_budget": BUDGET, "zero_stage_identity_included": False, "global_power_split_merge_enabled": False, "shift_clutch_state_graph_enabled": False, "planet_internal_load_sharing_is_not_an_exposed_branch": True, "axis_relation_word_is_not_a_spatial_certificate": True, "not_a_product_planner": True}, "atomic_stage_definitions": ATOMS, "planetary_role_definitions": PLANETARY_ROLES, "active_P_role": ATOMS["P"]["semantic_id"], "user_macro_definitions": {"M": {"name": "two_serial_fixed_ring_planetary_stages", "expands_to": ["P", "P"], "physical_stage_weight": 2, "adds_canonical_topology": False, "interface_assumption": "stage-1 carrier can couple to stage-2 sun; both rings independently grounded; real supports and geometry OPEN"}}, "parameter_domains": parameter_domains, "entries": entries, "rejection_ledger": "rejection-ledger.csv", "rejection_ledger_rows": len(rejection_rows), "out_of_grammar": ["differential_with_free_third_member", "explicit_power_split_and_merge", "clutch_or_shift_state_graph", "compound_or_stepped_planetary_train", "belt_chain_friction_and_harmonic_drives", "screw_rack_or_other_rotary_to_linear_terminal", "motor_and_external_load_contract", "bearing_and_housing_layout_variants"], "canonicalization_rule": "Exact ordered expanded atomic semantic IDs; never sort stage IDs, compare total ratio only, or use a family-only signature for deduplication.", "industrial_cases_verified": 0}
    output_dir.mkdir(parents=True, exist_ok=True)
    json_write(output_dir / "enum-counts.json", counts)
    json_write(output_dir / "topology-library.json", library)
    json_write(output_dir / "negative-probes.json", {"grammar_id": GRAMMAR_ID, "passed": len(probes), "failed": 0, "probes": probes})
    csv_write(output_dir / "topology-library-summary.csv", summary, list(summary[0]))
    csv_write(output_dir / "topology-group-summary.csv", group_rows, list(group_rows[0]))
    csv_write(output_dir / "rejection-ledger.csv", rejection_rows, list(rejection_rows[0]))
    return {"grammar_id": GRAMMAR_ID, "output_dir": str(output_dir), "four_atom_topologies": 340, "six_atom_topologies": len(entries), "six_atom_macro_representations": 1676, "negative_probes_passed": len(probes), "rejection_ledger_rows": len(rejection_rows), "source_state_unchanged": before == after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(build_artifacts(args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
