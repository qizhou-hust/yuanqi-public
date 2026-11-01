"""Source-bound finite gear front and explicit tolerance-scenario assessment.

This is complete enumeration of a declared finite set, not a continuous/global
Pareto claim. Physics and acceptance remain in source_optimize.verify_writeback.
No oil, material, safety limit or tolerance distribution is supplied implicitly.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import math
import pathlib

from ..kernel import epsilon as EP
from ..kernel import source_doc as SD
from ..kernel import units as U
from . import math_source as MS
from . import source_optimize as SO

SCHEMA = "gearmath.source-frontier/1"
SENSES = {"volume_mm3": "min", "center_distance_mm": "min", "safety_min": "max"}


def implementation_sha256():
    """Invalidate on any executable source change in the calculation package."""
    root = pathlib.Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.py")):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def identity(doc, decl, spec):
    root = pathlib.Path(__file__).resolve().parents[2]
    evidence = {}
    for row in doc.get("evidence", {}).values():
        certificate = row.get("certificate") or {}
        ref = certificate.get("ref", "")
        if certificate.get("kind") == "file":
            p = root / ref
            evidence[ref] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    return {"source_sha256": SD.sha256_of(doc), "declaration_sha256": SD.sha256_of(decl),
            "spec_sha256": SD.sha256_of(spec), "implementation_sha256": implementation_sha256(),
            "evidence_file_sha256": evidence}


def is_current(report, doc, decl, spec):
    return not _certificate_errors(doc) and report.get("identity") == identity(doc, decl, spec)


def _certificate_errors(doc):
    """A current actual-file hash cannot replace a registered expected-file hash."""
    errors = MS.validate(doc)
    return errors if errors else MS.verify_certificates(doc)


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _validate(decl, spec):
    if not isinstance(spec.get("source"), str) or not spec["source"].strip():
        raise ValueError("finite-set source is required")
    variables = {v["name"]: v for v in decl["variables"]}
    axes = spec.get("axes", {})
    if set(axes) != set(variables):
        raise ValueError("axes must cover exactly the declaration variables")
    for name, axis in axes.items():
        v = variables[name]
        if not isinstance(axis, list) or not axis or not all(_finite(x) for x in axis):
            raise ValueError(f"{name}: nonempty finite numeric axis required")
        if len(set(axis)) != len(axis):
            raise ValueError(f"{name}: duplicate axis value")
        for x in axis:
            if v["kind"] in ("ordered_choice", "choice"):
                if x not in v["values"]:
                    raise ValueError(f"{name}: value outside declared choices")
            elif not v["lo"] <= x <= v["hi"]:
                raise ValueError(f"{name}: value outside declared bounds")
            if v["kind"] == "integer" and int(x) != x:
                raise ValueError(f"{name}: integer required")
            if v["kind"] == "continuous":
                ticks = x / v["resolution"]
                if abs(ticks - round(ticks)) > 1e-8:
                    raise ValueError(f"{name}: value off manufacturing resolution")
    scenarios = spec.get("tolerance_scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("explicit nonempty tolerance_scenarios required")
    ids = set()
    for s in scenarios:
        if not isinstance(s.get("id"), str) or not s["id"] or s["id"] in ids:
            raise ValueError("unique scenario ids required")
        ids.add(s["id"])
        if not isinstance(s.get("source"), str) or not s["source"].strip():
            raise ValueError("scenario source required")
        if set(s.get("offsets", {})) != set(variables):
            raise ValueError("scenario offsets must explicitly cover all variables (zero included)")
        for n, delta in s["offsets"].items():
            if not _finite(delta):
                raise ValueError("finite scenario offsets required")
            if variables[n]["kind"] != "continuous" and delta != 0:
                raise ValueError("manufacturing offsets apply only to continuous variables")
    return variables


def _document(parent, work, decl, x, provenance):
    doc = copy.deepcopy(work)
    tag = SD.sha256_of({"x": x, "provenance": provenance})[:16]
    doc["id"] = f"{parent['id']}.finite-{tag}"
    for v in decl["variables"]:
        doc["inputs"][v["name"]] = {"value": x[v["name"]], "unit": v["unit"],
                                    "provenance": "optimizer", "source": provenance}
    doc["note"] = (doc.get("note", "") + " Finite candidate; held evidence remains exactly as declared. "
                   "Candidate constraints and ranges may be agent_proposed; this is not engineering release.")
    return doc


def _evaluate(doc, decl):
    errors = _certificate_errors(doc)
    if errors:
        return {"status": "blocked", "reason": "invalid_source_certificate", "certificate_errors": errors}
    try:
        ver = SO.verify_writeback(doc, decl)  # fresh source rebuild, no search cache
        fam, case = SO._family(decl)
        model = SO.build_family_model(doc, fam, case)  # independent objective rebuild
        res = model.evaluate(["V_blank", "a_w", "S_F_1", "S_F_2", "S_H_1", "S_H_2"])
        if res.status != "ok" or res.domain_violations:
            return {"status": "blocked", "reason": res.status, "verification": ver}
        values = {"volume_mm3": U.from_canonical(res.values["V_blank"], "mm^3"),
                  "center_distance_mm": U.from_canonical(res.values["a_w"], "mm"),
                  "safety_min": min(res.values[n] for n in ("S_F_1", "S_F_2", "S_H_1", "S_H_2"))}
        if not all(_finite(x) for x in values.values()):
            return {"status": "blocked", "reason": "nonfinite_objective", "verification": ver}
        return {"status": "pass" if ver["all_confirmed"] else "fail", **values, "verification": ver}
    except (ValueError, ArithmeticError, KeyError) as exc:
        return {"status": "blocked", "reason": f"{type(exc).__name__}: {exc}"}


def finite_frontier(doc, decl, spec):
    """Enumerate explicit axes in declaration units; report all scenario outcomes.

    safety_min is min(SF1,SF2,SH1,SH2), dimensionless raw safety, not a
    normalized margin. Feasibility separately enforces each declared limit.
    Offsets are in variable declaration units and bypass nominal design bounds:
    manufacturing deviations are checked against physics and acceptance limits.
    """
    SO.require_tip_shortening(decl)
    variables = _validate(decl, spec)
    errors = _certificate_errors(doc)
    if errors:
        raise SO.OptimizeBlocked(errors)
    work, _, _, errors = SO.check_against_document(doc, decl)
    if errors:
        raise SO.OptimizeBlocked(errors)
    origin = identity(doc, decl, spec)
    provenance = f"explicit finite enumeration; {spec['source']}; identity={SD.canonical_json(origin)}"
    names = list(variables)
    points = []
    for vals in itertools.product(*(spec["axes"][n] for n in names)):
        x = dict(zip(names, vals))
        candidate = _document(doc, work, decl, x, provenance)
        point = {"index": len(points), "x": x, "document": candidate,
                 "document_sha256": SD.sha256_of(candidate), **_evaluate(candidate, decl)}
        samples = []
        for s in spec["tolerance_scenarios"]:
            sx = {n: x[n] + s["offsets"][n] for n in names}
            sd = _document(doc, work, decl, sx, provenance + f"; tolerance scenario {s['id']}: {s['source']}")
            samples.append({"id": s["id"], "x": sx, "document_sha256": SD.sha256_of(sd), **_evaluate(sd, decl)})
        counts = {k: sum(s["status"] == k for s in samples) for k in ("pass", "fail", "blocked")}
        point["tolerance"] = {"scenarios": samples, "counts": counts, "total": len(samples),
                              "feasible_fraction": counts["pass"] / len(samples),
                              "all_scenarios_feasible": counts["pass"] == len(samples)}
        points.append(point)
    feasible = [p for p in points if p["status"] == "pass"]
    front = [feasible[i]["index"] for i in EP.nondominated(feasible, SENSES)]
    return {"schema": SCHEMA, "identity": origin, "source_id": doc["id"], "declaration_id": decl["id"],
            "status": "ok" if front else "no_feasible_point", "spec": copy.deepcopy(spec), "senses": dict(SENSES),
            "points": points, "front": front, "coverage": {"finite_candidates": len(points), "feasible": len(feasible)},
            "scope": "Complete only for explicit finite axes. Not a global continuous Pareto front. "
                     "Safety=min(SF1,SF2,SH1,SH2); each acceptance limit is checked separately. "
                     "Tolerance fraction is unweighted specified-scenario coverage, not probability or interval proof. "
                     "Tribology, thermal, shaft/bearing/key are not checked here. Held evidence limitations remain."}
