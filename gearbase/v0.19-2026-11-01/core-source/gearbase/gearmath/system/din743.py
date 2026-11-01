"""DIN 743（2012）轴与心轴承载能力计算：安全系数、疲劳/静强度核算、缺口与尺寸/表面影响系数、等效损伤应力。

资料与核对口径（本机私有 PDF，逐式渲染原图核对；代码中只写条款号、式号、页码，不复制原文）：
  - DIN 743-1:2012-12  英译本（文件 DIN 743-1-2012(E).pdf，25 页扫描），PDF 页 = 印刷页；
  - DIN 743-2:2012-12  德文原版（文件 DIN 743-2 (2012-12-00).pdf，34 页扫描），PDF 页 = 印刷页；
  - DIN 743-3:2012-12  德文原版（文件 DIN 743-3 (2012-12-00).pdf，9 页扫描，首页为勘误提示页），PDF 页 = 印刷页 + 1；
  - DIN 743-4          英译本，页眉印 "DIN 743-4:2012-10"（文件名写 2012(E)），PDF 页 = 印刷页。
本机 PDF 不含 DIN 743 Beiblatt 1/2（算例）：本模块全部公式证据等级为 null（未评估），测试只做独立重写对拍与同页一致性核对。
v0.15 EXTM36：KISSsoft 2026 W010 截面 R1-L1-S1/S2/S3a 同输入逐字段一致的公式另登记 external E5（_ks，口径同 system/_base）；
evidence_level（标准算例口径）仍为 null，覆盖分支写在 external source 中，未覆盖分支不因此提升。

约定：
  - 应力、强度单位 N/mm²；长度 mm；力 N；力矩 N·mm；Rz 单位 µm；均以 float 传入。
  - 全部参数为仅限关键字且无默认值；缺输入（None）抛 MissingInput；越出条文适用域抛 OutOfDomain；
    原图无法确认或条文未覆盖的取值抛 Unconfirmed（阻断，不猜）。
  - 安全系数下限 S_min、表面状态、载荷情形（Case 1/2）、材料曲线等一律由调用方显式给出。
  - 本模块不 import gearmath.gear，也不放在 gearmath/kernel/ 中。
"""
from __future__ import annotations

import math

P1 = "DIN 743-1:2012"
P2 = "DIN 743-2:2012"
P3 = "DIN 743-3:2012"
P4 = "DIN 743-4:2012"
EVIDENCE_NULL_REASON = ("无外部算例：本机 PDF 不含 DIN 743 Beiblatt 1/2；测试仅为独立重写对拍与同页一致性核对（自洽），"
                        "不构成外部参照")

# 公式 id → 元数据（ref、source_check、evidence_level=None、函数名）。只读登记，供 REPORT/注册表核对。
FORMULAS: dict = {}


class Din743Error(ValueError):
    """DIN 743 计算输入/适用域错误。code：missing_input | bad_input | out_of_domain | unconfirmed。"""

    def __init__(self, name, code, message):
        super().__init__(f"{name}：{message}")
        self.name, self.code = name, code


class MissingInput(Din743Error):
    def __init__(self, name):
        super().__init__(name, "missing_input", "缺少输入（DIN 743 计算不设隐式默认）")


class OutOfDomain(Din743Error):
    def __init__(self, name, message):
        super().__init__(name, "out_of_domain", message)


class Unconfirmed(Din743Error):
    def __init__(self, name, message):
        super().__init__(name, "unconfirmed", "无法确认：" + message)


def _formula(fid, ref, note="", external=None):
    """external：KISSsoft 同输入逐字段一致的外部对拍（仅 E5；口径同 system/_base.make_registry，v0.15 EXTM36 起）。
    evidence_level 保持标准算例口径（null）；evidence_level_effective = 两者取高。"""
    if "原图已核" not in ref:
        raise AssertionError(f"{fid} 的 ref 必须注明原图已核")
    if external is not None:
        src, tst = external.get("source") or "", external.get("test") or ""
        if external.get("level") != "E5" or "KISSsoft" not in src or "sha256" not in src or "::" not in tst:
            raise AssertionError(f"{fid}：external 仅允许 E5（KISSsoft 同输入逐字段一致），source 须含 KISSsoft 与 sha256，test 为 path::Class")

    def deco(fn):
        meta = {"id": fid, "ref": ref, "note": note, "source_check": "pdf_image_checked",
                "evidence_level": None, "evidence_level_null_reason": EVIDENCE_NULL_REASON,
                "external_evidence_level": external["level"] if external else None,
                "external_evidence_source": external["source"] if external else None,
                "external_evidence_test": external["test"] if external else None,
                "evidence_level_effective": "E5" if external else None}
        fn.REF = meta
        if fid in FORMULAS:
            raise AssertionError(f"公式 id 重复：{fid}")
        FORMULAS[fid] = dict(meta, function=fn.__name__)
        return fn
    return deco


_KS_TEST = "tests/test_m36_kisssoft_v015.py::TestDin743KISSsoft"
_KS_SHA = {"S1": "bd76c7edd772", "S2": "3308205a9c54", "S3a": "6fe5aeed95ea"}


def _ks(cover, *secs):
    """KISSsoft R1 L1（集中力）截面同输入逐字段一致 → external E5。cover：本次对拍覆盖的分支/取值范围（未覆盖分支不因此提升）。"""
    return {"level": "E5", "test": _KS_TEST,
            "source": "KISSsoft Release 2026 W010 DIN 743:2012 截面 " + "、".join(f"R1-L1-{s}（W10 sha256 {_KS_SHA[s]}…）" for s in secs)
                      + f"；提取件 data/kisssoft_v015/R1-L1-*.json；覆盖：{cover}"}


# ------------------------------------------------------------------ 输入校验
def _num(name, v):
    if v is None:
        raise MissingInput(name)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise Din743Error(name, "bad_input", f"应为数值，收到 {type(v).__name__}")
    v = float(v)
    if not math.isfinite(v):
        raise Din743Error(name, "bad_input", "应为有限数值")
    return v


def _pos(name, v):
    v = _num(name, v)
    if v <= 0:
        raise OutOfDomain(name, f"须 > 0，收到 {v}")
    return v


def _nonneg(name, v):
    v = _num(name, v)
    if v < 0:
        raise OutOfDomain(name, f"须 ≥ 0，收到 {v}")
    return v


def _flag(name, v):
    if v is None:
        raise MissingInput(name)
    if not isinstance(v, bool):
        raise Din743Error(name, "bad_input", "应为 True/False")
    return v


def _choice(name, v, options):
    if v is None:
        raise MissingInput(name)
    if v not in options:
        raise Din743Error(name, "bad_input", f"应为 {sorted(options)} 之一，收到 {v!r}")
    return v


def _range(name, v, lo, hi, lo_incl=True, hi_incl=True, why=""):
    ok_lo = v >= lo if lo_incl else v > lo
    ok_hi = v <= hi if hi_incl else v < hi
    if not (ok_lo and ok_hi):
        raise OutOfDomain(name, f"{v} 不在 {'[' if lo_incl else '('}{lo}, {hi}{']' if hi_incl else ')'}{('（' + why + '）') if why else ''}")
    return v


_DIRECT = ("zd", "b")
_KINDS = ("zd", "b", "t")


# =================================================================== DIN 743-1
@_formula("din743_1.eq1", f"{P1} 4.1 式(1) S ≥ S_min，方法要求 S_min = 1,2（PDF9/印9 原图已核）；5.1 静强度同（PDF14/印14 原图已核）",
          note="S_min < 1,2 视为越出方法前提而阻断；S_min 本身须由调用方约定给出")
