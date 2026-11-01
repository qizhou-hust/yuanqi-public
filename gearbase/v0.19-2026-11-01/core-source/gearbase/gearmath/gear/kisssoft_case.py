"""KISSsoft 商业工具案例（M33）：对拍契约 + 从 data/kisssoft/<case>.json 装配 gearmath 模型 + 按规定顺序逐项比较。

规则（用户）：比较顺序 = 版次与方法 → 输入与单位 → 几何 → 载荷 → K 系数 → Z/Y 系数 → 实际应力 → 许用应力 → 安全系数；
不调输入去追结果；严格区分四种结论：
  资料可读         —— 证据文件能读出数值（data/kisssoft/*.json 已记录来源与哈希）；
  商业工具复算一致 —— KISSsoft 自身重开复算一致（证据包已做，本模块不重复）；
  公式对拍通过     —— gearmath 公式由输入独立算出的值与 KISSsoft 在容差内一致（本模块的 verdict="一致"）；
  产品强度合格     —— 本模块不给出（不调用 rate，不判定通过/不通过）。

口径（方法选择器）按案例契约显式给出并记录来源（CONTRACT_SELECTORS，来源为报告文本/数值），可由调用方覆盖：
K01 契约 = K_V 方法B（m_red 式(7)(8)、fpb = fpT·cosαt）、K_Hβ 方法C、K_Hα/K_Fα 方法B、齿根用 xE,min。
旧回放模式的系数（ZNT、ZL/ZV/ZR/ZW/ZX、YNT、Yδ、YR、YX、YB、YDT）以 KISSsoft 值作为 provenance="evidence" 输入；
v0.6 显式factor_selectors分支会跳过已公式化输出，K01_FULL_FACTOR_SELECTORS可清除该回填清单，
在比较结果中单列为"证据回填（未验证）"，不计入公式对拍通过；选 external 的 K 系数同样如此。
本模块只新增案例专用公式（轮坯系数 C_R 式(87)、内径比 q 式(32)），经 rating.pair_model(extra_formulas=...) 并入。
"""
from __future__ import annotations

import json
import math
import pathlib

from ..kernel import units as U
from ..kernel.graph import Formula, InputSpec
from .dynamic import CONSTANTS
from .formulas import _pair
from .load_distribution import set_ld_constants
from .rating import SELECTOR_REQUIRES, pair_model

DATA = pathlib.Path(__file__).resolve().parents[2] / "data" / "kisssoft"
F, S = Formula, InputSpec

# ---------------------------------------------------------------- 版次与方法
# RechSt.RechenMethID → 强度分册版次（证据包 README：方法 ID 10029 = ISO 6336:2019；K01 报告第 1 节 "ISO 6336:2019"）
METHOD_EDITIONS = {10029: {"ISO 6336-1": "2019", "ISO 6336-2": "2019", "ISO 6336-3": "2019"}}
# RechSt.GeometrieMeth → 几何标准版次（K01 报告第 2 节 "ISO 21771:2007 (withdrawn)"；仅凭报告文本对应，COM 文档未说明枚举）
GEOMETRY_EDITIONS = {1: {"ISO 21771": "2007"}}

# 自动/输入标志：只接受已用报告文本核实过含义的组合；其它组合拒绝装配（否则 KISSsoft 值可能是用户输入而非计算值）
FLAGS = {
    "Zst.KVFlag": ("false", "KV 由 KISSsoft 计算（报告 18.2 'Kv according to Method B'）"),
    "Zst.KHaFlag": ("false", "KHα/KFα 由 KISSsoft 计算（报告 18.2 'KHα, KFα according to Method B'）"),
    "Zst.KHbVariant": (0.0, "KHβ/KFβ 由 KISSsoft 计算（报告 18.2 'KHβ and KFβ according to Method C'）；K04/K05 为 1 = 原模型输入"),
    "Zst.KwbVariant": (0.0, "含义未在 COM 文档中说明；K01 中 Kwb=1"),
    "ZR[0].kFlag": ("false", "齿顶缩短标志（kXmn=0）"), "ZR[1].kFlag": ("false", "同上"),
    "ZR[0].kFaktorFlag": ("false", "齿顶缩短系数标志"), "ZR[1].kFaktorFlag": ("false", "同上"),
}

