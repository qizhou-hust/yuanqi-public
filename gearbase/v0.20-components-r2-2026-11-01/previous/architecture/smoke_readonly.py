"""Audit-only recipes. Reads the frozen product; writes JSON only to stdout.

Run from the frozen package root with python -X utf8 -B and one case name.
No commits, no persisted state, no CAD/GUI or FE process is invoked.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
EXPECTED = "80117283778cf8732b5557fa15c2e41f626f92fc"


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def base():
    rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    assert rev == EXPECTED, (rev, EXPECTED)
    return {"source_root": str(ROOT), "head": rev, "VERSION": (ROOT / "VERSION").read_text().strip(),
            "python": sys.version, "executable": sys.executable,
            "safety": {"write_product": False, "invoke_gui": False, "invoke_fe_solver": False,
                       "persist_design": False, "dont_write_bytecode": sys.dont_write_bytecode}}


def mcp():
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "freeze-readonly-audit", "version": "1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}},
        {"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "gear_rate", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "gear_preview_edit", "arguments": {"design": "audit_readonly", "edit": {"params": {"b": {"value": 33, "unit": "mm", "provenance": "user"}}}}}},
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "gear_get_design", "arguments": {"design": "audit_readonly"}}},
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "gear_rate", "arguments": {"params": {"b": {"value": 33, "unit": "mm", "provenance": "user"}}}}},
        {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "gear_rate", "arguments": {"params": {"d_1": {"value": 40, "unit": "mm", "provenance": "user"}}}}},
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "gear_rate", "arguments": {"params": {"b": {"value": 33, "unit": "N", "provenance": "user"}}}}},
        {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "gear_explain", "arguments": {"quantity": "S_H_1"}}},
    ]
    env = dict(os.environ)
    env.pop("GEARBASE_STATE_DIR", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    command = [sys.executable, "-X", "utf8", "-B", "mcp_server.py"]
    completed = subprocess.run(command, input="".join(json.dumps(q, ensure_ascii=False) + "\n" for q in requests),
                               capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
    replies = [json.loads(line) for line in completed.stdout.splitlines()]
    assert completed.returncode == 0 and len(replies) == len(requests), completed.stderr
    assert all("error" not in row for row in replies), replies
    data = {r["id"]: r["result"].get("structuredContent", {}).get("result") for r in replies}
    assert data[6]["status"] == "preview" and data[7]["saved"] is False and data[7]["version"] == 0
    checks0 = {r["id"]: r["value"] for r in data[5]["checks"]}
    checks1 = {r["id"]: r["value"] for r in data[8]["checks"]}
    assert data[5]["model_sha256"] != data[8]["model_sha256"] and checks0 != checks1
    assert data[9]["status"].startswith("blocked") and data[10]["status"].startswith("blocked")
    return {"child_command": command, "requests": requests, "stdout_raw": completed.stdout, "stderr_raw": completed.stderr,
            "returncode": completed.returncode, "replies": replies,
            "summary": {"server_info": replies[0]["result"]["serverInfo"], "tool_count": len(replies[1]["result"]["tools"]),
                        "gear_rate_baseline": data[5]["status"], "preview_status": data[6]["status"],
                        "saved_after_preview": data[7]["saved"], "changed_checks": [k for k in checks0 if checks0[k] != checks1[k]],
                        "derived_override": data[9]["status"], "wrong_unit": data[10]["status"]}}


def requirements():
    from gearmath.tools import ai_tools as AI, nlp_templates as NT
    from gearmath.gear.problem import stage_sizing_problem
    AI.configure_state(None)
    requirement_a = dict(torque_Nm=40.0, speed_rpm=1000.0, ratio=1.8, ratio_tol_percent=2.0,
                         max_b_over_d1=1.2, min_S_H=1.1, min_S_F=1.4, life_h=10000.0,
                         material="Authored audit material A; no property values supplied", stages=1, gear_type="spur",
                         max_center_distance_mm=100.0, max_face_width_mm=40.0)
    requirement_b = dict(requirement_a, torque_Nm=400.0, speed_rpm=3000.0, life_h=30000.0,
                         material="Authored audit material B; different heat treatment, no property values supplied",
                         max_center_distance_mm=20.0, max_face_width_mm=5.0)
    compiled = [AI.call("requirement_compile", {"requirement": req}) for req in (requirement_a, requirement_b)]
    assert all(c["status"] == "pass_pending_human_confirmation" for c in compiled)
    assert compiled[0]["template_call"] == compiled[1]["template_call"]
    assert compiled[0]["rating_edit"] != compiled[1]["rating_edit"]
    # One authored discrete assignment bounds this software probe. It is not a
    # product claim over the full domain; both requests receive the same subset.
    calls = [dict(c["template_call"]["arguments"], discrete_assignments=[{"z1": 20, "m_n": 2.0}]) for c in compiled]
    optimized = [AI.call("optimize_nlp", args) for args in calls]
    assert all(o.get("solution") is not None for o in optimized), optimized
    assert optimized[0] == optimized[1]
    ratings = [AI.call("gear_rate", {"params": c["rating_edit"]["arguments"]["edit"]["params"]}) for c in compiled]
    checks = [{c["id"]: c["value"] for c in r["checks"]} for r in ratings]
    assert checks[0] != checks[1]
    witness_x = dict(z1=20, m_n=2.0, b=30.0, x1=0.2)
    evaluated = [stage_sizing_problem(**c["template_call"]["arguments"]["template_params"]).evaluate(witness_x) for c in compiled]
    assert evaluated[0] == evaluated[1]
    unsupported = AI.call("requirement_compile", {"requirement": dict(requirement_a, stages=2, gear_type="helical")})
    unknown_axis = AI.call("requirement_compile", {"requirement": dict(requirement_a, axis_relation="coaxial")})
    assert unsupported["status"] == "blocked_unsupported_scope" and unknown_axis["status"] == "blocked_invalid_inputs"
    return {"requirements": [requirement_a, requirement_b], "compiler_responses": compiled,
            "optimization_calls": calls, "optimization_responses": optimized, "rating_responses": ratings,
            "witness_x": witness_x, "template_evaluations": evaluated, "unsupported_multistage_helical": unsupported,
            "unknown_axis_relation": unknown_axis,
            "summary": {"template_calls_equal": compiled[0]["template_call"] == compiled[1]["template_call"],
                        "optimized_responses_equal": optimized[0] == optimized[1], "template_point_equal": evaluated[0] == evaluated[1],
                        "rating_checks_changed": checks[0] != checks[1],
                        "compiler_explicitly_discloses_limits": all(c.get("applicability") and c.get("unapplied") and c.get("post_checks") for c in compiled)}}


def flagships():
    from gearmath.tools import ai_tools as AI
    from gearmath.product import flagship_system as FS
    rows = {}
    for family in FS.FAMILIES:
        req = json.loads((ROOT / "data/flagships-stage0" / f"{family}.json").read_text(encoding="utf-8"))["requirement"]
        workflow = AI.call("flagship_workflow", {"action": "run", "requirement": req})
        system = FS.solve_family(family)
        assert workflow["status"] == "completed_stage0" and workflow["engineering_accepted"] is False
        assert workflow["persisted"] is False and system["system_status"] == "blocked"
        rows[family] = {"requirement": req, "workflow_response": workflow, "system_response": system,
                        "summary": {"outcome": workflow["outcome"], "candidate_count": len(workflow["result"]["candidates"]),
                                    "system_status": system["system_status"],
                                    "missing_template_count": len(system["template"]["missing"]) + len(system["template"]["missing_structural"]),
                                    "unsupported": system["template"]["unsupported"]}}
    return rows


def system():
    from gearmath.tools import ai_tools as AI, system_closure as SC
    from gearmath.gear import math_source as MS
    checks = {d: AI.call("design_check", {"design": d, "scope": ["all"]}) for d in ("C001", "K01-spur")}
    assert all(r["status"] == "ok" for r in checks.values())
    fixture = json.loads((ROOT / "data/system-optimization/v017-capability-probe.json").read_text(encoding="utf-8"))
    fixture_sha_before = sha(fixture)
    closure = SC.report(fixture)
    assert closure["system_optimization_passed"] is True and sha(fixture) == fixture_sha_before
    doc = json.loads((ROOT / "data/source/C001.math-source.json").read_text(encoding="utf-8"))
    original_sha = sha(doc)
    edited = copy.deepcopy(doc)
    edited["inputs"]["b"]["value"] = 33.0
    edited["inputs"]["b"]["source"] = "Read-only audit in-memory authored width edit"
    projection0, projection1 = MS.project_receipt(doc), MS.project_receipt(edited)
    assert sha(doc) == original_sha
    assert projection0["source_sha256"] != projection1["source_sha256"]
    derived0, derived1 = projection0["receipt"]["values"], projection1["receipt"]["values"]
    changed = [k for k in derived0 if derived0[k] != derived1.get(k)]
    assert "S_H_1" in changed
    assert doc["evidence"] == edited["evidence"]
    return {"design_checks": checks, "system_closure": closure,
            "source_projection_before": projection0, "source_projection_after": projection1,
            "summary": {"design_check_statuses": {d: {s: v["status"] for s,v in r["result"]["checks"].items()} for d,r in checks.items()},
                        "closure_passed": closure["system_optimization_passed"], "closure_domain": closure["full_reference_combinations"],
                        "closure_feasible": closure["feasible_count"], "source_changed_values": changed,
                        "external_evidence_held_unchanged": doc["evidence"] == edited["evidence"]}}


if __name__ == "__main__":
    case = sys.argv[1]
    assert case in ("mcp", "requirements", "flagships", "system")
    report = base()
    report.update(case=case, results=globals()[case]())
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
