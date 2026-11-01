"""TR30 source-gated comparison: reference values never become model inputs.

The suite explicitly indexes the eight original-source transcriptions.
Missing source bytes remain blocked; actual partial/full diagnostics never
masquerade as standard-example acceptance.
Run ``python3 -m gearmath.gear.tr30_case`` to audit all eight slots (exit 2
while blocked). All code uses the standard library and the existing model.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from ..kernel import units
from ..kernel.expr import FormulaError
from ..kernel.graph import InputError
from .rating import pair_model

DATA = Path(__file__).resolve().parents[2] / "data" / "tr30" / "suite.json"
STAGES = ("geometry", "load", "K", "Z/Y", "stress", "safety")


class ContractError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def load_suite():
    suite = json.loads(DATA.read_text(encoding="utf-8"))
    if "case_files" in suite:
        suite["cases"] = [case for name in suite["case_files"]
                          for case in json.loads((DATA.parent / name).read_text(encoding="utf-8"))["cases"]]
    return suite


def load(case_id):
    for case in load_suite()["cases"]:
        if case["id"] == case_id:
            return case
    raise ValueError(f"Unknown TR30 slot: {case_id}")


def _require(condition, message):
    if not condition:
        raise ContractError("blocked_invalid_contract", message)


def _number(value, label):
    _require(type(value) in (int, float) and math.isfinite(value), f"{label}: finite number required")
    return value


def _sources(case, evidence):
    sources = case.get("sources")
    if not sources:
        raise ContractError("blocked_missing_sources", case.get("blocking_reason") or "TR30 original pages missing")
    _require(isinstance(sources, list), "sources must be a list")
    verified = {}
    for row in sources:
        _require(isinstance(row, dict), "source entry must be an object")
        sid, sha = row.get("id"), row.get("sha256")
        _require(isinstance(sid, str) and sid and sid not in verified, "source id missing/duplicate")
        _require(isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), "source sha256 invalid")
        data = evidence.get(sid)
        if data is None:
            raise ContractError("blocked_missing_sources", f"Source bytes missing: {sid}")
        _require(isinstance(data, bytes), f"source {sid}: bytes required")
        if hashlib.sha256(data).hexdigest() != sha:
            raise ContractError("blocked_invalid_sources", f"Source hash mismatch: {sid}")
        _require(type(row.get("page_count")) is int and row["page_count"] > 0, f"source {sid}: page_count required")
        verified[sid] = row
    return verified


def _citation(citation, sources, label):
    _require(isinstance(citation, dict), f"{label}: citation required")
    source = sources.get(citation.get("source"))
    _require(source is not None, f"{label}: unknown source")
    page = citation.get("pdf_page")
    _require(type(page) is int and 1 <= page <= source["page_count"], f"{label}: PDF page outside source")
    _require(isinstance(citation.get("location"), str) and citation["location"].strip(), f"{label}: table/row/section location required")
    return f"{citation['source']} PDF {page}: {citation['location']}"


def build_model(case, evidence=None):
    """Build only after source, edition, method, and per-field citations exist.

    ``evidence`` maps source IDs to exact user-provided PDF bytes. It is not a
    map of calculated coefficients. No document paths or network are opened.
    """
    if isinstance(case, str):
        case = load(case)
    _require(isinstance(case, dict), "case must be an object")
    _require(case.get("schema") == "gearmath.tr30_case/v1", "unsupported case schema")
    _require(case.get("standard") == "ISO/TR 6336-30:2022", "TR30 edition must be explicit: 2022")
    sources = _sources(case, evidence or {})
    official = case.get("official_example")
    _require(isinstance(official, dict) and isinstance(official.get("label"), str) and official["label"].strip(), "official example label must be transcribed from source")
    _citation(official.get("citation"), sources, "official_example")
    editions, selectors = case.get("editions"), case.get("selectors")
    _require(isinstance(editions, dict) and editions, "explicit editions required")
    _require(isinstance(selectors, dict) and selectors, "explicit method selectors required")
    edition_citations, selector_citations = case.get("edition_citations", {}), case.get("selector_citations", {})
    _require(isinstance(edition_citations, dict) and isinstance(selector_citations, dict), "edition/selector citations must be objects")
    for part, edition in editions.items():
        _require(isinstance(part, str) and isinstance(edition, str) and edition, "invalid edition")
        _citation(edition_citations.get(part), sources, f"edition {part}")
    method_sources = {name: _citation(selector_citations.get(name), sources, f"selector {name}") for name in selectors}
    factor_options = {}
    factor_sources = {}
    if "factor_selectors" in case:
        factors, citations = case["factor_selectors"], case.get("factor_selector_citations", {})
        _require(isinstance(factors, dict) and isinstance(citations, dict), "factor selectors and citations must be objects")
        factor_sources = {name: _citation(citations.get(name), sources, f"factor selector {name}") for name in factors}
        factor_options["factor_selectors"] = factors
        factor_options["factor_selector_sources"] = factor_sources
    model = pair_model(editions=editions, selectors=selectors, selector_sources=method_sources, **factor_options)
    model.selector_sources.update(factor_sources)
    for part in editions:
        model.edition_sources[part] = _citation(edition_citations[part], sources, f"edition {part}")
    values = case.get("inputs")
    _require(isinstance(values, dict) and values, "input records required")
    references = case.get("references")
    _require(isinstance(references, list) and references, "reference rows required")
    names = set()
    previous_stage = -1
    for row in references:
        _require(isinstance(row, dict), "reference row must be an object")
        q = row.get("quantity")
        _require(isinstance(q, str) and q and q not in names, "reference quantity missing/duplicate")
        names.add(q)
        _require(row.get("stage") in STAGES, f"{q}: invalid comparison stage")
        stage = STAGES.index(row["stage"])
        _require(stage >= previous_stage, "references must be ordered geometry/load/K/Z-Y/stress/safety")
        previous_stage = stage
        _number(row.get("value"), f"{q} reference")
        for field in ("abs_tol", "rel_tol"):
            _require(_number(row.get(field), f"{q} {field}") >= 0, f"{q}: negative tolerance")
        _citation(row.get("citation"), sources, f"reference {q}")
        _require(isinstance(row.get("tolerance_basis"), str) and row["tolerance_basis"].strip(), f"{q}: tolerance basis required")
        _require(q in model.formulas or q in model.specs, f"{q}: unknown model quantity")
        expected_unit = model.formulas[q].unit if q in model.formulas else model.specs[q].unit
        _require(row.get("unit") in units.UNITS and units.unit(row["unit"])[0] == units.unit(expected_unit)[0], f"{q}: reference unit dimension mismatch")
    for name, row in values.items():
        _require(isinstance(row, dict), f"{name}: input record must be an object")
        source = _citation(row.get("citation"), sources, f"input {name}")
        _number(row.get("value"), f"{name} input")
        provenance = row.get("provenance")
        _require(provenance in {"user", "standard_constant", "evidence"}, f"{name}: assumptions/agent proposals cannot validate TR30")
        model.set(name, row["value"], row.get("unit"), provenance, source)
    return model


def compare(case, evidence=None):
    """Compare independently computed outputs with immutable reference rows.

    A matching evidence input is ``input_not_formula``. Full numerical coverage
    is reported separately from source review. This runner cannot grant E4 or
    M33 acceptance until an independent formula-source review gate is added.
    Product strength is not assessed by this standard-example runner.
    """
    if isinstance(case, str):
        case = load(case)
    if not isinstance(case, dict):
        return {"accepted": False, "status": "blocked_invalid_contract", "errors": ["case must be an object"]}
    if "raw_inputs" in case:
        # Original transcriptions are dispatched only after exact source bytes
        # and every transcribed row's page index have been checked.
        try:
            sources = _sources(case, evidence or {})
            for field in ("raw_inputs", "raw_outputs"):
                for row in case[field]:
                    _citation(row.get("citation"), sources, field)
            for name in case.get("surface_selectors", {}):
                _citation(case.get("surface_selector_citations", {}).get(name), sources, f"selector {name}")
        except ContractError as exc:
            return {"id": case.get("id"), "accepted": False, "numerical_complete": False,
                    "status": exc.code, "errors": [str(exc)], "rows": [],
                    "product_strength": "not_assessed", "evidence_level": "not_assessed"}
        from .tr30_examples58 import compare_probe
        if case.get("example_number") in (1, 2, 3, 4):
            from .tr30_rating import compare_rating
            from .m33_acceptance import tr30_acceptance
            report = compare_rating(case)
            report["geometry_load_probe"] = compare_probe(case, evidence)
            if report.get("status") == "full_rating_diagnostic":
                # 分档判据（4.2.14/4.2.15）给出数值验收；E4/全表另要求输出表全覆盖、附录A 中间量齐全、
                # 无显式适用性假设（m33_acceptance.e4_gate），任一不满足即不授予
                acceptance = tr30_acceptance(report, case)
                report["acceptance"] = acceptance
                report["accepted"] = acceptance["e4_gate"]
        else:
            report = compare_probe(case, evidence)
        report["source_identity_verified"] = True
        report["contract_sha256"] = hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=False,
                                                             allow_nan=False).encode()).hexdigest()
        return report
    head = {"id": case.get("id"), "standard": case.get("standard"), "accepted": False,
            "product_strength": "not_assessed", "evidence_level": "not_assessed",
            "numerical_complete": False, "formula_source_review": "not_assessed",
            "limitations": ["Numerical agreement does not verify unreviewed formula sources or grant M33/E4 acceptance"],
            "rows": [], "first_divergence": None}
    try:
        model = build_model(case, evidence)
    except ContractError as exc:
        return {**head, "status": exc.code, "errors": [str(exc)]}
    except (FormulaError, InputError) as exc:
        return {**head, "status": "blocked_invalid_contract", "errors": [str(exc)]}
    result = model.evaluate([row["quantity"] for row in case["references"]])
    validation = getattr(model, "factor_validation", {})
    head.update(model_sha256=result.model_sha256, editions=model.editions, selectors=model.selectors,
                selector_sources=model.selector_sources, factor_validation=validation,
                contract_sha256=hashlib.sha256(json.dumps(case, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest(),
                source_review_blockers=[{"group": name, **record} for name, record in validation.items()
                                        if record.get("iso_equation_images") != "verified"])
    if result.status != "ok":
        return {**head, "status": result.status, "missing": result.missing,
                "missing_editions": result.missing_editions, "errors": result.errors,
                "domain_violations": result.domain_violations}
    rows = []
    for ref in case["references"]:
        q = ref["quantity"]
        actual = units.from_canonical(result.values[q], ref["unit"])
        expected = ref["value"]
        delta = actual - expected
        absolute_bound, relative_bound = ref["abs_tol"], ref["rel_tol"] * abs(expected)
        both = case.get("tolerance_policy") == "tr30_both" or ref.get("tolerance_mode") == "absolute_and_relative"
        tolerance = min(absolute_bound, relative_bound) if both else max(absolute_bound, relative_bound)
        derived = q in model.formulas
        rows.append({"quantity": q, "stage": ref["stage"], "actual": actual,
                     "reference": expected, "unit": ref["unit"], "difference": delta,
                     "tolerance": tolerance, "tolerance_policy": "absolute_and_relative" if both else "max_declared_bounds",
                     "absolute_match": abs(delta) <= absolute_bound, "relative_match": abs(delta) <= relative_bound,
                     "formula_derived": derived,
                     "verdict": "input_not_formula" if not derived else ("match" if abs(delta) <= tolerance else "divergence"),
                     "citation": ref["citation"]})
    required = set(load_suite()["required_formula_outputs"])
    matched = {row["quantity"] for row in rows if row["verdict"] == "match"}
    missing = sorted(required - matched)
    first = next((row for row in rows if row["verdict"] == "divergence"), None)
    numerical_complete = first is None and not missing and all(row["verdict"] == "match" for row in rows)
    return {**head, "rows": rows, "first_divergence": first, "missing_formula_coverage": missing,
            "numerical_complete": numerical_complete,
            "status": "numerically_matched_pending_source_review" if numerical_complete else ("fail" if first else "partial_match")}


def run_suite(evidence=None, contracts=None):
    contracts = load_suite()["cases"] if contracts is None else contracts
    expected_ids = {row["id"] for row in load_suite()["cases"]}
    if not isinstance(contracts, list) or len(contracts) != 8 or \
            any(not isinstance(row, dict) for row in contracts) or \
            any(not isinstance(row.get("id"), str) for row in contracts) or \
            {row.get("id") for row in contracts} != expected_ids:
        return {"schema": "gearmath.tr30_results/v1", "status": "blocked_invalid_suite",
                "accepted": 0, "errors": ["Exactly the eight distinct TR30 slot IDs are required"]}
    labels = [row["official_example"].get("label") for row in contracts if isinstance(row.get("official_example"), dict)]
    if any(not isinstance(label, str) for label in labels) or len(labels) != len(set(labels)):
        return {"schema": "gearmath.tr30_results/v1", "status": "blocked_invalid_suite",
                "accepted": 0, "errors": ["Official example labels must be distinct"]}
    cases = [compare(case, evidence) for case in contracts]
    accepted = sum(case["accepted"] for case in cases)
    return {"schema": "gearmath.tr30_results/v1", "standard": "ISO/TR 6336-30:2022",
            "status": "pass" if accepted == 8 and len(cases) == 8 else "not_accepted",
            "total": len(cases), "accepted": accepted,
            "numerically_complete": sum(case["numerical_complete"] for case in cases),
            "numerically_accepted": sum(case.get("acceptance", {}).get("verdict") == "pass" for case in cases),
            "blocked": sum(case["status"].startswith("blocked_") for case in cases), "cases": cases}


if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="TR30 eight-case source audit and comparison")
    parser.add_argument("--contracts", type=Path, help="JSON suite with the eight fully transcribed case contracts")
    parser.add_argument("--source", action="append", default=[], metavar="ID=PATH", help="exact local source bytes for a contract source ID; repeat as needed")
    parser.add_argument("--output", type=Path, help="write the JSON audit report (exit 2 while blocked)")
    args = parser.parse_args()
    evidence = {}
    for value in args.source:
        sid, sep, path = value.partition("=")
        if not sep or not sid or sid in evidence:
            parser.error("--source requires a unique ID=PATH")
        evidence[sid] = Path(path).read_bytes()
    contracts = None
    if args.contracts:
        suite = json.loads(args.contracts.read_text(encoding="utf-8"))
        if not isinstance(suite, dict) or suite.get("schema") != "gearmath.tr30_suite/v1":
            parser.error("--contracts requires schema gearmath.tr30_suite/v1")
        contracts = suite.get("cases", [])
    report = run_suite(evidence, contracts)
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content, end="")
    sys.exit(0 if report["status"] == "pass" else 2)