# ---------------------------------------------------------------- 本案例新增公式（方法B 路径用）
R1 = "ISO 6336-1:2019"
BLANK = [
    F("kc.C_R", "C_R", "1", "1 + log(bs_b)/(5*exp(sR_mn/5))",
      f"{R1} 9.3.2.4 式(87) 轮坯系数 C_R（PDF 第 82 页核图；sR/mn 以模数为单位给出）",
      ("bs_b >= 0.2", "bs_b <= 1.2", "sR_mn >= 1")),
    *_pair("kc.q", "q_{i}", "1", "d_inner_{i}/dm_{i}", f"{R1} 6.5.9 式(32) q = di/dm（PDF 第 45 页核图）"),
]
BLANK_INPUTS = [
    S("bs_b", "1", "腹板厚/齿宽 bs/b"), S("sR_mn", "1", "轮缘厚/法向模数 sR/mn"),
    *[S(f"d_inner_{i}", "mm", f"轮坯内径 di（{w}）", (f"d_inner_{i} >= 0",)) for i, w in (("1", "小轮"), ("2", "大轮"))],
]

# 案例契约：选择器取值 + 来源（报告文本/数值，extracted.txt 行号）。不是库默认值。
CONTRACT_SELECTORS = {
    "K01-spur": {
        "method.K_V": ("B", "报告 18.2 'Kv according to Method B'（第 2194 行）；COM Zst.KVFlag=false"),
        "method.m_red": ("exact", "报告 [mRed]=0.06255（第 877 行）：式(7)(8) 得 0.0625496、式(30) 得 0.0633941"
                                  "（数值判定，报告未写式号）"),
        "method.f_pb": ("fpbT", "报告 [fpbT]=10.34 = fpT·cosαt（第 1866 行）、[yp]=0.8（第 846 行）"),
        "method.K_Hbeta": ("C", "报告 18.2 'KHβ and KFβ according to Method C'（第 2196 行）；COM Zst.KHbVariant=0"),
        "method.K_Halpha": ("B", "报告 18.2 'KHα, KFα according to Method B'（第 2200 行）；COM Zst.KHaFlag=false"),
        "method.root_shift": ("generating", "报告第 6 节 'Calculated with generating profile shift coefficient' [xE.i]"
                                            "（第 998–999 行）"),
    },
}
# 选择 external 时作为证据输入的 K 系数（COM 字段）
EXTERNAL_EVIDENCE = {
    "method.K_V": [("K_V", "ZP[0].KV.KV", "KV 方法B（KISSsoft）")],
    "method.K_Hbeta": [("K_Hbeta", "ZP[0].KHb", "KHβ 方法C（KISSsoft）")],
    "method.K_Halpha": [("K_Halpha", "ZP[0].KHa", "KHα 方法B（KISSsoft）"), ("K_Falpha", "ZP[0].KFa", "KFα 方法B（KISSsoft）")],
}


# ---------------------------------------------------------------- 输入映射
def load(case="K01-spur"):
    if isinstance(case, dict):
        return case
    return json.loads((DATA / f"{case}.json").read_text(encoding="utf-8"))


def _com(d, key):
    return d["com"][key]


def _same(d, k0, k1):
    """gearmath 公式库中该量为单值；两轮 KISSsoft 值必须相同，否则拒绝（不悄悄取其一）。"""
    a, b = _com(d, k0), _com(d, k1)
    if a != b:
        raise NotImplementedError(f"{k0}={a} 与 {k1}={b} 不同，而 gearmath 公式库中该量为单值")
    return a


