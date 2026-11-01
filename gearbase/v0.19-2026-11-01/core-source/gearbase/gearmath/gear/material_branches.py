"""逐轮材料分支（ISO 6336-5:2016 表1、ISO 6336-2:2019 表5、ISO 6336-3:2019 表3/表4/式(87)(88)/表5）。

用途：TR30 例5–8 需要两轮材料不同（例5 感应淬硬 IF + 铸钢 St(cast)）、ML 质量等级、允许有限点蚀
（例7）及 HRC 标尺（例8）。tr30_material_factors.py 只支持 Eh/V、MQ、禁点蚀、0.85 长寿命端点，
本模块按"每轮独立选择"补齐这些分支，全部为公式数据，不从 TR30 输出回填。

逐项原图核对（证据包 standards/core，渲染页图）：
- ISO 6336-5:2016 5.5 式(2) 与表1 第3/7/24/25/30/31/42/47/49/52 行：PDF12–14（印6–8）；
  表5 第7.1项 MQ 表面硬度"660–800 HV 或 58–64 HRC"：PDF39（印33）。
- ISO 6336-2:2019 11.3 图6/表5 Z_NT（曲线1 允许有限点蚀：6e5→1.6、1e7→1.3、1e9→1.0、1e10→端点；
  曲线2 禁点蚀：1e5→1.6、5e7→1.0、1e10→端点）：PDF31（印23）。
- ISO 6336-3:2019 12.3.3 图11/表3 Y_NT（St/V：1e4→2.5；Eh/IF(root)：1e3→2.5；3e6→1.0；1e10→端点）：PDF39（印31）。
- ISO 6336-3:2019 13.3.2.1 式(75)–(77)、表4 滑移层厚 ρ′（第4/5项 St σS=300/400；第6–9项 V；第10项 Eh/IF）：PDF41（印33）。
- ISO 6336-3:2019 14.3.2.1 b) 式(87)（V/Eh/IF）与式(88)（St），1 µm ≤ Rz ≤ 40 µm：PDF49（印41）。
- ISO 6336-3:2019 15.3.3.1 表5 Y_X（St/V：1.03−0.006mn，≥30 取 0.85；Eh/IF：1.05−0.01mn，≥25 取 0.8）：PDF51（印43）。

硬度标尺：表1 的 x 为成品表面 HBW 或 HV（式(2) 定义）。HB→HV 换算按 ISO 6336-5 5.1 指向 ISO 18265。调用方须显式选择：
- 'ISO18265_A1_linear'：ISO 18265:2013 表A.1（非合金/低合金钢、铸钢，PDF19–20 原图已核；数据 data/iso18265/table-a1.json）
  相邻行间线性插值。表A.1 为资料性附录、数值为估计值，插值方式为本库选择（原文未规定），作为 E2 条件证据；
- 'HV_external_readback'：HV 作为外部证据输入 mat_hv_ext_i（provenance=evidence，例如 KISSsoft 2026 齿轮模块对 HBW 输入的
  读回值，数值上≈HB/0.9505），只用于"相同 HV 下两实现是否一致"的对拍，不是换算口径、不是默认；缺输入即阻断；
- 'HB_div_0.95_assumption'：HV≈HB/0.95 近似，provenance=assumption，不能用于验收。HRC 只在 A=0 的行（Eh MQ）按表5 第7.1项的 58–64 HRC 作适用域，
不做任何数值换算。
"""
from __future__ import annotations

import json
import pathlib

from ..kernel.expr import FormulaError

_ISO18265_A1 = pathlib.Path(__file__).resolve().parents[2] / "data" / "iso18265" / "table-a1.json"


def iso18265_a1_rows():
    """ISO 18265:2013 表A.1 (HB, HV10) 行，按 HB 升序。"""
    rows = json.loads(_ISO18265_A1.read_text(encoding="utf-8"))["rows"]
    return [(float(r["HB"]), float(r["HV10"])) for r in rows]


