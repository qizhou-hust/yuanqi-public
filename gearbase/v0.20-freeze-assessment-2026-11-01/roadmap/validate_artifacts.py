"""Validate only this audit's deliverables and immutable source bindings."""
import hashlib
import json
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(r"D:\my_Works\Gears\gearbase-v020-work")
COMMIT = "80117283778cf8732b5557fa15c2e41f626f92fc"


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)


def check_line(path, n):
    assert path.is_file(), f"Missing source/link: {path}"
    assert 1 <= n <= len(path.read_text(encoding="utf-8-sig").splitlines()), f"Out-of-range line: {path}:{n}"


goal, freeze, probes = (read(f) for f in ("goal-map.json", "freeze-contract.json", "boundary-probes.json"))
checks = []
for doc in (goal, freeze, probes):
    assert doc["source_commit"] == COMMIT
    assert doc["audit_date"] == "2026-11-01"
checks.append("Three JSON documents parse with no duplicate keys and bind to the same baseline/date.")

slice_ids = [s["id"] for s in goal["slices"]]
assert slice_ids == [f"R{i}" for i in range(1, 9)] == goal["slice_priority"]
for row in goal["slices"]:
    for key in ("input", "output", "acceptance_gate", "dependencies", "software_independent", "external_engineering"):
        assert row[key], f"Missing slice field: {row['id']}.{key}"
checks.append("Eight ordered slices all contain inputs, outputs, gates, dependencies, software and external-engineering scope.")

evidence_ids = {e["id"] for e in goal["evidence"]}
assert len(evidence_ids) == len(goal["evidence"])
for row in goal["requirements"]:
    assert set(row["evidence"]) <= evidence_ids
    assert set(row["slices"]) <= set(slice_ids)
for evidence in goal["evidence"]:
    path = (HERE if evidence["path"] == "boundary-probes.json" else ROOT) / evidence["path"]
    assert path.is_file(), f"Missing evidence file: {path}"
    for line in evidence.get("lines", []):
        check_line(path, line)
    for ref in evidence.get("related", "").split(";"):
        if not ref:
            continue
        match = re.fullmatch(r"(.+?):(\d+)", ref)
        if match:
            check_line(ROOT / match[1], int(match[2]))
        else:
            assert (ROOT / ref).is_file(), f"Missing related source: {ref}"
checks.append("All requirement/evidence/slice references resolve; every cited source line exists.")

markdown = (HERE / "ROADMAP.md").read_text(encoding="utf-8")
links = re.findall(r"\]\((D:/[^)]+)\)", markdown)
for link in links:
    match = re.fullmatch(r"(.+?):(\d+)", link)
    if match:
        check_line(pathlib.Path(match[1]), int(match[2]))
    else:
        assert pathlib.Path(link).is_file(), f"Missing local Markdown link: {link}"
assert "## Where This Review May Be Wrong" in markdown
assert len(re.findall(r"^### R[1-8]：", markdown, re.M)) == 8
assert not re.search(r"\d+(?:\.\d+)?\s*%", markdown)
checks.append(f"All {len(links)} local Markdown links resolve; eight gates and counter-review are present; no maturity percentage is invented.")

for key in ("can_freeze", "experimental_only", "disabled_for_engineering_release", "requires_human_signoff", "revalidation_triggers"):
    assert freeze[key]
assert goal["thaw_authorized"] is False and freeze["thaw_authorized"] is False
assert goal["existing_acceptance_gates_changed"] is False
assert freeze["controlled_thaw_proposal"]["original_gates_are_binding"] is True
assert freeze["controlled_thaw_proposal"]["roadmap_gates_are_additive_not_substitutes"] is True
assert "既有自主推进" in freeze["authorization_note"]
assert "new_FE_or_commercial_runs_authorized_by_this_file" not in freeze
checks.append("Freeze categories are complete, M40/gates remain unchanged, and existing user authorization is preserved.")

assert probes["source_contract"]["baseline_errors"] == []
assert probes["source_contract"]["added_topology_errors"]
assert probes["generic_output_requirement"]["result"]["status"] == "blocked_invalid_inputs"
assert probes["multi_stage_requirement"]["status"] == "blocked_unsupported_scope"
assert probes["unknown_mixed_family"]["status"] == "blocked_unsupported_scope"
assert probes["bench"]["case_count"] == 40 and probes["bench"]["labeled_cases"] == 0
assert probes["caller_provenance"]["agent_proposed"]["status"] == "pass_pending_human_confirmation"
assert probes["caller_provenance"]["user"]["status"] == "pass"
checks.append("Stored read-only boundary observations match every runtime conclusion reported here.")

for rel, expected in probes["source_files_sha256"].items():
    assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == expected, f"Source drift: {rel}"
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).splitlines()
assert head == COMMIT and status == []
checks.append("All bound source/data/gate/report bytes still match; product HEAD is unchanged and worktree is clean.")

deliverables = ["goal-map.json", "freeze-contract.json", "ROADMAP.md", "boundary-probes.json", "probe_boundaries.py"]
report = {
    "schema": "gearbase.goal-artifact-validation/1",
    "passed": True,
    "source_commit": head,
    "scope": "Audit artifact consistency and original-byte bindings only; not a full product, CAD, FE or engineering-release validation.",
    "checks": checks,
    "product_git_status": status,
    "artifacts_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in deliverables},
}
(HERE / "artifact-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