# gearmath 输入名 → (单位, COM 字段或两轮字段对, 说明)。单位为 KISSsoft COM 单位（角度 rad）
INPUT_MAP = [
    ("z_1", "1", "ZR[0].z", ""), ("z_2", "1", "ZR[1].z", ""),
    ("m_n", "mm", "ZS.Geo.mn", ""), ("alpha_n", "rad", "ZS.Geo.alfn", ""), ("beta", "rad", "ZS.Geo.beta", ""),
    ("x_1", "1", "ZR[0].x.nul", "名义变位"), ("x_2", "1", "ZR[1].x.nul", ""),
    ("b", "mm", ("ZR[0].b", "ZR[1].b"), "两轮齿宽相同"),
    ("haP", "1", ("ZR[0].Tool.RefProfile.haP", "ZR[1].Tool.RefProfile.haP"), "刀具基本齿条（ISO 53 A）"),
    ("hfP", "1", ("ZR[0].Tool.RefProfile.hfP", "ZR[1].Tool.RefProfile.hfP"), ""),
    ("rhofP", "1", ("ZR[0].Tool.RefProfile.rhofP", "ZR[1].Tool.RefProfile.rhofP"), ""),
    ("n_1", "rpm", "ZR[0].nnominal", ""),
    ("K_A", "1", "ZS.KA", ""),
    ("E", "MPa", ("ZR[0].mat.E", "ZR[1].mat.E"), "同材料"), ("nu", "1", ("ZR[0].mat.ny", "ZR[1].mat.ny"), ""),
    ("sigma_Hlim_1", "MPa", "ZR[0].mat.limh", ""), ("sigma_Hlim_2", "MPa", "ZR[1].mat.limh", ""),
    ("sigma_Flim_1", "MPa", "ZR[0].mat.limf", ""), ("sigma_Flim_2", "MPa", "ZR[1].mat.limf", ""),
    ("Y_ST", "1", "ZS.Yst", "试验齿轮应力修正系数（标准值 2.0）"),
]
# gearmath 尚无公式 → KISSsoft 计算值作为证据输入（未验证）
EVIDENCE_MAP = [
    ("Z_L", ("ZPP[0].Flanke.ZL", "ZPP[1].Flanke.ZL"), ""), ("Z_V", ("ZPP[0].Flanke.ZV", "ZPP[1].Flanke.ZV"), ""),
    ("Z_R", ("ZPP[0].Flanke.ZR", "ZPP[1].Flanke.ZR"), ""), ("Z_W", ("ZPP[0].Flanke.ZW", "ZPP[1].Flanke.ZW"), ""),
    ("Z_X", ("ZR[0].Flanke.ZX", "ZR[1].Flanke.ZX"), ""),
    ("Z_NT_1", "ZR[0].Flanke.ZNT", ""), ("Z_NT_2", "ZR[1].Flanke.ZNT", ""),
    ("Y_NT_1", "ZR[0].Fuss.YNT", ""), ("Y_NT_2", "ZR[1].Fuss.YNT", ""),
    ("Y_drelT_1", "ZPP[0].Fuss.Ydrel", ""), ("Y_drelT_2", "ZPP[1].Fuss.Ydrel", ""),
    ("Y_RrelT_1", "ZR[0].Fuss.YR", ""), ("Y_RrelT_2", "ZR[1].Fuss.YR", ""),
    ("Y_X", ("ZR[0].Fuss.YX", "ZR[1].Fuss.YX"), ""), ("Y_B", ("ZR[0].Fuss.YB", "ZR[1].Fuss.YB"), ""),
    ("Y_DT", "ZP[0].Fuss.YDT", ""),
]
# 方法B 路径：报告中可读到的输入（报告键，gearmath 名，单位）
KVB_REPORT_INPUTS = [("K_gamma", "K_gamma", "1"), ("Q_grade_1", "Q_grade", "1"),
                     ("f_pt_1", "f_pt_1", "um"), ("f_pt_2", "f_pt_2", "um"),
                     ("f_falpha_1", "f_falpha_1", "um"), ("f_falpha_2", "f_falpha_2", "um"),
                     ("bs_b", "bs_b", "1"), ("sR_mn", "sR_mn", "1"),
                     ("d_inner_1", "d_inner_1", "mm"), ("d_inner_2", "d_inner_2", "mm")]
# 方法B 所需、报告中没有的输入：显式假设（不是 KISSsoft 值）
RHO_STEEL = 7.83e-6   # kg/mm³；与报告第 15.1 节质量 m 回算一致（见 compare 的输入一致性行）
KVB_ASSUMPTIONS = [("rho_1", RHO_STEEL, "kg/mm^3"), ("rho_2", RHO_STEEL, "kg/mm^3")]
# K_Hβ 方法C 输入：(gearmath 名, 报告键 或 None, 值覆盖, 单位, 说明)
KHB_REPORT_INPUTS = [("l_sh", "l_sh", "mm"), ("s_sh", "s_sh", "mm"), ("d_sh", "d_sh", "mm"),
                     ("pinion_arrangement", "pinion_arrangement", "1"), ("f_Hbeta5", "f_Hbeta5", "um"),
                     ("f_Hbeta_1", "f_Hbeta_1", "um"), ("f_Hbeta_2", "f_Hbeta_2", "um")]
# 报告文本 → 枚举输入（gearmath 名, 值, report_text 键, 判定说明）
KHB_TEXT_INPUTS = [("pinion_stiffening", 1, "pinion_stiffening", "With stiffening → 有加强（图13 注a）"),
                   ("helix_mod", 1, "flank_modification", "无齿向修形 → 表12 第1行"),
                   ("contact_favourable", 1, "contact_pattern", "接触斑点 favorable → 式(55)"),
                   ("B_star", 1, "methods", "单一啮合直齿：式(59) B*=1")]