def hb_to_hv_expr(var, hv_lo=None, hv_hi=None):
    """HB→HV 的分段线性表达式（相邻表行间插值），返回 (expr, hb_min, hb_max)。

    给出 hv_lo/hv_hi 时只取覆盖该 HV 区间的表行（各外扩一行），以免表达式超长。"""
    rows = iso18265_a1_rows()
    if hv_lo is not None:
        lo = max(k for k, (_, v) in enumerate(rows) if v <= hv_lo) if rows[0][1] <= hv_lo else 0
        hi = min(k for k, (_, v) in enumerate(rows) if v >= hv_hi) if rows[-1][1] >= hv_hi else len(rows) - 1
        rows = rows[lo:hi + 1]
    expr = None
    for (b0, v0), (b1, v1) in reversed(list(zip(rows, rows[1:]))):
        seg = f"({v0!r} + ({var} - {b0!r})*{(v1 - v0)/(b1 - b0)!r})"
        expr = seg if expr is None else f"where({var} <= {b1!r}, {seg}, {expr})"
    return expr, rows[0][0], rows[-1][0]
from ..kernel.graph import Formula, InputSpec

F, S = Formula, InputSpec
R5, R2, R3 = "ISO 6336-5:2016", "ISO 6336-2:2019", "ISO 6336-3:2019"

# 表1 行：(行号, A, B, 标尺, 最小硬度, 最大硬度, PDF 页, 图号)
TABLE1 = {
    ("St_cast", "ML", "H"): (3, 0.986, 131, "HBW", 140, 210, 12, "1 b)"),
    ("St_cast", "MQ", "H"): (3, 0.986, 131, "HBW", 140, 210, 12, "1 b)"),
    ("St_cast", "ML", "F"): (7, 0.313, 62, "HBW", 140, 210, 12, "2 b)"),
    ("St_cast", "MQ", "F"): (7, 0.313, 62, "HBW", 140, 210, 12, "2 b)"),
    ("V_alloy", "ML", "H"): (24, 1.313, 188, "HV", 200, 360, 13, "5"),
    ("V_alloy", "MQ", "H"): (25, 1.313, 373, "HV", 200, 360, 13, "5"),
    ("V_alloy", "ML", "F"): (30, 0.423, 104, "HV", 200, 360, 13, "6"),
    ("V_alloy", "MQ", "F"): (31, 0.425, 187, "HV", 200, 360, 13, "6"),
    ("Eh", "MQ", "H"): (42, 0.0, 1500, "HV", 660, 800, 14, "9"),
    ("Eh", "MQ", "F"): (47, 0.0, 500, "HV", 660, 800, 14, "10"),
    ("IF", "ML", "H"): (49, 0.740, 602, "HV", 485, 615, 14, "11"),
    ("IF", "ML", "F"): (52, 0.305, 76, "HV", 485, 615, 14, "12"),
}

# 族属性：Z_NT 族（表5 只区分曲线 1/2，St/V/Eh/IF 同族）、Y_NT 静强度起点、ρ′、Y_RrelT 式、Y_X 行、跑合材料组
FAMILY = {
    "St_cast": {"ynt_static": 1e4, "slip": "St", "yr": "88", "yx": "St_V", "group": 1},
    "V_alloy": {"ynt_static": 1e4, "slip": "V", "yr": "87", "yx": "St_V", "group": 1},
    "Eh": {"ynt_static": 1e3, "slip": "EhIF", "yr": "87", "yx": "EhIF", "group": 3},
    "IF": {"ynt_static": 1e3, "slip": "EhIF", "yr": "87", "yx": "EhIF", "group": 3},
}

# TR30 原表材料文字 → 族（只认原表文字，不推断）
RAW_MATERIAL = {"Eh": "Eh", "IF": "IF", "St (cast)": "St_cast", "V": "V_alloy", "V (alloy steel)": "V_alloy"}


def parse_hardness(text):
    """'550 HV' / '200 HBW' / '342 HB' / '58 HRC' → (数值, 标尺)。"""
    parts = str(text).replace(",", ".").split()
    if len(parts) != 2 or parts[1] not in {"HV", "HBW", "HB", "HRC"}:
        raise FormulaError(f"无法识别的硬度声明 {text!r}")
    return float(parts[0]), parts[1]