def check_safety(*, S, S_min):
    """返回 S ≥ S_min（布尔）。S_min 必须显式给出且 ≥ 1,2。"""
    S = _pos("S", S)
    S_min = _num("S_min", S_min)
    if S_min < 1.2:
        raise OutOfDomain("S_min", "DIN 743-1 4.1/5.1 方法本身要求 S_min ≥ 1,2")
    return S >= S_min


@_formula("din743_1.table1.section", f"{P1} 4.2 表1 截面面积与截面模量 A、W_b、W_t（PDF10/印10 原图已核）；表4 同（PDF18/印18 原图已核）",
          external=_ks("实心圆截面 d = 25/30/34 mm", "S1", "S2", "S3a"))
def section_properties(*, d, d_i):
    """圆截面/空心圆截面：A = π/4·(d²−d_i²)，W_b = π/32·(d⁴−d_i⁴)/d，W_t = π/16·(d⁴−d_i⁴)/d。实心轴须显式给 d_i = 0。"""
    d = _pos("d", d)
    d_i = _nonneg("d_i", d_i)
    if d_i >= d:
        raise OutOfDomain("d_i", "内径须小于外径")
    return {"A": math.pi / 4 * (d ** 2 - d_i ** 2),
            "W_b": math.pi / 32 * (d ** 4 - d_i ** 4) / d,
            "W_t": math.pi / 16 * (d ** 4 - d_i ** 4) / d}


@_formula("din743_1.table1.stress", f"{P1} 4.2 表1 工作应力幅与平均值（受压区平均值为负，见表注；PDF10/印10 原图已核）",
          external=_ks("弯曲幅值、扭转平均值（同 Mb、T 输入）", "S1", "S2", "S3a"))
def working_stresses(*, d, d_i, F_zda, F_zdm, M_ba, M_bm, M_ta, M_tm):
    """名义应力（N/mm²）：幅值 = 载荷幅/截面量，平均值 = 平均载荷/截面量。幅值须 ≥ 0，平均值可为负（受压）。"""
    s = section_properties(d=d, d_i=d_i)
    F_zda, M_ba, M_ta = _nonneg("F_zda", F_zda), _nonneg("M_ba", M_ba), _nonneg("M_ta", M_ta)
    F_zdm, M_bm, M_tm = _num("F_zdm", F_zdm), _num("M_bm", M_bm), _num("M_tm", M_tm)
    return {"sigma_zda": F_zda / s["A"], "sigma_zdm": F_zdm / s["A"],
            "sigma_ba": M_ba / s["W_b"], "sigma_bm": M_bm / s["W_b"],
            "tau_ta": M_ta / s["W_t"], "tau_tm": M_tm / s["W_t"]}


@_formula("din743_1.table4.stress", f"{P1} 5.4 表4 最大名义应力（PDF18/印18 原图已核）；压应力在式(25)中取负号（5.1.1，PDF15/印15）",
          external=_ks("σbmax、τtmax（最大载荷系数 2,0 显式乘入载荷）", "S1", "S2", "S3a"))
def maximum_stresses(*, d, d_i, F_zdmax, M_bmax, M_tmax):
    s = section_properties(d=d, d_i=d_i)
    return {"sigma_zdmax": _num("F_zdmax", F_zdmax) / s["A"],
            "sigma_bmax": _num("M_bmax", M_bmax) / s["W_b"],
            "tau_tmax": _num("M_tmax", M_tmax) / s["W_t"]}


@_formula("din743_1.eq2", f"{P1} 4.1 式(2) 拉压+弯曲+扭转合成疲劳安全系数（同相位假定；PDF9/印9 原图已核）",
          external=_ks("弯曲+扭转（扭转幅值 0）", "S1", "S2"))
def safety_fatigue(*, sigma_zda, sigma_zdADK, sigma_ba, sigma_bADK, tau_ta, tau_tADK):
    """S = 1/√((σzda/σzdADK + σba/σbADK)² + (τta/τtADK)²)。六个量都须给出；幅值 ≥ 0，可承受幅值 > 0。"""
    a1, a2, a3 = _nonneg("sigma_zda", sigma_zda), _nonneg("sigma_ba", sigma_ba), _nonneg("tau_ta", tau_ta)
    A1, A2, A3 = _pos("sigma_zdADK", sigma_zdADK), _pos("sigma_bADK", sigma_bADK), _pos("tau_tADK", tau_tADK)
    den = math.sqrt((a1 / A1 + a2 / A2) ** 2 + (a3 / A3) ** 2)
    if den == 0:
        raise OutOfDomain("amplitudes", "全部应力幅为 0，安全系数无定义")
    return 1.0 / den


@_formula("din743_1.eq3_4", f"{P1} 4.1 式(3)(4) 单一应力 S = σADK/σa（式(3) 对拉压同样适用，PDF9–10/印9–10 原图已核）")
def safety_fatigue_single(*, amplitude, ADK):
    return _pos("ADK", ADK) / _pos("amplitude", amplitude)


@_formula("din743_1.eq5_7", f"{P1} 4.3 式(5)(6)(7) 零件交变疲劳极限 σzdWK、σbWK、τtWK = W(d_B)·K1(d_eff)/K（PDF11/印11 原图已核）",
          external=_ks("拉压/弯曲/扭转三类，轴肩与光轴", "S1", "S2", "S3a"))
def component_fatigue_limit(*, kind, W_dB, K1_deff, K):
    """kind：'zd'（式5）、'b'（式6）、't'（式7）。W_dB 为试棒直径 d_B 下材料交变疲劳极限（DIN 743-3），
    K1_deff 为抗拉强度的技术尺寸系数（DIN 743-2 式(10)–(14)，见 743-1 脚注2），K 为综合影响系数（式8/9）。"""
    _choice("kind", kind, _KINDS)
    return _pos("W_dB", W_dB) * _pos("K1_deff", K1_deff) / _pos("K", K)


@_formula("din743_1.eq8_9", f"{P1} 4.3 式(8)(9) 综合影响系数 Kσ、Kτ = (β/K2(d) + 1/KF − 1)·1/KV（PDF11/印11 原图已核；附录B 图B.2 PDF24 同式）",
          external=_ks("σ、τ 两式，KV = 1", "S1", "S2", "S3a"))
def total_influence_factor(*, kind, beta, K2_d, K_F, K_V):
    """kind：'sigma'（拉压/弯曲，式8）或 'tau'（扭转，式9）。"""
    _choice("kind", kind, ("sigma", "tau"))
    beta, K2_d, K_F, K_V = _pos("beta", beta), _pos("K2_d", K2_d), _pos("K_F", K_F), _pos("K_V", K_V)
    K = (beta / K2_d + 1.0 / K_F - 1.0) / K_V
    if K <= 0:
        raise OutOfDomain("K", f"综合影响系数 {K} ≤ 0，输入组合不合理")
    return K


@_formula("din743_1.eq20_22", f"{P1} 4.3 式(20)(21)(22) 平均应力敏感系数 ψ = WK/(2·K1(d_eff)·σB(d_B) − WK)（PDF14/印14 原图已核）",
          external=_ks("三类", "S1", "S2", "S3a"))