MAT_GROUP_TEXT = ("material_group", 3, "渗碳淬火钢 → 跑合材料组 3（Eh，7.5.3.2/8.3.6.2）")
KHA_TEXT_INPUTS = [("k_pb", 1.0, "profile_modification", "无齿廓修形（仅跑合）→ f_pb 不折减（8.3.2）")]


def _check_method_and_flags(d):
    com = d["com"]
    mid, gid = int(com["RechSt.RechenMethID"]), int(com["RechSt.GeometrieMeth"])
    if mid not in METHOD_EDITIONS:
        raise NotImplementedError(f"强度方法 ID {mid} 未建立契约（只支持 {sorted(METHOD_EDITIONS)}）")
    if gid not in GEOMETRY_EDITIONS:
        raise NotImplementedError(f"几何方法 {gid} 未建立契约")
    for k, (want, _) in FLAGS.items():
        if com.get(k) != want:
            raise NotImplementedError(f"标志 {k}={com.get(k)!r} 与已核实组合 {want!r} 不同，未建立该组合的契约")
    if com["ZS.Geo.beta"] != 0:
        raise NotImplementedError("斜齿案例（K02/K04/K05）的契约尚未建立，见 docs/M33-对拍契约.md")
    return {**METHOD_EDITIONS[mid], **GEOMETRY_EDITIONS[gid]}


def contract_selectors(case="K01-spur", overrides=None):
    """案例契约的选择器取值与来源；overrides（调用方指定）覆盖契约值。K_V≠B 时去掉只属于方法B 的口径选择器。"""
    d = load(case)
    if d["id"] not in CONTRACT_SELECTORS:
        raise NotImplementedError(f"{d['id']} 的选择器契约尚未建立")
    sel = {k: v for k, (v, _) in CONTRACT_SELECTORS[d["id"]].items()}
    src = {k: f"KISSsoft {d['id']} 契约：{why}" for k, (_, why) in CONTRACT_SELECTORS[d["id"]].items()}
    for k, v in (overrides or {}).items():
        sel[k], src[k] = v, "调用方指定（偏离案例契约）"
    for k, (dep, val) in SELECTOR_REQUIRES.items():
        if k in sel and sel.get(dep) != val:
            sel.pop(k), src.pop(k)
    return sel, src


