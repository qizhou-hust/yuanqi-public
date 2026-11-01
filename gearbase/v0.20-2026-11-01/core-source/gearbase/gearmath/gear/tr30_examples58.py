"""TR30 examples 5--8 transcription and an input-only geometry/load probe.

The probe accepts the common raw-case schema used by examples 1--8. It uses
the ordinary Formula/Model engine, never reads raw_outputs while constructing
formulas or inputs, and does not substitute its partial coverage for a full
rating. Internal roots, double-helical rating and residual protuberance remain
explicit full-rating limitations even when the geometric identities match.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..kernel.graph import Formula, InputSpec, Model
from ..kernel import units

DATA = Path(__file__).resolve().parents[2] / "data/tr30/examples-5-8.json"
REF = "ISO/TR 6336-30:2022"


def load_cases():
    return json.loads(DATA.read_text(encoding="utf-8"))["cases"]


def load(number):
    return next(case for case in load_cases() if case["example_number"] == number)


def _rows(case, field="raw_inputs"):
    aliases = {"da": "d_a", "db": "d_b", "df": "d_f", "xE": "x_E", "xEV": "x_EV",
               "hfP": "h_fP", "rhofP": "rho_fP", "k_span": "k", "helix_hand": "hand",
               "f_pt": "f_pT", "v": "v_w"}
    return {aliases.get(row["key"], row["key"]): row for row in case[field]}


def _require_number(value, name):
    if type(value) not in (int, float):
        raise ValueError(f"Missing independent numeric input: {name}")
    return value


def build_probe(case):
    """Build a Formula graph from raw input rows only; no reference readback.

    da is an independent input in TR tables, so it is never a formula check.
    Parenthesized x values are excluded. Span measurements determine xE;
    operating centre distance plus the non-parenthesized x determines nominal
    x. For internal wheels without a span, no wheel xE/root result is invented.
    """
    raw = _rows(case)
    values, specs, formulas = {}, [], []

    def put(name, key, index=0, unit=None, domain=()):
        row = raw[key]
        value = _require_number(row["values"][index], f"{key}[{index}]")
        chosen_unit = unit or row["unit"]
        if row["unit"] == "kN*m":
            value *= 1000
            chosen_unit = "N*m"
        specs.append(InputSpec(name, chosen_unit, row["label"], tuple(domain)))
        cite = row["citation"]
        values[name] = (value, chosen_unit, "user", f"{cite['source']} PDF {cite['pdf_page']}: {cite['location']}")

    def add(q, unit, expr, description, domain=()):
        formulas.append(Formula(f"tr30.probe.{q}", q, unit, expr, f"{REF} {description}", tuple(domain),
                                note="Partial input-only geometry/load probe; no complete rating acceptance"))

    put("m_n", "m_n", domain=("m_n > 0",))
    put("alpha_n", "alpha_n", domain=("alpha_n > 0", "alpha_n < pi/2"))
    put("beta", "beta", domain=("beta >= 0", "beta < pi/2"))
    put("a_w", "a_w")
    put("T_1", "T_1", domain=("T_1 > 0",))
    put("n_1", "n_1", domain=("n_1 > 0",))
    put("b_eff", "b_eff", domain=("b_eff > 0",))
    for i in (1, 2):
        put(f"z_{i}", "z", i-1, domain=(f"z_{i}**2 > 0",))
        put(f"da_{i}", "d_a", i-1)
        put(f"f_pt_{i}", "f_pT", i-1)
    add("alpha_t", "rad", "atan(tan(alpha_n)/cos(beta))", "4.2.1 / Annex A.6: normal-to-transverse angle")
    add("m_t", "mm", "m_n/cos(beta)", "Annex A.6: transverse module")
    add("beta_b", "rad", "atan(tan(beta)*cos(alpha_t))", "Annex A.6: base helix angle")
    for i in (1, 2):
        add(f"d_{i}", "mm", f"z_{i}*m_t", "4.2.13 / Annex A.6: signed reference diameter")
        add(f"db_{i}", "mm", f"d_{i}*cos(alpha_t)", "Annex A.6: signed base diameter")
        add(f"dw_{i}", "mm", f"2*a_w*z_{i}/(z_1 + z_2)", "Annex A.6: signed working pitch diameter")
    add("alpha_wt", "rad", "acos((d_1+d_2)*cos(alpha_t)/(2*a_w))", "Annex A.6: working pressure angle from input centre distance",
        ("a_w*(z_1+z_2) > 0",))
    add("x_sum", "1", "(inv(alpha_wt)-inv(alpha_t))/rad*(z_1+z_2)/(2*tan(alpha_n))",
        "4.2.18 / Annex A.6: nominal shift sum from operating centre distance")
    xrow = raw["x"]
    # The printed parentheses are part of the source contract, not optional metadata.
    independent = [i for i, display in enumerate(xrow["display"]) if not display.strip().startswith("(")]
    if len(independent) != 1:
        raise ValueError("TR30 nominal shift needs exactly one non-parenthesized independent value")
    i = independent[0]+1
    j = 3-i
    put(f"x_{i}", "x", i-1)
    add(f"x_{j}", "1", f"x_sum-x_{i}", "4.2.18 / Annex A.6: dependent nominal profile shift")
    for i in (1, 2):
        if raw["W_k"]["values"][i-1] is None:
            continue
        put(f"W_k_{i}", "W_k", i-1)
        put(f"k_span_{i}", "k", i-1)
        put(f"hfP_{i}", "h_fP", i-1)
        add(f"xE_{i}", "1", f"(W_k_{i}-m_n*cos(alpha_n)*(pi*(k_span_{i}-.5)+z_{i}*inv(alpha_t)/rad))/(2*m_n*sin(alpha_n))",
            "Annex A.6: generating shift from independent normal span measurement", (f"z_{i} > 0",))
        if "h_fP_pre" in raw:
            put(f"hfP_pre_{i}", "h_fP_pre", i-1)
            put(f"q_{i}", "q", i-1)
            add(f"xEV_{i}", "1", f"xE_{i}+q_{i}/(m_n*sin(alpha_n))",
                "4.10 / ISO 21771-1:2024 9.5 equations 249/250: pre-finish offset with same thickness basis")
            add(f"df_{i}", "mm", f"d_{i}+2*m_n*(xEV_{i}-hfP_pre_{i})",
                "4.10 Table 18 root diameter based on pre-finishing generated profile")
        else:
            add(f"df_{i}", "mm", f"d_{i}+2*m_n*(xE_{i}-hfP_{i})", "4.2.12 / Annex A.6: generated root diameter")
    hand = " ".join(str(v) for v in raw["hand"]["values"]).lower()
    if "double" in hand:
        if "b_per_helix" in raw:
            put("b_overlap", "b_per_helix")
        else:
            add("b_overlap", "mm", "b_eff/2", "4.2.9: double-helical overlap uses one helix")
    else:
        add("b_overlap", "mm", "b_eff", "4.2.9: single-helix/spur contact width")
    add("eps_beta", "1", "b_overlap*sin(beta)/(pi*m_n)", "4.2.9 / Annex A.6: overlap ratio")
    add("eps_alpha", "1", "(sqrt(da_1**2-db_1**2)+where(z_2 > 0, sqrt(da_2**2-db_2**2), -sqrt(da_2**2-db_2**2))-2*a_w*sin(alpha_wt))/(2*pi*m_t*cos(alpha_t))",
        "4.2.13 / Annex A.6: signed transverse contact ratio")
    add("eps_gamma", "1", "eps_alpha+eps_beta", "Annex A.6: total contact ratio")
    add("F_t", "N", "2*T_1/d_1", "Annex A.7: reference-cylinder tangential force")
    add("v", "m/s", "pi*d_1*n_1", "Annex A.7: reference-cylinder pitch-line velocity")
    add("v_w", "m/s", "pi*dw_1*n_1", "Tables 4--18: working pitch-line velocity v_w")
    add("f_pb", "um", "max(f_pt_1,f_pt_2)*cos(alpha_t)", "4.2.1 equation (1): base pitch deviation without rounding")
    m = Model(formulas, inputs=specs, editions={"ISO/TR 6336-30": "2022"})
    for name, value in values.items():
        m.set(name, *value)
    m.probe_case_id = case["id"]
    m.probe_scope = "geometry_load_base_pitch_only"
    return m


def compare_probe(case, evidence=None):
    """Numerical diagnostic with strict and printed-precision results separate.

    Source bytes are optional for diagnostic use, but without them the result
    cannot claim source identity verification. This function never accepts a
    standard case: complete K/Z/Y/stress/safety coverage is outside its scope.
    """
    evidence = evidence or {}
    verified = True
    for source in case["sources"]:
        blob = evidence.get(source["id"])
        if blob is None:
            verified = False
        elif hashlib.sha256(blob).hexdigest() != source["sha256"]:
            return {"id": case["id"], "accepted": False, "status": "blocked_invalid_sources", "rows": []}
    try:
        m = build_probe(case)
    except (KeyError, ValueError) as exc:
        return {"id": case.get("id"), "accepted": False, "status": "blocked_missing_inputs", "errors": [str(exc)], "rows": []}
    raw = _rows(case, "raw_outputs")
    aliases = {"d": "d", "d_b": "db", "x_E": "xE", "x_EV": "xEV", "d_f": "df", "d_w": "dw",
               "F_t": "F_t", "v_w": "v_w", "f_pb": "f_pb", "eps_alpha": "eps_alpha", "eps_beta": "eps_beta", "eps_gamma": "eps_gamma"}
    refs = []
    for key, prefix in aliases.items():
        if key not in raw:
            continue
        rr = raw[key]
        for index, value in enumerate(rr["values"]):
            q = f"{prefix}_{index+1}" if len(rr["values"]) == 2 else prefix
            if q in m.formulas:
                display = rr["display"][index].replace(" ", "").replace(",", ".")
                decimals = len(display.split(".", 1)[1]) if "." in display else 0
                refs.append((q, rr, index, value, decimals))
    result = m.evaluate([r[0] for r in refs])
    if result.status != "ok":
        return {"id": case["id"], "accepted": False, "status": result.status, "errors": result.errors,
                "domain_violations": result.domain_violations, "rows": []}
    rows = []
    for q, rr, index, expected, decimals in refs:
        actual = units.from_canonical(result.values[q], rr["unit"])
        delta = actual-expected
        absolute = abs(delta) <= .01+1e-12
        relative = abs(delta) <= .005*abs(expected)+1e-12
        rounding = abs(delta) <= .5*10**(-decimals)+1e-12
        stage = "load" if q in ("F_t", "v_w") else "K" if q == "f_pb" else "geometry"
        rows.append({"quantity": q, "stage": stage, "actual": actual, "reference": expected, "unit": rr["unit"],
                     "difference": delta, "absolute_tolerance": .01, "relative_tolerance": .005,
                     "strict_match": absolute and relative, "rounding_compatible": rounding,
                     "display": rr["display"][index], "citation": rr["citation"], "formula_derived": True})
    rows.sort(key=lambda row: ("geometry", "load", "K").index(row["stage"]))
    return {"id": case["id"], "official_example": case["official_example"], "accepted": False,
            "numerical_complete": False, "evidence_level": "not_assessed",
            "status": "partial_comparison", "source_identity_verified": verified,
            "scope": m.probe_scope, "model_sha256": result.model_sha256,
            "rows": rows, "first_divergence": next((r for r in rows if not r["strict_match"]), None),
            "formula_inputs": sorted(m.inputs), "product_strength": "not_assessed",
            "full_rating_blockers": case.get("unsupported_features", ["Full rating not implemented by geometry/load probe"]),
            "unmodelled_reference_rows": len(case["raw_outputs"])-len({r[1]["key"] for r in refs})}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="exact supplemented TR30 PDF bytes")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = {"tr30": args.source.read_bytes()} if args.source else None
    report = {"schema": "gearmath.tr30_partial/v1", "cases": [compare_probe(c, evidence) for c in load_cases()]}
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content, end="")
    raise SystemExit(2)