def mean_stress_sensitivity(*, kind, WK, K1_deff, sigma_B_dB):
    """kind：'zd'（式20）、'b'（式21）、't'（式22）；WK 为对应的 σzdWK/σbWK/τtWK。"""
    _choice("kind", kind, _KINDS)
    WK, K1, sB = _pos("WK", WK), _pos("K1_deff", K1_deff), _pos("sigma_B_dB", sigma_B_dB)
    den = 2.0 * K1 * sB - WK
    if den <= 0:
        raise OutOfDomain("WK", "2·K1·σB − WK ≤ 0，式(20)–(22) 无意义")
    return WK / den


@_formula("din743_1.eq23_24", f"{P1} 4.3 式(23)(24) 等效平均应力 σmv、τmv；σzdm+σbm<0 时以 H 式代替式(23)，σmv<0 时 τmv=0"
          "（PDF12–14/印12–14 原图已核）",
          external=_ks("式(23) 分支（σzdm+σbm ≥ 0），含 τtm > 0；H 分支未覆盖", "S1", "S2", "S3a"))
def equivalent_mean_stresses(*, sigma_zdm, sigma_bm, tau_tm):
    """返回 {"sigma_mv", "tau_mv", "branch"}。
    σzdm+σbm ≥ 0：σmv = √((σzdm+σbm)² + 3τtm²)（式23）；
    σzdm+σbm < 0：H = (σbm+σzdm)³/|σbm+σzdm| + 3τtm²，σmv = H/|H|·√|H|；
    τmv = σmv/√3（式24），σmv < 0 时 τmv = 0。"""
    s = _num("sigma_zdm", sigma_zdm) + _num("sigma_bm", sigma_bm)
    t = _num("tau_tm", tau_tm)
    if s >= 0:
        smv, branch = math.sqrt(s ** 2 + 3.0 * t ** 2), "eq23"
    else:
        H = s ** 3 / abs(s) + 3.0 * t ** 2
        smv = 0.0 if H == 0 else H / abs(H) * math.sqrt(abs(H))
        branch = "H"
    tmv = 0.0 if smv < 0 else smv / math.sqrt(3.0)
    return {"sigma_mv": smv, "tau_mv": tmv, "branch": branch}


@_formula("din743_1.eq10_19_tabA1", f"{P1} 4.3 式(10)–(14)（Case 1，PDF12/印12）、式(15)–(19)（Case 2，PDF13/印13）、"
          "式(15)–(17) 适用条件（PDF14/印14）、附录A 表A.1 受压区（PDF21/印21）原图已核",
          note="Case 1/2 由调用方显式选择（标准：存疑且 σzdm+σbm ≥ 0 时可按 Case 2，PDF12）；"
               "表A.1 的 σdFK 须显式给出（表注允许以 σzdFK 代用，本库不自动代用）",
          external=_ks("Case 1 式(10)(11)(12) 分支（σmv ≤ 极限）；式(13)(14)、表A.1、Case 2 未覆盖", "S1", "S2", "S3a"))
def endurable_amplitude(*, load_case, kind, WK, FK, psi, mv, amplitude, sigma_dFK, sigma_B_d):
    """可承受应力幅 σzdADK / σbADK / τtADK。返回 {"ADK", "branch"}。

    load_case：1（σmv 恒定）或 2（σmv/σa 恒定）；kind：'zd'、'b'、't'。
    WK：零件交变疲劳极限（式5–7）；FK：零件屈服点（式31/32）；psi：式(20)–(22)；
    mv：σmv（直接应力）或 τmv（扭转）；amplitude：本应力类型的现有幅值（Case 2 必需且 > 0；Case 1 不参与计算，须显式传值或 None）；
    sigma_dFK、sigma_B_d：直接应力（zd、b）的受压区表A.1 所需，扭转须显式传 None。
    """
    lc = _choice("load_case", load_case, (1, 2))
    _choice("kind", kind, _KINDS)
    WK, FK, psi = _pos("WK", WK), _pos("FK", FK), _nonneg("psi", psi)
    mv = _num("mv", mv)
    if psi >= 1:
        raise OutOfDomain("psi", "ψ ≥ 1：Case 1/2 条件式分母不为正")
    direct = kind in _DIRECT
    if direct:
        dFK, sBd = _pos("sigma_dFK", sigma_dFK), _pos("sigma_B_d", sigma_B_d)
    else:
        if sigma_dFK is not None or sigma_B_d is not None:
            raise Din743Error("sigma_dFK", "bad_input", "扭转不适用表A.1，sigma_dFK/sigma_B_d 须为 None")
        if mv < 0:
            raise OutOfDomain("mv", "τmv 按式(24) 不为负")
    if lc == 1:
        if amplitude is not None:
            _nonneg("amplitude", amplitude)
        if direct:
            grenz = (WK - dFK) * (1.0 - WK / (2.0 * sBd))           # 表A.1 Case 1
            if mv < grenz:
                return {"ADK": mv + dFK, "branch": "tabA1.case1"}
        lim = (FK - WK) / (1.0 - psi)
        if mv <= lim:
            return {"ADK": WK - psi * mv, "branch": "eq11" if kind == "b" else ("eq10" if kind == "zd" else "eq12")}
        return {"ADK": FK - mv, "branch": "eq13" if direct else "eq14"}
    a = _pos("amplitude", amplitude)
    r = mv / a
    if direct:
        grenz2 = (WK - dFK) / (psi * dFK + WK)                       # 表A.1 Case 2
        if not r > grenz2:
            if a - mv <= 0:
                raise OutOfDomain("mv", "表A.1 Case 2 要求 σzd,ba − σmv > 0")
            return {"ADK": dFK * a / (a - mv), "branch": "tabA1.case2"}
    den = WK - FK * psi
    if den <= 0:
        raise Unconfirmed("psi", "Case 2 条件式分母 WK − FK·ψ ≤ 0，标准未给出此情形的处理")
    if r <= (FK - WK) / den:
        return {"ADK": WK / (1.0 + psi * r), "branch": {"zd": "eq15", "b": "eq16", "t": "eq17"}[kind]}
    return {"ADK": FK / (1.0 + r), "branch": "eq18" if direct else "eq19"}


@_formula("din743_1.eq31_32", f"{P1} 5.2 式(31)(32) 零件屈服点 σzd,bFK = K1(d_eff)·K2F·γF·σS(d_B)，τtFK = …/√3（PDF16/印16 原图已核）",
          note="此处 K1(d_eff) 为屈服强度用技术尺寸系数（PDF17 说明）",
          external=_ks("三类，K1(σS) 按调质钢曲线式(14)", "S1", "S2", "S3a"))
def component_yield_point(*, kind, K1_deff, K2F, gamma_F, sigma_S_dB):
    _choice("kind", kind, _KINDS)
    v = _pos("K1_deff", K1_deff) * _pos("K2F", K2F) * _pos("gamma_F", gamma_F) * _pos("sigma_S_dB", sigma_S_dB)
    return v / math.sqrt(3.0) if kind == "t" else v


@_formula("din743_1.table2", f"{P1} 5.2 表2 屈服点提高系数 γF（无硬化表层、环向缺口；PDF17/印17 原图已核）",
          note="表中区间端点 1,5 / 2,0 / 3,0 在相邻两行同时出现，端点归属无法确认 → 恰在端点时阻断",
          external=_ks("环向缺口 1,5 < α < 3,0 行 γF = 1,10（拉压/弯曲）、扭转与无缺口 γF = 1", "S1", "S2", "S3a"))
