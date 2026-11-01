"""Read-only scoped probes; no solvers, GUI, source edits or golden refreshes."""
import copy
import hashlib
import json
import pathlib
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(r"D:\my_Works\Gears\gearbase-v020-work")
OUT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from gearmath.gear import math_source as MS
from gearmath.tools import intent as IT
from gearmath.tools import flagship_workflow as FW
from gearmath.tools import ai_tools as AI


def read(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def digest(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


report = {
    "schema": "gearbase.goal-boundary-probes/1",
    "audit_date": "2026-11-01",
    "source_root": str(ROOT),
    "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "scope": "Only source-schema, requirement compiler and metadata; not a whole-system rating or engineering release test.",
    "new_fe_runs": 0,
    "new_commercial_tool_runs": 0,
}

doc = read("data/source/C001.math-source.json")
schema = read("data/source/gears.math-source-2.schema.json")
report["source_contract"] = {
    "schema_properties": sorted(schema["properties"]),
    "baseline_errors": MS.validate(doc),
}
with_topology = copy.deepcopy(doc)
with_topology["topology"] = {"ordered_stages": [{"id": "st1", "kind": "cylindrical_parallel"}]}
report["source_contract"]["added_topology_errors"] = MS.validate(with_topology)

rotary_requirement = {
    "output_speed_rpm": 30,
    "output_torque_Nm": 20,
    "envelope_mm": [100, 100, 100],
    "shaft_relation": "coaxial",
}
report["generic_output_requirement"] = {
    "input": rotary_requirement,
    "result": IT.requirement_compile({"requirement": rotary_requirement}),
}
report["multi_stage_requirement"] = IT.requirement_compile({"requirement": {"gear_type": "spur", "stages": 2}})
report["flagship_families"] = sorted(FW.MODELS)
report["flagship_without_scope"] = FW.compile_requirement({"family": "W2W", "parameters": {}, "source": "audit probe"})
report["unknown_mixed_family"] = FW.compile_requirement({"family": "planetary_worm", "scope": "stage0", "parameters": {}, "source": "audit probe"})

bench = read("data/bench/v1/requirements.json")
report["bench"] = {
    "status": bench["status"],
    "case_count": len(bench["cases"]),
    "labeled_cases": sum(c["gold"].get("status") == "labeled" for c in bench["cases"]),
    "pending_engineer_label": sum(c["gold"].get("status") == "pending_engineer_label" for c in bench["cases"]),
}

# Read-only semantic probe: same number, different caller-asserted provenance.
# This is not an authentication attack and does not write a design.
report["caller_provenance"] = {}
for provenance in ("agent_proposed", "user"):
    result = AI.call("gear_rate", {"params": {"T_1": {"value": 25, "unit": "N*m", "provenance": provenance}}})
    report["caller_provenance"][provenance] = {
        "status": result.get("status"),
        "agent_proposed_inputs": result.get("agent_proposed_inputs"),
        "errors": result.get("errors"),
    }
report["caller_provenance"]["interpretation"] = (
    "The local API accepts caller-supplied provenance. A preview/CAS token and a provenance string do not attest an independent engineer or a release decision."
)

tracked = [
    "docs/顶层设计.html", "docs/真源格式-v2.md", "docs/系统层输入-schema.md",
    "gearmath/tools/ai_tools.py", "gearmath/tools/optimize_commit.py",
    "gearmath/tools/flagship_workflow.py", "gearmath/product/flagship_system.py",
    "gearmath/product/system_optimize.py", "gearmath/gear/source_frontier.py",
    "gearmath/tools/milestones.py", "gearmath/gear/m33_acceptance.py", "gearmath/tools/fea_ingest.py",
    "data/source/gears.math-source-2.schema.json", "data/bench/v1/requirements.json",
    "output/m36/closure.json", "output/m39/closure.json", "output/m38/closure.json",
    "docs/v020-progress.md", "docs/v020-M35-review-preparation.md",
    "archive/m31/src/cadbench/command_naming.py", "archive/m31/src/cadbench/design_rebinding.py",
]
report["source_files_sha256"] = {rel: digest(rel) for rel in tracked}
report["product_git_status_after"] = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).splitlines()
(OUT / "boundary-probes.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "source_files_sha256"}, ensure_ascii=False, indent=2))
