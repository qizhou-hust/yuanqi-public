"""KISSsoft v0.14 外部证据（Release 2026 / 26.0.0.0）P2：K01 优化设计（z 23/68、m_n 6、b 28.3、x1 0.427、a=274.0558）的外部回归。

数据：data/kisssoft_v014/P2-K01-opt.json（由 extract_p2() 从用户私有证据目录提取的最小 JSON；每个值带来源文件相对路径、
sha256 与字段定位；不含 PDF/Z12）。私有证据目录按私有资料处理，不进包。

对拍规则（docs/M33-对拍契约.md + lanes3 共同规则）：
  1. 先对齐输入：KISSsoft P2 实际使用的输入逐字段列出（p2_input_alignment），本库按 KISSsoft 实际输入装配（p2_model）；
     其中 KISSsoft 自动改动、而本库优化写回文档未改动的输入（d_inner、小轮轴 l/s/d_sh、f_Hβ/f_Hβ5、齿顶缩短 k·m_n）逐项标出；
  2. 再比较输出（compare_p2）：只对"输入已对齐且公式路径相同"的量设门，门限由误差预算给出（GATES，见下）；
     其余量列为已知差异（KNOWN_DIFFERENCES），附归因或"未归因"；
  3. 不调输入、系数或门限追平 KISSsoft；参照值来自文件，不改。

适配：K01 K 链的 geo.da 不含齿顶缩短（formulas.py 注明）；KISSsoft P2 自动齿顶缩短 kXmn=−0.015 mm（COM ZR[i].kXmn）。
对齐模型用与 kisssoft_multi 相同的 'additive_kXmn_mm' 适配（da_i 加 2·k_X_i，k_X_i 取 KISSsoft 输出），只在本回归内使用。
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import pathlib
import re
from dataclasses import replace

from ..kernel import units as U
from ..kernel.graph import InputSpec, Model

ROOT = pathlib.Path(__file__).resolve().parents[2]
P2_PATH = ROOT / "data" / "kisssoft_v014" / "P2-K01-opt.json"
P2_SCHEMA = "gearbase.kisssoft_v014.p2/1"
RUN = "P2-K01-geometry-mapped/run.json"
TXT = "P2-K01-geometry-mapped/P2-K01-geometry-mapped.txt"
SOURCE_FILES = (RUN, TXT, "P2-comparison.json", "RESULTS.txt", "review.txt", "README.md", "AI_START_HERE.md")

# ---------------------------------------------------------------- 提取（只在有私有证据目录时运行）
# (名, run.json values 键, 单位)
COM_FIELDS = [
    # 输入（readback）
    ("z_1", "ZR[0].z", "1"), ("z_2", "ZR[1].z", "1"), ("m_n", "ZS.Geo.mn", "mm"), ("alpha_n", "ZS.Geo.alfn", "rad"),
    ("beta", "ZS.Geo.beta", "rad"), ("b_1", "ZR[0].b", "mm"), ("b_2", "ZR[1].b", "mm"),
    ("x_1", "ZR[0].x.nul", "1"), ("x_2", "ZR[1].x.nul", "1"), ("a", "ZP[0].a", "mm"),
    ("n_1", "ZR[0].nnominal", "rpm"), ("P", "ZS.Pnominal", "kW"), ("K_A", "ZS.KA", "1"), ("H", "ZS.Hreport", "h"),
    ("haP_1", "ZR[0].Tool.RefProfile.haP", "1"), ("hfP_1", "ZR[0].Tool.RefProfile.hfP", "1"),
    ("rhofP_1", "ZR[0].Tool.RefProfile.rhofP", "1"),
    ("haP_2", "ZR[1].Tool.RefProfile.haP", "1"), ("hfP_2", "ZR[1].Tool.RefProfile.hfP", "1"),
    ("rhofP_2", "ZR[1].Tool.RefProfile.rhofP", "1"),
    ("sigma_Hlim_1", "ZR[0].mat.limh", "MPa"), ("sigma_Hlim_2", "ZR[1].mat.limh", "MPa"),
    ("sigma_Flim_1", "ZR[0].mat.limf", "MPa"), ("sigma_Flim_2", "ZR[1].mat.limf", "MPa"),
    ("E", "ZR[0].mat.E", "MPa"), ("nu", "ZR[0].mat.ny", "1"),
    ("Rz_H_1", "ZR[0].RZH", "um"), ("Rz_H_2", "ZR[1].RZH", "um"), ("Rz_F_1", "ZR[0].RZF", "um"), ("Rz_F_2", "ZR[1].RZF", "um"),
    ("A_sn_i_1", "ZR[0].As.i", "mm"), ("A_sn_i_2", "ZR[1].As.i", "mm"),
    ("k_X_1", "ZR[0].kXmn", "mm"), ("k_X_2", "ZR[1].kXmn", "mm"),
    ("d_inner_1", "ZR[0].di", "mm"), ("d_inner_2", "ZR[1].di", "mm"),
    ("l_sh", "ZP[0].KHdat.l", "mm"), ("s_sh", "ZP[0].KHdat.S", "mm"), ("d_sh", "ZP[0].KHdat.dsh", "mm"),
    ("f_Hbeta5", "ZP[0].KHdat.fHb5", "um"), ("bs_b", "ZP[0].bs_to_b", "1"), ("K_gamma", "ZS.Kgam", "1"),
    ("pinion_arrangement_code", "ZP[0].KHdat.Belastung", "1"), ("K_prime", "ZP[0].KHdat.FaktorK", "1"),
    # 输出
    ("S_H_1", "ZPP[0].Flanke.SH", "1"), ("S_H_2", "ZPP[1].Flanke.SH", "1"),
    ("S_F_1", "ZPP[0].Fuss.SFnorm", "1"), ("S_F_2", "ZPP[1].Fuss.SFnorm", "1"),
    ("eps_alpha", "ZP[0].Eps.a", "1"), ("alpha_wt", "ZP[0].alfwt", "rad"),
    ("da_1", "ZR[0].da.nul", "mm"), ("da_2", "ZR[1].da.nul", "mm"), ("df_1", "ZR[0].df.nul", "mm"), ("df_2", "ZR[1].df.nul", "mm"),
    ("df_min_1", "ZR[0].df.i", "mm"), ("df_min_2", "ZR[1].df.i", "mm"),
    ("s_an_1", "ZR[0].san.nul", "mm"), ("s_an_2", "ZR[1].san.nul", "mm"),
    ("s_an_E_1", "ZR[0].san.E", "mm"), ("s_an_i_1", "ZR[0].san.i", "mm"),
    ("s_an_E_2", "ZR[1].san.E", "mm"), ("s_an_i_2", "ZR[1].san.i", "mm"),
    ("F_t", "ZP[0].Ft", "N"), ("K_V", "ZP[0].KV.KV", "1"), ("K_Hbeta", "ZP[0].KHb", "1"), ("K_Fbeta", "ZP[0].KFb", "1"),
    ("K_Halpha", "ZP[0].KHa", "1"), ("K_Falpha", "ZP[0].KFa", "1"),
    ("m_red", "ZP[0].KV.mRed", "kg/mm"), ("c_th", "ZP[0].KV.cThe", "N/(mm*um)"), ("c_s", "ZP[0].KV.cStr", "N/(mm*um)"),
    ("c_gamma_alpha", "ZP[0].KV.cg", "N/(mm*um)"), ("c_gamma_beta", "ZP[0].KV.cgbet", "N/(mm*um)"),
    ("C_R", "ZP[0].KV.CR", "1"), ("C_B", "ZP[0].KV.CBS", "1"), ("n_E1", "ZP[0].KV.nE1", "rpm"), ("N_res", "ZP[0].KV.n", "1"),
    ("y_p", "ZP[0].KV.yp", "um"), ("y_f", "ZP[0].KV.yf", "um"), ("y_alpha", "ZP[0].KV.ya", "um"),
    ("f_sh", "ZP[0].KHdat.fsh", "um"), ("f_ma", "ZP[0].KHdat.fma", "um"), ("F_bx", "ZP[0].KHdat.Fbx", "um"),
    ("F_by", "ZP[0].KHdat.Fby", "um"), ("y_beta", "ZP[0].KHdat.yb", "um"),
    ("Z_H", "ZP[0].Flanke.ZH", "1"), ("Z_E", "ZP[0].Flanke.ZE", "sqrt(MPa)"), ("Z_eps", "ZP[0].Flanke.Zeps", "1"),
    ("Z_B", "ZPP[0].Flanke.ZBD", "1"), ("Z_D", "ZPP[1].Flanke.ZBD", "1"),
    ("sigma_H0", "ZP[0].Flanke.sigH0", "MPa"), ("sigma_H_1", "ZPP[0].Flanke.sigHBD", "MPa"),
    ("sigma_H_2", "ZPP[1].Flanke.sigHBD", "MPa"),
    ("sigma_HG_1", "ZPP[0].Flanke.sigHP", "MPa"), ("sigma_HG_2", "ZPP[1].Flanke.sigHP", "MPa"),
    ("Z_NT_1", "ZR[0].Flanke.ZNT", "1"), ("Z_NT_2", "ZR[1].Flanke.ZNT", "1"),
    ("Z_L", "ZPP[0].Flanke.ZL", "1"), ("Z_V", "ZPP[0].Flanke.ZV", "1"), ("Z_R", "ZPP[0].Flanke.ZR", "1"),
    ("Y_F_1", "ZPP[0].Fuss.YF", "1"), ("Y_F_2", "ZPP[1].Fuss.YF", "1"), ("Y_S_1", "ZPP[0].Fuss.YS", "1"),
    ("Y_S_2", "ZPP[1].Fuss.YS", "1"), ("den_1", "ZPP[0].Fuss.d_en", "mm"), ("den_2", "ZPP[1].Fuss.d_en", "mm"),
    ("alpha_Fen_1", "ZPP[0].Fuss.alfen", "rad"), ("alpha_Fen_2", "ZPP[1].Fuss.alfen", "rad"),
    ("sFn_1", "ZPP[0].Fuss.sFn", "mm"), ("sFn_2", "ZPP[1].Fuss.sFn", "mm"), ("hFe_1", "ZPP[0].Fuss.hF", "mm"),
    ("hFe_2", "ZPP[1].Fuss.hF", "mm"), ("rhoF_1", "ZPP[0].Fuss.roF", "mm"), ("rhoF_2", "ZPP[1].Fuss.roF", "mm"),
    ("xE_1", "ZR[0].x.i", "1"), ("xE_2", "ZR[1].x.i", "1"),
    ("sigma_F_1", "ZPP[0].Fuss.sigF", "MPa"), ("sigma_F_2", "ZPP[1].Fuss.sigF", "MPa"),
    ("sigma_FG_1", "ZPP[0].Fuss.sigFP", "MPa"), ("sigma_FG_2", "ZPP[1].Fuss.sigFP", "MPa"),
    ("Y_NT_1", "ZR[0].Fuss.YNT", "1"), ("Y_NT_2", "ZR[1].Fuss.YNT", "1"), ("Y_X", "ZR[0].Fuss.YX", "1"),
    ("Y_drelT_1", "ZPP[0].Fuss.Ydrel", "1"), ("Y_drelT_2", "ZPP[1].Fuss.Ydrel", "1"),
    ("Y_RrelT_1", "ZR[0].Fuss.YR", "1"), ("Y_RrelT_2", "ZR[1].Fuss.YR", "1"),
    ("Y_B", "ZR[0].Fuss.YB", "1"), ("Y_DT", "ZP[0].Fuss.YDT", "1"),
]
# 报告 TXT 中才有的量：(名, 报告键, 起始节标题, 单位, 取第几个值 0/1)
TXT_FIELDS = [
    ("n_2", "[n]", "1 Overview", "rpm", 1), ("N_L_1", "[NL]", "1 Overview", "1e6", 0), ("N_L_2", "[NL]", "1 Overview", "1e6", 1),
    ("nu_40", "[ν40]", "3.2 Lubrication", "mm^2/s", 0), ("T_oil", "[TS]", "3.2 Lubrication", "degC", 0),
    ("v", "[v]", "5.1 Forces", "m/s", 0),
    ("qs_1", "[qs]", "6 Calculation of tooth root", "1", 0), ("qs_2", "[qs]", "6 Calculation of tooth root", "1", 1),
    ("Y_ST", "[YST]", "6 Calculation of tooth root", "1", 0),
    ("f_pt_1", "[fpT]", "13 Gear tolerances", "um", 0), ("f_pt_2", "[fpT]", "13 Gear tolerances", "um", 1),
    ("f_pbT_1", "[fpbT]", "13 Gear tolerances", "um", 0), ("f_pbT_2", "[fpbT]", "13 Gear tolerances", "um", 1),
    ("f_falpha_1", "[ffαT]", "13 Gear tolerances", "um", 0), ("f_falpha_2", "[ffαT]", "13 Gear tolerances", "um", 1),
    ("f_Hbeta_1", "[fHβT]", "13 Gear tolerances", "um", 0), ("f_Hbeta_2", "[fHβT]", "13 Gear tolerances", "um", 1),
    ("Q_grade_1", "[Q]", "13 Gear tolerances", "A", 0), ("Q_grade_2", "[Q]", "13 Gear tolerances", "A", 1),
]
_NUM = re.compile(r"^[±]?\s*A?(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)\s*$")


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _txt_value(lines, key, section, which):
    start = next(i for i, ln in enumerate(lines) if ln.strip().startswith(section))
    k = next(i for i in range(start, len(lines)) if lines[i].strip() == key)
    vals = []
    for j in range(k + 1, min(k + 8, len(lines))):
        s = lines[j].strip().replace("±", "")
        m = _NUM.match(s)
        if m:
            vals.append((float(m.group(1)), j + 1, m.group(1)))
        elif vals or (s and not s.startswith("(")):
            if vals:
                break
    v, line, text = vals[which]
    dec = len(text.split(".")[1]) if "." in text else 0
    return v, line, dec


def extract_p2(private_root):
    """从私有证据目录提取 P2 最小 JSON（不写盘）。只读 run.json 与 TXT；其余文件只登记 sha256。"""
    pr = pathlib.Path(private_root)
    run = json.loads((pr / RUN).read_text(encoding="utf-8"))
    vals = run["values"]
    lines = (pr / TXT).read_text(encoding="utf-8").splitlines()
    fields = {}
    for name, key, unit in COM_FIELDS:
        fields[name] = {"value": vals[key], "unit": unit, "source": RUN, "locator": f"values[\"{key}\"]"}
    for name, key, sec, unit, which in TXT_FIELDS:
        v, line, dec = _txt_value(lines, key, sec, which)
        if unit == "1e6":
            v, unit, dec = float(round(v * 1e6)), "1", dec - 6
        fields[name] = {"value": v, "unit": unit, "source": TXT, "locator": f"{key}（第 {line} 行，§{sec}）",
                        "decimals": dec}
    edits = [{k: e[k] for k in ("field", "before", "requested", "readback")} for e in run["edits"]]
    return {
        "schema": P2_SCHEMA, "id": "P2-K01-opt",
        "description": "KISSsoft Release 2026（26.0.0.0）对 OPT 路 K01 优化设计的本机复算（P2-K01-geometry-mapped）：最小提取",
        "status": "external_evidence_partial：KISSsoft 计算与原生重载成功；数值等价未成立（S_H1<1、S_F2<S_Fmin）；"
                  "P2-K01-requested-edits（a=303 失败）为诊断记录，不作参照",
        "software": {"name": "KISSsoft", "release": run.get("version"), "file_version": run.get("file_version"),
                     "module": run.get("module"), "calculate_return": run.get("calculate_return")},
        "native_baseline": {"file": "K01-spur.Z12（原机路径见 run.json source）", "sha256": run["source_sha256"]},
        "edits": edits,
        "edit_note": "只改 z1、z2、mn、b1、b2、x1；a 由 inv αw = inv α + 2(x1+x2)tanα/(z1+z2) 导出并显式写入（第 7 处改动，"
                     "RESULTS.txt：保持 a=303 时 CalculateRetVal=false）",
        "kisssoft_automatic_changes": {
            "d_inner": "di 由 KISSsoft 按轮缘厚 sR≈5mn 从最小根圆导出（77.58/377.5 → 67.726/329.496）",
            "pinion_shaft": "l、s、dsh 按齿宽缩放（88/8.8/44 → 56.6/5.66/28.3）",
            "tolerances": "fHβT、fHβ5 按 ISO 1328-1:2013 随 d、b 重算（10/10、7.5 → 9.0/9.5、7.0）；fpT、ffαT 不变",
            "tip_alteration": "kXmn 自动 −0.015 mm（x1+x2≠0 时保持顶隙；原 K01 x1+x2=0，kXmn=0）",
        },
        "files": {f: {"sha256": _sha(pr / f)} for f in SOURCE_FILES if (pr / f).is_file()},
        "fields": fields,
        "gearbase_user_v014": {"source": "P2-comparison.json（用户 gearbase v0.14 OPT 路结果，即 output/m34/K01-spur-min-volume.run.json）",
                               "values": {r["field"]: r["gearbase_user"]
                                          for r in json.loads((pr / "P2-comparison.json").read_text(encoding="utf-8"))}},
    }


def write_p2(private_root, path=P2_PATH):
    d = extract_p2(private_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return d


def load_p2(path=P2_PATH):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def ks(p2, name, unit=None):
    """P2 字段值（换算到 unit；缺省为记录单位）。"""
    f = p2["fields"][name]
    return f["value"] if unit is None or unit == f["unit"] else U.from_canonical(U.to_canonical(f["value"], f["unit"]), unit)


# ---------------------------------------------------------------- 对齐模型
# P2 实际输入 -> 本库输入名（逐字段对齐；值取 KISSsoft 记录，不调）。按组，供逐步归因（stepwise_attribution）
ALIGN_GROUPS = {
    "design": [("z_1", "1"), ("z_2", "1"), ("m_n", "mm"), ("x_1", "1"), ("x_2", "1"), ("A_sn_i_1", "mm"), ("A_sn_i_2", "mm"),
               ("f_pt_1", "um"), ("f_pt_2", "um"), ("f_falpha_1", "um"), ("f_falpha_2", "um")],
    "blank_bore": [("d_inner_1", "mm"), ("d_inner_2", "mm")],
    "khb_inputs": [("l_sh", "mm"), ("s_sh", "mm"), ("d_sh", "mm"),
                   ("f_Hbeta5", "um"), ("f_Hbeta_1", "um"), ("f_Hbeta_2", "um")],
}
ALIGNED_INPUTS = [r for g in ALIGN_GROUPS.values() for r in g]
_TIP_DERIVED = ("formulas", "standard_editions", "_exprs", "_dom", "_used", "specs", "_spec_dom", "_fingerprint")


def _with_tip_alteration(m):
    """da_i = d_i + 2 m_n (haP + x_i) + 2 k_X_i（kisssoft_multi 'additive_kXmn_mm' 同式；k_X_i 为 KISSsoft 输出 kXmn，mm）。"""
    fs = []
    for f in m.formulas.values():
        for i in ("1", "2"):
            if f.output == f"da_{i}":
                f = replace(f, id=f"p2.da_kX.{i}", expr=f"d_{i} + 2*m_n*(haP + x_{i}) + 2*k_X_{i}",
                            note="P2 外部回归适配：加 KISSsoft 自动齿顶缩短 kXmn（只在本回归内使用）")
        fs.append(f)
    specs = list(m.specs.values()) + [InputSpec(f"k_X_{i}", "mm", "KISSsoft 齿顶缩短 kXmn（带符号，mm）") for i in ("1", "2")]
    m2 = Model(fs, inputs=specs)
    for k, v in m.__dict__.items():
        if k not in _TIP_DERIVED:
            setattr(m2, k, copy.copy(v))
    return m2


def p2_model(p2=None, *, tip_alteration=True, factors="formula", groups=tuple(ALIGN_GROUPS)):
    """K01 K 链 + 按 P2 实际输入逐字段对齐。返回 (model, alignment 行)。
    factors="formula"：K01 显式系数契约（K01_FULL_FACTOR_SELECTORS，Z/Y 系数由公式按 P2 几何计算）；
    factors="held"：K 链旧回放（Z/Y 系数为 K01 原设计 KISSsoft 值，即 v0.14 OPT 路优化时保持的证据）。
    groups：对齐哪些输入组（"design" 必含）；tip_alteration：是否加 KISSsoft 自动齿顶缩短。"""
    from . import kisssoft_case as KC
    from .factor_methods import K01_FULL_FACTOR_SELECTORS
    p2 = p2 or load_p2()
    if "design" not in groups or factors not in ("formula", "held"):
        raise ValueError("groups 须含 design；factors 取 formula/held")
    base, _ = KC.build_model("K01-spur", factor_selectors=K01_FULL_FACTOR_SELECTORS if factors == "formula" else None)
    m = _with_tip_alteration(base) if tip_alteration else base
    rows = []
    for g in groups:
        for name, unit in ALIGN_GROUPS[g]:
            before = U.from_canonical(m.inputs[name].value, unit)
            v = ks(p2, name, unit)
            m.set(name, v, unit, "user", f"KISSsoft P2 实际输入 {p2['fields'][name]['locator']}（{p2['fields'][name]['source']}）")
            rows.append({"input": name, "group": g, "unit": unit, "K01_doc_or_opt": before, "kisssoft_P2": v, "changed": before != v})
    if p2["fields"]["b_1"]["value"] != p2["fields"]["b_2"]["value"]:
        raise NotImplementedError("P2 两轮齿宽不同")
    m.set("b", ks(p2, "b_1", "mm"), "mm", "user", "KISSsoft P2 ZR[0].b = ZR[1].b")
    if tip_alteration:
        for i in ("1", "2"):
            m.set(f"k_X_{i}", ks(p2, f"k_X_{i}", "mm"), "mm", "user", f"KISSsoft P2 输出 ZR[{int(i) - 1}].kXmn（自动齿顶缩短）")
    for name, unit in (("n_1", "rpm"), ("K_A", "1"), ("sigma_Hlim_1", "MPa"), ("sigma_Flim_2", "MPa"), ("Rz_F_1", "um"),
                       ("Rz_H_1", "um"), ("nu_40", "mm^2/s"), ("E", "MPa")):
        if name not in m.inputs:
            continue
        got = U.from_canonical(m.inputs[name].value, unit)
        rows.append({"input": name, "unit": unit, "K01_doc_or_opt": got, "kisssoft_P2": ks(p2, name, unit),
                     "changed": False, "identical": got == ks(p2, name, unit)})
    return m, rows


# ---------------------------------------------------------------- 比较
# 门限（误差预算论证，见 docs/M34-系数对账-P2.md §3）：
#   geometry   ：两侧同式、输入为 COM 全精度 → 只剩浮点与迭代（inv⁻¹）误差，预算 1e-9；门 1e-6（=契约 TOL_GEOMETRY）
#   factor     ：K01 契约 TOL_FACTOR = 1e-4（M33 既有，不为本回归设）；本回归已知最大残差 Z_R 1.0e-5、Z_V 5.9e-6
#   safety     ：S = σ_G/σ ，ln S = Σ ln(系数) 的线性组合；按 TOL_FACTOR 逐项预算会到 1e-3，但实测因子残差合成
#                ≤ 2e-5，取 TOL_FACTOR 1e-4 作门（不放宽到预算上限，也不收紧到实测）
#   report     ：报告显示值（N_L、q_s、公差）按末位半格
GATES = {"geometry": 1e-6, "factor": 1e-4, "safety": 1e-4}
COMPARE = [
    ("geometry", "alpha_wt", "rad"), ("geometry", "da_1", "mm"), ("geometry", "da_2", "mm"),
    ("geometry", "df_1", "mm"), ("geometry", "df_2", "mm"), ("geometry", "eps_alpha", "1"), ("geometry", "F_t", "N"),
    ("geometry", "xE_1", "1"), ("geometry", "xE_2", "1"),
    ("factor", "C_R", "1"), ("factor", "C_B", "1"), ("factor", "c_th", "N/(mm*um)"), ("factor", "c_s", "N/(mm*um)"),
    ("factor", "c_gamma_alpha", "N/(mm*um)"), ("factor", "c_gamma_beta", "N/(mm*um)"), ("factor", "m_red", "kg/mm"),
    ("factor", "n_E1", "rpm"), ("factor", "N_res", "1"), ("factor", "y_p", "um"), ("factor", "y_f", "um"),
    ("factor", "K_V", "1"), ("factor", "f_sh", "um"), ("factor", "f_ma", "um"), ("factor", "F_bx", "um"),
    ("factor", "y_beta", "um"), ("factor", "F_by", "um"), ("factor", "K_Hbeta", "1"), ("factor", "K_Fbeta", "1"),
    ("factor", "y_alpha", "um"), ("factor", "K_Halpha", "1"), ("factor", "K_Falpha", "1"),
    ("factor", "Z_H", "1"), ("factor", "Z_E", "sqrt(MPa)"), ("factor", "Z_eps", "1"), ("factor", "Z_B", "1"), ("factor", "Z_D", "1"),
    ("factor", "Z_NT_1", "1"), ("factor", "Z_NT_2", "1"), ("factor", "Z_L", "1"), ("factor", "Z_V", "1"), ("factor", "Z_R", "1"),
    ("factor", "den_1", "mm"), ("factor", "den_2", "mm"), ("factor", "alpha_Fen_1", "rad"), ("factor", "alpha_Fen_2", "rad"),
    ("factor", "sFn_1", "mm"), ("factor", "sFn_2", "mm"), ("factor", "hFe_1", "mm"), ("factor", "hFe_2", "mm"),
    ("factor", "rhoF_1", "mm"), ("factor", "rhoF_2", "mm"),
    ("factor", "Y_F_1", "1"), ("factor", "Y_F_2", "1"), ("factor", "Y_S_1", "1"), ("factor", "Y_S_2", "1"),
    ("factor", "Y_NT_1", "1"), ("factor", "Y_NT_2", "1"), ("factor", "Y_X", "1"),
    ("factor", "Y_drelT_1", "1"), ("factor", "Y_drelT_2", "1"), ("factor", "Y_RrelT_1", "1"), ("factor", "Y_RrelT_2", "1"),
    ("factor", "Y_B", "1"), ("factor", "Y_DT", "1"),
    ("safety", "sigma_H0", "MPa"), ("safety", "sigma_H_1", "MPa"), ("safety", "sigma_H_2", "MPa"),
    ("safety", "sigma_HG_1", "MPa"), ("safety", "sigma_HG_2", "MPa"),
    ("safety", "sigma_F_1", "MPa"), ("safety", "sigma_F_2", "MPa"), ("safety", "sigma_FG_1", "MPa"), ("safety", "sigma_FG_2", "MPa"),
    ("safety", "S_H_1", "1"), ("safety", "S_H_2", "1"), ("safety", "S_F_1", "1"), ("safety", "S_F_2", "1"),
]
# 报告显示值（末位半格）
COMPARE_REPORT = [("N_L_1", "1"), ("N_L_2", "1"), ("qs_1", "1"), ("qs_2", "1"),
                  ("f_pt_1", "um"), ("f_pt_2", "um"), ("f_falpha_1", "um"), ("f_falpha_2", "um"),
                  ("f_Hbeta_1", "um"), ("f_Hbeta_2", "um")]
# 输入已对齐但公式口径不同 / 未归因的量：不设门，单列（rel 为记录时的实测，供漂移观察，不作判定）
KNOWN_DIFFERENCES = {
    "Z_V": "未归因：同式(47)、v_ref 口径，残差 +5.9e-6（K01 原几何 +5.4e-6，同号同量级，系统性）；v_w 口径为 +8.4e-5，可排除",
    "Z_R": "未归因：同式(50)(53)、ρ_red 两侧同式，残差 −1.0e-5（K01 原几何 +1.8e-6）",
}


def _tip_formulas_kx():
    from .source_optimize import TIP_FORMULAS
    out = []
    for f in TIP_FORMULAS:
        if f.id.startswith("opt.s_an_rel."):
            i = f.id[-1]
            out.append(replace(f, id=f"p2.s_an_rel.kX.{i}", expr=f.expr.replace(f"(haP + x_{i})", f"(haP + x_{i} + k_X_{i}/m_n)")))
        else:
            out.append(f)
    return out


def compare_p2(p2=None):
    """对齐模型 vs KISSsoft P2。返回 {alignment, rows, report_rows, known_differences, s_an}。"""
    p2 = p2 or load_p2()
    m, align = p2_model(p2)
    names = [q for _, q, _ in COMPARE] + ["N_L_1", "N_L_2", "qs_1", "qs_2"]
    res = m.evaluate(names)
    if res.status != "ok":
        raise RuntimeError(f"P2 对齐模型求值未完成：{res.status} {res.missing} {res.errors} {res.domain_violations}")
    rows = []
    for cat, q, unit in COMPARE:
        g = U.from_canonical(res.values[q], unit)
        k = ks(p2, q, unit)
        rel = (g - k) / k if k else g - k
        known = KNOWN_DIFFERENCES.get(q)
        rows.append({"category": cat, "quantity": q, "unit": unit, "gearbase": g, "kisssoft": k, "rel_diff": rel,
                     "gate": None if known else GATES[cat], "status": "known_difference" if known else
                     ("pass" if abs(rel) <= GATES[cat] else "FAIL"), "note": known or ""})
    rrows = []
    for q, unit in COMPARE_REPORT:
        f = p2["fields"][q]
        g = U.from_canonical(res.values[q], unit) if q in res.values else U.from_canonical(m.inputs[q].value, unit)
        half = 0.5 * 10 ** (-f["decimals"])
        rrows.append({"quantity": q, "unit": unit, "gearbase": g, "kisssoft": f["value"], "abs_diff": g - f["value"],
                      "half_unit": half, "status": "pass" if abs(g - f["value"]) <= half * (1 + 1e-9) + 1e-12 else "FAIL",
                      "source": f["locator"]})
    # 齿顶法向齿厚（名义 x，含齿顶缩短）
    mt = _with_tip_formulas(m)
    r2 = mt.evaluate(["s_an_1", "s_an_2"])
    san = [{"quantity": f"s_an_{i}", "gearbase_with_kX": U.from_canonical(r2.values[f"s_an_{i}"], "mm"),
            "kisssoft_nominal": ks(p2, f"s_an_{i}"), "kisssoft_E": ks(p2, f"s_an_E_{i}"), "kisssoft_i": ks(p2, f"s_an_i_{i}")}
           for i in ("1", "2")]
    return {"alignment": align, "rows": rows, "report_rows": rrows, "s_an": san, "known_differences": dict(KNOWN_DIFFERENCES)}


def _with_tip_formulas(m):
    fs = list(m.formulas.values()) + _tip_formulas_kx()
    m2 = Model(fs, inputs=list(m.specs.values()))
    for k, v in m.__dict__.items():
        if k not in _TIP_DERIVED:
            setattr(m2, k, copy.copy(v))
    return m2


# ---------------------------------------------------------------- 对数分解（系数对账）
SH_FACTORS = {  # S_H_i = σHlim·Z_NT_i·Z_L·Z_V·Z_R·Z_W·Z_X / (Z_B|D·Z_H·Z_E·Z_ε·Z_β·√(F_t/(d_1 b)·(u+1)/u)·√(K_A K_V K_Hβ K_Hα))
    "num": ("Z_NT_{i}", "Z_L", "Z_V", "Z_R"),
    "den": ("Z_H", "Z_E", "Z_eps"),
    "den_sqrt": ("K_V", "K_Hbeta", "K_Halpha"),
}
SF_FACTORS = {  # S_F_i = σFlim·Y_ST·Y_NT_i·Y_δ_i·Y_R_i·Y_X / (F_t/(b m_n)·Y_F_i·Y_S_i·Y_β·Y_B·Y_DT·K_A K_V K_Fβ K_Fα)
    "num": ("Y_NT_{i}", "Y_drelT_{i}", "Y_RrelT_{i}", "Y_X"),
    "den": ("Y_F_{i}", "Y_S_{i}", "K_V", "K_Fbeta", "K_Falpha", "Y_B", "Y_DT"),
}


def log_decomposition(values_a, values_b, which):
    """ln(S_a/S_b) 按系数分解：返回 [{factor, a, b, contribution}] 与合计、剩余（=ln 比 − Σ贡献）。
    values_*：{量: 值}（同一单位约定）；which 如 'S_H_1'。正贡献 = a 侧安全系数更高。"""
    i = which[-1]
    spec = SH_FACTORS if which.startswith("S_H") else SF_FACTORS
    rows = []
    for kind, names in spec.items():
        for n in names:
            n = n.replace("{i}", i)
            a, b = values_a[n], values_b[n]
            c = math.log(a / b) * (1.0 if kind == "num" else -1.0 if kind == "den" else -0.5)
            rows.append({"factor": n, "a": a, "b": b, "contribution": c})
    total = math.log(values_a[which] / values_b[which])
    return {"quantity": which, "ln_ratio": total, "rows": rows, "residual": total - sum(r["contribution"] for r in rows)}


# ---------------------------------------------------------------- 逐步归因（从"优化时的模型"走到"KISSsoft 对齐模型"）
STEPS = [
    ("0 优化时（v0.14 OPT：系数保持 K01 原设计证据，d_inner/轴/fHβ 按原设计，无齿顶缩短）",
     dict(factors="held", groups=("design",), tip_alteration=False)),
    ("1 + Z/Y 系数由公式按新几何重算", dict(factors="formula", groups=("design",), tip_alteration=False)),
    ("2 + 轮坯内径 d_inner 按 KISSsoft（sR 从 df.i 量起）", dict(factors="formula", groups=("design", "blank_bore"), tip_alteration=False)),
    ("3 + 小轮轴 l/s/d_sh 与 fHβ/fHβ5 按 KISSsoft", dict(factors="formula", groups=tuple(ALIGN_GROUPS), tip_alteration=False)),
    ("4 + KISSsoft 自动齿顶缩短 kXmn=−0.015 mm", dict(factors="formula", groups=tuple(ALIGN_GROUPS), tip_alteration=True)),
]
TRACKED = [("S_H_1", "1"), ("S_H_2", "1"), ("S_F_1", "1"), ("S_F_2", "1"), ("eps_alpha", "1"), ("K_V", "1"), ("K_Hbeta", "1"),
           ("Z_V", "1"), ("Z_R", "1"), ("Z_NT_2", "1"), ("Y_NT_2", "1"), ("Y_drelT_1", "1"), ("Y_drelT_2", "1"),
           ("Y_F_2", "1"), ("Y_S_2", "1"), ("Z_eps", "1")]


def model_values(m, names):
    """模型中各量（公式输出或输入）的值，记录单位见 names。"""
    res = m.evaluate([n for n, _ in names if n in m.formulas])
    out = {}
    for n, u in names:
        v = res.values[n] if n in m.formulas else m.inputs[n].value
        out[n] = U.from_canonical(v, u)
    return out


def stepwise_attribution(p2=None):
    """逐步对齐：每步的 S_H/S_F 等及其相对上一步的 ln 变化。顺序相关（只作归因说明，不作判定）。"""
    p2 = p2 or load_p2()
    rows, prev = [], None
    for label, kw in STEPS:
        m, _ = p2_model(p2, **kw)
        v = model_values(m, TRACKED)
        row = {"step": label, "values": v}
        if prev is not None:
            row["dln"] = {k: math.log(v[k] / prev[k]) for k in ("S_H_1", "S_H_2", "S_F_1", "S_F_2")}
        rows.append(row)
        prev = v
    final = {k: ks(p2, k) for k, _ in TRACKED}
    rows.append({"step": "KISSsoft P2", "values": final,
                 "dln": {k: math.log(final[k] / prev[k]) for k in ("S_H_1", "S_H_2", "S_F_1", "S_F_2")}})
    return rows


FACTOR_NAMES = [(n, "1") for n in ("S_H_1", "S_H_2", "S_F_1", "S_F_2", "Z_NT_1", "Z_NT_2", "Z_L", "Z_V", "Z_R", "Z_H", "Z_E",
                                   "Z_eps", "K_V", "K_Hbeta", "K_Halpha", "K_Fbeta", "K_Falpha", "Y_NT_1", "Y_NT_2",
                                   "Y_drelT_1", "Y_drelT_2", "Y_RrelT_1", "Y_RrelT_2", "Y_X", "Y_F_1", "Y_F_2", "Y_S_1", "Y_S_2",
                                   "Y_B", "Y_DT", "eps_alpha")]


def reconcile_document(doc, family, case, p2=None):
    """优化写回文档（经统一校核同一装配）vs KISSsoft P2：逐系数差 + 四个安全系数的对数分解。"""
    from .source_optimize import build_family_model
    p2 = p2 or load_p2()
    m = build_family_model(doc, family, case)
    a = model_values(m, FACTOR_NAMES)
    b = {n: ks(p2, n) for n, _ in FACTOR_NAMES}
    prov = {n: ("formula" if n in m.formulas else m.inputs[n].provenance) for n, _ in FACTOR_NAMES}
    factors = [{"name": n, "gearbase": a[n], "kisssoft": b[n], "rel_diff": a[n] / b[n] - 1, "gearbase_source": prov[n]}
               for n, _ in FACTOR_NAMES]
    dec = {q: log_decomposition(a, b, q) for q in ("S_H_1", "S_H_2", "S_F_1", "S_F_2")}
    return {"factors": factors, "decomposition": dec}


# ---------------------------------------------------------------- 复核预测（新 KISSsoft 运行请求用）
def iso21771_tip_alteration_mm(model):
    """k·m_n = a_w − a_d − (x_1 + x_2)·m_n（保持标准顶隙的齿顶高变动；ISO 21771 关系，KISSsoft P2 自动值 −0.015 mm 与本式
    −0.0152 mm 在其 0.001 mm 显示精度内一致）。只用于预测 KISSsoft 自动行为，不进入本库校核。"""
    r = model.evaluate(["a_w", "a"])
    k = U.from_canonical(r.values["a_w"] - r.values["a"], "mm") - (model.inputs["x_1"].value + model.inputs["x_2"].value) * \
        U.from_canonical(model.inputs["m_n"].value, "mm")
    return k


def predict_for_document(doc, family, case, *, k_X_mm=0.0, shaft=None):
    """在文档的装配（统一校核同一模型）上加齿顶缩短 k_X 与可选的小轮轴输入，求 S_H/S_F/ε_α 等。
    shaft=None 保持文档值；shaft={"l_sh": mm, "s_sh": mm, "d_sh": mm} 覆盖（模拟 KISSsoft 按齿宽缩放）。"""
    from .source_optimize import build_family_model
    m = _with_tip_alteration(build_family_model(doc, family, case))
    for i in ("1", "2"):
        m.set(f"k_X_{i}", k_X_mm, "mm", "assumption", "复核预测：齿顶缩短 k·m_n")
    for n, v in (shaft or {}).items():
        m.set(n, v, "mm", "assumption", "复核预测：小轮轴按 KISSsoft P2 自动缩放")
    names = [("S_H_1", "1"), ("S_H_2", "1"), ("S_F_1", "1"), ("S_F_2", "1"), ("eps_alpha", "1"), ("a_w", "mm"),
             ("K_V", "1"), ("K_Hbeta", "1"), ("Z_V", "1"), ("Z_R", "1"), ("Z_NT_2", "1"), ("Y_NT_2", "1"),
             ("Y_drelT_1", "1"), ("Y_drelT_2", "1"), ("d_inner_1", "mm"), ("d_inner_2", "mm"), ("f_Hbeta5", "um"),
             ("f_Hbeta_1", "um"), ("f_Hbeta_2", "um"), ("da_1", "mm"), ("da_2", "mm"), ("alpha_wt", "rad")]
    return model_values(m, [(n, u) for n, u in names if n in m.formulas or n in m.inputs])