def build_model(case="K01-spur", selectors=None, factor_selectors=None):
    """只用数据文件中的输入装配模型；返回 (model, data)。每个输入都带来源。
    selectors：覆盖案例契约的选择器（如 {"method.K_V": "external"} 回到证据回填路径）。"""
    d = load(case)
    cid = d["id"]
    eds = _check_method_and_flags(d)
    sel, src = contract_selectors(d, selectors)
    kvb = sel.get("method.K_V") == "B"
    from .factor_methods import K01_FACTOR_SELECTOR_SOURCES
    fsrc = {k: f"K01 显式系数契约：{v}；" + K01_FACTOR_SELECTOR_SOURCES.get(k, "所选ISO公式原图已核，适用性假设另列")
            for k, v in (factor_selectors or {}).items()}
    m = pair_model(selectors=sel, selector_sources=src, factor_selectors=factor_selectors,
                   factor_selector_sources=fsrc,
                   extra_formulas=BLANK if kvb else (), extra_inputs=BLANK_INPUTS if kvb else ())
    m.set_editions(eds, f"KISSsoft {cid} COM RechSt.RechenMethID={d['com']['RechSt.RechenMethID']:.0f} / "
                        f"RechSt.GeometrieMeth={d['com']['RechSt.GeometrieMeth']:.0f}（报告第 1、2 节）")
    for name, unit, key, note in INPUT_MAP:
        v = _same(d, *key) if isinstance(key, tuple) else _com(d, key)
        ksrc = " = ".join(key) if isinstance(key, tuple) else key
        m.set(name, v, unit, "user", f"KISSsoft {cid} COM {ksrc}{('；' + note) if note else ''}")
    # 名义扭矩由功率与转速导出（KISSsoft 输入为功率 P）
    P, n = U.to_canonical(_com(d, "ZS.Pnominal"), "kW"), U.to_canonical(_com(d, "ZR[0].nnominal"), "rpm")
    m.set("T_1", P / (2 * math.pi * n), "N*mm", "derived", f"T1 = P/(2π n1)，KISSsoft {cid} COM ZS.Pnominal、ZR[0].nnominal")
    ev = list(EVIDENCE_MAP) + [row for k, rows in EXTERNAL_EVIDENCE.items() if sel.get(k) == "external" for row in rows]
    for name, key, note in ev:
        if name in m.formulas:
            continue
        v = _same(d, *key) if isinstance(key, tuple) else _com(d, key)
        ksrc = " = ".join(key) if isinstance(key, tuple) else key
        m.set(name, v, "1", "evidence", f"KISSsoft {cid} COM 字段 {ksrc}（商业工具计算值，未经公式验证{('；' + note) if note else ''}）")
    rep, txt = d["report"], d["report_text"]

    def put(name, key, unit, prov="user"):
        r = rep[key]
        m.set(name, r["value"], unit, prov, f"KISSsoft {cid} 报告 {r['label']}（extracted.txt 第 {r['line']} 行）")

    def put_text(name, value, key, why, unit="1"):
        t = txt[key]
        m.set(name, value, unit, "user", f"KISSsoft {cid} 报告 '{t['text']}'（extracted.txt 第 {t['line']} 行）：{why}")

    for k in ("S_Hmin", "S_Fmin"):
        put(k, k, "1")
    if kvb:
        for rk, name, unit in KVB_REPORT_INPUTS:
            put(name, rk, unit)
        if rep["Q_grade_1"]["value"] != rep["Q_grade_2"]["value"]:
            raise NotImplementedError("两轮精度等级不同；方法B 输入 Q_grade 为单值")
        for name, v, unit in KVB_ASSUMPTIONS:
            m.set(name, v, unit, "assumption", "钢密度假设：K01 报告未列密度；与报告第 15.1 节质量回算一致")
        for i in (1, 2):
            put_text(f"C_f_{i}", 0.0, "profile_modification", "无齿廓修形 → 式(17) Cf=0（精度 6 级时 Bk=1，不进入结果）", "um")
        for name, v, unit, ref in CONSTANTS:
            m.set(name, v, unit, "standard_constant", ref)
    if sel.get("method.K_Hbeta") == "C":
        for name, key, unit in KHB_REPORT_INPUTS:
            put(name, key, unit)
        for row in KHB_TEXT_INPUTS:
            put_text(*row)
    if sel.get("method.K_Halpha") == "B":
        for row in KHA_TEXT_INPUTS:
            put_text(*row)
    if sel.get("method.K_Hbeta") == "C" or sel.get("method.K_Halpha") == "B":
        for i in (1, 2):
            put_text(f"mat_group_{i}", MAT_GROUP_TEXT[1], MAT_GROUP_TEXT[0], MAT_GROUP_TEXT[2])
        set_ld_constants(m)
    if sel.get("method.root_shift") == "generating":
        for i in (1, 2):
            r = rep[f"A_sn_i_{i}"]
            m.set(f"A_sn_i_{i}", r["value"], "mm", "user",
                  f"KISSsoft {cid} 报告 {r['label']} DIN 3967 cd25 下偏差（extracted.txt 第 {r['line']} 行）")
    if factor_selectors is not None:
        from .factor_methods import set_k01_factor_inputs
        set_k01_factor_inputs(m, d)
    return m, d


# ---------------------------------------------------------------- 对拍契约（输出比较）
STAGES = ("1 版次与方法", "2 输入与单位", "3 几何", "4 载荷", "5 K 系数", "6 Z/Y 系数", "7 实际应力", "8 许用应力", "9 安全系数")
TOL_GEOMETRY, TOL_FACTOR = 1e-6, 1e-4
TOL_ASSUMPTION = 1e-3   # 密度假设只做合理性检查：报告质量 4 位有效数字，体积按 (da+df)/2…di 圆环近似

