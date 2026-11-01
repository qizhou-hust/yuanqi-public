"""DIN 6892:2012-08 平键连接 方法 C（概略设计）主流程，及 DIN 6885-1:2021-06 表1 平键/键槽尺寸（已核行）。

资料与核对口径（本机私有 PDF，逐式渲染原图核对；代码只写条款号、式号、表号、页码，不复制原文）：
  - DIN 6892:2012-08 德文原版（文件 DIN 6892 (2012-08-00).pdf，48 页扫描），PDF 页 = 印刷页；
    第7章 方法 C：7.1 假设、7.2 适用界限 式(31)、7.3 式(32)–(34)、7.4 式(35)(36)（PDF21–22）。
    附录D D.3.2 为方法 C 算例（PDF40–41）：测试逐值复现 → 式(31)–(34) 证据 E4（标准配套算例复现）。
  - DIN 6885-1:2021-06 德文原版（文件 DIN 6885-1 (2021-06-00).pdf，17 页扫描），PDF 页 = 印刷页；
    已被 2021-11 修正版替代，修正版未取得（见私有库 KNOWN_ISSUES）。
    本轮只收录表1（第1部分，b = 2–22 mm）的 b、h、轴径区间、t1、t2（Rückenspiel）五列（PDF10/印10 原图已核）；
    表2（b ≥ 25 mm，PDF13–15）原图有空白格（b=28 列 b 值、b=50 列 h 值、b=80 列 b 值、b=90 列 t1 值），
    且 KNOWN_ISSUES 记表2 第13列新版读数与脚注 g 未确认 → 表2 整表阻断；质量列（脚注 g 所在）不收录。
方法 A/B（第5、6章）、附录C（AGMA 几何系数）、图8 fL 读图均未收录（TODO），fL 由调用方给出。
单位：长度 mm；力矩 N·mm；应力 N/mm²。
"""
from __future__ import annotations

from ._base import MissingInput, OutOfDomain, Unconfirmed, bad, choice, flag, make_registry, nonneg, pos

STD = "DIN 6892:2012"
STD_KEY = "DIN 6885-1:2021-06"
FORMULAS, _formula = make_registry(r"^DIN 6892|^DIN 6885-1", "无标准配套算例覆盖：测试仅为独立重写对拍（自洽）")
_KS_R4C = {"level": "E5", "test": "tests/test_m36_kisssoft_v015.py::TestDin6892KISSsoft",
           "source": "KISSsoft Release 2026 M02A 方法 C：R4-user-C-unidirectional-nominal-only（M2A sha256 f6528a20ed9b…）、"
                     "R4-vendor-C-unidirectional（M2A sha256 300dc18337a7…）；提取件 data/kisssoft_v015/R4-DIN6892.json；"
                     "覆盖：i = 1、单向扭矩、钢毂与脆性毂（Rm 代 Re）；p_zul 对比取三构件最小值"}

_EX_D32 = {"level": "E4", "source": f"{STD} 附录D D.3.2 方法 C 算例（PDF41/印41；几何与载荷 PDF40/印40）",
           "test": "tests/test_m36_din6892.py::TestStandardExampleD32"}

# ------------------------------------------------------------------ DIN 6885-1 表1（第1部分）
# (b, h, d1 über, d1 bis, t1 Wellennut, t2 Nabennut bei Rückenspiel)；PDF10/印10
_TABLE1 = (
    (2, 2, 6, 8, 1.2, 1.0), (3, 3, 8, 10, 1.8, 1.4), (4, 4, 10, 12, 2.5, 1.8), (5, 5, 12, 17, 3.0, 2.3),
    (6, 6, 17, 22, 3.5, 2.8), (8, 7, 22, 30, 4.0, 3.3), (10, 8, 30, 38, 5.0, 3.3), (12, 8, 38, 44, 5.0, 3.3),
    (14, 9, 44, 50, 5.5, 3.8), (16, 10, 50, 58, 6.0, 4.3), (18, 11, 58, 65, 7.0, 4.4), (20, 12, 65, 75, 7.5, 4.9),
    (22, 14, 75, 85, 9.0, 5.4))


def _row(t):
    return {"b": float(t[0]), "h": float(t[1]), "d_over": float(t[2]), "d_to": float(t[3]), "t1": t[4], "t2_back_clearance": t[5],
            "ref": f"{STD_KEY} 表1（PDF10/印10 原图已核）"}


@_formula("din6885_1.table1", f"{STD_KEY} 表1 第1部分 b=2–22 mm：b、h、轴径区间（über…bis）、t1、t2（Rückenspiel）（PDF10/印10 原图已核）",
          note="轴径区间按 'über d_over bis d_to' 取左开右闭；d ≤ 6 或 d > 85 mm（表2 范围）阻断；"
               "底本 2021-06，2021-11 修正版未取得（KNOWN_ISSUES；官方修正据记录仅涉质量值，本函数不含质量列）")