def gamma_F(*, kind, alpha_or_beta, hard_surface, circumferential_notch):
    _choice("kind", kind, _KINDS)
    hard, notch = _flag("hard_surface", hard_surface), _flag("circumferential_notch", circumferential_notch)
    x = _num("alpha_or_beta", alpha_or_beta)
    if x < 1:
        raise OutOfDomain("alpha_or_beta", "须 ≥ 1")
    if hard or not notch or kind == "t":
        return 1.0                                                  # PDF17：硬表层或无环向缺口 γF=1；扭转 Any → 1
    if x in (1.5, 2.0, 3.0):
        raise Unconfirmed("alpha_or_beta", f"表2 区间端点 {x} 同属相邻两行，归属不明")
    if x < 1.5:
        return 1.00
    if x < 2.0:
        return 1.05
    if x < 3.0:
        return 1.10
    return 1.15


@_formula("din743_1.table3", f"{P1} 5.2 表3 静支撑系数 K2F（无硬化表层；硬表层 K2F=1 见 PDF17 说明；PDF17/印17 原图已核）",
          external=_ks("实心、无硬化表层", "S1", "S2", "S3a"))
def K2F(*, kind, hollow, hard_surface):
    _choice("kind", kind, _KINDS)
    hollow, hard = _flag("hollow", hollow), _flag("hard_surface", hard_surface)
    if hard:
        return 1.0
    return {("zd", False): 1.0, ("zd", True): 1.0, ("b", False): 1.2, ("b", True): 1.1,
            ("t", False): 1.2, ("t", True): 1.0}[(kind, hollow)]


@_formula("din743_1.eq25", f"{P1} 5.1.1 式(25) 防永久变形合成安全系数（压应力取负；PDF15/印15 原图已核）",
          external=_ks("纯弯、弯+扭、纯扭", "S1", "S2", "S3a"))
def safety_static(*, sigma_zdmax, sigma_zdFK, sigma_bmax, sigma_bFK, tau_tmax, tau_tFK):
    x = _num("sigma_zdmax", sigma_zdmax) / _pos("sigma_zdFK", sigma_zdFK) + _num("sigma_bmax", sigma_bmax) / _pos("sigma_bFK", sigma_bFK)
    y = _num("tau_tmax", tau_tmax) / _pos("tau_tFK", tau_tFK)
    den = math.sqrt(x ** 2 + y ** 2)
    if den == 0:
        raise OutOfDomain("max_stresses", "最大应力全为 0，安全系数无定义")
    return 1.0 / den


@_formula("din743_1.eq26_27", f"{P1} 5.1.1 式(26)(27) 单一应力 S = FK/σmax（式26 对拉压同样适用；PDF15/印15 原图已核）",
          note="式(26)(27) 未写符号处理；本库取 |σmax|（式(25) 中单项平方后与此一致），属本库口径")
def safety_static_single(*, max_stress, FK):
    """单一应力类型时 |σmax| 与 FK 之比（压应力以绝对值计）。"""
    m = _num("max_stress", max_stress)
    if m == 0:
        raise OutOfDomain("max_stress", "须非零")
    return _pos("FK", FK) / abs(m)


@_formula("din743_1.eq28", f"{P1} 5.1.2 式(28) 硬表层防初始裂纹/过载断裂（正应力理论，局部应力；PDF16/印16 原图已核）")
def safety_incipient_crack(*, alpha_zd, sigma_zdmax, sigma_zdBRand, alpha_b, sigma_bmax, sigma_bBRand,
                           alpha_t, tau_tmax, tau_tBRand):
    """S = 1/(0,5·[x + √(x² + y²)])，x = ασzd·σzdmax/σzdBRand + ασb·σbmax/σbBRand，y = 2·ατ·τtmax/τtBRand。"""
    x = (_pos("alpha_zd", alpha_zd) * _num("sigma_zdmax", sigma_zdmax) / _pos("sigma_zdBRand", sigma_zdBRand)
         + _pos("alpha_b", alpha_b) * _num("sigma_bmax", sigma_bmax) / _pos("sigma_bBRand", sigma_bBRand))
    y = 2.0 * _pos("alpha_t", alpha_t) * _num("tau_tmax", tau_tmax) / _pos("tau_tBRand", tau_tBRand)
    den = 0.5 * (x + math.sqrt(x ** 2 + y ** 2))
    if den <= 0:
        raise OutOfDomain("stresses", "式(28) 分母 ≤ 0（无拉伸主应力），安全系数无定义")
    return 1.0 / den


@_formula("din743_1.eq29_30", f"{P1} 5.1.2 式(29)(30) 单一应力 S = BRand/(σmax·α)（式29 对拉压同样适用；PDF16/印16 原图已核）")
def safety_incipient_crack_single(*, max_stress, alpha, BRand):
    return _pos("BRand", BRand) / (_pos("max_stress", max_stress) * _pos("alpha", alpha))


@_formula("din743_1.eq33_34", f"{P1} 5.3 式(33)(34) σzd,bBRand = σBRand，τtBRand = σBRand（PDF17/印17 原图已核）",
          note="式(34) 原图即 τtBRand = σBRand（与式(28) 中 2·ατ·τ 的正应力理论写法一致），照录")
def crack_limits(*, sigma_BRand):
    s = _pos("sigma_BRand", sigma_BRand)
    return {"sigma_zdBRand": s, "sigma_bBRand": s, "tau_tBRand": s}


def fatigue_proof(*, load_case, S_min, sigma_zda, sigma_zdm, sigma_ba, sigma_bm, tau_ta, tau_tm,
                  sigma_zdW_dB, sigma_bW_dB, tau_tW_dB, sigma_B_dB, sigma_B_d, K1_deff,
                  K_sigma_zd, K_sigma_b, K_tau, sigma_zdFK, sigma_bFK, tau_tFK, sigma_dFK):
    """DIN 743-1 第4章疲劳核算主流程（附录B 图B.1 左支，PDF22/印22 原图已核）：
    式(23)(24) → 式(5)–(7) → 式(20)–(22) → 式(10)–(19)/表A.1 → 式(2) → 式(1)。全部输入必需。
    K1_deff 为抗拉强度的技术尺寸系数；sigma_B_d 为表A.1 用 σB(d)（不自动取 K1·σB(d_B)）。"""
    mv = equivalent_mean_stresses(sigma_zdm=sigma_zdm, sigma_bm=sigma_bm, tau_tm=tau_tm)
    amps = {"zd": sigma_zda, "b": sigma_ba, "t": tau_ta}
    Wd = {"zd": sigma_zdW_dB, "b": sigma_bW_dB, "t": tau_tW_dB}
    Ks = {"zd": K_sigma_zd, "b": K_sigma_b, "t": K_tau}
    FKs = {"zd": sigma_zdFK, "b": sigma_bFK, "t": tau_tFK}
    out = {"sigma_mv": mv["sigma_mv"], "tau_mv": mv["tau_mv"], "mean_branch": mv["branch"]}
    ADK = {}
    for k in _KINDS:
        WK = component_fatigue_limit(kind=k, W_dB=Wd[k], K1_deff=K1_deff, K=Ks[k])
        psi = mean_stress_sensitivity(kind=k, WK=WK, K1_deff=K1_deff, sigma_B_dB=sigma_B_dB)
        a = _nonneg(f"amplitude_{k}", amps[k])
        m = mv["tau_mv"] if k == "t" else mv["sigma_mv"]
        if load_case == 2 and a == 0:
            # Case 2 中 σmv/σa 对零幅值无定义；零幅值对式(2) 无贡献，此处不求该 ADK（不是默认值，式(2) 项恒为 0）
            out[f"{k}"] = {"WK": WK, "psi": psi, "ADK": None, "branch": "zero_amplitude"}
            continue
        r = endurable_amplitude(load_case=load_case, kind=k, WK=WK, FK=FKs[k], psi=psi, mv=m,
                                amplitude=a if load_case == 2 else None,
                                sigma_dFK=sigma_dFK if k in _DIRECT else None,
                                sigma_B_d=sigma_B_d if k in _DIRECT else None)
        ADK[k] = r["ADK"]
        out[f"{k}"] = {"WK": WK, "psi": psi, "ADK": r["ADK"], "branch": r["branch"]}
    terms_s = sum(_nonneg(f"amplitude_{k}", amps[k]) / ADK[k] for k in _DIRECT if k in ADK)
    term_t = (_nonneg("tau_ta", tau_ta) / ADK["t"]) if "t" in ADK else 0.0
    den = math.sqrt(terms_s ** 2 + term_t ** 2)
    if den == 0:
        raise OutOfDomain("amplitudes", "全部应力幅为 0，安全系数无定义")
    S = 1.0 / den
    out.update({"S": S, "S_min": S_min, "ok": check_safety(S=S, S_min=S_min),
                "ref": f"{P1} 附录B 图B.1（PDF22/印22 原图已核）；各步见 FORMULAS"})
    return out


