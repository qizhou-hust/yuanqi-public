"""v0.17 K02GAP：OPT3-3-K02（K02 优化修订解 z 26/98、m_n 2、b 27/26、x1 0.3）的 KISSsoft 2026 外部复核 —— 偏差归因。

数据：data/kisssoft_v017/OPT3-3-K02.json（extract() 从只读外部证据 ext18/evidence 提取的最小 JSON；每个值带字段定位，
来源文件带相对路径与 sha256；不含 PDF/Z12/HTML）。按私有资料处理（与 data/kisssoft 同级）。

归因方法（替换实验）：S_H/S_F 在本库与 KISSsoft 中均为系数之积（S_H = σHG/σH，σHG = σHlim·Z_NT·Z_L·Z_V·Z_R·Z_W·Z_X，
σH = Z_B|D·Z_H·Z_E·Z_ε·Z_β·√(F_t/(d_1 b)·(u+1)/u)·√(K_A K_V K_Hβ K_Hα)；S_F 同理）。从本库预测出发，按 ORDER_* 顺序
逐项把系数换成 KISSsoft 值并重算乘积：每步 Δln S 为该项贡献（纯乘积下与顺序无关），残差 = ln(S_KS/S_本库) − Σ贡献，
同时核对 KISSsoft 自身输出满足同一乘积（ks_product_rel）。Z_W·Z_X 合并为 ZWX = σHG/(σHlim Z_NT Z_L Z_V Z_R)（KISSsoft 未导出单项）。
不调输入/系数/门限追平 KISSsoft；参照值来自文件。
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATH = ROOT / "data" / "kisssoft_v017" / "OPT3-3-K02.json"
SCHEMA = "gearbase.kisssoft_v017.case/1"
EVIDENCE = pathlib.Path("/home/claude/in/ext18/evidence")
RUN = "commercial-original/cases/OPT3-3-K02/run.json"
RECEIPT = "commercial-audit/receipt.json"
REPORT = "commercial-audit/derived-txt/OPT3-3-K02.txt"
FACTOR_DIFF = "commercial-original/evidence/optimizer-factor-diff.json"

# (名, run.json values 键, 单位)
FIELDS = [
    # 输入（readback / 自动改动）
    ("z_1", "ZR[0].z", "1"), ("z_2", "ZR[1].z", "1"), ("m_n", "ZS.Geo.mn", "mm"), ("alpha_n", "ZS.Geo.alfn", "rad"),
    ("beta", "ZS.Geo.beta", "rad"), ("b_1", "ZR[0].b", "mm"), ("b_2", "ZR[1].b", "mm"), ("x_1", "ZR[0].x.nul", "1"),
    ("x_2", "ZR[1].x.nul", "1"), ("a_w", "ZP[0].a", "mm"), ("n_1", "ZR[0].nnominal", "rpm"), ("P", "ZS.Pnominal", "kW"),
    ("K_A", "ZS.KA", "1"), ("H", "ZS.Hreport", "h"), ("K_gamma", "ZS.Kgam", "1"), ("bs_b", "ZP[0].bs_to_b", "1"),
    ("l_sh", "ZP[0].KHdat.l", "mm"), ("s_sh", "ZP[0].KHdat.S", "mm"), ("d_sh", "ZP[0].KHdat.dsh", "mm"),
    ("pinion_arrangement_code", "ZP[0].KHdat.Belastung", "1"), ("K_prime", "ZP[0].KHdat.FaktorK", "1"),
    ("lsdFlag", "Zst.lsdFlag", "bool"), ("KHbVariant", "Zst.KHbVariant", "1"),
    ("kFaktorFlag_1", "ZR[0].kFaktorFlag", "bool"), ("kFaktorFlag_2", "ZR[1].kFaktorFlag", "bool"),
    ("k_X_1", "ZR[0].kXmn", "mm"), ("k_X_2", "ZR[1].kXmn", "mm"), ("d_inner_1", "ZR[0].di", "mm"), ("d_inner_2", "ZR[1].di", "mm"),
    ("Q_DIN3961_1", "ZR[0].Vqual", "1"), ("Q_DIN3961_2", "ZR[1].Vqual", "1"),
    ("A_sn_e_1", "ZR[0].As.E", "mm"), ("A_sn_i_1", "ZR[0].As.i", "mm"), ("A_sn_e_2", "ZR[1].As.E", "mm"), ("A_sn_i_2", "ZR[1].As.i", "mm"),
    ("tol_name_1", "ZR[0].ZDTolName", "text"), ("tol_name_2", "ZR[1].ZDTolName", "text"),
    ("f_Hbeta_1", "ZR[0].Tol.fHb", "um"), ("f_Hbeta_2", "ZR[1].Tol.fHb", "um"), ("f_falpha_1", "ZR[0].Tol.ff", "um"),
    ("f_falpha_2", "ZR[1].Tol.ff", "um"), ("f_base_1", "ZR[0].Tol.fpe", "um"), ("f_base_2", "ZR[1].Tol.fpe", "um"),
    ("f_pt_1", "ZR[0].Tol.fp", "um"), ("f_pt_2", "ZR[1].Tol.fp", "um"),
    ("sigma_Hlim_1", "ZR[0].mat.limh", "MPa"), ("sigma_Hlim_2", "ZR[1].mat.limh", "MPa"),
    ("sigma_Flim_1", "ZR[0].mat.limf", "MPa"), ("sigma_Flim_2", "ZR[1].mat.limf", "MPa"),
    ("Rz_H_1", "ZR[0].RZH", "um"), ("Rz_H_2", "ZR[1].RZH", "um"), ("Cf_1", "ZR[0].Cf", "1"), ("Cf_2", "ZR[1].Cf", "1"),
    # 输出：几何
    ("d_1", "ZR[0].d", "mm"), ("d_2", "ZR[1].d", "mm"), ("u", "ZP[0].uDIN", "1"), ("eps_alpha", "ZP[0].Eps.a", "1"),
    ("eps_beta", "ZP[0].Eps.b", "1"), ("alpha_wt", "ZP[0].alfwt", "rad"), ("da_1", "ZR[0].da.nul", "mm"), ("da_2", "ZR[1].da.nul", "mm"),
    ("xE_1", "ZR[0].x.i", "1"), ("xE_2", "ZR[1].x.i", "1"), ("df_min_2", "ZR[1].df.i", "mm"),
    # 输出：载荷与 K 系数
    ("F_t", "ZP[0].Ft", "N"), ("K_V", "ZP[0].KV.KV", "1"), ("K_Hbeta", "ZP[0].KHb", "1"), ("K_Fbeta", "ZP[0].KFb", "1"),
    ("K_Halpha", "ZP[0].KHa", "1"), ("K_Falpha", "ZP[0].KFa", "1"), ("m_red", "ZP[0].KV.mRed", "kg/mm"),
    ("c_gamma_alpha", "ZP[0].KV.cg", "N/(mm*um)"), ("c_gamma_beta", "ZP[0].KV.cgbet", "N/(mm*um)"), ("C_R", "ZP[0].KV.CR", "1"),
    ("N_res", "ZP[0].KV.n", "1"),
    # K_Hβ 方法 C 中间量（KISSsoft 字段口径：fsh = B1·f_sh(式59)，fsh00 = f_sh(式59)，fma = B2·f_ma(式66)）
    ("f_Hbeta5", "ZP[0].KHdat.fHb5", "um"), ("ks_fsh", "ZP[0].KHdat.fsh", "um"), ("ks_fsh00", "ZP[0].KHdat.fsh00", "um"),
    ("ks_fma", "ZP[0].KHdat.fma", "um"), ("F_bx", "ZP[0].KHdat.Fbx", "um"), ("F_by", "ZP[0].KHdat.Fby", "um"),
    ("y_beta", "ZP[0].KHdat.yb", "um"), ("B_1", "ZP[0].KHdat.B1", "1"), ("B_2", "ZP[0].KHdat.B2", "1"),
    # 输出：接触
    ("Z_H", "ZP[0].Flanke.ZH", "1"), ("Z_E", "ZP[0].Flanke.ZE", "sqrt(MPa)"), ("Z_eps", "ZP[0].Flanke.Zeps", "1"),
    ("Z_beta", "ZP[0].Flanke.Zbet", "1"), ("Z_B", "ZPP[0].Flanke.ZBD", "1"), ("Z_D", "ZPP[1].Flanke.ZBD", "1"),
    ("f_ZCa", "ZP[0].Flanke.fZCa", "1"), ("sigma_H0", "ZP[0].Flanke.sigH0", "MPa"),
    ("sigma_H_1", "ZPP[0].Flanke.sigHBD", "MPa"), ("sigma_H_2", "ZPP[1].Flanke.sigHBD", "MPa"),
    ("sigma_HG_1", "ZPP[0].Flanke.sigHP", "MPa"), ("sigma_HG_2", "ZPP[1].Flanke.sigHP", "MPa"),
    ("Z_NT_1", "ZR[0].Flanke.ZNT", "1"), ("Z_NT_2", "ZR[1].Flanke.ZNT", "1"), ("Z_L", "ZPP[0].Flanke.ZL", "1"),
    ("Z_V", "ZPP[0].Flanke.ZV", "1"), ("Z_R", "ZPP[0].Flanke.ZR", "1"),
    ("S_H_1", "ZPP[0].Flanke.SH", "1"), ("S_H_2", "ZPP[1].Flanke.SH", "1"),
    # 输出：齿根
    ("Y_F_1", "ZPP[0].Fuss.YF", "1"), ("Y_F_2", "ZPP[1].Fuss.YF", "1"), ("Y_S_1", "ZPP[0].Fuss.YS", "1"), ("Y_S_2", "ZPP[1].Fuss.YS", "1"),
    ("Y_beta", "ZP[0].Fuss.Ybet", "1"), ("Y_eps", "ZP[0].Fuss.Yeps", "1"), ("Y_B_1", "ZR[0].Fuss.YB", "1"), ("Y_B_2", "ZR[1].Fuss.YB", "1"),
    ("Y_DT", "ZP[0].Fuss.YDT", "1"), ("Y_NT_1", "ZR[0].Fuss.YNT", "1"), ("Y_NT_2", "ZR[1].Fuss.YNT", "1"),
    ("Y_drelT_1", "ZPP[0].Fuss.Ydrel", "1"), ("Y_drelT_2", "ZPP[1].Fuss.Ydrel", "1"),
    ("Y_RrelT_1", "ZR[0].Fuss.YR", "1"), ("Y_RrelT_2", "ZR[1].Fuss.YR", "1"), ("Y_X", "ZR[0].Fuss.YX", "1"),
    ("sigma_F_1", "ZPP[0].Fuss.sigF", "MPa"), ("sigma_F_2", "ZPP[1].Fuss.sigF", "MPa"),
    ("sigma_FG_1", "ZPP[0].Fuss.sigFP", "MPa"), ("sigma_FG_2", "ZPP[1].Fuss.sigFP", "MPa"),
    ("S_F_1", "ZPP[0].Fuss.SFnorm", "1"), ("S_F_2", "ZPP[1].Fuss.SFnorm", "1"),
]
Y_ST_REPORT = 2.0   # KISSsoft σFG = σFlim·Y_ST·Y_NT·Y_δ·Y_R·Y_X 逐位复核（σFG_1 = 713.6714…），Y_ST 未单独导出


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def extract(root=EVIDENCE):
    """只在外部证据目录存在时运行；返回最小 JSON（不复制原生/报告文件）。"""
    run = json.loads((root / RUN).read_text(encoding="utf-8"))
    rec = json.loads((root / RECEIPT).read_text(encoding="utf-8"))
    case = next(c for c in rec["cases"] if c["id"] == "OPT3-3-K02")
    vals = run["values"]
    values = {}
    for name, key, unit in FIELDS:
        v = vals[key]
        values[name] = {"field": key, "unit": unit, "value": v if isinstance(v, str) else float(v), "source": "run"}
    edits = [{k: e[k] for k in ("field", "requested", "logged_readback", "native_saved", "requested_matches_saved_native")}
             for e in case["input_edits"]]
    return {
        "schema": SCHEMA, "case": "OPT3-3-K02",
        "note": "KISSsoft 2026（26.0.0.0）Z012 既有运行记录（未重跑）；本库 K02 优化写回 K02-helical.factors.opt-4ee0a4da 的外部复核。"
                "值为 run.json values 全精度；输入身份见 input_edits（x_2 原生保存值比请求值 −2.418e-8，KISSsoft 自行重算）。",
        "sources": {k: {"path": p, "sha256": _sha(root / p)}
                    for k, p in (("run", RUN), ("receipt", RECEIPT), ("report_txt", REPORT), ("factor_diff", FACTOR_DIFF))},
        "source_root": "ext18/evidence（只读外部证据，相对路径）",
        "identity": {"version": run["version"], "file_version": run["file_version"], "module": run["module"],
                     "source_sha256": run["source_sha256"], "native_sha256": run["native_sha256"],
                     "calculate_return": run["calculate_return"], "reload_differences": run["reload_differences"],
                     "accepted": run["accepted"]},
        "input_edits": edits,
        "prediction_v017": {k: case["prediction_comparison"][f]["predicted"] for k, f in
                            (("S_H_1", "ZPP[0].Flanke.SH"), ("S_H_2", "ZPP[1].Flanke.SH"),
                             ("S_F_1", "ZPP[0].Fuss.SFnorm"), ("S_F_2", "ZPP[1].Fuss.SFnorm"))},
        "values": values,
    }


def write(root=EVIDENCE, path=PATH):
    d = extract(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return d


def load(path=PATH):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def ks_values(d=None):
    d = d or load()
    out = {n: r["value"] for n, r in d["values"].items() if not isinstance(r["value"], str)}
    out["Y_ST"] = Y_ST_REPORT
    out["b"] = min(out["b_1"], out["b_2"])
    return out


# ---------------------------------------------------------------- 替换实验（对数分解）
ORDER_H = ("K_Hbeta", "K_Halpha", "K_V", "Z_NT_{i}", "Z_eps", "Z_R", "Z_H", "Z_L", "Z_V", "Z_E", "Z_beta", "Z_B", "Z_D",
           "ZWX", "geom_H", "K_A", "sigma_Hlim_{i}")
ORDER_F = ("K_Fbeta", "K_Falpha", "K_V", "Y_F_{i}", "Y_S_{i}", "Y_NT_{i}", "Y_drelT_{i}", "Y_RrelT_{i}", "Y_X", "Y_beta",
           "Y_B_{i}", "Y_DT", "F_t", "b_{i}", "m_n", "K_A", "Y_ST", "sigma_Flim_{i}")
MODEL_NAMES = [("S_H_1", "1"), ("S_H_2", "1"), ("S_F_1", "1"), ("S_F_2", "1"), ("Z_NT_1", "1"), ("Z_NT_2", "1"), ("Z_L", "1"),
               ("Z_V", "1"), ("Z_R", "1"), ("Z_B", "1"), ("Z_D", "1"), ("Z_H", "1"), ("Z_E", "sqrt(MPa)"), ("Z_eps", "1"),
               ("Z_beta", "1"), ("K_A", "1"), ("K_V", "1"), ("K_Hbeta", "1"), ("K_Halpha", "1"), ("K_Fbeta", "1"),
               ("K_Falpha", "1"), ("Y_NT_1", "1"), ("Y_NT_2", "1"), ("Y_drelT_1", "1"), ("Y_drelT_2", "1"), ("Y_RrelT_1", "1"),
               ("Y_RrelT_2", "1"), ("Y_X", "1"), ("Y_F_1", "1"), ("Y_F_2", "1"), ("Y_S_1", "1"), ("Y_S_2", "1"), ("Y_beta", "1"),
               ("Y_B_1", "1"), ("Y_B_2", "1"), ("Y_DT", "1"), ("Y_ST", "1"), ("F_t", "N"), ("d_1", "mm"), ("b", "mm"),
               ("b_1", "mm"), ("b_2", "mm"), ("m_n", "mm"), ("u", "1"), ("sigma_Hlim_1", "MPa"), ("sigma_Hlim_2", "MPa"),
               ("sigma_Flim_1", "MPa"), ("sigma_Flim_2", "MPa"), ("sigma_HG_1", "MPa"), ("sigma_HG_2", "MPa"),
               ("f_Hbeta5", "um"), ("F_bx", "um"), ("eps_alpha", "1"), ("xE_1", "1")]


def _derived(s):
    s = dict(s)
    s["ZWX"] = s["sigma_HG_1"] / (s["sigma_Hlim_1"] * s["Z_NT_1"] * s["Z_L"] * s["Z_V"] * s["Z_R"])
    s["geom_H"] = math.sqrt(s["F_t"] / (s["d_1"] * s["b"]) * (s["u"] + 1) / s["u"])
    return s


def s_h(s, i):
    zb = s["Z_B"] if i == "1" else s["Z_D"]
    return (s[f"sigma_Hlim_{i}"] * s[f"Z_NT_{i}"] * s["Z_L"] * s["Z_V"] * s["Z_R"] * s["ZWX"]) / (
        zb * s["Z_H"] * s["Z_E"] * s["Z_eps"] * s["Z_beta"] * s["geom_H"] * math.sqrt(s["K_A"] * s["K_V"] * s["K_Hbeta"] * s["K_Halpha"]))


def s_f(s, i):
    return (s[f"sigma_Flim_{i}"] * s["Y_ST"] * s[f"Y_NT_{i}"] * s[f"Y_drelT_{i}"] * s[f"Y_RrelT_{i}"] * s["Y_X"]) / (
        s["F_t"] / (s[f"b_{i}"] * s["m_n"]) * s[f"Y_F_{i}"] * s[f"Y_S_{i}"] * s["Y_beta"] * s[f"Y_B_{i}"] * s["Y_DT"]
        * s["K_A"] * s["K_V"] * s["K_Fbeta"] * s["K_Falpha"])


def substitution(ours, ks):
    """ours/ks：{量: 值}（单位见 MODEL_NAMES）。返回四个安全系数的逐项替换贡献、残差与 KISSsoft 乘积自洽。"""
    a, b = _derived(ours), _derived(ks)
    out = {}
    for q, fn, order in (("S_H_1", s_h, ORDER_H), ("S_H_2", s_h, ORDER_H), ("S_F_1", s_f, ORDER_F), ("S_F_2", s_f, ORDER_F)):
        i = q[-1]
        cur, rows = dict(a), []
        prev = fn(cur, i)
        start = prev / a[q] - 1
        for n in order:
            n = n.replace("{i}", i)
            cur[n] = b[n]
            s = fn(cur, i)
            rows.append({"factor": n, "gearbase": a[n], "kisssoft": b[n], "dln": math.log(s / prev)})
            prev = s
        total = math.log(b[q] / a[q])
        out[q] = {"gearbase": a[q], "kisssoft": b[q], "rel": b[q] / a[q] - 1, "ln_ks_over_gearbase": total, "rows": rows,
                  "residual": total - sum(r["dln"] for r in rows), "gearbase_product_rel": start,
                  "ks_product_rel": fn(b, i) / b[q] - 1}
    return out


def model_point(doc, sets=()):
    """文档装配（统一校核同一模型）在其写回点的系数值；sets=[(名, 值, 单位)] 覆盖输入（替换实验用）。"""
    from .kisssoft_v014 import model_values
    from .source_optimize import build_family_model
    m = build_family_model(doc, "kisssoft_chain", "K02-helical")
    for n, v, u in sets:
        m.set(n, v, u, "assumption", "v0.17 K02GAP 替换实验：取 KISSsoft OPT3-3-K02 值")
    return model_values(m, [(n, u) for n, u in MODEL_NAMES if n in m.formulas or n in m.inputs])


# 全模型传播替换（有耦合：K_Hβ → K_Hα（F_tH）→ K_Fβ/K_Fα；A_sn → x_E → Y_F/Y_S）
PROPAGATION_STEPS = (
    ("f_Hbeta5", "um"), ("f_Hbeta_2", "um"), ("Z_NT_2", "1"), ("Y_NT_2", "1"), ("Y_drelT_1", "1"), ("Y_drelT_2", "1"), ("A_sn_i_1", "mm"),
)


def propagation(doc, ks=None):
    from ..kernel.graph import InputError
    ks = ks or ks_values()
    rows, acc = [], []
    rows.append({"step": "start", "values": model_point(doc)})
    for n, u in PROPAGATION_STEPS:
        acc.append((n, ks[n], u))
        try:
            rows.append({"step": n, "values": model_point(doc, acc)})
        except InputError:          # 该量在本文档中已是公式输出（如修复后的 f_Hbeta5）：不覆盖
            acc.pop()
            rows.append({"step": n, "skipped": "formula_output"})
    return rows