# (阶段序号, gearmath 量, KISSsoft 来源 "com:字段" 或 "report:键", 比较单位)
# 只比较模型中由公式推出的量；某选择器下该量不存在或是证据输入时不列入（证据输入单列为"证据回填"）
OUTPUTS = [
    (3, "d_1", "com:ZR[0].d", "mm"), (3, "d_2", "com:ZR[1].d", "mm"),
    (3, "m_t", "report:m_t", "mm"), (3, "alpha_t", "report:alpha_t", "deg"),
    (3, "db_1", "report:db_1", "mm"), (3, "db_2", "report:db_2", "mm"),
    (3, "da_1", "com:ZR[0].da.nul", "mm"), (3, "da_2", "com:ZR[1].da.nul", "mm"),
    (3, "df_1", "com:ZR[0].df.nul", "mm"), (3, "df_2", "com:ZR[1].df.nul", "mm"),
    (3, "h_1", "report:h_1", "mm"), (3, "h_2", "report:h_2", "mm"),
    (3, "zn_1", "report:zn_1", "1"), (3, "zn_2", "report:zn_2", "1"),
    (3, "u", "report:u", "1"),
    (3, "alpha_wt", "com:ZP[0].alfwt", "rad"), (3, "a_w", "com:ZP[0].a", "mm"),
    (3, "eps_alpha", "com:ZP[0].Eps.a", "1"), (3, "eps_beta", "com:ZP[0].Eps.b", "1"),
    (4, "T_1", "com:ZR[0].Tnominal", "N*m"), (4, "F_t", "com:ZP[0].Ft", "N"),
    (4, "v", "report:v", "m/s"),
    (4, "N_L_1", "report:N_L_1", "1"), (4, "N_L_2", "report:N_L_2", "1"),
    (5, "c_th", "report:c_th", "N/(mm*um)"), (5, "C_B", "report:C_B", "1"),
    (5, "C_R", "report:C_R", "1"), (5, "c_s", "report:c_s", "N/(mm*um)"),
    (5, "c_gamma_alpha", "report:c_gamma_alpha", "N/(mm*um)"),
    (5, "c_gamma_beta", "report:c_gamma_beta", "N/(mm*um)"),
    (5, "m_red", "report:m_red", "kg/mm"), (5, "n_E1", "report:n_E1", "rpm"),
    (5, "N_res", "report:N_res", "1"),
    (5, "f_pbT_1", "report:f_pbT_1", "um"), (5, "f_pbT_2", "report:f_pbT_2", "um"),
    (5, "y_p", "report:y_p", "um"), (5, "y_f", "report:y_f", "um"), (5, "K_V", "com:ZP[0].KV.KV", "1"),
    (5, "K_prime", "report:K_prime", "1"), (5, "f_sh", "report:f_sh", "um"), (5, "f_ma", "report:f_ma", "um"),
    (5, "F_bx", "report:F_bx", "um"), (5, "y_beta", "report:y_beta", "um"), (5, "F_by", "report:F_by", "um"),
    (5, "K_Hbeta", "com:ZP[0].KHb", "1"), (5, "K_Fbeta", "com:ZP[0].KFb", "1"),
    (5, "y_alpha", "report:y_alpha", "um"),
    (5, "K_Halpha", "com:ZP[0].KHa", "1"), (5, "K_Falpha", "com:ZP[0].KFa", "1"),
    (6, "Z_H", "com:ZP[0].Flanke.ZH", "1"), (6, "Z_E", "report:Z_E", "sqrt(MPa)"),
    (6, "Z_eps", "com:ZP[0].Flanke.Zeps", "1"), (6, "Z_beta", "com:ZP[0].Flanke.Zbet", "1"),
    (6, "Z_B", "com:ZPP[0].Flanke.ZBD", "1"), (6, "Z_D", "com:ZPP[1].Flanke.ZBD", "1"),
    (6, "xE_1", "report:xE_i_1", "1"), (6, "xE_2", "report:xE_i_2", "1"),
    (6, "den_1", "report:den_1", "mm"), (6, "den_2", "report:den_2", "mm"),
    (6, "alpha_Fen_1", "report:alpha_Fen_1", "deg"), (6, "alpha_Fen_2", "report:alpha_Fen_2", "deg"),
    (6, "sFn_1", "com:ZPP[0].Fuss.sFn", "mm"), (6, "sFn_2", "com:ZPP[1].Fuss.sFn", "mm"),
    (6, "hFe_1", "com:ZPP[0].Fuss.hF", "mm"), (6, "hFe_2", "com:ZPP[1].Fuss.hF", "mm"),
    (6, "rhoF_1", "com:ZPP[0].Fuss.roF", "mm"), (6, "rhoF_2", "com:ZPP[1].Fuss.roF", "mm"),
    (6, "qs_1", "report:qs_1", "1"), (6, "qs_2", "report:qs_2", "1"),
    (6, "Y_F_1", "com:ZPP[0].Fuss.YF", "1"), (6, "Y_F_2", "com:ZPP[1].Fuss.YF", "1"),
    (6, "Y_S_1", "com:ZPP[0].Fuss.YS", "1"), (6, "Y_S_2", "com:ZPP[1].Fuss.YS", "1"),
    (6, "Y_beta", "com:ZP[0].Fuss.Ybet", "1"),
    *[(6, name, "com:" + key[0] if isinstance(key, tuple) else "com:" + key, "1")
      for name, key, _ in EVIDENCE_MAP],
    (7, "sigma_H0", "com:ZP[0].Flanke.sigH0", "MPa"),
    (7, "sigma_H_1", "com:ZPP[0].Flanke.sigHBD", "MPa"), (7, "sigma_H_2", "com:ZPP[1].Flanke.sigHBD", "MPa"),
    (7, "sigma_F_1", "com:ZPP[0].Fuss.sigF", "MPa"), (7, "sigma_F_2", "com:ZPP[1].Fuss.sigF", "MPa"),
    # COM 字段 sigHP/sigFP 的数值等于报告的 σHG/σFG（见契约文档"字段语义"）
    (8, "sigma_HG_1", "com:ZPP[0].Flanke.sigHP", "MPa"), (8, "sigma_HG_2", "com:ZPP[1].Flanke.sigHP", "MPa"),
    (8, "sigma_FG_1", "com:ZPP[0].Fuss.sigFP", "MPa"), (8, "sigma_FG_2", "com:ZPP[1].Fuss.sigFP", "MPa"),
    (9, "S_H_1", "com:ZPP[0].Flanke.SH", "1"), (9, "S_H_2", "com:ZPP[1].Flanke.SH", "1"),
    (9, "S_F_1", "com:ZPP[0].Fuss.SFnorm", "1"), (9, "S_F_2", "com:ZPP[1].Fuss.SFnorm", "1"),
]

