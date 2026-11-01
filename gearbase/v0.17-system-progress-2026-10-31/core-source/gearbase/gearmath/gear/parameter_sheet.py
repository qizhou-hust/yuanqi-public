"""M35：齿轮制造参数表——从公式图模型生成的只读投影（JSON + Markdown），不写回源。

装配（build）与投影（project）分开：
  build(gears, tip_diameter=..., groups=...) → (Model, layout)：公式来自库（geo.*、iso1328.*、mfg.*），输入全部声明；
      gears：{序号: "external" | "internal"}（显式），tip_diameter："basic_rack"（da 由 haP_i、x_i 算）| "input"（da 为输入），
      groups：要出的栏目（显式，见 GROUPS），没有默认值；
  project(model, layout) → dict：一次 evaluate 取全部字段；缺输入 → status=blocked_missing_inputs 并列出缺项，不出数值；
      越适用域的字段逐项标 out_of_domain（值仍给出，供审阅）；投影前后核对 model_sha256 与输入不变（只读）；
  render_markdown(sheet) → str。
"""
from __future__ import annotations

import copy
import json
import re

from ..kernel import units as U
from . import iso1328 as T
from . import tooth_thickness as M
from .formulas import GEOMETRY as LIB_GEOMETRY

SCHEMA = "gearbase.parameter-sheet/1"
EDITIONS = {"ISO 21771": "2007", "ISO 1328-1": "2013"}
GROUPS = ("tolerances", "single_flank", "filter_cutoff", "measurement_diameter", "span", "balls", "chordal")
TIP = ("basic_rack", "input")
_EXTERNAL_ONLY = {"span", "chordal"}

