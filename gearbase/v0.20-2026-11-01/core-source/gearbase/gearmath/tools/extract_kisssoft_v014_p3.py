"""从 KISSsoft v0.14 本地复算证据目录提取 P3（K01–K05 胶合/微点蚀）最小 JSON 到 data/kisssoft_v014/。

用法（显式调用，不被测试执行）：
    python3 -I gearmath/tools/extract_kisssoft_v014_p3.py <证据目录，含 P3-K0*/run.json> <输出目录>
只读证据目录；每个字段记录 KISSsoft 键名/报告标签与来源文件相对路径 + sha256。不复制 PDF/Z12。
-22 只对 seven_points_valid=true 的 K01/K02 提取七点；K03–K05 的零值为无效占位，只记原因。
私有资料：输出与 data/kisssoft 同级处理，不外传。
"""
import hashlib
import json
import pathlib
import re
import sys

KS = OUT = None
CASES = ["P3-K01-spur", "P3-K02-helical", "P3-K03-premachining", "P3-K04-EV-stage1", "P3-K05-EV-stage2"]
MP_VALID = {"P3-K01-spur": "K01-spur", "P3-K02-helical": "K02-helical"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def src(rel):
    return {"path": rel, "sha256": sha(KS / rel)}


def fmt_txt(p):
    lines = [ln.rstrip() for ln in p.read_text(encoding="utf-8").replace("\r", "").split("\n") if ln.strip()]
    s = "|".join(lines)
    s = re.sub(r"\|\[", " [", s)
    s = re.sub(r"\] *\|", "]: ", s)
    return s.split("|")


INPUT_KEYS = {
    # name: (KISSsoft key, unit)
    "z1": ("ZR[0].z", "1"), "z2": ("ZR[1].z", "1"), "a": ("ZP[0].a", "mm"),
    "alpha_n": ("ZS.Geo.alfn", "rad"), "alpha_t": ("ZS.Geo.alft", "rad"), "alpha_wt": ("ZP[0].alfwt", "rad"),
    "beta": ("ZS.Geo.beta", "rad"), "beta_b": ("ZS.Geo.betab", "rad"),
    "d1": ("ZR[0].d", "mm"), "d2": ("ZR[1].d", "mm"), "d_w1": ("ZPP[0].dw", "mm"), "d_w2": ("ZPP[1].dw", "mm"),
    "d_a1": ("ZR[0].da.nul", "mm"), "d_a2": ("ZR[1].da.nul", "mm"), "d_b1": ("ZR[0].dB", "mm"), "d_b2": ("ZR[1].dB", "mm"),
    "b1": ("ZR[0].b", "mm"), "b2": ("ZR[1].b", "mm"), "b_min": ("ZP[0].bMin", "mm"),
    "eps_alpha": ("ZP[0].Eps.a", "1"), "eps_beta": ("ZP[0].Eps.b", "1"),
    "eps_1": ("ZPP[0].eps.nul", "1"), "eps_2": ("ZPP[1].eps.nul", "1"),
    "g_alpha": ("ZP[0].EL.ga.nul", "mm"), "p_et": ("ZS.Geo.pet", "mm"),
    "rho_t1_A": ("ZP[0].EL.T1A.nul", "mm"), "rho_t1_C": ("ZP[0].EL.T1C.nul", "mm"), "rho_t1_E": ("ZP[0].EL.T1E.nul", "mm"),
    "n1": ("ZR[0].nnominal", "1/min"), "T1": ("ZR[0].Tnominal", "N*m"), "F_t": ("ZP[0].Ft", "N"), "v": ("ZS.v", "m/s"),
    "K_A": ("ZS.KA", "1"), "K_v": ("ZP[0].KV.KV", "1"), "K_Hbeta": ("ZP[0].KHb", "1"), "K_Halpha": ("ZP[0].KHa", "1"),
    "K_Bbeta": ("ZP[0].KBb", "1"), "K_Balpha": ("ZP[0].KBa", "1"), "K_gamma": ("ZS.Kgam", "1"),
    "c_prime": ("ZP[0].KV.cStr", "N/(mm*um)"), "c_gamma_alpha": ("ZP[0].KV.cg", "N/(mm*um)"),
    "E1": ("ZR[0].mat.E", "N/mm2"), "E2": ("ZR[1].mat.E", "N/mm2"), "nu1": ("ZR[0].mat.ny", "1"), "nu2": ("ZR[1].mat.ny", "1"),
    "B_M1": ("ZR[0].BM", "N/(mm*s^0.5*K)"), "B_M2": ("ZR[1].BM", "N/(mm*s^0.5*K)"),
    "material1": ("ZR[0].mat.bez", "-"), "material2": ("ZR[1].mat.bez", "-"),
    "Ra1": ("ZR[0].RAH", "um"), "Ra2": ("ZR[1].RAH", "um"),
    "C_eff": ("ZP[0].Ceff", "um"), "C_eq": ("ZPP[0].Ceq", "um"), "Ca_valid_flag": ("ZPP[0].CaValid", "-"),
    "oil_name": ("ZS.Oil.SchmierTyp", "-"), "nu_40": ("ZS.Oil.nu40", "mm2/s"), "nu_100": ("ZS.Oil.nu100", "mm2/s"),
    "rho_15": ("ZS.Oil.roOil", "kg/dm3"), "theta_oil": ("ZS.Oil.theOil", "degC"),
    "lubrication_type_code": ("ZS.Oil.SchmierungsArt", "-"), "lubricant_base_code": ("ZS.Oil.SchmierBase", "-"),
    "fzg_load_stage": ("ZS.Oil.FZGtestA", "1"), "scoring_test_name": ("ZS.Oil.ScoringTestName", "-"),
    "fzg_test_mp": ("ZS.Oil.FZGtestMP", "1"), "micropitting_test": ("ZS.Oil.MicroPittingTest", "-"),
    "X_S": ("ZS.Oil.XS", "1"), "X_mp": ("ZP[0].Scoring_Xmp", "1"), "X_WrelT": ("ZP[0].XWrelT", "1"),
    "scoring_runin": ("RechSt.Scoring_RunIn", "-"), "scoring_standard_used": ("RechSt.ScoringStandardUsed", "-"),
    "micropitting_standard": ("RechSt.MicropittingStandard", "-"), "theta_M_input_flag": ("RechSt.ThetaMInput", "-"),
    "use_iso15144_mu": ("RechSt.UseISO15144_my", "-"),
}
OUT21 = {
    "eta_oil": ("ZP[0].FIT.etaOil", "mPa*s"), "mu_mC": ("ZP[0].FIT.mym", "1"), "X_M": ("ZP[0].FIT.XM", "K*N^-0.75*s^0.5*m^-0.5*mm"),
    "X_BE": ("ZP[0].FIT.XBE", "1"), "X_alphabeta": ("ZP[0].FIT.Xalfbet", "1"), "X_Q": ("ZP[0].FIT.XQ", "1"),
    "X_Ca": ("ZP[0].FIT.XCa", "1"), "X_eps": ("ZP[0].FIT.XE", "1"), "X_E": ("ZP[0].Scoring_XE", "1"),
    "K_Bgamma": ("ZP[0].Kbg", "1"), "wBt_times_KBgamma": ("ZP[0].Scoring_wBT", "N/mm"),
    "theta_flaint": ("ZP[0].FIT.theflaint", "K"), "theta_M": ("ZP[0].FIT.theMC", "degC"),
    "theta_int": ("ZP[0].FIT.theint", "degC"), "theta_intS": ("ZP[0].FIT.theSint", "degC"),
    "S_intS": ("ZP[0].FIT.SSint", "1"), "S_Sl": ("ZP[0].FIT.SSL", "1"),
}
OUT20 = {
    "mu_m": ("ZP[0].FBT.mymy", "1"), "X_L_part1": ("ZP[0].FBT.XLforPart1", "1"), "X_J_at_max": ("ZP[0].Scoring_XJ", "1"),
    "X_Gamma_at_max": ("ZP[0].FBT.XGam", "1"), "Gamma_at_max": ("ZP[0].FBT.Gamma", "1"),
    "theta_flmax": ("ZP[0].FBT.theflamax", "K"), "theta_flm": ("ZP[0].Scoring_Theflm", "K"),
    "theta_Mi": ("ZP[0].FBT.them", "degC"), "theta_Bmax": ("ZP[0].FBT.theB", "degC"), "theta_S": ("ZP[0].FBT.thes", "degC"),
    "S_B": ("ZP[0].FBT.SB", "1"), "X_M": ("ZP[0].FBT.XM", "K*N^-0.75*s^0.5*m^-0.5*mm"), "eta_oil": ("ZP[0].FBT.etaOil", "mPa*s"),
}
MP_SCALARS = {
    "S_lambda_B": ("ZP[0].MP_ISO.SlamB", "1"), "lambda_GF_min": ("ZP[0].MP_ISO.lamGFY", "1"),
    "critical_point": ("ZP[0].MP_ISO.CriticalPoint", "0..6"), "h_Y_min": ("ZP[0].MP_ISO.hYmin", "um"),
    "alpha_38": ("ZS.Oil.alfa38", "mm2/N (=1e-6 m2/N)"), "alpha_thetaM": ("ZS.Oil.alfa", "mm2/N (=1e-6 m2/N)"),
    "lambda_GFT": ("ZS.RefMP.lamGFT", "1"),
}
PT_KEYS = ["GamY", "gY", "XY", "pHYB", "phidynYB", "Theta_flY", "TheBY", "alpha", "UY", "WY", "SGFY", "hY", "lamGFY",
           "ronY", "Slam", "vgY"]
PT_GEAR = ["dY", "vrY", "rtY"]
POINTS = ["A", "AB", "B", "C", "D", "DE", "E"]


def txt_value(lines, label, after=None):
    start = 0
    if after:
        start = next(i for i, ln in enumerate(lines) if after in ln)
    for i in range(start, len(lines)):
        if label in lines[i]:
            return i
    return None


def main(argv):
    global KS, OUT
    if len(argv) != 2:
        raise SystemExit("用法：extract_kisssoft_v014_p3.py <证据目录> <输出目录>")
    KS, OUT = pathlib.Path(argv[0]), pathlib.Path(argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    supp = json.loads((KS / "P3-supplemental-scalars.json").read_text())
    for case in CASES:
        d = KS / case
        run = json.loads((d / "run.json").read_text())
        det = json.loads((d / "p3-detail.json").read_text())
        vals = dict(run["values"])
        dv = det["values"]
        srcmap = {k: "run" for k in vals}
        for k, x in dv.items():
            if k not in vals:
                srcmap[k] = "detail"
            vals[k] = x
        lines = fmt_txt(d / f"{case}.txt")
        rec = {
            "schema": "gearbase.kisssoft_v014.p3/1",
            "id": case,
            "software": "KISSsoft Release 2026, file version 26.0.0.0",
            "scope": "原生厂商例模型（与 data/kisssoft 同源 Z12）+原生油品/工况；仅改 RechSt.ScoringStandard=1"
                     "（ISO/TS 6336-20/21:2022）与 MicropittingStandard=1（ISO/TS 6336-22:2018）；不是 P2 优化几何",
            "private": True,
            "sources": {
                "run": src(f"{case}/run.json"), "detail": src(f"{case}/p3-detail.json"),
                "report_txt": src(f"{case}/{case}.txt"),
                "micropitting_txt": src(f"{case}/micropitting-seven-points.txt"),
                "supplemental": src("P3-supplemental-scalars.json"), "review": src("review.txt"),
                "results": src("RESULTS.txt"),
            },
            "native": {"source_sha256": run["source_sha256"], "native_sha256": run["native_sha256"],
                       "calculate_return": run["calculate_return"], "reload_calculate_return": run["reload_calculate_return"],
                       "reload_differences": run["reload_differences"], "source_unchanged": run["source_unchanged"],
                       "edits": run["edits"]},
            "units_note": "角度 rad；COM 原值全精度；报告文本字段为打印精度",
            "inputs": {}, "outputs": {"iso6336_21": {}, "iso6336_20": {}, "iso6336_22": {}},
        }
        for name, (key, unit) in INPUT_KEYS.items():
            rec["inputs"][name] = {"v": vals[key], "key": key, "src": srcmap[key], "unit": unit}
        # report-text inputs
        i = txt_value(lines, "Gear driving (+) / driven (-)")
        rec["inputs"]["driver"] = {"v": "pinion" if lines[i + 1].strip() == "+" and lines[i + 2].strip() == "-" else None,
                                   "key": "Gear driving (+) / driven (-): " + lines[i + 1].strip() + "/" + lines[i + 2].strip(),
                                   "src": "report_txt", "unit": "-"}
        i = txt_value(lines, "Accuracy grade")
        rec["inputs"]["accuracy_grade"] = {"v": [lines[i].split(":")[-1].strip(), lines[i + 1].strip()],
                                           "key": lines[i].split("]:")[0] + "]", "src": "report_txt", "unit": "-"}
        i = txt_value(lines, "Lubrication type")
        rec["inputs"]["lubrication_type"] = {"v": lines[i + 1].strip(), "key": "Lubrication type", "src": "report_txt", "unit": "-"}
        i = txt_value(lines, "Lubricant base")
        rec["inputs"]["lubricant_base"] = {"v": lines[i + 1].strip(), "key": "Lubricant base", "src": "report_txt", "unit": "-"}
        i = txt_value(lines, "Type of profile modification")
        rec["inputs"]["profile_modification"] = {"v": lines[i + 1].strip(), "key": "Type of profile modification",
                                                 "src": "report_txt", "unit": "-"}
        sc = "Scuffing load capacity"
        i = txt_value(lines, "Ca taken as optimal", after=sc)
        rec["inputs"]["Ca_taken_as_optimal"] = {"v": [int(lines[i + 1]), int(lines[i + 2])],
                                                "key": "Scuffing: Ca taken as optimal in the calculation (0=no,1=yes)",
                                                "src": "report_txt", "unit": "-"}
        i = txt_value(lines, "Relevant tip relief", after=sc)
        if i is not None:
            rec["inputs"]["Ca_relevant"] = {"v": [float(lines[i].split(":")[-1]), float(lines[i + 1])],
                                            "key": "Scuffing: Relevant tip relief [Ca]", "src": "report_txt", "unit": "um"}
        else:
            rec["inputs"]["Ca_relevant"] = {"v": None, "key": "Scuffing: Relevant tip relief [Ca] 未打印（报告给 Ceq 行）",
                                            "src": "report_txt", "unit": "um"}
        i = txt_value(lines, "[Ca L/R]")
        parts = [lines[i].split("]:")[-1].strip()]
        for ln in lines[i + 1:i + 6]:
            if "[" in ln or "Basic data" in ln or not re.match(r"^[\s/0-9.]+$", ln):
                break
            parts.append(ln.strip())
        rec["inputs"]["Ca_LR_text"] = {"v": " ".join(parts), "key": lines[i].split("]:")[0] + "]（首次出现，最终加工信息节）",
                                       "src": "report_txt", "unit": "um"}
        i = txt_value(lines, "[FZGtest]")
        rec["inputs"]["fzg_test_text"] = {"v": lines[i].split("]:")[-1].strip() + " " + lines[i + 1].strip(),
                                          "key": "[FZGtest]", "src": "report_txt", "unit": "-"}
        for name, (key, unit) in OUT21.items():
            rec["outputs"]["iso6336_21"][name] = {"v": vals[key], "key": key, "src": srcmap[key], "unit": unit}
        w = vals["ZP[0].Scoring_wBT"] / vals["ZP[0].Kbg"]
        rec["outputs"]["iso6336_21"]["w_Bt"] = {"v": w, "key": "DERIVED ZP[0].Scoring_wBT/ZP[0].Kbg（review.txt：Z010Scoringe.rpt:182-186）",
                                                "src": "detail", "unit": "N/mm"}
        for name, (key, unit) in OUT20.items():
            rec["outputs"]["iso6336_20"][name] = {"v": vals[key], "key": key, "src": srcmap[key], "unit": unit}
        mp = rec["outputs"]["iso6336_22"]
        if case in MP_VALID and det.get("seven_points_valid"):
            sk = MP_VALID[case]
            mp["valid"] = True
            mp["scalars"] = {n: {"v": vals[k], "key": k, "src": srcmap[k], "unit": u} for n, (k, u) in MP_SCALARS.items()}
            mp["scalars"]["lambda_GFP"] = {"v": float(supp[sk]["ZP[0].RefMP.lamGFP"]), "key": "ZP[0].RefMP.lamGFP",
                                           "src": "supplemental", "unit": "1"}
            mp["scalars"]["theta_M"] = {"v": float(supp[sk]["ZP[0].MP_ISO.th0"]), "key": "ZP[0].MP_ISO.th0",
                                        "src": "supplemental", "unit": "degC"}
            pts = {}
            for j, p in enumerate(POINTS):
                row = {k: vals[f"ZP[0].MP_ISO.analysisPoints[{j}].{k}"] for k in PT_KEYS}
                for g in (0, 1):
                    for k in PT_GEAR:
                        row[f"{k}{g + 1}"] = vals[f"ZPP[{g}].MP_ISO.analysisPoints[{j}].{k}"]
                pts[p] = row
            mp["points"] = pts
            mp["point_keys"] = "ZP[0].MP_ISO.analysisPoints[i].<key>，<dY|vrY|rtY><1|2> = ZPP[0|1].MP_ISO.analysisPoints[i].<key>；i: 0=A … 6=E"
            mp["units"] = {"pHYB": "N/mm2", "phidynYB": "N/mm2", "Theta_flY": "K", "TheBY": "degC", "alpha": "mm2/N",
                           "hY": "um", "ronY": "mm", "dY": "mm", "vrY": "m/s", "vgY": "m/s", "gY": "mm"}
        else:
            mp["valid"] = False
            mp["reason"] = ("NOT CALCULATED：ZS.Oil.FZGtestMP=%s、MicroPittingTest=%s（缺油品微点蚀试验数据）；"
                            "KISSsoft 输出的零值为无效占位，不得使用（RESULTS.txt / review.txt）"
                            % (vals.get("ZS.Oil.FZGtestMP"), vals.get("ZS.Oil.MicroPittingTest")))
        rec["not_available"] = ["-21 θflaE、θMT、θflaintT 独立字段（review.txt FINDINGS 2）",
                                "-20 XJ(Γ)、XΓ(Γ)、θfl(Γ) 分布（review.txt FINDINGS 1）；只有最大点标量"]
        (OUT / f"{case}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(case, "ok", mp["valid"])


if __name__ == "__main__":
    main(sys.argv[1:])