# =================================================================== DIN 743-2（德文原版）
@_formula("din743_2.eq3", f"{P2} 4.2 式(3) β(d) = β(d_BK)·K3(d_BK)/K3(d)（拉压、弯曲、扭转同；PDF6/印6 原图已核）")
def beta_size_transfer(*, beta_dBK, K3_dBK, K3_d):
    return _pos("beta_dBK", beta_dBK) * _pos("K3_dBK", K3_dBK) / _pos("K3_d", K3_d)


def _sigma_B_chart(sigma_B_d, why):
    return _range("sigma_B_d", _pos("sigma_B_d", sigma_B_d), 400.0, 1200.0, why=why)


@_formula("din743_2.table1.keyway", f"{P2} 4.2.1 表1 平键（Passfeder）βσ(d_BK) ≈ 3,0·(σB(d)/1000)^0,38，βτ ≈ 0,56·βσ + 0,1，"
          "两键 ×1,15，d_BK = 40 mm，KFσ=KFτ=1（PDF7/印7 原图已核）",
          note="σB(d) 限于表列 400–1200 N/mm²（表值为近似式依据；超出范围阻断）；两键系数按'βσ,τ 乘 1,15'施于两者")
def beta_keyway(*, sigma_B_d, n_keys):
    sB = _sigma_B_chart(sigma_B_d, "表1 列值范围")
    n = _choice("n_keys", n_keys, (1, 2))
    bs = 3.0 * (sB / 1000.0) ** 0.38
    bt = 0.56 * bs + 0.1
    f = 1.15 if n == 2 else 1.0
    return {"beta_sigma_dBK": f * bs, "beta_tau_dBK": f * bt, "d_BK": 40.0}


@_formula("din743_2.table1.pressfit", f"{P2} 4.2.1 表1 压配合（Presssitz）β(d_BK) ≈ 2,7·(σB(d)/1000)^0,43，βτ ≈ 0,65·βσ，d_BK = 40 mm"
          "（PDF7/印7 原图已核）",
          note="原图该近似式左侧符号印作 βτ(d_BK)，但位于 βσ 行，且其数值与同页 βσ 行表值一致（400→1,8 … 1200→2,9），"
               "故按 βσ 实现；此为原文排印疑点，已在 REPORT 列出")
def beta_press_fit(*, sigma_B_d):
    sB = _sigma_B_chart(sigma_B_d, "表1 列值范围")
    bs = 2.7 * (sB / 1000.0) ** 0.43
    return {"beta_sigma_dBK": bs, "beta_tau_dBK": 0.65 * bs, "d_BK": 40.0}


@_formula("din743_2.4_2_2.spline", f"{P2} 4.2.2 花键/细齿/渐开线花键轴 βτ*(d_BK) = exp(4,2·10⁻⁷·(σB(d))²) 及各型式线性式，d_BK = 29 mm"
          "（PDF8–9/印8–9 原图已核）",
          note="σB(d) 限于图1 范围 400–1200 N/mm²；不含毂影响（PDF8）；渗碳淬火时 β=1、KV=1（PDF9）由调用方处理")
def beta_spline(*, profile, sigma_B_d):
    """profile：'keilwelle'（矩形花键）、'kerbzahnwelle'（细齿花键）、'evolvente'（渐开线花键）。"""
    p = _choice("profile", profile, ("keilwelle", "kerbzahnwelle", "evolvente"))
    sB = _sigma_B_chart(sigma_B_d, "图1 横轴范围")
    bstar = math.exp(4.2e-7 * sB ** 2)
    bt = bstar if p in ("keilwelle", "kerbzahnwelle") else 1.0 + 0.75 * (bstar - 1.0)
    bs = 1.0 + {"keilwelle": 0.45, "kerbzahnwelle": 0.65, "evolvente": 0.49}[p] * (bstar - 1.0)
    return {"beta_tau_star": bstar, "beta_sigma_dBK": bs, "beta_tau_dBK": bt, "d_BK": 29.0}


@_formula("din743_2.4_2_3.vnotch", f"{P2} 4.2.3 环向尖角缺口 βσ(d_BK)=0,109·σB/100+1,074（拉压）、0,0923·σB/100+0,985（弯曲）、"
          "βτ=0,80·βσ弯曲，d_BK=15 mm，r=0,1 mm，Rz_B=20 µm，t/d=0,05–0,20（PDF10–11/印10–11 原图已核）",
          note="σB(d) 限于图2 范围 400–1200 N/mm²")
def beta_v_notch(*, sigma_B_d, t_over_d):
    sB = _sigma_B_chart(sigma_B_d, "图2 横轴范围")
    _range("t_over_d", _pos("t_over_d", t_over_d), 0.05, 0.20, why="PDF11：其它值时缺口系数偏离")
    bz = 0.109 * sB / 100.0 + 1.074
    bb = 0.0923 * sB / 100.0 + 0.985
    return {"beta_sigma_zd_dBK": bz, "beta_sigma_b_dBK": bb, "beta_tau_dBK": 0.80 * bb, "d_BK": 15.0}


@_formula("din743_2.4_2_4.rho_star", f"{P2} 4.2.4 结构半径 ρ* = 10^−(0,514 + 0,00152·σS(d)) mm（钢；PDF12/印12 原图已核）",
          note="σS(d) 限于图3 范围 200–800 N/mm²")
def rect_groove_rho_star(*, sigma_S_d):
    sS = _range("sigma_S_d", _pos("sigma_S_d", sigma_S_d), 200.0, 800.0, why="图3 横轴范围")
    return 10.0 ** (-(0.514 + 0.00152 * sS))


@_formula("din743_2.4_2_4.beta_star", f"{P2} 4.2.4 矩形环槽 βσ*(d_BK)=0,9·(1,27+1,17√(t/r_f))（拉压）、0,9·(1,14+1,08√(t/r_f))（弯曲）"
          "（PDF11/印11 原图已核）；扭转 β*=1,48+0,45√(t/r_f)（PDF12/印12 原图已核，左侧下标印作 r，按'Torsion'行读）；"
          "r_f = r + 2,9ρ*（拉压、弯曲）/ r + ρ*（扭转）；d_BK=30 mm，Rz_B=20 µm（PDF12）")