# (键, 符号, 名称, 模型量名模板, 显示单位, 小数位)
SHARED_FIELDS = [
    ("m_n", "mn", "法向模数", "m_n", "mm", 4),
    ("alpha_n", "αn", "法向压力角（基本齿条齿形角）", "alpha_n", "deg", 4),
    ("beta", "β", "分度圆螺旋角", "beta", "deg", 4),
    ("alpha_t", "αt", "端面压力角", "alpha_t", "deg", 4),
    ("beta_b", "βb", "基圆螺旋角", "beta_b", "deg", 4),
]
GEAR_FIELDS = {
    "basic": [
        ("z", "z", "齿数", "z_{i}", "1", 0),
        ("x", "x", "法向变位系数", "x_{i}", "1", 4),
        ("b", "b", "齿宽", "b_{i}", "mm", 3),
        ("A1328", "A", "ISO 1328-1:2013 齿面公差等级", "A1328_{i}", "1", 0),
    ],
    "basic_rack": [
        ("haP", "haP*", "基本齿条齿顶高系数", "haP_{i}", "1", 4),
        ("hfP", "hfP*", "基本齿条齿根高系数", "hfP_{i}", "1", 4),
        ("rhofP", "ρfP*", "基本齿条齿根圆角半径系数", "rhofP_{i}", "1", 4),
    ],
    "diameters": [
        ("d", "d", "分度圆直径", "d_{i}", "mm", 4),
        ("db", "db", "基圆直径", "db_{i}", "mm", 4),
        ("da", "da", "齿顶圆直径", "da_{i}", "mm", 4),
        ("df", "df", "齿根圆直径（名义）", "df_{i}", "mm", 4),
    ],
    "tolerances": [
        ("fpT", "fpT", "单个齿距公差 ±", "fpT_{i}", "um", 1),
        ("FpT", "FpT", "齿距累积总公差", "FpT_{i}", "um", 1),
        ("Fpz8T", "Fpz/8T", "扇形齿距公差 ±（附录D）", "Fpz8T_{i}", "um", 1),
        ("fuT", "fuT", "相邻齿距差公差（附录G）", "fuT_{i}", "um", 1),
        ("fHaT", "fHαT", "齿廓倾斜公差 ±", "fHaT_{i}", "um", 1),
        ("ffaT", "ffαT", "齿廓形状公差", "ffaT_{i}", "um", 1),
        ("FaT", "FαT", "齿廓总公差", "FaT_{i}", "um", 1),
        ("fHbT", "fHβT", "螺旋线倾斜公差 ±", "fHbT_{i}", "um", 1),
        ("ffbT", "ffβT", "螺旋线形状公差", "ffbT_{i}", "um", 1),
        ("FbT", "FβT", "螺旋线总公差", "FbT_{i}", "um", 1),
        ("FrT", "FrT", "径向跳动公差（附录E）", "FrT_{i}", "um", 1),
    ],
    "single_flank": [
        ("f_isdesign", "fis(design)", "单面啮合综合偏差设计值", "f_isdesign_{i}", "um", 1),
        ("fisTmax", "fisT,max", "单面啮合齿间综合公差上限（附录F）", "fisTmax_{i}", "um", 1),
        ("fisTmin", "fisT,min", "单面啮合齿间综合公差下限（附录F）", "fisTmin_{i}", "um", 1),
        ("FisT", "FisT", "单面啮合综合总公差（附录F）", "FisT_{i}", "um", 1),
    ],
    "measurement_diameter": [("dM", "dM", "测量直径（4.4.5）", "dM_{i}", "mm", 3)],
    "filter_cutoff": [
        ("L_alpha", "Lα", "齿廓评定长度", "L_alpha_{i}", "mm", 3),
        ("lambda_a", "λα", "齿廓形状滤波截止", "lambda_a_{i}", "mm", 3),
        ("lambda_b", "λβ", "螺旋线形状滤波截止", "lambda_b_{i}", "mm", 3),
    ],
    "thickness": [
        ("A_sn_e", "Asn,e", "法向齿厚上偏差", "A_sn_e_{i}", "mm", 3),
        ("A_sn_i", "Asn,i", "法向齿厚下偏差", "A_sn_i_{i}", "mm", 3),
        ("s_n", "sn", "法向分度圆弧齿厚（无侧隙）", "s_n_{i}", "mm", 4),
        ("s_ne", "sn,e", "法向弧齿厚（上偏差）", "s_ne_{i}", "mm", 4),
        ("s_ni", "sn,i", "法向弧齿厚（下偏差）", "s_ni_{i}", "mm", 4),
    ],
    "span": [
        ("k_span", "k", "公法线跨齿数", "k_span_{i}", "1", 0),
        ("k_rec", "k_rec", "跨齿数推荐值（接触于 d+2x·mn）", "k_rec_{i}", "1", 0),
        ("W_k0", "Wk", "公法线长度（无侧隙）", "W_k0_{i}", "mm", 4),
        ("W_ke", "Wk,e", "公法线长度上限", "W_ke_{i}", "mm", 4),
        ("W_ki", "Wk,i", "公法线长度下限", "W_ki_{i}", "mm", 4),
        ("d_MWk", "dMWk", "公法线接触点直径（中值）", "d_MWk_{i}", "mm", 3),
    ],
    "balls": [
        ("D_M", "DM", "量球直径", "D_M_{i}", "mm", 4),
        ("M_dK0", "MdK", "量球距（无侧隙）", "M_dK0_{i}", "mm", 4),
        ("M_dKe", "MdK,e", "量球距（上偏差）", "M_dKe_{i}", "mm", 4),
        ("M_dKi", "MdK,i", "量球距（下偏差）", "M_dKi_{i}", "mm", 4),
    ],
    "chordal": [
        ("h_ac", "h̄ac", "弦齿高（自 da 起）", "h_ac_{i}", "mm", 4),
        ("s_c", "s̄c", "法向弦齿厚（无侧隙）", "s_c_{i}", "mm", 4),
        ("s_ce", "s̄c,e", "法向弦齿厚（上偏差，卡尺高度 h̄ac）", "s_ce_{i}", "mm", 4),
        ("s_ci", "s̄c,i", "法向弦齿厚（下偏差，卡尺高度 h̄ac）", "s_ci_{i}", "mm", 4),
    ],
}
SECTION_TITLES = {"basic": "基本参数", "basic_rack": "基本齿条", "diameters": "直径", "tolerances": "ISO 1328-1:2013 公差",
                  "single_flank": "单面啮合综合公差（附录F）", "measurement_diameter": "测量直径",
                  "filter_cutoff": "滤波截止波长", "thickness": "齿厚与偏差", "span": "公法线长度",
                  "balls": "量球距", "chordal": "法向弦齿厚"}


def _lib(fid):
    return next(f for f in LIB_GEOMETRY if f.id == fid)


def _sections(groups, kind):
    secs = ["basic", "basic_rack", "diameters", "thickness"]
    for g in GROUPS:
        if g in groups and not (kind == "internal" and g in _EXTERNAL_ONLY):
            secs.append(g)
    return secs