# KISSsoft 字段中 gearmath 尚未建模的量（契约状态 not-modelled-yet）
NOT_MODELLED = [
    ("ZP[0].Flanke.sigH", "σHw 节点接触应力（Z_B=1）", "gearmath 只输出 σH,B/D"),
    ("ZPP[i].Flanke.SHw", "节点接触安全系数", "同上"),
    ("ZPP[i].Fuss.sigF0", "名义齿根应力 σF0", "gearmath 未单列 σF0（σF 中已含）"),
    ("ZS.H / report:N_L_i", "寿命 h、循环次数 NL", "ZNT/YNT 公式未实现，NL 未进入公式图"),
    ("ZR[i].Ca / report:Ca_1", "跑合齿顶修缘 Ca", "仅 Q≤5 时进入 Bk（式17 脚注4）；K01 为 A6，Bk=1"),
    ("ZR[i].Qpre", "预加工质量（=8）", "含义未核实，未映射"),
    ("report:Ra/Rz/ν40/ν100/TS", "粗糙度、润滑", "ZL/ZV/ZR/YR 公式未实现"),
]


def _ks_value(d, src, unit):
    kind, key = src.split(":", 1)
    if kind == "com":
        return d["com"][key], None, f"COM {key}"
    r = d["report"][key]
    if r["unit"] != unit:
        raise ValueError(f"报告键 {key} 单位 {r['unit']} 与比较单位 {unit} 不同")
    return r["value"], 0.5 * 10 ** (-r["decimals"]), f"报告 {r['label']}（第 {r['line']} 行）"


def _verdict(gm, ks, half_unit, stage):
    rel = (gm - ks) / ks if ks else (gm - ks)
    if half_unit is None:                       # COM 全精度
        tol = TOL_GEOMETRY if stage <= 4 else TOL_FACTOR
        ok = abs(rel) <= tol
        tol_text = f"rel≤{tol:g}"
    else:                                       # 报告显示值：容差 = 末位半个单位（+1e-9 浮点余量）
        ok = abs(gm - ks) <= half_unit * (1 + 1e-9) + 1e-12
        tol_text = f"abs≤{half_unit:g}（报告末位）"
    return rel, ok, tol_text


def _present(model):
    """模型中由公式推出（或由案例输入导出，provenance=derived，如 T_1 = P/(2πn)）的比较量。"""
    return [o for o in OUTPUTS if o[1] in model.formulas
            or (o[1] in model.inputs and model.inputs[o[1]].provenance == "derived")]


def _rows(d, res, outputs):
    rows = []
    for stage, name, src, unit in outputs:
        gm = U.from_canonical(res.values[name], unit)
        ks, half, where = _ks_value(d, src, unit)
        rel, ok, tol = _verdict(gm, ks, half, stage)
        rows.append({"stage": STAGES[stage - 1], "quantity": name, "unit": unit, "kisssoft": ks, "gearmath": gm,
                     "rel_diff": rel, "tolerance": tol, "source": where, "provenance": "formula" if name != "T_1" else "derived",
                     "verdict": "一致" if ok else "分歧"})
    return rows


def _eval(model, names):
    res = model.evaluate(sorted(names))
    if res.status != "ok":
        raise RuntimeError(f"求值未完成：{res.status} {res.missing} {res.errors} {res.domain_violations}")
    return res