def rect_groove_beta_star(*, kind, t, r, sigma_S_d):
    k = _choice("kind", kind, _KINDS)
    t, r = _pos("t", t), _nonneg("r", r)
    rho = rect_groove_rho_star(sigma_S_d=sigma_S_d)
    rf = r + (rho if k == "t" else 2.9 * rho)
    q = math.sqrt(t / rf)
    b = {"zd": 0.9 * (1.27 + 1.17 * q), "b": 0.9 * (1.14 + 1.08 * q), "t": 1.48 + 0.45 * q}[k]
    return {"beta_star": b, "r_f": rf, "rho_star": rho, "d_BK": 30.0}


@_formula("din743_2.4_2_4.mt", f"{P2} 4.2.4 m/t ≥ 1,4 时系数 1；m/t < 1,4 时系数 1,08·(m/t)^−0,2（PDF12/印12 原图已核）",
          note="原图符号为 'ßG,τ(d_BK) = ßG,τ*(d_BK)·…'，下标 G 是否即 σ 无法确认；本函数只给出系数本身，"
               "不自动与 β* 合成，由调用方在确认后相乘")
def rect_groove_mt_factor(*, m, t):
    ratio = _pos("m", m) / _pos("t", t)
    return 1.0 if ratio >= 1.4 else 1.08 * ratio ** (-0.2)


@_formula("din743_2.4_2_4.cap", f"{P2} 4.2.4 图3 注：拉压/弯曲 βσ>4 时取 4，扭转 βτ>2,5 时取 2,5（PDF11/印11 原图已核）")
def rect_groove_cap(*, kind, beta):
    k = _choice("kind", kind, _KINDS)
    b = _pos("beta", beta)
    return min(b, 2.5 if k == "t" else 4.0)


@_formula("din743_2.eq4_6", f"{P2} 4.3.1 式(4)(5)(6) Stieler 法 β = α/n，n = 1+√(G'·mm)·10^−(0,33+σS(d)/712)（调质/正火等）或 "
          "1+√(G'·mm)·10^−0,7（硬表层）（PDF12/印12 原图已核）；图4 注1 n ≤ α（PDF13/印13 原图已核）",
          external=_ks("式(5)（非硬化表层），n < α", "S1"))
def beta_from_alpha(*, alpha, G_prime, sigma_S_d, hard_surface):
    """G_prime 单位 1/mm；hard_surface=True 用式(6)（此时 sigma_S_d 须显式传 None）。返回 {"n", "beta"}。"""
    a = _pos("alpha", alpha)
    G = _nonneg("G_prime", G_prime)
    if _flag("hard_surface", hard_surface):
        if sigma_S_d is not None:
            raise Din743Error("sigma_S_d", "bad_input", "式(6) 不用 σS，须为 None")
        n = 1.0 + math.sqrt(G) * 10.0 ** (-0.7)
    else:
        n = 1.0 + math.sqrt(G) * 10.0 ** (-(0.33 + _pos("sigma_S_d", sigma_S_d) / 712.0))
    n = min(n, a)                                                    # 图4 注1：n > α 时 n = α
    return {"n": n, "beta": a / n}


@_formula("din743_2.table2", f"{P2} 4.3.1 表2 相对应力梯度 G'：环槽 2(1+φ)/r、2(1+φ)/r、1/r；轴肩 2,3(1+φ)/r、2,3(1+φ)/r、1,15/r；"
          "d/D > 0,67 且 r > 0 时 φ = 1/(4√(t/r)+2)，否则 φ = 0（PDF14/印14 原图已核）",
          external=_ks("轴肩（absatz），d/D > 0,67 的 φ 分支", "S1"))
def stress_gradient(*, form, kind, r, t, d, D):
    f = _choice("form", form, ("rundnut", "absatz"))
    k = _choice("kind", kind, _KINDS)
    r, t, d, D = _pos("r", r), _pos("t", t), _pos("d", d), _pos("D", D)
    phi = 1.0 / (4.0 * math.sqrt(t / r) + 2.0) if d / D > 0.67 else 0.0
    c = {"rundnut": (2.0, 1.0), "absatz": (2.3, 1.15)}[f]
    return (c[0] * (1.0 + phi) / r) if k in _DIRECT else (c[1] / r)


_TABLE3 = {  # (form, kind) → (A, B, C, z)；C、z 原表为 '-' → 该项不存在
    ("rundnut", "zd"): (0.22, 1.37, None, None), ("rundnut", "b"): (0.2, 2.75, None, None),
    ("rundnut", "t"): (0.7, 10.3, None, None), ("absatz", "zd"): (0.62, 3.5, None, None),
    ("absatz", "b"): (0.62, 5.8, 0.2, 3.0), ("absatz", "t"): (3.4, 19.0, 1.0, 2.0)}


@_formula("din743_2.eq9", f"{P2} 5.2.1 式(9) 及表3 常数 A、B、C、z；适用 r/t ≥ 0,03、d/D ≤ 0,98、α ≤ 6（PDF15/印15 原图已核）；"
          "5.2.2 带退刀槽轴肩按轴肩常数、尺寸按图11（PDF22/印22 原图已核）",
          note="表3 中 C、z 为 '-' 的情形按该项不存在计算（同页文字：C、z 仅对轴肩弯曲/扭转已知）",
          external=_ks("轴肩三类（C、z 项仅弯曲/扭转）", "S1"))
def alpha_groove_shoulder(*, form, kind, r, t, d, D):
    f = _choice("form", form, ("rundnut", "absatz"))
    k = _choice("kind", kind, _KINDS)
    r, t, d, D = _pos("r", r), _pos("t", t), _pos("d", d), _pos("D", D)
    if r / t < 0.03:
        raise OutOfDomain("r/t", "式(9) 要求 r/t ≥ 0,03")
    if d / D > 0.98:
        raise OutOfDomain("d/D", "式(9) 要求 d/D ≤ 0,98")
    A, B, C, z = _TABLE3[(f, k)]
    s = A * r / t + 2.0 * B * r / d * (1.0 + 2.0 * r / d) ** 2
    if C is not None:
        s += C * (r / t) ** z * d / D
    alpha = 1.0 + 1.0 / math.sqrt(s)
    if alpha > 6:
        raise OutOfDomain("alpha", f"式(9) 要求 α ≤ 6，得 {alpha}")
    return alpha


@_formula("din743_2.fig12.cross_hole", f"{P2} 5.2.3 图12 横孔：ασ=3−2r/d（拉压）、3+1,4·(2r/d)−2,8·√(2r/d)（弯曲）、"
          "ατ=2,023−1,125·√(2r/d)；σn 与 G' 见图例（PDF23/印23 原图已核）",
          note="2r/d 限于图示横轴 (0, 0,3]（图示范围，非条文限值）")
def cross_hole(*, kind, r, d):
    """返回 {"alpha", "G_prime"(1/mm), "section"}；section 为名义应力分母（拉压 mm²，弯曲/扭转 mm³），σn = 载荷/section。"""
    k = _choice("kind", kind, _KINDS)
    r, d = _pos("r", r), _pos("d", d)
    x = _range("2r/d", 2.0 * r / d, 0.0, 0.3, lo_incl=False, why="图12 横轴范围")
    if k == "zd":
        return {"alpha": 3.0 - x, "G_prime": 2.3 / r, "section": math.pi * d ** 2 / 4.0 - 2.0 * r * d}
    if k == "b":
        return {"alpha": 3.0 + 1.4 * x - 2.8 * math.sqrt(x), "G_prime": 2.3 / r + 2.0 / d,
                "section": math.pi * d ** 3 / 32.0 - r * d ** 2 / 3.0}
    return {"alpha": 2.023 - 1.125 * math.sqrt(x), "G_prime": 1.15 / r + 2.0 / d,
            "section": math.pi * d ** 3 / 16.0 - r * d ** 2 / 3.0}


