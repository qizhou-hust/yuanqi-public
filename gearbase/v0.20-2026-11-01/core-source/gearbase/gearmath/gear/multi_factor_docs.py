"""v0.15 OPT3：K02（斜齿）与 K04（EV 第一级，斜齿高重合度）接入系数重算版优化 —— 派生真源文档。

只装配，不新增标准公式。K02–K05 链本身已由公式给出 K_V、K_Hα/K_Fα、Z_L/Z_V/Z_R、Y_B、Y_DT（K04 另含 Z_NT/Y_NT、
Y_δrelT/Y_RrelT/Y_X、Z_W/Z_X）；本模块在父文档上显式加几何口径与适配选择器（factor_recompute.ADAPTERS）：
  * adapter.tip_shortening：K02 = kisssoft_auto_equivalent（原 KISSsoft kXmn=−0.012 mm，本式在原几何下 −0.01187 mm，
    0.001 mm 圆整内一致）；K04 = none（原 KISSsoft kXmn=0，本式在原几何下 −0.0374 mm ≠ 0 → K04 未用自动齿顶缩短）；
  * adapter.face_widths = pinion_overhang：b_1 = b_2 + b_overhang（保持原设计齿宽差 K02 1 mm、K04 2 mm）；
  * adapter.blank_bore = rim_from_root_min_wheel：大轮 d_inner_2 = df_min_2 − 2 s_R（K02 sR/mn=3.5 报告值，原几何下
    146.3902 mm 与证据 146.39 在报告末位内一致；K04 报告无 sR/mn，按原生 di 与 df.i 反算 3.5000，provenance=agent_proposed）；
    小轮 d_inner_1（K02 轴齿轮 0、K04 轴孔 25 mm）保持；
  * adapter.tolerances = iso1328_grade：只 K04（报告 Q-ISO 1328:2013 A6）；K02 精度按 DIN 3961:1978（本库未实现）→ 公差保持；
  * adapter.f_Hbeta5 = iso1328_grade5：只 K02（v0.17 K02GAP）：fHβ5 为 5 级公差，与 DIN 3961 无关，按 ISO 1328-1:2013 式(10) 随几何重算。
仍保持（证据区或作者输入，须在优化声明 hold_rationale/geometry_coupled_held 中逐项给理由）：K02 Z_NT/Y_NT/Y_δrelT/Y_RrelT/
Y_X/Z_W/Z_X（契约 method.life/root_factors=external）、f_ZCa（两例）、K04 K_Hβ（契约 method.K_Hbeta=external）与 C_R。
"""
from __future__ import annotations

import json

from . import factor_recompute as FR
from . import math_source as MS
from . import math_source_kisssoft as MK

ROOT = MS.ROOT


def _sel(rows):
    return {k: (v, s) for k, v, s in rows}


def k02_factor_document():
    parent = MK.load_doc("K02-helical")
    over = parent["inputs"]["b_1"]["value"] - parent["inputs"]["b_2"]["value"]
    sel = _sel([
        ("adapter.tip_shortening", "kisssoft_auto_equivalent",
         "K02 KISSsoft 原报告/COM ZR[i].kXmn=−0.012 mm（自动齿顶缩短）；本式 a_w − a − (x1+x2)·m_n 在原几何下 −0.01187 mm，"
         "在 KISSsoft 0.001 mm 圆整内一致；" + FR.TIP_SHORTENING_SOURCE),
        ("adapter.face_widths", "pinion_overhang", f"K02 COM ZR[0].b=21、ZR[1].b=20 mm：保持小轮宽出 {over:g} mm"),
        ("adapter.blank_bore", "rim_from_root_min_wheel",
         "K02 报告 sr/mn=3.5（第 865 行）；原几何下 df_min_2 − 2·3.5·m_n = 146.3902 mm 与证据 d_inner_2=146.39（报告 2 位小数）一致；"
         "小轮 d_inner_1=0（轴齿轮）保持"),
        ("adapter.f_Hbeta5", "iso1328_grade5",
         "v0.17 K02GAP：fHβ5 是 ISO 6336-1:2019 7.5.3.4 式(55) 的 5 级螺旋线倾斜公差，不取自工件精度标准 DIN 3961；"
         "原几何（d 41.74/160.78、b 21/20 mm）本式 5.93→6.0、6.20→6.0 µm，取大 6.0 = 报告 [fHβ5]（第 935 行）；"
         "KISSsoft 2026 OPT3-3-K02（d 53.59/202.00、b 27/26 mm）ZP[0].KHdat.fHb5=6.5 = 本式 6.18→6.0、6.50→6.5 取大"
         "（data/kisssoft_v017/OPT3-3-K02.json）。原 hold 理由“同 DIN 3961”有误，致 K_Hβ 低估 2.7 %"),
    ])
    inputs = [("b_overhang", {"value": float(over), "unit": "mm", "provenance": "user",
                              "source": "K02 COM ZR[0].b − ZR[1].b（原设计齿宽差，作者意图按差值保持）"})]
    inputs += [(n, {"value": 1.0, "unit": u, "provenance": "standard_constant", "source": "Definition of metric length unit"})
               for n, u in (("root_mm", "mm"), ("root_um", "um")) if n not in parent["inputs"]]
    eds = {"ISO 1328-1": ("2013", "fHβ5（ISO 6336-1:2019 7.5.3.4 的 5 级公差）按 ISO 1328-1:2013 式(10)；"
                                  "工件精度仍为 DIN 3961:1978（报告 [Q-DIN 3961:1978]），未用本版公差")}
    return FR.derive_document(parent, "kisssoft_chain", "K02-helical", selectors=sel, inputs=inputs, editions=eds,
                              doc_id="K02-helical.factors",
                              title="KISSsoft 商业工具案例 K02-helical —— 系数重算修订（齿顶缩短、齿宽差、大轮内径随几何）",
                              extra_note="精度 DIN 3961:1978（本库未实现）→ f_pt/f_falpha/f_Hβ/f_pbT 保持；f_Hβ5 按 ISO 1328-1:2013 "
                                         "5 级随几何重算（adapter.f_Hbeta5）；K02 契约 method.life/"
                                         "root_factors=external → Z_NT/Y_NT/Y_δrelT/Y_RrelT/Y_X/Z_W/Z_X 保持（证据区）。")