def compare(case="K01-spur", selectors=None, factor_selectors=None):
    """按规定顺序逐项比较（契约选择器，可覆盖）；返回 {rows, first_divergence, selectors, evidence_inputs, assumptions,
    alternatives, ...}。"""
    d = load(case)
    m, _ = build_model(d, selectors, factor_selectors=factor_selectors)
    outs = _present(m)
    extra = ["dm_1"] if "dm_1" in m.formulas else []
    res = _eval(m, [o[1] for o in outs] + extra)
    head = [{"stage": STAGES[0], "quantity": "editions", "unit": "", "kisssoft": d["com"]["RechSt.RechenMethID"],
             "gearmath": dict(m.editions), "rel_diff": 0.0, "tolerance": "精确", "source": "COM RechSt.RechenMethID/GeometrieMeth",
             "provenance": "user", "verdict": "一致" if m.editions == {**METHOD_EDITIONS[10029], **GEOMETRY_EDITIONS[1]} else "分歧"}]
    head += [{"stage": STAGES[0], "quantity": k, "unit": "", "kisssoft": d["com"][k], "gearmath": want,
              "rel_diff": 0.0, "tolerance": "精确", "source": f"COM {k}", "provenance": "flag",
              "verdict": "一致" if d["com"][k] == want else "分歧"} for k, (want, _) in FLAGS.items()]
    if extra:   # 输入一致性：密度假设 vs 报告质量回算（质量按 (da+df)/2…di 圆环，报告第 15.1 节）
        mass = RHO_STEEL * math.pi / 4 * (res.values["dm_1"] ** 2 - d["report"]["d_inner_1"]["value"] ** 2) * d["com"]["ZR[0].b"]
        rep_m = d["report"]["mass_1"]
        head.append({"stage": STAGES[1], "quantity": "mass_1（ρ 假设回算）", "unit": "kg", "kisssoft": rep_m["value"],
                     "gearmath": mass, "rel_diff": mass / rep_m["value"] - 1, "tolerance": f"rel≤{TOL_ASSUMPTION:g}（假设合理性检查）",
                     "source": f"报告 {rep_m['label']}（第 {rep_m['line']} 行）", "provenance": "assumption",
                     "verdict": "一致" if abs(mass / rep_m["value"] - 1) <= TOL_ASSUMPTION else "分歧"})
    rows = head + _rows(d, res, outs)
    rows.sort(key=lambda x: STAGES.index(x["stage"]))      # 稳定排序：阶段内保持契约顺序
    first = next((x for x in rows if x["verdict"] == "分歧"), None)
    evidence_inputs = {k: {"value": i.value, "source": i.source} for k, i in m.inputs.items() if i.provenance == "evidence"}
    assumptions = {k: {"value": U.from_canonical(i.value, i.unit), "unit": i.unit, "source": i.source}
                   for k, i in m.inputs.items() if i.provenance == "assumption"}
    out = {"case": d["id"], "rows": rows, "first_divergence": first, "selectors": dict(m.selectors),
           "selector_sources": dict(m.selector_sources), "evidence_inputs": evidence_inputs, "assumptions": assumptions}
    out["model_sha256"] = res.model_sha256
    if factor_selectors is not None:
        out["factor_validation"] = m.factor_validation
    if selectors is None and factor_selectors is None:
        out["alternatives"] = alternatives(d, rows)
    return out


def alternatives(case="K01-spur", contract_rows=None):
    """每个契约选择器换成其它标准选项时，变化了的比较行（解释"若换口径会差多少"；不改变契约）。"""
    from .rating import SELECTOR_OPTIONS
    d = load(case)
    base = {r["quantity"]: r for r in (contract_rows or compare(d)["rows"])}
    out = {}
    sel, _ = contract_selectors(d)
    for k, v in sel.items():
        for alt in SELECTOR_OPTIONS[k]:
            if alt == v:
                continue
            over = {k: alt}
            if k == "method.K_V" and alt == "external":       # K_Hβ/K_Hα 公式路径依赖方法B，一并回到证据
                over.update({"method.K_Hbeta": "external", "method.K_Halpha": "external"})
            m, _ = build_model(d, over)
            outs = _present(m)
            res = _eval(m, [o[1] for o in outs])
            rows = [r for r in _rows(d, res, outs)
                    if r["quantity"] not in base or r["gearmath"] != base[r["quantity"]]["gearmath"]]
            out[f"{k}={alt}"] = rows
    return out