_K1_CURVES = {
    # 曲线 → (常数段上限, 斜率段上限(开), 系数, 对数分母(mm), 常数尾值)；6.2 PDF24–25
    "eq10": (100.0, 300.0, 0.23, 100.0, 0.89),   # 渗氮钢 σS、σB；一般/高强结构钢非调质 σB
    "eq11": (32.0, 300.0, 0.26, 32.0, 0.75),     # 一般/高强结构钢非调质 σS（2·d_B，d_B = 16 mm）
    "eq12": (16.0, 300.0, 0.26, 16.0, 0.67),     # Cr-Ni-Mo 渗碳钢 σS、σB；调质钢 σB
    "eq13": (16.0, 150.0, 0.41, 16.0, 0.60),     # 渗碳钢（Cr-Ni-Mo 除外）σS、σB
    "eq14": (16.0, 300.0, 0.34, 16.0, 0.57),     # 调质钢 σS
}


@_formula("din743_2.eq10_14", f"{P2} 6.2 式(10)–(14) 技术尺寸系数 K1(d_eff)，d_B = 16 mm，d_eff ≤ 500 mm（PDF24–25/印24–25 原图已核；"
          "图13 PDF25 一致）",
          note="曲线须由调用方按材料与强度类别显式选择；d_eff > 500 mm 须与钢厂商定 → 阻断；"
               "实际强度已知时 K1 = 1 由调用方决定，不在此默认",
          external=_ks("曲线式(12)（调质钢 σB）与式(14)（调质钢 σS），16 < d_eff < 300 mm", "S1", "S2", "S3a"))
def K1(*, curve, d_eff):
    c = _choice("curve", curve, tuple(_K1_CURVES))
    d = _pos("d_eff", d_eff)
    if d > 500.0:
        raise OutOfDomain("d_eff", "6.2：d_eff > 500 mm 的外推须与钢厂商定")
    lo, hi, k, ref, tail = _K1_CURVES[c]
    if d <= lo:
        return 1.0
    if d < hi:
        return 1.0 - k * math.log10(d / ref)
    return tail


@_formula("din743_2.eq15_16", f"{P2} 6.3 式(15) 拉压 K2=1；式(16) 弯曲/扭转 7,5 ≤ d < 150 mm：K2 = 1 − 0,2·lg(d/7,5)/lg20，"
          "d ≥ 150 mm：0,8；环形截面 d 取外径（PDF26/印26 原图已核）",
          note="弯曲/扭转 d < 7,5 mm 条文未覆盖 → 阻断",
          external=_ks("7,5 ≤ d < 150 mm 分支与拉压 K2 = 1", "S1", "S2", "S3a"))
def K2(*, kind, d):
    k = _choice("kind", kind, _KINDS)
    d = _pos("d", d)
    if k == "zd":
        return 1.0
    if d < 7.5:
        raise OutOfDomain("d", "式(16) 适用 d ≥ 7,5 mm")
    return 1.0 - 0.2 * math.log10(d / 7.5) / math.log10(20.0) if d < 150.0 else 0.8


@_formula("din743_2.eq17", f"{P2} 6.4 式(17) K3(d) = 1 − 0,2·lg α·lg(d/7,5)/lg20（7,5 ≤ d < 150 mm），d ≥ 150：1 − 0,2·lg α；"
          "扭转用 ατ，α 可近似以 β(d_BK) 代（PDF27/印27 原图已核）",
          note="d < 7,5 mm 条文未覆盖 → 阻断")
def K3(*, alpha, d):
    a = _num("alpha", alpha)
    if a < 1:
        raise OutOfDomain("alpha", "须 ≥ 1")
    d = _pos("d", d)
    if d < 7.5:
        raise OutOfDomain("d", "式(17) 适用 d ≥ 7,5 mm")
    if d < 150.0:
        return 1.0 - 0.2 * math.log10(a) * math.log10(d / 7.5) / math.log10(20.0)
    return 1.0 - 0.2 * math.log10(a)


@_formula("din743_2.eq18", f"{P2} 7 式(18) KFσ = 1 − 0,22·lg(Rz/µm)·(lg(σB(d)/20) − 1)，σB ≤ 2000 N/mm²（PDF28/印28 原图已核）",
          note="Rz < 1 µm 时式(18) 给出 >1，图16 以 '≤1' 标 KF=1，此读法属图读 → 阻断（Rz 须 ≥ 1 µm）；"
               "轧制表皮取 Rz=200 µm、沟纹取最大值等由调用方给定",
          external=_ks("Rz = 6,3 µm，σB(d) = K1·σB(d_B)", "S1", "S2", "S3a"))
def KF_sigma(*, Rz, sigma_B_d):
    Rz = _pos("Rz", Rz)
    if Rz < 1.0:
        raise Unconfirmed("Rz", "Rz < 1 µm 时式(18) 外推不明（图16 仅示 '≤1'）")
    sB = _range("sigma_B_d", _pos("sigma_B_d", sigma_B_d), 0.0, 2000.0, lo_incl=False, why="式(18) σB ≤ 2000 N/mm²")
    return 1.0 - 0.22 * math.log10(Rz) * (math.log10(sB / 20.0) - 1.0)


@_formula("din743_2.eq19", f"{P2} 7 式(19) KFτ = 0,575·KFσ + 0,425（PDF28/印28 原图已核）",
          external=_ks("KFτ 由 KFσ", "S1", "S2", "S3a"))
def KF_tau(*, KF_sigma):
    return 0.575 * _pos("KF_sigma", KF_sigma) + 0.425


@_formula("din743_2.eq20_21", f"{P2} 7 式(20)(21) 试验 β 对应 Rz_B 时 KF = KF(Rz)/KF(Rz_B)（PDF28/印28 原图已核）")
def KF_relative(*, KF_Rz, KF_RzB):
    return _pos("KF_Rz", KF_Rz) / _pos("KF_RzB", KF_RzB)


# =================================================================== DIN 743-3（德文原版，PDF 页 = 印刷页 + 1）
@_formula("din743_3.eq1_3", f"{P3} 4.1 式(1) σbW ≈ 0,5·σB（d_B ≤ 7,5 mm）、式(2) σzdW ≈ 0,4·σB、式(3) τtW ≈ 0,3·σB（d_B ≤ 7,5 mm）"
          "（PDF6/印5 原图已核）",
          note="'若无其它给定'时的估算；附录A 表A.1–A.5 材料值未转录（需另作私有数据文件登记）")
def fatigue_limits_from_tensile(*, sigma_B, d_B):
    sB = _pos("sigma_B", sigma_B)
    dB = _pos("d_B", d_B)
    if dB > 7.5:
        raise OutOfDomain("d_B", "式(1)(3) 仅适用 d_B ≤ 7,5 mm")
    return {"sigma_bW": 0.5 * sB, "sigma_zdW": 0.4 * sB, "tau_tW": 0.3 * sB}


@_formula("din743_3.eq4_5", f"{P3} 4.1 式(4) σB ≈ 3,2·HB（调质钢、渗碳钢心部），式(5) σB ≈ 3,4·HB（软化退火/正火钢）；"
          "适用 HB ≤ 360 且 σB ≤ 1300 N/mm²，20 °C（PDF6/印5 原图已核）")