def _log_interp(nl, n0, y0, n1, y1):
    """log-log 线性插值（ISO 6336-2 表5、ISO 6336-3 表3 的生命曲线做法）。"""
    return f"exp(log({y0})+log({nl}/{n0})*(log({y1})-log({y0}))/log({n1}/{n0}))"


def gear_branch(i, family, quality, scale, *, limited_pitting, znt_end, ynt_end,
                hardness_conversion=None):
    """返回 (formulas, specs, meta)：第 i 轮的材料极限与材料相关系数。

    family: St_cast | V_alloy | Eh | IF；quality: ML | MQ；scale: 原表硬度标尺 HV | HBW | HB | HRC。
    limited_pitting: 原表"Limited pitting allowable"；znt_end/ynt_end: 原表 1e10 端点（0.85 或 1.0）。
    """
    if family not in FAMILY:
        raise FormulaError(f"第{i}轮不支持的材料族 {family!r}")
    if (family, quality, "H") not in TABLE1:
        raise FormulaError(f"第{i}轮 {family}/{quality} 未在已核表1子集中")
    for end in (znt_end, ynt_end):
        if not 0.85 <= end <= 1.0:
            raise FormulaError("1e10 端点须在表5/表3 注a 的 0.85–1.0 之内")
    fam = FAMILY[family]
    hard = f"mat_hardness_{i}"
    row_h = TABLE1[(family, quality, "H")]
    table_scale = row_h[3]
    specs, meta = [], {"family": family, "quality": quality, "scale": scale, "assumptions": []}
    if scale == table_scale:
        x_expr, dom = hard, (f"{hard} >= {row_h[4]}", f"{hard} <= {row_h[5]}")
    elif scale == "HRC" and row_h[1] == 0.0 and family == "Eh" and quality == "MQ":
        # A=0：数值不依赖硬度；适用域按 ISO 6336-5 表5 第7.1项 MQ 58–64 HRC（PDF39）
        x_expr, dom = "0", (f"{hard} >= 58", f"{hard} <= 64")
    elif scale == "HB" and table_scale == "HV" and hardness_conversion == "ISO18265_A1_linear":
        hv_chain, hb_lo, hb_hi = hb_to_hv_expr(hard, row_h[4], row_h[5])
        x_expr = f"mat_hv_{i}"
        dom = (f"{x_expr} >= {row_h[4]}", f"{x_expr} <= {row_h[5]}+0.5")
        meta["hv_formula"] = F(f"iso18265.A1.hb_hv.{i}", x_expr, "1", hv_chain,
                               "ISO 18265:2013 表A.1 HB→HV10 相邻行线性插值（PDF19–20 原图已核；资料性附录，估计值）",
                               (f"{hard} >= {hb_lo!r}", f"{hard} <= {hb_hi!r}"))
        meta["assumptions"].append(
            f"第{i}轮 HB→HV 按 ISO 18265:2013 表A.1（资料性，估计值）相邻行线性插值；插值方式为本库选择")
    elif scale == "HB" and table_scale == "HV" and hardness_conversion == "HV_external_readback":
        # 外部证据变体（非默认、非正式口径）：HV 由调用方以 provenance=evidence 逐轮给出（如 KISSsoft 齿轮模块读回值），
        # 缺输入即阻断；原表 HB 只作适用域核对，不参与数值
        x_expr = f"mat_hv_ext_{i}"
        dom = (f"{x_expr} >= {row_h[4]}", f"{x_expr} <= {row_h[5]}+0.5")
        specs.append(S(x_expr, "1", f"第{i}轮外部证据读回的 HV（hardness_conversion=HV_external_readback）",
                       (f"{x_expr} > 0",)))
        meta["assumptions"].append(
            f"第{i}轮 HV 取外部证据读回值（HV_external_readback，provenance=evidence）；不是 ISO 18265 换算，不能作为正式口径")
    elif scale == "HB" and table_scale == "HV" and hardness_conversion == "HB_div_0.95_assumption":
        x_expr = f"({hard}/0.95)"
        dom = (f"{hard}/0.95 >= {row_h[4]}", f"{hard}/0.95 <= {row_h[5]}+0.5")
        meta["assumptions"].append(
            f"第{i}轮 HB→HV 用 HV≈HB/0.95 近似；ISO 6336-5 5.1 指向 ISO 18265，正式口径请选 ISO18265_A1_linear；本近似不能用于验收")
    else:
        raise FormulaError(f"第{i}轮硬度标尺 {scale} 与表1行 {row_h[0]} 的 {table_scale} 不一致，且未显式选择换算")
    hard_dom = meta["hv_formula"].domain if "hv_formula" in meta else \
        ((f"{hard} > 0",) if hardness_conversion == "HV_external_readback" and scale == "HB" else dom)
    specs.append(S(hard, "1", f"第{i}轮原表表面硬度（{scale}）", hard_dom))
    fs = [meta.pop("hv_formula")] if "hv_formula" in meta else []
    for stress in ("H", "F"):
        row, a, b, _, _, _, page, fig = TABLE1[(family, quality, stress)]
        fs.append(F(f"matb.{family}.{quality}.{stress}.{i}", f"sigma_{stress}lim_{i}", "MPa",
                    f"({a!r}*{x_expr} + {b!r})*material_stress_unit",
                    f"{R5} 5.5 式(2)，表1 第{row}行（{family}/{quality}，图{fig}；PDF{page}原图已核）",
                    dom))
    nl = f"N_L_{i}"
    # ISO 6336-2 表5：曲线1（允许有限点蚀）/曲线2（禁点蚀）
    if limited_pitting:
        znt = (f"where({nl} <= 6e5, 1.6, where({nl} <= 1e7, {_log_interp(nl, 6e5, 1.6, 1e7, 1.3)}, "
               f"where({nl} <= 1e9, {_log_interp(nl, 1e7, 1.3, 1e9, 1.0)}, {_log_interp(nl, 1e9, 1.0, 1e10, znt_end)})))")
        n_static, n_ref, curve = 6e5, 1e9, "曲线1（允许有限点蚀）"
    else:
        znt = (f"where({nl} <= 1e5, 1.6, where({nl} <= 5e7, {_log_interp(nl, 1e5, 1.6, 5e7, 1.0)}, "
               f"{_log_interp(nl, 5e7, 1.0, 1e10, znt_end)}))")
        n_static, n_ref, curve = 1e5, 5e7, "曲线2（禁点蚀）"
    fs.append(F(f"matb.Z_NT.{i}", f"Z_NT_{i}", "1", znt,
                f"{R2} 11.3 图6/表5 {curve}，1e10 端点 {znt_end}（PDF31/印23 原图已核）",
                (f"{nl} > 0", f"{nl} <= 1e10")))
    fs.append(F(f"matb.contact_weight.{i}", f"contact_reference_weight_{i}", "1",
                f"min(1, max(0, log({nl}/{n_static})/log({n_ref}/{n_static})))",
                f"ISO/TR 6336-30:2022 4.2.4（PDF13/印7）：Z_L…Z_X 在静强度点 {n_static:g} 与参考点 {n_ref:g} 间 log 插值",
                (f"{nl} > 0",)))
    fs.append(F(f"matb.Z_NT_long.{i}", f"Z_NT_long_{i}", "1", f"where({nl} >= {n_ref}, Z_NT_{i}, 1)",
                f"{R2} 表5 {curve}：参考点 {n_ref:g} 之后的长寿命段"))
    ns = fam["ynt_static"]
    fs.append(F(f"matb.Y_NT.{i}", f"Y_NT_{i}", "1",
                f"where({nl} <= {ns}, 2.5, where({nl} <= 3e6, {_log_interp(nl, ns, 2.5, 3e6, 1.0)}, "
                f"{_log_interp(nl, 3e6, 1.0, 1e10, ynt_end)}))",
                f"{R3} 12.3.3 图11/表3（{family}：静强度 {ns:g} 次 2.5，3e6 次 1.0，1e10 次 {ynt_end}；PDF39/印31 原图已核）",
                (f"{nl} > 0", f"{nl} <= 1e10")))
    if fam["slip"] == "EhIF":
        slip, sdom = "0.003*root_mm", ()
        sref = "表4 第10项 Eh、IF(root) 0.0030 mm"
    elif fam["slip"] == "St":
        y = f"yield_strength_{i}/root_MPa"
        slip, sdom = f"(0.0833+(0.0445-0.0833)*({y}-300)/100)*root_mm", (f"{y} >= 300", f"{y} <= 400")
        sref = "表4 第4/5项 St σS=300/400（注a 同类内插值，不外推）"
    else:
        y = f"yield_strength_{i}/root_MPa"
        slip = (f"where({y} <= 600, 0.0281+(0.0194-0.0281)*({y}-500)/100, "
                f"where({y} <= 800, 0.0194+(0.0064-0.0194)*({y}-600)/200, "
                f"0.0064+(0.0014-0.0064)*({y}-800)/200))*root_mm")
        sdom = (f"{y} >= 500", f"{y} <= 1000")
        sref = "表4 第6–9项 V σ0.2=500–1000（注a 同类内插值，不外推）"
    fs.append(F(f"matb.slip.{i}", f"slip_layer_{i}", "mm", slip, f"{R3} 13.3.2.1 {sref}（PDF41/印33 原图已核）", sdom))
    fs.append(F(f"matb.Y_drelT.{i}", f"Y_drelT_{i}", "1",
                f"(1+sqrt(slip_layer_{i}/root_mm*0.2*(1+2*qs_{i})))/(1+sqrt(slip_layer_{i}/root_mm*1.2))",
                f"{R3} 13.3.2.1 式(75)–(77)，参考齿轮 qsT=2.5（PDF41/印33 原图已核）",
                (f"qs_{i} >= 1", f"qs_{i} < 8", f"{nl} >= 3e6")))
    rz = f"Rz_F_{i}/root_um"
    yr = (f"1.674-0.529*({rz}+1)**0.1", "式(87) V/GGG/Eh/IF(root)/GTS") if fam["yr"] == "87" else \
         (f"5.306-4.203*({rz}+1)**0.01", "式(88) St")
    fs.append(F(f"matb.Y_RrelT.{i}", f"Y_RrelT_{i}", "1", yr[0],
                f"{R3} 14.3.2.1 b) {yr[1]}，1 µm ≤ Rz ≤ 40 µm（PDF49/印41 原图已核）",
                (f"{rz} >= 1", f"{rz} <= 40", f"root_surface_intact_{i} >= 1", f"{nl} >= 3e6")))
    if fam["yx"] == "St_V":
        yx, yref = "where(m_n/root_mm <= 5, 1, where(m_n/root_mm < 30, 1.03-0.006*m_n/root_mm, 0.85))", "St/V 行"
    else:
        yx, yref = "where(m_n/root_mm <= 5, 1, where(m_n/root_mm < 25, 1.05-0.01*m_n/root_mm, 0.8))", "Eh/IF(root) 行"
    fs.append(F(f"matb.Y_X.{i}", f"Y_X_{i}", "1", yx,
                f"{R3} 15.1 逐轮确定、15.3.3.1 表5 {yref}（参考应力，3e6 次；PDF49/51 原图已核）",
                ("m_n > 0", f"{nl} >= 3e6")))
    meta["mat_group"] = fam["group"]
    meta["contact_curve"] = 1 if limited_pitting else 2
    meta["n_ref"] = n_ref
    return fs, specs, meta


BRANCH_INPUTS = [
    *[S(f"yield_strength_{i}", "MPa", f"第{i}轮原表屈服/条件屈服强度", (f"yield_strength_{i} > 0",)) for i in (1, 2)],
    S("root_MPa", "MPa", "1 MPa 单位尺度", ("root_MPa >= 1", "root_MPa <= 1")),
    S("material_stress_unit", "MPa", "式(2) 的 1 MPa 单位尺度", ("material_stress_unit >= 1", "material_stress_unit <= 1")),
]