def build(gears, *, tip_diameter, groups):
    """装配制造参数表模型。gears={1: "external", 2: "internal"}；tip_diameter ∈ TIP；groups ⊆ GROUPS（显式）。"""
    from ..kernel.graph import Model
    if not gears or any(k not in ("external", "internal") for k in gears.values()):
        raise ValueError(f"gears 必须是 {{序号: 'external'|'internal'}}，收到 {gears!r}")
    if tip_diameter not in TIP:
        raise ValueError(f"tip_diameter 必须显式选择 {TIP}，收到 {tip_diameter!r}")
    groups = tuple(groups)
    bad = [g for g in groups if g not in GROUPS]
    if bad:
        raise ValueError(f"未知栏目 {bad}；可选 {GROUPS}")
    fs = [_lib("geo.alpha_t"), _lib("geo.m_t"), _lib("geo.beta_b")]
    specs = list(M.SHARED_INPUTS)
    layout = {"gears": {}, "tip_diameter": tip_diameter, "groups": list(groups)}
    for i, kind in sorted(gears.items()):
        internal = kind == "internal"
        if not internal:
            fs.append(_lib(f"geo.d.{i}"))
        fs.append(_lib(f"geo.db.{i}"))
        geo = M.geometry_formulas(i, internal)
        if tip_diameter == "input":
            geo = [f for f in geo if f.output != f"da_{i}"]
        fs += geo + M.thickness_formulas(i)
        if "tolerances" in groups or "single_flank" in groups:
            fs += T.tolerance_formulas(i)
        if "single_flank" in groups:
            fs += T.single_flank_formulas(i)
        if "measurement_diameter" in groups:
            fs += T.measurement_diameter_formulas(i)
        if "filter_cutoff" in groups:
            fs += T.filter_cutoff_formulas(i)
        if "balls" in groups:
            fs += M.ball_formulas(i)
        if not internal and "span" in groups:
            fs += M.span_formulas(i)
        if not internal and "chordal" in groups:
            fs += [_lib(f"geo.zn.{i}")] + M.chordal_formulas(i)
        secs = _sections(groups, kind)
        layout["gears"][str(i)] = {"kind": kind, "sections": secs,
                                   "not_applicable": sorted(set(groups) & _EXTERNAL_ONLY) if internal else []}
        specs += M.measurement_inputs(i, internal=internal)
    outputs = {f.output for f in fs}
    used = set()
    for f in fs:
        from ..kernel.graph import compile_expr
        used |= set(compile_expr(f.expr).names)
        for p in f.domain:
            used |= set(compile_expr(p).names)
    shown = {name.replace("{i}", i) for i, g in layout["gears"].items() for s in g["sections"]
             for _, _, _, name, _, _ in GEAR_FIELDS[s]}
    specs = [s for s in specs if s.name not in outputs and (s.name in used or s.name in shown)]
    model = Model(fs, inputs=specs, editions=EDITIONS)
    model.set("root_mm", 1, "mm", "standard_constant", "Definition of metric length unit") if "root_mm" in model.specs else None
    model.set("root_um", 1, "um", "standard_constant", "Definition of metric length unit") if "root_um" in model.specs else None
    return model, layout


def _fields(layout):
    out = [(None, "shared", f) for f in SHARED_FIELDS]
    for i, g in layout["gears"].items():
        for s in g["sections"]:
            for f in GEAR_FIELDS[s]:
                out.append((i, s, (f[0], f[1], f[2], f[3].replace("{i}", i), f[4], f[5])))
    return out


def _fmt(v, dec):
    return f"{v:.{dec}f}" if dec > 0 else f"{v:.0f}"


