"""M38 unlabelled evaluation and receipt-bound model-output file adapter.

No engineer labels are created. The model pipeline is explicitly model extraction
and reply followed by the existing deterministic requirement_compile tool.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import pathlib

from . import bench as B
from . import intent as IT
from . import nlp_templates as NT

MODEL_SCHEMA = "gearbase.model-bench-output/1"
OUTPUT_KEYS = {"parsed_requirement", "parser_derivations", "reply_text", "compile_result"}


def file_sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _sources(text):
    """Preserve exact source spans while excluding standard/material identifiers."""
    out = [{"value": r['value'], "kind": "input_text", "span": r['span'], "quote": r['quote']}
           for r in B.text_number_sources(text) if r['value'] is not None]
    for template, row in NT.TEMPLATES.items():
        for param, (lo, hi, _) in row["params"].items():
            out.extend({"value": float(v), "kind": "published_constant", "ref": f"nlp_templates.{template}.{param}.{bound}"}
                       for bound, v in (("lo", lo), ("hi", hi)))
    return out


def field_sources(text, output):
    sources = _sources(text)
    derivations = list(output.get("parser_derivations", []))
    derivations += (output.get("compile_result") or {}).get("derivations", [])
    pending = list(derivations)
    while pending:
        remaining = []
        for d in pending:
            try:
                operands = d["operands"]
                expected = IT.recompute(d)
                valid = all(any(math.isclose(float(v), s["value"], rel_tol=1e-9, abs_tol=1e-12) for s in sources)
                            for v in operands.values()) and math.isclose(expected, d["value"], rel_tol=1e-9)
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                valid = False
            if valid:
                sources.append({"value": float(d["value"]), "kind": "registered_derivation",
                                "formula_id": d["formula_id"], "operands": operands})
            else:
                remaining.append(d)
        if len(remaining) == len(pending):
            break
        pending = remaining
    return [{"field": k, "value": v, "sources": [s for s in sources if math.isclose(float(v), s["value"], rel_tol=1e-9, abs_tol=1e-12)]}
            for k, v in output["parsed_requirement"].items() if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _pipeline_output(output):
    if not isinstance(output, dict) or set(output) - OUTPUT_KEYS:
        raise ValueError("output accepts only parsed_requirement/parser_derivations/reply_text/compile_result")
    if not isinstance(output.get("parsed_requirement"), dict) or not isinstance(output.get("reply_text"), str):
        raise ValueError("parsed_requirement object and reply_text string are required")
    if not isinstance(output.get("parser_derivations", []), list):
        raise ValueError("parser_derivations must be an array")
    # Reconstruct rather than trusting model-authored static explanations or tool numbers.
    compiled = IT.requirement_compile({"requirement": output["parsed_requirement"]})
    if "compile_result" in output and output["compile_result"] != compiled:
        raise ValueError("supplied compile_result differs from actual requirement_compile result")
    return {**output, "compile_result": compiled}


def evaluate_outputs(outputs, cases_doc=None):
    doc = cases_doc or B.load_cases()
    expected = [c["id"] for c in doc["cases"]]
    if set(outputs) != set(expected) or len(expected) != len(set(expected)):
        raise ValueError("outputs must cover every benchmark id exactly once")
    prepared = {cid: _pipeline_output(outputs[cid]) for cid in expected}
    iterator = iter(expected)
    result = B.evaluate(lambda _: prepared[next(iterator)], doc)
    # Keep the original metric and its scope unchanged; independently strengthen
    # self-consistency so a forged compiled state cannot hide missing questions.
    for case, row in zip(doc["cases"], result["per_case"]):
        out = prepared[case["id"]]
        res = out["compile_result"]
        asked = {q["field"] for q in res.get("questions", [])}
        if res["status"] in ("needs_clarification", "pass_pending_human_confirmation"):
            required = set(IT.required_fields(out["parsed_requirement"]))
            row["clarification_consistent"] = asked == required
            row["required_fields"] = sorted(required)
        else:
            row["clarification_consistent"] = None
            row["required_fields"] = None
        row["field_sources"] = field_sources(case["text_zh"], out)
    result["metrics"]["clarification_inconsistent_cases"] = [r["id"] for r in result["per_case"] if r["clarification_consistent"] is False]
    result["evaluation_scope"] = (
        "All benchmark cases contribute to number traceability, outcome distribution and tool clarification self-consistency. "
        "Accuracy and clarification precision/recall require engineer gold and remain null without labels. "
        "Model extraction/reply is followed by the real deterministic compiler; this does not assess engineering correctness "
        "or semantic completeness of extraction, nor whether free-text model questions match compiler questions.")
    return result, prepared


def evaluate_model_file(path, cases_doc=None, bench_path=B.BENCH):
    path = pathlib.Path(path)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if envelope.get("schema") != MODEL_SCHEMA:
        raise ValueError(f"schema must be {MODEL_SCHEMA}")
    if envelope.get("bench_sha256") != file_sha(bench_path):
        raise ValueError("benchmark hash mismatch")
    for key in ("name", "version"):
        if not isinstance(envelope.get("model", {}).get(key), str) or not envelope["model"][key].strip():
            raise ValueError(f"model.{key} is required")
    run = envelope.get("run", {})
    for key in ("id", "provider"):
        if not isinstance(run.get(key), str) or not run[key].strip():
            raise ValueError(f"run.{key} is required")
    if run.get("kind") != "actual_model_run":
        raise ValueError("only kind=actual_model_run is eligible for a model report; fixtures are not runs")
    if not all(isinstance(run.get(k), str) for k in ("started_at", "completed_at")):
        raise ValueError("run started_at/completed_at are required")
    start, end = (datetime.fromisoformat(run[k].replace("Z", "+00:00")) for k in ("started_at", "completed_at"))
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError("ordered timezone-aware run timestamps required")
    receipt = run.get("receipt", {})
    if not isinstance(receipt.get("path"), str) or not receipt["path"]:
        raise ValueError("run.receipt.path is required")
    receipt_path = pathlib.Path(receipt["path"])
    if not receipt_path.is_absolute():
        receipt_path = path.parent / receipt_path
    if not receipt_path.is_file() or not receipt_path.stat().st_size or file_sha(receipt_path) != receipt.get("sha256"):
        raise ValueError("nonempty run receipt file with matching sha256 required")
    rows = envelope.get("cases", [])
    if not isinstance(rows, list) or any(not isinstance(r, dict) or "id" not in r or "output" not in r for r in rows):
        raise ValueError("cases must contain id/output rows")
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("duplicate case ids")
    result, outputs = evaluate_outputs({r["id"]: r["output"] for r in rows}, cases_doc)
    result["system"] = {"kind": "actual_model_output_file", "model": envelope["model"], "run": run,
                        "output_file": str(path.resolve()), "output_file_sha256": file_sha(path), "bench_file_sha256": file_sha(bench_path),
                        "receipt_verification": "file integrity checked; model/provider identity is run-recorded, not provider-attested"}
    return result, outputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-output", type=pathlib.Path)
    p.add_argument("--out", type=pathlib.Path, required=True)
    args = p.parse_args()
    if args.model_output:
        result, outputs = evaluate_model_file(args.model_output)
    else:
        doc = B.load_cases()
        outputs = {c["id"]: B.rule_baseline(c["text_zh"]) for c in doc["cases"]}
        result, outputs = evaluate_outputs(outputs, doc)
        result["system"] = {"kind": "deterministic_rule_baseline", "model": None, "bench_file_sha256": file_sha(B.BENCH)}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    (args.out / "outputs.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))
    return 0 if result["metrics"]["hallucination_gate"] == "pass" and not result["metrics"]["clarification_inconsistent_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