def key_dimensions(*, d):
    """按轴径 d 取表1 行。"""
    d = pos("d", d)
    for t in _TABLE1:
        if t[2] < d <= t[3]:
            return _row(t)
    if d > _TABLE1[-1][3]:
        raise Unconfirmed("d", f"d = {d} mm 属表2（b ≥ 25）范围：表2 原图有空白格且第13列/脚注 g 未确认（KNOWN_ISSUES）→ 阻断")
    raise OutOfDomain("d", f"d = {d} mm 小于表1 最小区间（über 6 mm）")


def key_by_width(*, b):
    """按键宽 b 取表1 行（b 须为表1 列值）。"""
    b = pos("b", b)
    for t in _TABLE1:
        if t[0] == b:
            return _row(t)
    raise Unconfirmed("b", f"b = {b} 不在已核表1 列值 {[t[0] for t in _TABLE1]} 中（表2 阻断）")


# ------------------------------------------------------------------ DIN 6892 方法 C
@_formula("din6892.eq31", f"{STD} 7.2 b) 式(31) l_tr ≤ 1,3·d；7.2 a)/c)/d) 只计扭矩、i ≤ 2、扭矩换向不得用方法 C（PDF21/印21 原图已核）",
          note="超过 1,3d 的长度'无显著贡献'：本库不截断而阻断，由调用方显式给出 ≤ 1,3d 的 l_tr",
          evidence=_EX_D32)
def check_limits(*, l_tr, d, i, torque_reversal):
    l_tr, d = pos("l_tr", l_tr), pos("d", d)
    i = choice("i", i, (1, 2))
    if flag("torque_reversal", torque_reversal):
        raise OutOfDomain("torque_reversal", "7.2 d)：扭矩换向时不能按方法 C 核算，须用方法 B（本库未收录）")
    if l_tr > 1.3 * d:
        raise OutOfDomain("l_tr", f"式(31)：l_tr = {l_tr} > 1,3·d = {1.3 * d}")
    return {"l_tr_over_d": l_tr / d, "i": i}


@_formula("din6892.eq33", f"{STD} 7.3 a) 式(33) p_zul = 0,9·R_emin；R_emin 为轴、毂、键材料屈服强度最小值，脆性毂（如灰铸铁）用 Rm 代 Re"
          "（PDF21/印21 原图已核）", evidence=_EX_D32,
          external=_KS_R4C)
def p_zul(*, Re_shaft, Re_hub, Re_key, hub_brittle, Rm_hub):
    """hub_brittle=True 时用 Rm_hub（Re_hub 须为 None）；否则用 Re_hub（Rm_hub 须为 None）。返回 {"R_emin", "p_zul"}。"""
    brittle = flag("hub_brittle", hub_brittle)
    if brittle:
        if Re_hub is not None:
            raise bad("Re_hub", "脆性毂按式(33) 说明用 Rm，Re_hub 须为 None")
        hub = pos("Rm_hub", Rm_hub)
    else:
        if Rm_hub is not None:
            raise bad("Rm_hub", "非脆性毂用 Re，Rm_hub 须为 None")
        hub = pos("Re_hub", Re_hub)
    R = min(pos("Re_shaft", Re_shaft), hub, pos("Re_key", Re_key))
    return {"R_emin": R, "p_zul": 0.9 * R}


@_formula("din6892.phi", f"{STD} 7.3 b) 承载份额 φ：i=1 时 1，i=2 时 0,75（PDF21/印21 原图已核）", evidence=_EX_D32)
def phi(*, i):
    return {1: 1.0, 2: 0.75}[choice("i", i, (1, 2))]


@_formula("din6892.eq34", f"{STD} 7.3 c) 式(34) M_teq = K_A·M_tnenn；K_A 按 DIN 3990-1（附录A，PDF23–24）由调用方给出（PDF21/印21 原图已核）",
          evidence=_EX_D32,
          external=_KS_R4C)
def M_teq(*, K_A, M_tnenn):
    K = pos("K_A", K_A)
    if K < 1:
        raise OutOfDomain("K_A", "应用系数须 ≥ 1")
    return K * nonneg("M_tnenn", M_tnenn)


@_formula("din6892.eq32", f"{STD} 7.3 式(32) M_tzul = p_zul·(h − t1)·l_tr·(d/2)·i·φ ≥ M_teq（PDF21/印21 原图已核）", evidence=_EX_D32,
          external=_KS_R4C)
def M_tzul(*, p_zul, h, t1, l_tr, d, i):
    h, t1 = pos("h", h), pos("t1", t1)
    if t1 >= h:
        raise OutOfDomain("t1", "须 t1 < h（毂侧承载高度 h − t1 > 0）")
    return pos("p_zul", p_zul) * (h - t1) * pos("l_tr", l_tr) * pos("d", d) / 2.0 * choice("i", i, (1, 2)) * phi(i=i)


@_formula("din6892.eq32_pressure", f"{STD} 7.3 式(32) 改写：在 7.1 a) 均布假设下，扭矩 M 对应的键侧挤压应力 p = 2M/(d·(h − t1)·l_tr·i·φ)"
          "（PDF21/印21 原图已核；改写为本库口径）",
          note="与式(32) 等价：p ≤ p_zul ⇔ M ≤ M_tzul；仅作结果展示",
          external=_KS_R4C)