def project(model, layout, *, title):
    """只读投影：求值一次，生成参数表 dict（JSON 可序列化）。"""
    sha0, inputs0 = model.sha256(), copy.deepcopy(model.inputs)
    fields = _fields(layout)
    names = [f[3] for _, _, f in fields]
    targets = [n for n in names if n in model.formulas]
    missing_decl = sorted(n for n in names if n not in model.formulas and n not in model.specs)
    if missing_decl:
        raise ValueError(f"参数表字段在模型中既不是公式输出也不是已声明输入：{missing_decl}")
    res = model.evaluate(targets)
    sheet = {"schema": SCHEMA, "title": title, "model_sha256": res.model_sha256, "status": res.status,
             "editions": dict(sorted(res.editions.items())), "tip_diameter": layout["tip_diameter"],
             "groups": list(layout["groups"]), "read_only": True,
             "note": "只读投影：由公式图模型求值生成，不写回源；公差值按 ISO 1328-1:2013 5.2.3 取整；"
                     "几何/测量尺寸公式的 ISO 21771 原文不在证据包（source_check = not_in_evidence）。"}
    missing_in = sorted({n for n in names if n in model.specs and n not in model.inputs})
    if res.status.startswith("blocked") or missing_in:
        sheet.update(status=res.status if res.status.startswith("blocked") else "blocked_missing_inputs",
                     missing=sorted(set(res.missing) | set(missing_in)), errors=res.errors, shared=[], gears={})
        _assert_unchanged(model, sha0, inputs0)
        return sheet
    bad = {}
    for v in res.domain_violations:
        bad.setdefault(v["formula"], []).append(v["predicate"])
    out_of = {f.output: (f.id, bad[f.id]) for f in model.formulas.values() if f.id in bad}

    def row(key, sym, label, name, unit, dec):
        if name in model.formulas:
            f = model.formulas[name]
            val = U.from_canonical(res.values[name], unit)
            chain = [n for n in model.order([name]) if n in out_of]
            r = {"key": key, "symbol": sym, "label": label, "quantity": name, "value": val, "unit": unit,
                 "display": _fmt(val, dec), "formula_id": f.id, "clause": f.ref, "kind": "derived",
                 "status": "out_of_domain" if chain else "ok"}
            raw = f"{name.rsplit('_', 1)[0]}_raw_{name.rsplit('_', 1)[1]}"
            if raw in res.values and model.formulas[raw].unit == "1" and unit == "um":
                r["unrounded"] = res.values[raw]
            if chain:
                r["domain_violations"] = [{"quantity": n, "formula": out_of[n][0], "predicates": out_of[n][1]} for n in chain]
            return r
        i = model.inputs[name]
        val = U.from_canonical(i.value, unit)
        return {"key": key, "symbol": sym, "label": label, "quantity": name, "value": val, "unit": unit,
                "display": _fmt(val, dec), "kind": "input", "provenance": i.provenance, "source": i.source, "status": "ok"}

    sheet["shared"] = [row(*f) for i, _, f in fields if i is None]
    gears = {}
    for i, sec, f in fields:
        if i is None:
            continue
        g = gears.setdefault(i, {"kind": layout["gears"][i]["kind"], "not_applicable": layout["gears"][i]["not_applicable"],
                                 "sections": {}})
        g["sections"].setdefault(sec, []).append(row(*f))
    sheet["gears"] = gears
    sheet["domain_violations"] = res.domain_violations
    _assert_unchanged(model, sha0, inputs0)
    return sheet


def _assert_unchanged(model, sha0, inputs0):
    if model.sha256() != sha0 or model.inputs != inputs0:
        raise RuntimeError("参数表投影改变了模型（应为只读）")


def to_json(sheet):
    return json.dumps(sheet, ensure_ascii=False, indent=1) + "\n"


def render_markdown(sheet):
    lines = [f"# {sheet['title']}", "",
             f"- 模型 sha256：`{sheet['model_sha256']}`", f"- 状态：{sheet['status']}",
             "- 版次：" + "，".join(f"{k}:{v}" for k, v in sheet["editions"].items()), f"- 说明：{sheet['note']}", ""]
    if sheet["status"].startswith("blocked"):
        lines += ["**阻断**：缺少输入，不出数值（不使用默认值）。", "", "缺项：" + "、".join(f"`{m}`" for m in sheet["missing"]), ""]
        return "\n".join(lines)
    lines += ["## 共用参数", "", "| 符号 | 名称 | 值 | 单位 |", "|---|---|---:|---|"]
    lines += [f"| {r['symbol']} | {r['label']} | {r['display']} | {r['unit']} |" for r in sheet["shared"]]
    gears = sheet["gears"]
    idx = sorted(gears)
    secs = []
    for i in idx:
        for s in gears[i]["sections"]:
            if s not in secs:
                secs.append(s)
    for s in secs:
        lines += ["", f"## {SECTION_TITLES[s]}", "",
                  "| 符号 | 名称 | " + " | ".join(f"齿轮{i}（{'内齿' if gears[i]['kind'] == 'internal' else '外齿'}）" for i in idx)
                  + " | 单位 | 依据 |",
                  "|---|---|" + "---:|" * len(idx) + "---|---|"]
        keys = []
        for i in idx:
            for r in gears[i]["sections"].get(s, []):
                if r["key"] not in [k[0] for k in keys]:
                    keys.append((r["key"], r))
        for key, r0 in keys:
            cells = []
            for i in idx:
                r = next((x for x in gears[i]["sections"].get(s, []) if x["key"] == key), None)
                if r is None:
                    cells.append("不适用")
                else:
                    cells.append(r["display"] + (" ⚠越域" if r["status"] == "out_of_domain" else ""))
            fid = r0.get("formula_id")
            basis = re.sub(r"\.\d+$", ".i", fid) if fid else f"输入（{r0.get('provenance')}）"   # 依据列跨轮共用：去掉轮序号
            lines.append(f"| {r0['symbol']} | {r0['label']} | " + " | ".join(cells) + f" | {r0['unit']} | {basis} |")
    if sheet.get("domain_violations"):
        lines += ["", "## 适用域提示", ""]
        lines += [f"- `{v['formula']}`：不满足 `{v['predicate']}`" for v in sheet["domain_violations"]]
    return "\n".join(lines) + "\n"