def tensile_from_brinell(*, HB, condition):
    c = _choice("condition", condition, ("quenched_tempered_or_case_core", "soft_annealed_normalized"))
    hb = _range("HB", _pos("HB", HB), 0.0, 360.0, lo_incl=False, why="HB ≤ 360")
    sB = (3.2 if c == "quenched_tempered_or_case_core" else 3.4) * hb
    if sB > 1300.0:
        raise OutOfDomain("sigma_B", "式(4)(5) 适用 σB ≤ 1300 N/mm²")
    return sB


# =================================================================== DIN 743-4（英译本，页眉 2012-10）
@_formula("din743_4.eq2_3", f"{P4} 4.2.1.3 式(2)(3) σANK = (N_D/N_L)^(1/q)·σADK，适用 N_S ≤ N_L ≤ N_D（PDF6/印6 原图已核）",
          note="q（缺口圆棒弯曲/拉压 5、扭转 8）、N_D（10⁶）、N_S（10³）为标准'未另行规定时'的取值，本库不默认，须显式给出；"
               "原文写'Equations (3) and (4) apply for N_S ≤ N_L ≤ N_D'，按上下文指式(2)(3)")
def limited_life_strength(*, ADK, q, N_D, N_L, N_S):
    ADK, q = _pos("ADK", ADK), _pos("q", q)
    N_D, N_L, N_S = _pos("N_D", N_D), _pos("N_L", N_L), _pos("N_S", N_S)
    if N_S >= N_D:
        raise OutOfDomain("N_S", "须 N_S < N_D")
    if not (N_S <= N_L <= N_D):
        raise OutOfDomain("N_L", "式(2)(3) 适用 N_S ≤ N_L ≤ N_D")
    return (N_D / N_L) ** (1.0 / q) * ADK


@_formula("din743_4.eq4_5", f"{P4} 4.2.2.1 式(4)(5) S = σADK/σa（疲劳）或 σANK/σa（有限寿命）；式(1) S_min ≥ 1,2（PDF5、PDF7/印5、印7 原图已核）")
def safety_spectrum_single(*, strength, equivalent_amplitude):
    return _pos("strength", strength) / _pos("equivalent_amplitude", equivalent_amplitude)


@_formula("din743_4.eq6_14", f"{P4} 4.2.2.3 式(6) 等效损伤应力幅 σa = σa1/K_K、式(7) K_K、式(9)(10) 谱形 ν、式(11)–(14) 截断与 N*"
          "（PDF8–10/印8–10 原图已核）",
          note="D_M 推荐 0,3（式8）、一般 0,3 < D_M ≤ 1，本库不默认，须显式给出（限 0 < D_M ≤ 1）；"
               "各级须按幅值由大到小排列（σa1 为最大载荷级），不自动排序")
def spectrum_equivalent_amplitude(*, bins, q, N_D, D_M):
    """bins：[(n_i, 幅值_i), …]，幅值降序；返回 {"k", "n_e", "N_star", "nu", "K_K", "amplitude_1", "equivalent_amplitude", "domain"}。"""
    q, N_D = _pos("q", q), _pos("N_D", N_D)
    D_M = _range("D_M", _pos("D_M", D_M), 0.0, 1.0, lo_incl=False, why="D_M ≤ 1")
    if bins is None:
        raise MissingInput("bins")
    if not isinstance(bins, (list, tuple)) or not bins:
        raise Din743Error("bins", "bad_input", "须为非空的 (n_i, 幅值_i) 序列")
    ns, amps = [], []
    for i, b in enumerate(bins):
        if not isinstance(b, (list, tuple)) or len(b) != 2:
            raise Din743Error(f"bins[{i}]", "bad_input", "须为 (n_i, 幅值_i)")
        ns.append(_pos(f"bins[{i}].n", b[0]))
        amps.append(_nonneg(f"bins[{i}].amplitude", b[1]))
    if amps[0] <= 0:
        raise OutOfDomain("bins[0].amplitude", "最大级幅值须 > 0")
    if any(amps[i] < amps[i + 1] for i in range(len(amps) - 1)):
        raise Din743Error("bins", "bad_input", "各级须按幅值降序排列（式9/10 以 σa1 为最大级）")
    total = sum(ns)
    if total >= N_D:                                                # 式(11)(13)：疲劳强度域
        acc, k = 0.0, None
        for i, n in enumerate(ns):
            if acc + n >= N_D:
                k = i
                break
            acc += n
        n_e = N_D - acc
        N_star, domain = N_D, "fatigue"
        used = ns[:k] + [n_e]
    else:                                                           # 式(12)(14)：有限寿命域，k = j
        k, n_e = len(ns) - 1, ns[-1]
        N_star, domain = total, "limited_life"
        used = list(ns)
    nu = sum((n / N_star) * (amps[i] / amps[0]) ** q for i, n in enumerate(used)) ** (1.0 / q)
    KK = ((1.0 / nu ** q - 1.0) * D_M + 1.0) ** (1.0 / q)
    return {"k": k + 1, "n_e": n_e, "N_star": N_star, "nu": nu, "K_K": KK, "amplitude_1": amps[0],
            "equivalent_amplitude": amps[0] / KK, "domain": domain}


@_formula("din743_4.eq15_16", f"{P4} 4.3 式(15)（有限寿命，σANK/τtANK）、式(16)（疲劳，σADK/τtADK）合成安全系数（PDF10/印10 原图已核）")
def safety_combined_spectrum(*, sigma_zda, sigma_zd_strength, sigma_ba, sigma_b_strength, tau_ta, tau_t_strength):
    """与 DIN 743-1 式(2) 同构；strength 依域传入 ANK（式15）或 ADK（式16）。"""
    a1, a2, a3 = _nonneg("sigma_zda", sigma_zda), _nonneg("sigma_ba", sigma_ba), _nonneg("tau_ta", tau_ta)
    A1 = _pos("sigma_zd_strength", sigma_zd_strength)
    A2 = _pos("sigma_b_strength", sigma_b_strength)
    A3 = _pos("tau_t_strength", tau_t_strength)
    den = math.sqrt((a1 / A1 + a2 / A2) ** 2 + (a3 / A3) ** 2)
    if den == 0:
        raise OutOfDomain("amplitudes", "全部应力幅为 0，安全系数无定义")
    return 1.0 / den


# 无法确认 / 未收录（阻断）清单：调用方查询用，不参与计算
UNCONFIRMED = {
    "din743_2.fig5_10": f"{P2} 5.2.1 图5–10 形状系数读图（PDF16–21）：图表读数无法逐字核对，未收录；用式(9)",
    "din743_2.fig4": f"{P2} 4.3.1 图4 支持数 n 曲线（PDF13）：仅为式(5)(6) 图示，不另读图",
    "din743_2.table4_KV": f"{P2} 8 表4 KV 为区间型 Richtwerte（PDF33），d 区间端点 25 mm 归属、d > 40 mm 线性化（图17–19，PDF31–32）"
                          "均为图读 → 未收录，KV 须由调用方给出",
    "din743_2.4_2_4.composition": f"{P2} 4.2.4 'ßG,τ' 下标 G 无法确认 → m/t 系数与 β* 不自动合成",
    "din743_3.tables_A1_A5": f"{P3} 附录A 表A.1–A.5 材料强度值（PDF7–8）：未转录进代码（大段表格数据；如需纳入应作私有数据文件由 D 登记）",
    "din743_1.tableA1_sigma_dFK": f"{P1} 表A.1 注：无经验时可以 σzFK(d) 代 σdFK（PDF21）——本库不自动代用",
}
