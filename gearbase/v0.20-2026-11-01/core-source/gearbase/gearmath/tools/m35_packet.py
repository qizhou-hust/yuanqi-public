"""Deterministic K02 manufacturing review *preparation*, never a release gate.

The existing audited tooth authority rejects nonzero shifts. Therefore the SVG
is a dimensioned macrogeometry drawing with an explicit missing-profile hold.
No rack/root/flank geometry or ISO 1328 grade is invented to fill this gap.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from ..gear import parameter_sheet as P
from ..kernel import units as U

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "data/kisssoft/K02-helical.json"
SCHEMA = "gearbase.m35-review-preparation/1"
GAPS = [
    "G1: audited tooth_authority rejects nonzero shift; shifted helical flank/root/cutter envelope absent",
    "G2: DIN 3961:1978 grade 6 retained; ISO 1328 grade/requirements not authorized",
    "G3: bore/hub/keyway, datum scheme, fits, dimensional tolerances and surface finish unspecified",
    "G4: material/heat-treatment manufacturing specification and inspection acceptance need approval",
    "G5: helix hand and coordinate convention not explicit in source; no hand inferred from absolute beta",
    "G6: measurement span k and ball diameter not evidenced; Wk/MdK inspection plan pending",
    "G7: external process reviewer, issues closure and signature absent",
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n").encode()


def parameter_table(raw):
    case = json.loads(raw)
    if case.get("id") != "K02-helical" or case.get("schema") != "gearbase.kisssoft.case/2":
        raise ValueError("K02 source identity/schema required")
    c, report = case["com"], case["report"]
    model, _ = P.build({1: "external", 2: "external"}, tip_diameter="input", groups=())
    values = {}

    def put(name, value, unit, locator):
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError("finite numeric source required: "+name)
        values[name] = dict(value=value, unit=unit, source=SOURCE, locator=locator)
        if name in model.specs:
            model.set(name, value, unit, "evidence", SOURCE+":"+locator)

    for n, key, unit in (("m_n", "ZS.Geo.mn", "mm"), ("alpha_n", "ZS.Geo.alfn", "rad"), ("beta", "ZS.Geo.beta", "rad")):
        put(n, c[key], unit, 'com['+repr(key)+']')
    if not 0 < c["ZS.Geo.beta"] < math.pi/4:
        raise ValueError("nonzero bounded helical angle required")
    for i in (1, 2):
        g = f"ZR[{i-1}]"
        for n, key, unit in (("z", "z", "1"), ("x", "x.nul", "1"), ("b", "b", "mm"),
                             ("da", "da.nul", "mm"), ("haP", "Tool.RefProfile.haP", "1"),
                             ("hfP", "Tool.RefProfile.hfP", "1"), ("rhofP", "Tool.RefProfile.rhofP", "1")):
            put(f"{n}_{i}", c[g+"."+key], unit, 'com['+repr(g+"."+key)+']')
        for n in ("A_sn_e", "A_sn_i"):
            r = report[f"{n}_{i}"]
            if r["unit"] != "mm":
                raise ValueError("source thickness deviations must be mm")
            put(f"{n}_{i}", r["value"], "mm", f"report.{n}_{i} (line {r['line']})")
        q = report[f"Q_grade_{i}"]
        if q["label"] != "[Q-DIN 3961:1978]" or q["unit"] != "1":
            raise ValueError("DIN source grade contract changed")
        put(f"DIN3961_grade_{i}", q["value"], "1", f"report.Q_grade_{i} (line {q['line']})")
        for key in ("f_pt", "f_pbT", "f_falpha", "f_Hbeta"):
            r = report[f"{key}_{i}"]
            if r["unit"] != "um":
                raise ValueError("reported tolerance unit must be um")
            put(f"reported_{key}_{i}", r["value"], "um", f"report.{key}_{i} (line {r['line']}; DIN source, not ISO conversion)")
    if not any(values[f"x_{i}"]["value"] != 0 for i in (1, 2)):
        raise ValueError("shifted case required")
    targets = ["alpha_t", "beta_b"]+[f"{n}_{i}" for i in (1, 2) for n in ("d", "db", "df", "s_n", "s_ne", "s_ni")]
    result = model.evaluate(targets)
    if result.status != "ok":
        raise ValueError(f"geometry blocked: {result.status}: {result.errors}")
    for name in targets:
        f = model.formulas[name]
        unit = "deg" if name in ("alpha_t", "beta_b") else "mm"
        values[name] = dict(value=U.from_canonical(result.values[name], unit), unit=unit,
                            formula_id=f.id, ref=f.ref, source_check="not_in_evidence")
    for i in (1, 2):
        g = f"ZR[{i-1}]"
        for n, field in (("d", "d"), ("df", "df.nul")):
            if not math.isclose(values[f"{n}_{i}"]["value"], c[g+"."+field], abs_tol=1e-9):
                raise ValueError("derived geometry disagrees with commercial reference")
    return dict(schema=SCHEMA, source_id=case["id"], source_sha256=sha(raw), source_path=SOURCE,
                model_sha256=model.sha256(), units={"length":"mm", "angle":"explicit per row"},
                status="review_preparation_incomplete", manufacturing_release=False,
                external_review_completed=False, geometry_scope="diameter envelopes only; no tooth profile",
                source_report=case["sources"]["report"], parameters=values, gaps=GAPS)


def drawing(table):
    """SVG physical coordinates in mm: axial Z right, transverse X right/Y up.

    Every circle is a graph diameter (da is explicit source input to preserve
    source tip shortening). Circles are envelopes, never drawn as tooth edges.
    """
    p = table["parameters"]
    v = lambda n: p[n]["value"]
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 420 297">',
         '<style>text{font-family:Arial,sans-serif;font-size:3px} .dim{stroke:#444;stroke-width:.25;fill:none} .base{stroke:#148;stroke-dasharray:1,1} .pitch{stroke:#198;stroke-dasharray:3,1} .root{stroke:#b60;stroke-dasharray:1,1}</style>',
         '<rect width="420" height="297" fill="white"/>',
         '<text x="8" y="9" style="font-size:5px">K02 SHIFTED HELICAL - MANUFACTURING REVIEW PREPARATION</text>',
         '<text x="8" y="16" fill="#b00">HOLD: DIAMETER ENVELOPES ONLY. SHIFTED TOOTH PROFILE / ROOT NOT GENERATED. NOT FOR MANUFACTURE.</text>',
         f'<text x="8" y="22">Source SHA256: {table["source_sha256"]}</text>',
         '<text x="8" y="28">Model units mm; transverse +X right, +Y up; axial +Z right. Views separated, not assembly. Scale 1:1 at A3.</text>']
    for i, cx, cy in ((1, 45, 85), (2, 235, 125)):
        ra = v(f"da_{i}")/2
        s.append(f'<text x="{cx-ra}" y="{cy-ra-5}">GEAR {i} | z={v(f"z_{i}"):g} | x={v(f"x_{i}"):.8g} | beta abs={math.degrees(v("beta")):.6g} deg; hand TBD</text>')
        for n, cls in (("da", ""), ("d", "pitch"), ("db", "base"), ("df", "root")):
            r = v(f"{n}_{i}")/2
            s.append(f'<circle class="dim {cls}" cx="{cx}" cy="{cy}" r="{r:.9f}"/>')
        s.append(f'<path class="dim" d="M {cx-ra-3} {cy} H {cx+ra+3} M {cx} {cy-ra-3} V {cy+ra+3}"/>')
        y = cy+ra+10
        s.append(f'<path class="dim" d="M {cx-ra} {cy+ra} V {y+2} M {cx+ra} {cy+ra} V {y+2} M {cx-ra} {y} H {cx+ra}"/>')
        s.append(f'<text x="{cx-ra}" y="{y-1}">tip DIA {2*ra:.6f} mm (source shortened tip)</text>')
        for j, n in enumerate(("d", "db", "df")):
            s.append(f'<text x="{cx-ra}" y="{y+7+5*j}">{n} DIA {v(f"{n}_{i}"):.6f} mm</text>')
        # Axial outer-envelope view; no unsupported bore or helical trace.
        ax, ay, b = (85, 65, v(f"b_{i}")) if i == 1 else (350, 43, v(f"b_{i}"))
        s.append(f'<rect class="dim" x="{ax}" y="{ay}" width="{b}" height="{2*ra}"/>')
        s.append(f'<path class="dim" d="M {ax} {ay+2*ra} V {ay+2*ra+9} M {ax+b} {ay+2*ra} V {ay+2*ra+9} M {ax} {ay+2*ra+7} h {b}"/>')
        s.append(f'<text x="{ax}" y="{ay+2*ra+13}">Z width b={b:g} mm</text>')
    for j, gap in enumerate(GAPS):
        s.append(f'<text x="8" y="{250+5*j}">{html.escape(gap)}</text>')
    s.append('<text x="8" y="290">DIN 3961:1978 grade 6; no ISO 1328 equivalence asserted. Reviewer: __________________ Date: __________</text></svg>')
    return inline_presentation("\n".join(s))


def inline_presentation(svg):
    """Use presentation attributes for renderers without SVG stylesheet support."""
    ns = "http://www.w3.org/2000/svg"
    ET.register_namespace("", ns)
    root = ET.fromstring(svg)
    for element in list(root):
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "style":
            root.remove(element)
        elif tag == "text":
            # Title size was authored explicitly; all other text is 3 mm high.
            size = "5" if element.attrib.pop("style", "") == "font-size:5px" else "3"
            element.set("font-family", "Arial, sans-serif")
            element.set("font-size", size)
            element.set("fill", element.get("fill", "#111"))
            element.set("stroke", "none")
            element.set("stroke-width", "0")
        elif tag in ("circle", "rect", "path", "line"):
            classes = element.get("class", "").split()
            element.set("fill", element.get("fill", "none"))
            element.set("stroke", "#444" if "dim" in classes else "none")
            element.set("stroke-width", ".25" if "dim" in classes else "0")
            for cls, color, dash in (("base", "#148", "1,1"), ("pitch", "#198", "3,1"), ("root", "#b60", "1,1")):
                if cls in classes:
                    element.set("stroke", color)
                    element.set("stroke-dasharray", dash)
    return ET.tostring(root, encoding="utf-8")+b"\n"


def artifacts():
    raw = (ROOT/SOURCE).read_bytes()
    table = parameter_table(raw)
    md = ["# K02 shifted helical manufacturing review preparation", "", "**HOLD: incomplete; not for manufacture; external review not completed.**", "",
          f"Source: `{SOURCE}`; SHA256 `{table['source_sha256']}`", f"Formula model SHA256: `{table['model_sha256']}`", "",
          "The SVG contains dimensioned diameter envelopes and axial widths only. The audited archived tooth authority rejects nonzero profile shift. No tooth curves are fabricated.",
          "Source tip diameters are used explicitly (including shortening), not replaced by basic-rack tip formulas. ISO 21771 original text remains not_in_evidence. DIN 3961:1978 grade is retained without conversion.", "",
          "| Quantity | Value | Unit | Source locator / formula |", "|---|---:|---|---|"]
    for n, r in table["parameters"].items():
        md.append(f"| {n} | {r['value']:.10g} | {r['unit']} | {r.get('locator', r.get('formula_id'))} |")
    md += ["", "## Open manufacturing gaps", ""]+["- "+g for g in GAPS]
    md += ["", "A complete manufacturing drawing requires the missing geometry and engineering inputs before external process approval. Hash verification checks reproducibility, not engineering independence or signatures.", ""]
    form = dict(schema="gearbase.external-process-review-form/1", source_id=table["source_id"],
                source_sha256=table["source_sha256"], status="unsigned_template", reviewer_name=None,
                organization=None, independent_of_author=None, review_date=None, signature=None,
                conclusion=None, issues=[dict(id=f"G{i+1}", issue=g, disposition=None, closure_evidence=None) for i, g in enumerate(GAPS)])
    return {"source.json":raw, "parameters.json":encoded(table), "parameters.md":("\n".join(md)).encode(),
            "manufacturing-review.svg":drawing(table), "external-review-unsigned.json":encoded(form)}


def generate(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = artifacts()
    manifest = expected_manifest(files)
    for name, data in files.items():
        (out/name).write_bytes(data)
    (out/"manifest.json").write_bytes(encoded(manifest))
    return verify(out)


def expected_manifest(files):
    producers = ("gearmath/tools/m35_packet.py", "gearmath/gear/parameter_sheet.py",
                 "gearmath/gear/formulas.py", "gearmath/gear/tooth_thickness.py",
                 "archive/m31/src/cadbench/tooth_authority.py")
    return dict(schema=SCHEMA, source_id="K02-helical",
                artifacts=[dict(path=n, sha256=sha(b)) for n, b in sorted(files.items())],
                producer_sources={n:sha((ROOT/n).read_bytes()) for n in producers},
                manufacturing_release=False, external_review_completed=False)


def verify(out):
    out = Path(out)
    files = artifacts()  # trusted repository source and current formula graph
    manifest = json.loads((out/"manifest.json").read_bytes())
    expected = expected_manifest(files)
    if manifest != expected:
        raise ValueError("manifest/source identity/order/claim mismatch")
    if {p.name for p in out.iterdir()} != set(files)|{"manifest.json"}:
        raise ValueError("unexpected/missing packet artifact")
    for name, data in files.items():
        if (out/name).read_bytes() != data:
            raise ValueError("artifact differs from trusted deterministic projection: "+name)
    return dict(packet_integrity_verified=True, source_id="K02-helical", manufacturing_release=False,
                external_review_completed=False, remaining_gaps=GAPS)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    print(json.dumps(verify(args.out) if args.verify else generate(args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
