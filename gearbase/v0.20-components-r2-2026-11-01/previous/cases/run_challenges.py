"""Read-only, deterministic v0.20 case census and bounded generation challenge.

Run: python -B run_challenges.py --source D:/my_Works/Gears/gearbase-v020-work
Every output is written next to this script. No CAD/GUI/FE process is launched.
Original inputs, selectors, engineering limits and gold files are never edited.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import datetime as dt
import hashlib
import importlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time

sys.dont_write_bytecode = True
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent
BASELINE = "80117283778cf8732b5557fa15c2e41f626f92fc"
FILES: dict[str, dict] = {}


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def bind(path, role="consumed_source"):
    path = Path(path).resolve()
    key = str(path)
    if key not in FILES:
        data = path.read_bytes()
        FILES[key] = {"path": path.as_posix(), "bytes": len(data),
                      "source_sha256": hashlib.sha256(data).hexdigest(), "roles": []}
    if role not in FILES[key]["roles"]:
        FILES[key]["roles"].append(role)
    return {"path": path.as_posix(), "source_sha256": FILES[key]["source_sha256"]}


def read(path, role="consumed_json"):
    bind(path, role)
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")
    return bind(path, "assessment_output")


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, encoding="utf-8", check=True)
    return result.stdout.strip()


def leaves(node, pointer=""):
    """Field provenance, including nulls; no fabricated values or new certificates."""
    rows = []
    if isinstance(node, dict) and "value" in node:
        rows.append({"json_pointer": pointer or "/", "value_is_null": node["value"] is None,
                     "unit": node.get("unit"), "declared_source": node.get("source"),
                     "declared_provenance": node.get("provenance"),
                     "certificate": node.get("certificate")})
    if isinstance(node, dict):
        for key, value in node.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            rows.extend(leaves(value, pointer + "/" + escaped))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            rows.extend(leaves(value, pointer + "/" + str(i)))
    return rows


def count_status(checks):
    return dict(collections.Counter(v["status"] for v in checks.values()))


def null_fields(node, pointer=""):
    if node is None:
        return [pointer or "/"]
    if isinstance(node, dict):
        return [p for key, value in node.items() for p in null_fields(value, pointer + "/" + key)]
    if isinstance(node, list):
        return [p for i, value in enumerate(node) for p in null_fields(value, pointer + "/" + str(i))]
    return []


def summarize_system(result):
    return {"system_status": result["system_status"],
            "scope_status": {k: v["status"] for k, v in result.get("checks", {}).items()},
            "gear_rating_status": {k: v["status"] for k, v in result.get("gear_rating", {}).items()},
            "missing_count": len(result["template"].get("missing", [])),
            "missing_structural": result["template"].get("missing_structural", []),
            "unsupported": result["template"].get("unsupported", []),
            "full_system_pass": result["system_status"] == "solved" and
                all(v["status"] == "pass" for v in result.get("checks", {}).values()) and
                all(v["status"] == "pass" for v in result.get("gear_rating", {}).values())}


def variant_key(family, candidate):
    if family == "H2":
        fields = ("mn_mm", "z1", "z2", "beta_deg")
    elif family == "W2W":
        fields = ("m_mm", "q", "z1", "z2")
    else:
        fields = ("zs", "zp", "zr", "n_p")
    return tuple(tuple(candidate[st][k] for k in fields) for st in ("stage1", "stage2"))


def simple_kinematics(family, p, candidate):
    ratios = []
    for stage in ("stage1", "stage2"):
        s = candidate[stage]
        ratios.append(1 + s["zr"] / s["zs"] if family == "P2" else s["z2"] / s["z1"])
    total = ratios[0] * ratios[1]
    target = p[{"H2": "total_ratio", "W2W": "target_ratio", "P2": "target_total_ratio"}[family]]
    tol = p[{"H2": "tol", "W2W": "ratio_band", "P2": "i_tol"}[family]]
    return math.isclose(total, candidate["i_total"], rel_tol=1e-13) and abs(total-target)/target <= tol


def run_flagship(root, family, modules):
    IT, FW, FS, H2, W2W, P2 = modules
    src_path = root / "data/flagships-stage0" / (family + ".json")
    doc = read(src_path)
    system_path = root / "data/flagships-system" / (family + ".system-source.json")
    source = read(system_path)
    origin = root / doc["origin"]["path"]
    origin_binding = bind(origin, "declared_flagship_origin")
    assert origin_binding["source_sha256"] == doc["origin"]["sha256"], "origin hash mismatch"
    req = doc["requirement"]
    compiled = IT.requirement_compile({"requirement": copy.deepcopy(req)})
    t0 = time.perf_counter()
    result = FW.run(compiled["workflow_call"])
    elapsed = time.perf_counter() - t0
    raw = result["result"]
    candidates = raw["candidates"]
    model = {"H2": H2, "W2W": W2W, "P2": P2}[family]
    # H2/W2W verify() re-enumerates membership; avoid calling it once per row.
    # Use the existing direct H2/P2 local geometry verifier where available.
    if family == "H2":
        from gearmath.gear.h2_flagship import verify_stage0_geometry
        p = req["parameters"]
        geometry = [verify_stage0_geometry(c, p["a1_mm"], p["a2_mm"], p["total_ratio"],
                                           p["beta_range"], p["tol"]) for c in candidates]
        stage_counts = [len(s) for s in raw["stage_domains"]]
        pair_domain = math.prod(stage_counts)
        accepted = raw["feasible"]
        search = {"stage_domain_counts": stage_counts, "pair_domain": pair_domain,
                  "pair_evaluations": raw["pair_evaluations"], "pair_boxes_rejected": raw["pair_boxes_rejected"],
                  "seed_count": raw["seed_count"], "accepted_before_output_cap": accepted}
    elif family == "W2W":
        p = req["parameters"]
        geometry = []
        for c in candidates:
            local = []
            for st, center, speed in (("stage1", p["a1_mm"], p["n1_rpm"]),
                                      ("stage2", p["a2_mm"], c["n_mid_rpm"])):
                s = c[st]
                fresh = W2W._stage(center, s["m_mm"], s["q"], s["z1"], p["rho_v_deg"], speed)
                local.append(fresh is not None and all(fresh[k] == s[k] for k in fresh))
            geometry.append(all(local))
        search = raw["search"]
        pair_domain, accepted = search["pairs_examined"], search["feasible"]
    else:
        p = req["parameters"]
        geometry = [P2.verify(p, c)["ok"] for c in candidates]
        search = raw["search"]
        pair_domain, accepted = search["pairs_examined"], search["in_tolerance_pairs"]
    kin = [simple_kinematics(family, p, c) for c in candidates]
    systems = []
    for rank, candidate in enumerate(candidates, 1):
        rank_source = copy.deepcopy(source)
        rank_source["candidate_rank"] = {"value": rank, "unit": "1",
            "source": "Assessment requests existing returned candidate rank; original demand unchanged"}
        solved = FS.solve(rank_source, req)
        summary = summarize_system(solved)
        summary.update(rank=rank, candidate_sha256=digest(candidate),
                       candidate_identity=variant_key(family, candidate),
                       kinematics_pass=kin[rank-1], stage0_geometry_pass=geometry[rank-1])
        systems.append(summary)
        if rank == 1:
            write(f"{family}-system-first.json", solved)
    full = sum(s["full_system_pass"] for s in systems)
    blocked = sum(s["system_status"] == "blocked" for s in systems)
    thermal_pass = sum(c.get("thermal_ok") is True for c in candidates) if family == "W2W" else None
    summary = {"id": family, "title": doc["title"],
        "challenge_kind": "within_fixed_family_stage0_enumeration", "calculation_mode": "fresh_deterministic_replay",
        "equivalence_group_id": family + "-original-demand", "source_ids": [family + "-stage0", family + "-system"],
        "source_sha256": bind(src_path)["source_sha256"],
        "requirement_sha256": result["requirement_sha256"], "requirement": req,
        "requirement_summary": {"H2": "H→H; a1=80 mm,a2=100 mm,i=10±3%; original sampled zero-shift geometry",
            "W2W": "W→W; a1=100 mm,a2=125 mm,nin=1440 rpm,i=144±2%,Tout=800 Nm; K=12,A=.5 m²,30→90°C",
            "P2": "P→P; nin=1440 rpm,i=40±2%; fixed rings,sun input/carrier output; original integer domain"}[family],
        "candidate_count": len(candidates), "raw_candidate_count": accepted,
        "raw_pair_domain_count": pair_domain, "unique_topology_count": 1 if candidates else 0,
        "topology_identity": {"H2": "H→H_parallel_external", "W2W": "W→W", "P2": "P→P_fixed_ring_NGW"}[family],
        "unique_parameter_variant_count_in_returned": len({variant_key(family, c) for c in candidates}),
        "stage_A_count": accepted, "stage_A_definition": "solver accepted in-band Stage0 pair rows before reporting cap/frontier; no strength qualification",
        "kinematic_pass_count_checked": sum(kin), "kinematic_checked_population": "all returned candidates",
        "geometry_pass_count_checked": sum(geometry), "geometry_checked_population": "all returned candidates, Stage0 predicates only",
        "geometry_scope": "nominal analytic Stage0 geometry; tooth contact, full-motion clearance and housed spatial fit not checked",
        "strength_system_checked_count": len(systems), "full_system_pass_count": full,
        "full_system_pass_population": "returned candidates only; remaining accepted pair rows not system-rated",
        "blocked_count": blocked, "failed_system_count": sum(s["system_status"] != "blocked" and not s["full_system_pass"] for s in systems),
        "thermal_pass_count": thermal_pass, "thermal_fail_count": len(candidates)-thermal_pass if thermal_pass is not None else None,
        "space_verified": False, "space_status": "not_run; no CAD/GUI/FE replay authorized",
        "engineering_accepted": False, "search": search, "outcome": result["outcome"],
        "workflow_verification": result["verification"], "elapsed_seconds": elapsed,
        "blocked_reasons": sorted({u["reason"] for s in systems for u in s["unsupported"]}) or
                           ["Original source lacks strength/tool/material/life/efficiency/load path, shaft, bearing and key inputs; see first-system raw evidence"],
        "reporting_limitations": ["Each family is a different demand. H2/W2W/P2 must not be shown as three implementations of one demand.",
            "H2 max_candidates=40 is an output cap; P2 returns Pareto representatives and groups module choices. Counts use different declared units.",
            "system_status=solved means evaluable, including fail; this assessment requires all requested checks pass."]}
    if family == "P2":
        summary["blocked_reasons"].append(P2.BACKLASH_NOTE)
        summary["assembly_clearance_status"] = "not qualified: the original zero-shift geometry warns of zero theoretical backlash at both meshes"
    write(f"{family}-workflow-raw.json", {"compile": compiled, "workflow": result})
    write(f"{family}-candidates-checked.json", systems)
    return summary


def fixed_pair(root, case):
    from gearmath.product import design_check as DC
    from gearmath.gear import source_optimize as SO
    from gearmath.kernel import units as U
    dp, sp = root / f"data/source/{case}.math-source.json", root / f"data/system/{case}.system-input.json"
    doc, si = read(dp), read(sp)
    refs = leaves(doc) + leaves(si)
    for row in refs:
        cert = row.get("certificate")
        if isinstance(cert, dict) and cert.get("kind") == "file" and (root / cert["ref"]).is_file():
            actual = bind(root / cert["ref"], "input_certificate")
            assert actual["source_sha256"] == cert["sha256"], "certificate bytes mismatch"
    result = DC.check(doc, si, "all")
    family = si["design_ref"]["model_family"]
    model = SO.build_family_model(doc, family.split(":")[0], family.split(":")[1] if ":" in family else None)
    wanted = [q for q in ("u", "eps_alpha", "d_1", "d_2", "S_H_1", "S_H_2", "S_F_1", "S_F_2") if q in model.formulas]
    evaluated = model.evaluate(wanted)
    values = {q: {"value": U.from_canonical(evaluated.values[q], model.formulas[q].unit),
                  "unit": model.formulas[q].unit} for q in wanted if q in evaluated.values}
    summary = {"id": case + "-fixed-pair", "title": doc["title"],
        "challenge_kind": "supplied_fixed_pair_check_only", "calculation_mode": "fresh_deterministic_check_using_declared_evidence_inputs",
        "equivalence_group_id": case + "-fixed-pair-input", "source_ids": [doc["id"], si["id"] + "-system"],
        "requirement_summary": "Existing fixed G1 mesh" if case == "C001" else "Existing KISSsoft fixed spur-pair inputs",
        "source_sha256": bind(dp)["source_sha256"], "source_fields": refs,
        "candidate_count": 1, "auto_generated_candidate_count": 0, "raw_candidate_count": None,
        "unique_topology_count": None, "stage_A_count": None,
        "count_reason": "The caller already supplied one geometry. No topology generation was requested or performed.",
        "full_system_pass_count": int(result["computation"]["status"] == "pass"),
        "blocked_count": int(result["computation"]["status"] == "blocked"),
        "failed_system_count": int(result["computation"]["status"] == "fail"),
        "computation": result["computation"], "scope_status": {k: v["status"] for k, v in result["checks"].items()},
        "computed_values": values, "model_sha256": evaluated.model_sha256,
        "space_verified": False, "space_status": "not_run", "engineering_accepted": False,
        "blocked_reasons": {k: v["missing"] for k, v in result["checks"].items() if v["status"] == "blocked"},
        "field_conflicts_or_pending": si.get("user_decisions_pending", []),
        "evidence_boundary": "Fresh formula output still depends on declared report-derived coefficients; no KISSsoft rerun and no external evidence promotion."}
    write(case + "-fixed-pair-raw.json", result)
    return summary


def same_demand(root, modules):
    IT, FW, FS, *_ = modules
    doc = read(root / "data/flagships-stage0/H2.json")
    source = read(root / "data/flagships-system/H2.system-source.json")
    family_free = copy.deepcopy(doc["requirement"])
    family_free.pop("family")
    response = IT.requirement_compile({"requirement": family_free})
    direct = FW.run({"action": "run", "requirement": family_free})
    full_contract = copy.deepcopy(family_free)
    full_contract["operating"] = copy.deepcopy(source["operating"])
    full_contract["axis_relationship"] = {"value": "parallel axes in original H2",
        "source": "gearmath/gear/h2_flagship.py docstring"}
    full_response = IT.requirement_compile({"requirement": full_contract})
    return {"id": "SAME-H2-DEMAND", "title": "同一H2既有需求不指定family的跨族入口探针",
        "equivalence_group_id": "H2-original-demand", "challenge_kind": "family_free_same_demand_capability_probe",
        "calculation_mode": "fresh_actual_compiler_response", "source_ids": ["H2-stage0", "H2-system"],
        "requirement_summary": "Keep original H2 parameters; retain original source operating 600 Nm@150 rpm in the contract; remove family only.",
        "original_parameters": doc["requirement"]["parameters"], "original_operating_source": source["operating"],
        "contract": {"ratio": {"value": 10, "source_pointer": "data/flagships-stage0/H2.json#/requirement/parameters/total_ratio"},
                     "output_operating": source["operating"],
                     "space_constraints": {"a1_mm": 80, "a2_mm": 100, "source": "original center distances, not a housing envelope"},
                     "axis_relationship": {"value": "parallel axes in original H→H family", "source": "gearmath/gear/h2_flagship.py docstring"},
                     "efficiency": None, "input_torque": None, "housing_envelope": None,
                     "cross_family_axis_permissions": None},
        "actual_call": {"tool": "requirement_compile", "arguments": {"requirement": family_free}},
        "compile_result": response, "direct_workflow_result": direct,
        "full_contract_call": {"tool": "requirement_compile", "arguments": {"requirement": full_contract}},
        "full_contract_compile_result": full_response,
        "unapplied_to_stage0_adapter": ["original H2 operating T_out/n_out", "explicit common axis relationship"],
        "adapter_boundary": "Minimal family-free call cannot carry the whole engineering contract. A second real call preserves the existing operating leaves and original parallel-axis meaning; the strict Stage0 schema rejects those fields.",
        "candidate_count": None, "unique_topology_count": None, "stage_A_count": None, "full_system_pass_count": None,
        "count_reason": "Unsupported request returns no search/count object; null is not measured zero feasible designs.",
        "blocked_reasons": response.get("errors", []), "space_verified": False,
        "not_comparable": {"W2W-original-demand": ["ratio144 rather than10", "centers100/125 rather than80/100",
            "nin1440/Tout800 rather than H2 nout150/Tout600", "worm axis relationships differ; no permitted axis transformation",
            "W2W constant-friction efficiency .54084 is not an H2 efficiency"],
            "P2-original-demand": ["ratio40 rather than10", "nin1440; original P2 has no torque/power",
                "fixed-ring coaxial NGW architecture; no common axis contract with H2", "P2 efficiency and thermal model absent"]},
        "clarification_required_for_cross_family_comparison": ["Can center-distance constraints be replaced by one common envelope and input/output shaft pose?",
            "Which efficiency or torque/power boundary and duty/life/material/thermal limits apply?",
            "Which shaft directions, offsets, ground members and transmission families are permitted?"],
        "engineering_accepted": False}


def case_census(root):
    # The archived bridge is deliberately disclosed: fresh typed arithmetic,
    # not a newly available product multi-family engineering planner.
    from gearmath.compat.m31 import calculator, optimizer
    sys.modules["cadbench.math_calculator"] = calculator
    sys.modules["cadbench.math_optimizer"] = optimizer
    sys.path.append(str(root / "archive/m31/src"))
    bridge = importlib.import_module("gears.benchmark.math_adapter")
    matrix_path = root / "archive/m31/benchmark50/CASE-MATRIX-M23.csv"
    bind(matrix_path, "historical_report_not_fresh_geometry")
    with matrix_path.open(encoding="utf-8-sig", newline="") as stream:
        matrix = {r["id"]: r for r in csv.DictReader(stream)}
    entries = []
    evidence_rows = []
    for p in sorted((root / "data/m31/cases").glob("C*.json")):
        d = read(p)
        receipt = bridge.verify(d)
        evidence_rows.append({"id": d["id"], "input_binding": bind(p), "receipt": receipt})
        entries.append({"id": d["id"], "title": d["title"], "category": "synthetic_fixed_transmission_benchmark",
            "entity_unit": "authored transmission instance, not independently sourced engineering demand",
            "source_binding": bind(p), "canonical_case_sha256": digest(d),
            "field_sources": {"geometry_and_operating": "this file /stages and /input: benchmark-authored values",
                "provenance": d["provenance"], "engineering": d.get("engineering", {}).get("evidence_maturity", "absent")},
            "families": [s["kind"] for s in d["stages"]], "input": d["input"],
            "stage_count": len(d["stages"]), "evidence_status": "fresh_ideal_lossless_kinematics_only",
            "ideal_output": receipt["ideal_output"], "kinematics_pass": True,
            "strength_inputs_present": bool(d.get("engineering")), "full_system_pass": False,
            "full_system_status": "not evidenced; C001 fixed G1 is checked separately",
            "historical_report_derived": {k: matrix[d["id"]][k] for k in (
                "math_kernel", "typed_math", "m12_stage_step", "strict_projection", "global_gear_train", "full_machine", "contact_strength")},
            "automatic_design_demand_status": "no standalone search demand/domain: fixed topology, teeth and modules already supplied"})
    write("benchmark50-kinematic-replay.json", {"scope": "fresh archived authored-case bridge routed to current gearmath kernel; ideal lossless only", "rows": evidence_rows})
    stats = {"denominator": len(entries), "denominator_definition": "unique C001..C050 authored instances",
             "synthetic_derived_provenance_count": sum(e["field_sources"]["provenance"]["parameter_status"] == "original_derived_benchmark_not_a_source_reproduction" for e in entries),
             "fresh_typed_ideal_kinematics_pass": len(evidence_rows),
             "with_engineering_assumptions": [e["id"] for e in entries if e["strength_inputs_present"]],
             "all_stages_spur_or_helical": [e["id"] for e in entries if set(e["families"]) <= {"spur", "helical"}],
             "stage_kind_occurrences": dict(collections.Counter(k for e in entries for k in e["families"])),
             "authored_stage_kind_sequences": len({tuple(e["families"]) for e in entries}),
             "topology_generation_interpretation": "50 distinct authored kind sequences; no claim these were generated from one common demand",
             "full_machine_verified_current_run": 0, "spatial_validation_current_run": "not_run",
             "historical_matrix_binding": bind(matrix_path),
             "historical_report_derived_only": {k: dict(collections.Counter(r[k] for r in matrix.values())) for k in (
                 "math_kernel", "typed_math", "m12_stage_step", "strict_projection", "global_gear_train", "full_machine", "contact_strength")}}
    return entries, stats


def add_catalog_metadata(root, entries):
    for fam in ("H2", "W2W", "P2"):
        p = root / f"data/flagships-stage0/{fam}.json"
        d = read(p)
        entries.append({"id": fam + "-stage0", "title": d["title"], "category": "synthetic_stage0_flagship",
            "entity_unit": "fixed-family sampled/enumerated demand", "source_binding": bind(p),
            "associated_sources": [bind(root / f"data/flagships-system/{fam}.system-source.json")],
            "field_sources": {"requirement": "this file /requirement; inherited original solver options, not engineering defaults", "origin": d["origin"]},
            "full_system_pass": False})
    for p in sorted((root / "data/kisssoft").glob("K0*.json")):
        d = read(p)
        if d.get("schema", "").startswith("gearbase.kisssoft.case/"):
            sid = d["id"]
            related = sorted((root / "data/source").glob(sid + "*.json"))
            entries.append({"id": sid, "title": d.get("description", sid), "category": "commercial_fixed_mesh_comparison",
                "entity_unit": "fixed mesh example; K04/K05 are two EV stages, not two verified full gearboxes",
                "source_binding": bind(p), "associated_sources": [bind(q) for q in related],
                "field_sources": d["sources"], "limitations": d.get("limitations", []),
                "full_system_pass": False, "evidence_status": "existing report/COM-derived reference; commercial application not rerun"})
    for name in ("examples-1-4.json", "examples-5-8.json"):
        p = root / "data/tr30" / name
        d = read(p)
        for c in d["cases"]:
            entries.append({"id": "TR30-ex" + str(c["example_number"]), "title": c["title"],
                "category": "standard_fixed_mesh_verification", "entity_unit": "standard worked mesh, not whole system demand",
                "source_binding": {**bind(p), "json_pointer": "/cases/" + str(d["cases"].index(c))},
                "field_sources": {"sources": c.get("sources"), "input_contract": c.get("input_contract"),
                    "transcription": d["transcription_method"], "source_file": d.get("source_file")},
                "evidence_status": "metadata inventory only; no full TR30 replay in this case challenge", "full_system_pass": False})
    physical = {"nrel-grc-gb2-phase3", "ROOZING-VOLBEDA-2022-11R"}
    for p in sorted((root / "data/m31/external_references").glob("*.json")):
        d = read(p)
        category = "externally_reported_physical_test_reference" if d["id"] in physical else (
            "external_worked_pair_reference" if "contact-example" in p.name else "external_authored_CAD_reference")
        entries.append({"id": d["id"], "title": d["id"], "category": category,
            "entity_unit": "one pinned external design/reference; binary occurrences and output files do not add cases",
            "source_binding": bind(p), "field_sources": {k: v for k, v in d.items() if k in (
                "source", "provenance", "source_url", "repository", "commit", "source_member", "source_member_sha256", "archive_sha256", "dataset_doi")},
            "scope": d.get("scope", d.get("reference_role")),
            "evidence_status": "local metadata/provenance only; original files and external truth not newly requalified",
            "full_system_pass": False, "model_ready_for_same_demand_generation": False,
            "explicit_null_fields": null_fields(d),
            "declared_source_claims": d.get("source_claims"),
            "declared_STEP_stage_products": d.get("source_step_stage_products"),
            "missing_or_unqualified": d.get("unknown_boundaries", d.get("missing_boundaries", d.get("acceptance")))})
    p = root / "data/system-optimization/v017-capability-probe.json"
    read(p)
    entries.append({"id": "v017-capability-probe", "title": "Authored finite cylindrical system capability probe",
        "category": "synthetic_capability_fixture", "entity_unit": "capability fixture, not real C001 completion",
        "source_binding": bind(p), "evidence_status": "inventory only; not replayed in this case challenge"})
    p = root / "data/bench/v1/requirements.json"
    d = read(p)
    for c in d["cases"]:
        entries.append({"id": c["id"], "title": "Requirement-language fixture " + c["id"],
            "category": "synthetic_language_evaluation_fixture", "entity_unit": "language prompt, not qualified engineering machine",
            "source_binding": {**bind(p), "json_pointer": "/cases/" + str(d["cases"].index(c))},
            "tags": c.get("tags", []), "gold_status": c.get("gold", {}).get("status"),
            "evidence_status": "metadata only; no labels created and no model evaluation run"})


def workspace_survey(root):
    workspace = root.parent
    rows = []
    for name in ("gear-compiler", "fea-case-library", "gears_doc", "gearbase-v0.8-work"):
        p = workspace / name
        row = {"path": p.as_posix(), "scope": "first-level listing and explicitly named indices only", "exists": p.is_dir()}
        if p.is_dir():
            row["first_level"] = [{"name": q.name, "kind": "directory" if q.is_dir() else "file",
                **({"bytes": q.stat().st_size} if q.is_file() else {})} for q in sorted(p.iterdir())]
        rows.append(row)
    plan_path = workspace / "gear-compiler/stage0/reports/benchcad-local-plan.json"
    if plan_path.is_file():
        try:
            d = read(plan_path, "workspace_case_index")
            rows[0]["explicit_case_index"] = {"binding": bind(plan_path), "declared_status": d["status"],
                "declared_pilot_scope": d["pilot_scope"], "task_ids": [c["task_id"] for c in d["tasks"]],
                "assessment": "historical H2/W2W/P2 origin; not three new independent engineering demands"}
        except json.JSONDecodeError as exc:
            rows[0]["explicit_case_index"] = {"binding": bind(plan_path), "parse_status": "invalid_json",
                "error": str(exc), "assessment": "Historical plan is not machine-readable; visible task text and SPEC name H2/W2W/P2. No new case admitted from this malformed index."}
        spec = workspace / "gear-compiler/stage0/SPEC.md"
        rows[0]["spec_binding"] = bind(spec, "workspace_spec_read")
    p = workspace / "fea-case-library/CATALOG.json"
    if p.is_file():
        d = read(p, "workspace_case_index")
        rows[1]["explicit_case_index"] = {"binding": bind(p), "declared_physical_case_count": d.get("physical_case_count"),
            "entries": [{"id": e["id"], "class": e["class"], "status": e["status"]} for e in d["entries"]],
            "assessment": "25 FE problem contracts, mostly historical gear/numerical probes plus 5 public numerical references; not 25 independent transmission requirements; no FE rerun"}
    rows[2]["assessment"] = "Literature PDFs, profile scripts and archives exist. Contents not parsed; may contain additional engineering demands. No claim that all local real cases are absent."
    old = workspace / "gearbase-v0.8-work/gearbase"
    if old.is_dir():
        groups = {}
        for rel in ("data/m31/cases", "data/m31/external_references"):
            comp = []
            for p in sorted((old / rel).glob("*.json")):
                equivalent = root / rel / p.name
                a = bind(p, "old_package_duplicate_check")
                b = bind(equivalent) if equivalent.is_file() else None
                comp.append({"name": p.name, "old_source_sha256": a["source_sha256"],
                    "current_source_sha256": b["source_sha256"] if b else None,
                    "bytes_equal": bool(b and a["source_sha256"] == b["source_sha256"])})
            groups[rel] = comp
        rows[3]["duplicate_comparison"] = groups
    intake = []
    for name in ("POD需求确认.xlsx", "蜗杆、斜齿轮设计.docx", "蜗杆传动设计计算说明书.docx", "蜗杆斜齿计算.xlsx", "蜗杆斜齿计算.xlsm"):
        p = workspace / name
        if p.is_file():
            intake.append({**bind(p, "unparsed_workspace_intake"), "status": "unparsed; not admitted or counted as an engineering demand"})
    return {"directories": rows, "unparsed_intake_candidates": intake,
            "boundary": "No recursive drive scan. No zip/PDF/native CAD/standard scan contents copied or uploaded. Workspace literature and user workbooks not semantically inventoried."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=Path("D:/my_Works/Gears/gearbase-v020-work"))
    args = ap.parse_args()
    root = args.source.resolve()
    head, version = git(root, "rev-parse", "HEAD"), (root / "VERSION").read_text(encoding="utf-8").strip()
    if head != BASELINE or version != "0.20":
        raise SystemExit("Refuse baseline drift: expected commit " + BASELINE + " VERSION 0.20")
    before = git(root, "status", "--porcelain", "--untracked-files=all")
    sys.path.insert(0, str(root))
    from gearmath.tools import intent as IT, flagship_workflow as FW
    from gearmath.product import flagship_system as FS
    from gearmath.gear import flagship_h2 as H2, flagship_w2w as W2W, flagship_p2 as P2
    modules = (IT, FW, FS, H2, W2W, P2)
    bind(root / "VERSION")
    bind(root / "archive/m31/SPEC.md", "historical_flagship_spec")
    # Bind all current math/product code to avoid an incomplete transitive code receipt.
    for p in sorted((root / "gearmath").rglob("*.py")):
        bind(p, "current_math_code")
    for rel in ("data/source", "data/system", "data/flagships-system", "data/optimize"):
        for p in sorted((root / rel).glob("*.json")):
            read(p, "declared_input_inventory")
    entries, support = case_census(root)
    add_catalog_metadata(root, entries)
    survey = workspace_survey(root)
    challenges = [run_flagship(root, family, modules) for family in ("H2", "W2W", "P2")]
    challenges += [fixed_pair(root, case) for case in ("C001", "K01-spur")]
    challenges.append(same_demand(root, modules))
    after = git(root, "status", "--porcelain", "--untracked-files=all")
    if before != after:
        raise RuntimeError("Source git status changed during read-only assessment")
    # Hash actually imported archive/vendor Python too, without copying it.
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name:
            p = Path(name).resolve()
            if p.suffix == ".py" and root in p.parents and p.is_file():
                bind(p, "imported_code")
    script_binding = bind(Path(__file__), "assessment_runner")
    provenance = {"baseline_commit": head, "version": version, "source_root": root.as_posix(),
        "runner": script_binding, "python": {"executable": sys.executable, "version": sys.version, "platform": platform.platform()},
        "command_argv": [sys.executable, "-B", str(Path(__file__).resolve()), "--source", str(root)],
        "input_gold_mutated": False, "source_git_status_before": before, "source_git_status_after": after,
        "executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    provenance["command_sha256"] = digest(provenance["command_argv"])
    challenge_binding = write("challenge-results.json", {"schema": "gearbase.freeze-case-challenges/1",
        "provenance": provenance, "challenges": challenges, "benchmark50_support": support,
        "counting_contract": {"candidate_count": "returned actual rows, except fixed-pair=1 supplied check and unsupported=null",
            "raw_candidate_count": "solver accepted in-band pair rows before cap/frontier; not raw cartesian search size",
            "unique_topology_count": "distinct architecture families, not tooth/module parameter variants",
            "full_system_pass_count": "all system checks pass among actually checked returned rows only",
            "null": "unavailable/not defined; never silently interpreted as zero"}})
    catalog_binding = write("case-catalog.json", {"schema": "gearbase.freeze-case-catalog/1", "provenance": provenance,
        "distribution_boundary": "LOCAL_PRIVATE: standard input_contract and commercial evidence/source details can contain private numeric transcriptions. Public exports must replace private fields with source IDs, hashes, citation pointers and restrictions. No blanket redistribution permission is granted.",
        "deduplication_rules": ["Stable source design/example identity is the counting unit, not file count.",
            "C001 golden/source/factors/system/derived outputs are roles/variants of C001; never extra engineering cases.",
            "K01..K05 related reports/COM/P3/P4/source/factors are one fixed-mesh identity each. K04/K05 are not two complete EV transmissions.",
            "TR30 example n is counted once across table/annex/CSV/commercial follow-up; private scans are not redistributed.",
            "Historical package copies are compared by source bytes and logical ID, not counted again.",
            "FE and language test cases use separate denominators and never inflate transmission-design success."],
        "counts_by_category": dict(collections.Counter(e["category"] for e in entries)), "benchmark50_support": support,
        "entries": entries, "workspace_survey": survey,
        "interpretation": "A searchable inventory of heterogeneous evidence units, not a claim that their sum is a population of real engineering transmission demands."})
    inventory = {"schema": "gearbase.freeze-case-inventory/1", "provenance": provenance,
        "scan_boundary": "Named current repository data roots, all gearmath Python code, original flagship spec/tests, archived 50-case bridge/report, four named sibling directories and explicit indices.",
        "distribution_boundary": "LOCAL_PRIVATE: no source scans or commercial native files copied, but catalog/source-field details can contain private numeric transcriptions. Absence of PDF/native files does not make this directory publicly redistributable.",
        "catalog_binding": catalog_binding, "challenge_binding": challenge_binding,
        "sources": sorted(FILES.values(), key=lambda r: r["path"]), "workspace_survey": survey}
    write("inventory.json", inventory)
    print(json.dumps({"runner_sha256": script_binding["source_sha256"],
        "benchmark50_ideal_pass": support["fresh_typed_ideal_kinematics_pass"],
        "case_categories": dict(collections.Counter(e["category"] for e in entries)),
        "challenges": [{k: c[k] for k in ("id", "candidate_count", "unique_topology_count", "full_system_pass_count")} for c in challenges],
        "source_unchanged": before == after, "output": OUT.as_posix()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