def surface_pressure(*, M_t, h, t1, l_tr, d, i):
    h, t1 = pos("h", h), pos("t1", t1)
    if t1 >= h:
        raise OutOfDomain("t1", "须 t1 < h")
    return 2.0 * nonneg("M_t", M_t) / (pos("d", d) * (h - t1) * pos("l_tr", l_tr) * choice("i", i, (1, 2)) * phi(i=i))


@_formula("din6892.eq35_36", f"{STD} 7.4 式(35) M_tmax ≤ fL·M_tzul；有过盈配合时式(36) fL·M_tzul + 0,8·M_tRmin（M_tRmin 按 DIN 7190）"
          "（PDF22/印22 原图已核）",
          note="fL 取自图8（PDF18，未读图）由调用方给出；7.4 a) 单次载荷尖峰 1,3–1,5 倍为说明，不作默认")
def M_tmax_permissible(*, f_L, M_tzul, M_tRmin):
    f = pos("f_L", f_L)
    base = f * pos("M_tzul", M_tzul)
    if M_tRmin is None:
        return {"M_tmax_perm": base, "equation": "eq35"}
    return {"M_tmax_perm": base + 0.8 * nonneg("M_tRmin", M_tRmin), "equation": "eq36"}


def method_c(*, d, h, t1, l_tr, i, torque_reversal, Re_shaft, Re_hub, Re_key, hub_brittle, Rm_hub,
             K_A, M_tnenn, M_tmax, f_L, M_tRmin):
    """DIN 6892 方法 C 主流程：式(31) → 式(33) → 式(32) → 式(34) → [式(35)/(36)]。

    峰值扭矩核算：M_tmax 为 None 时 f_L、M_tRmin 也须为 None，结果注明'未核'（调用方显式声明）。
    返回含 p_zul、M_tzul、M_teq、p_eq（M_teq 下挤压应力）、ok_eq、峰值核算结果。
    """
    lim = check_limits(l_tr=l_tr, d=d, i=i, torque_reversal=torque_reversal)
    pz = p_zul(Re_shaft=Re_shaft, Re_hub=Re_hub, Re_key=Re_key, hub_brittle=hub_brittle, Rm_hub=Rm_hub)
    Mz = M_tzul(p_zul=pz["p_zul"], h=h, t1=t1, l_tr=l_tr, d=d, i=i)
    Meq = M_teq(K_A=K_A, M_tnenn=M_tnenn)
    out = {"l_tr_over_d": lim["l_tr_over_d"], "R_emin": pz["R_emin"], "p_zul": pz["p_zul"], "M_tzul": Mz, "M_teq": Meq,
           "p_eq": surface_pressure(M_t=Meq, h=h, t1=t1, l_tr=l_tr, d=d, i=i), "ok_eq": Mz >= Meq,
           "ref": f"{STD} 第7章 方法 C（PDF21–22 原图已核）"}
    if M_tmax is None:
        if f_L is not None or M_tRmin is not None:
            raise bad("M_tmax", "未给 M_tmax 时 f_L、M_tRmin 须为 None")
        out.update({"peak_check": "not_requested"})
        return out
    if f_L is None:
        raise MissingInput("f_L")
    pk = M_tmax_permissible(f_L=f_L, M_tzul=Mz, M_tRmin=M_tRmin)
    Mmax = nonneg("M_tmax", M_tmax)
    out.update({"peak_check": pk["equation"], "M_tmax": Mmax, "M_tmax_perm": pk["M_tmax_perm"], "ok_peak": Mmax <= pk["M_tmax_perm"],
                "p_max": surface_pressure(M_t=Mmax, h=h, t1=t1, l_tr=l_tr, d=d, i=i)})
    return out


UNCONFIRMED = {
    "din6885_1.table2": f"{STD_KEY} 表2（b = 25–100，PDF13–15）：原图空白格 4 处（b=28 列 b、b=50 列 h、b=80 列 b、b=90 列 t1）；"
                        "KNOWN_ISSUES：第13列新版读数与脚注 g 原句未确认 → 整表阻断",
    "din6885_1.mass_footnote_g": f"{STD_KEY} 表1/表2 质量列与脚注 g：KNOWN_ISSUES 未确认，且官方修正涉质量值 → 不收录",
    "din6885_1.tolerances": f"{STD_KEY} 表1 公差、t2（Übermaß）、r1/r2、d2、长度系列：本轮未收录（只收 b、h、轴径、t1、t2 Rückenspiel）",
    "din6892.methods_AB": f"{STD} 第5章 方法 A、第6章 方法 B（式(1)–(30)、图1–8）：本轮未收录",
    "din6892.fig8_fL": f"{STD} 图8 fL（PDF18）：不读图，fL 由调用方给出",
    "din6892.annexC": f"{STD} 附录C AGMA 键几何修正（PDF26–30）：未收录；方法 C 仅用于 DIN 6885 几何",
    "din6892.annexA_KA": f"{STD} 附录A K_A 表（转引 DIN 3990-1:1987）：未收录，K_A 由调用方给出",
}