def k04_factor_document():
    parent = MK.load_doc("K04-EV-stage1")
    over = parent["inputs"]["b_1"]["value"] - parent["inputs"]["b_2"]["value"]
    d = json.loads((ROOT / "data" / "kisssoft" / "K04-EV-stage1.json").read_text(encoding="utf-8"))
    sel = _sel([
        ("adapter.tip_shortening", "none",
         "K04 KISSsoft COM ZR[i].kXmn=0（未做齿顶缩短）；自动等效式在原几何下为 −0.0374 mm ≠ 0 → K04 原设计不是自动口径；"
         + FR.TIP_SHORTENING_SOURCE),
        ("adapter.face_widths", "pinion_overhang", f"K04 COM ZR[0].b=31、ZR[1].b=29 mm：保持小轮宽出 {over:g} mm"),
        ("adapter.blank_bore", "rim_from_root_min_wheel",
         "K04 报告无 bs/b、sr/mn（C_R 为证据）；原生 di=128.537 与 df.i=143.587 反算 sR/mn=3.5000（报告 [sr] 7.53 mm）；"
         "小轮 d_inner_1=25 mm（轴孔）保持"),
        ("adapter.tolerances", "iso1328_grade",
         f"K04 报告 {d['report']['Q_grade_1']['label']} A{d['report']['Q_grade_1']['value']:g}（第 {d['report']['Q_grade_1']['line']} 行）；"
         "原作者输入 f_pt=8.5、f_falpha=8.5 µm 即本式在原几何下的值（见测试）"),
    ])
    eds = {"ISO 1328-1": ("2013", f"K04 报告 {d['report']['Q_grade_1']['label']}；iso1328.py 实现 ISO 1328-1:2013")}
    inputs = [("b_overhang", {"value": float(over), "unit": "mm", "provenance": "user",
                              "source": "K04 COM ZR[0].b − ZR[1].b（原设计齿宽差，作者意图按差值保持）"}),
              ("sR_mn", {"value": 3.5, "unit": "1", "provenance": "agent_proposed",
                         "source": "由 K04 原生 ZR[1].di=128.537 与 df.i=143.587 反算 (df.i − di)/(2·m_n)=3.5000；报告无 sr/mn，"
                                   "按比值保持为代理提议，待用户确认"})]
    for i in ("1", "2"):
        q = d["report"][f"Q_grade_{i}"]
        inputs.append((f"A1328_{i}", {"value": float(q["value"]), "unit": "1", "provenance": "user",
                                      "source": f"KISSsoft K04 报告 {q['label']} A{q['value']:g}（extracted.txt 第 {q['line']} 行）"}))
    return FR.derive_document(parent, "kisssoft_chain", "K04-EV-stage1", selectors=sel, inputs=inputs, editions=eds,
                              doc_id="K04-EV-stage1.factors",
                              title="KISSsoft 商业工具案例 K04-EV-stage1 —— 系数重算修订（公差、齿宽差、大轮内径随几何）",
                              extra_note="K04 契约 method.K_Hbeta=external → K_Hβ 保持（证据区，结论受此限制）；C_R、f_ZCa 保持。")


DOCS = {"K02-helical.factors": k02_factor_document, "K04-EV-stage1.factors": k04_factor_document}


def write_all():
    out = {}
    for doc_id, fn in DOCS.items():
        doc = fn()
        FR.source_path(doc_id).write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        out[doc_id] = doc
    return out


if __name__ == "__main__":
    for k, doc in write_all().items():
        print(k, MS.source_sha256(doc))
