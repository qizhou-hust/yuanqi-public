"""K01–K05（KISSsoft 商业工具案例）-> gears.math-source/2 文档（M34 迁移）。

装配仍由 K 链（kisssoft_case.build_model / kisssoft_multi.build_model）完成，本模块只把"作者输入分区"落成文档，
并为证据输入补上指向 data/kisssoft/ 内文件的证书（kind=file：相对路径 + sha256 + 字段定位）。不改任何公式、参考值、K 链代码。

两处无法照搬 K 链装配结果的地方（均在文档的 source 文字里写明，并在 REPORT 说明）：
  1. T_1：K 链里 provenance=derived（T1 = P/(2π n1)）。v2 格式拒绝派生量入文档，也没有"名义功率"输入，
     故 T_1 存入 evidence 区（provenance=evidence），配 kind=tool_calculation 证书：证书写明 P（com["ZS.Pnominal"]，kW）
     与 n（com["ZR[0].nnominal"]，rpm）在 data/kisssoft/<case>.json 的位置并附该文件 sha256；T_1 = P/(2π n_1) 可由
     torque_from_power(case, n_1) 重算（n_1 取文档值），守门测试逐位比较；只改 n_1 不改 T_1 即失败。
  2. 文档按 K 链的公式集求值（kisssoft_case.BLANK、kisssoft_multi 的适配公式）；math_source.build_model(doc) 只装配
     rating.pair_model，不含这些公式，因此不能直接 build K 文档。验收测试用 K 链模型的公式集加载文档分区。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import re

from ..kernel import source_doc as SD
from . import kisssoft_case as KC
from . import kisssoft_multi as KM
from . import math_source as MS

ROOT = MS.ROOT
CASES = ("K01-spur",) + KM.CASES
SOURCE_DIR = ROOT / "data" / "source"
EXTRAS_REL = "data/kisssoft/K02-K05-extras.json"


def source_path(case):
    return SOURCE_DIR / f"{case}.math-source.json"


def reference_model(case):
    """K 链既有装配（验收对照）。返回 (model, 案例数据)。"""
    return KC.build_model(case) if case == "K01-spur" else KM.build_model(case)


# ---------------------------------------------------------------- 证书定位
def _loc(*toks):
    """路径 -> 定位字符串：标识符用 .a，其余键用 ["k"]，下标用 [i]。resolve_locator 是其逆。"""
    out = ""
    for t in toks:
        if isinstance(t, int):
            out += f"[{t}]"
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t):
            out += ("." if out else "") + t
        else:
            out += f'["{t}"]'
    return out


def resolve_locator(obj, loc):
    for m in re.finditer(r'\["([^"]+)"\]|\[(\d+)\]|\.?([A-Za-z_][A-Za-z0-9_]*)', loc):
        key = m.group(1) or m.group(3)
        obj = obj[key] if key is not None else obj[int(m.group(2))]
    return obj


def _file_cert(rel, locator):
    return {"kind": "file", "ref": rel, "sha256": hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), "locator": locator}


_COM_RE = re.compile(r"COM(?: 字段)? \(?'?([A-Za-z0-9_\[\].]+)'?")


def torque_from_power(case, n_rpm):
    """T_1 [N*mm] = P/(2π n)，P 取 data/kisssoft/<case>.json 的 com["ZS.Pnominal"]（kW），n 由调用方给（rpm）。与 K 链同一表达式。"""
    from ..kernel import units as U
    import math
    d = json.loads((ROOT / "data" / "kisssoft" / f"{case}.json").read_text(encoding="utf-8"))
    P, n = U.to_canonical(d["com"]["ZS.Pnominal"], "kW"), U.to_canonical(n_rpm, "rpm")
    return P / (2 * math.pi * n)


def t1_guard_errors(case, doc):
    """守门：文档 T_1 须等于 P/(2π n_1)（P 取证书指向的文件，n_1 取文档值）；证书哈希须与文件一致。返回错误列表。"""
    from ..kernel import units as U
    errs, row = [], doc["evidence"].get("T_1")
    if row is None or row["certificate"].get("kind") != "tool_calculation":
        return [{"path": "$.evidence.T_1", "code": "t1_certificate", "message": "T_1 须为带 tool_calculation 证书的证据"}]
    rel = f"data/kisssoft/{case}.json"
    if row["certificate"].get("sha256") != hashlib.sha256((ROOT / rel).read_bytes()).hexdigest():
        errs.append({"path": "$.evidence.T_1.certificate", "code": "certificate_hash", "message": f"{rel} 哈希不符"})
    if U.to_canonical(row["value"], row["unit"]) != torque_from_power(case, doc["inputs"]["n_1"]["value"]):
        errs.append({"path": "$.evidence.T_1", "code": "t1_mismatch", "message": "T_1 与 P/(2π n_1) 重算值不等（n_1 或 T_1 被单独改动）"})
    return errs


def _t1_cert(case):
    rel = f"data/kisssoft/{case}.json"
    return {"kind": "tool_calculation", "ref": "gearmath.gear.math_source_kisssoft.torque_from_power",
            "sha256": hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(),
            "locator": f'{rel}：T_1 = com["ZS.Pnominal"](kW) / (2π · n_1)，n_1 取本文档 inputs.n_1（rpm，抄录自 com["ZR[0].nnominal"]）；'
                       f"sha256 为该文件哈希；单位 N*mm"}


def _certificates(case, model):
    """证据输入 -> 证书。能在 data/kisssoft 文件里找到原值的给精确字段定位；定位处的值与文档值的一致性由验收测试核对。"""
    rel = f"data/kisssoft/{case}.json"
    d = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    x = json.loads((ROOT / EXTRAS_REL).read_text(encoding="utf-8"))["cases"].get(case)
    certs = {}
    for name, inp in model.inputs.items():
        if inp.provenance != "evidence":
            continue
        s = inp.source
        if name == "T_1":
            certs[name] = _t1_cert(case)
            continue
        m = re.match(r"d_inner_(\d)|rho_(\d)", name)
        if m:                                                   # 原生文件全精度字段，抄录在 extras
            i = int(m.group(1) or m.group(2))
            key = f"ZR[{i - 1}]." + ("di" if m.group(1) else "mat.rho")
            certs[name] = _file_cert(EXTRAS_REL, _loc("cases", case, "native", "fields", key, "value"))
        elif re.fullmatch(r"Rz_[HF]_\d", name):
            k, i = name[3], int(name[5])
            certs[name] = _file_cert(EXTRAS_REL, _loc("cases", case, "factors", "roughness", "Rz_" + k, i - 1))
        elif name in ("f_ZCa", "C_R"):
            certs[name] = _file_cert(rel, _loc("report", name, "value"))
        elif name == "surface_oil_mineral":                     # 值 1 = 报告该行出现 'Mineral-oil base'；定位到登记行号
            certs[name] = _file_cert(EXTRAS_REL, _loc("cases", case, "factors", "mineral_oil_line"))
        elif name == "aux_both_case_hardened":
            certs[name] = _file_cert(EXTRAS_REL, _loc("cases", case, "factors", "both_case_hardened_line"))
        elif name == "sigma_Hlim_surface":                      # 两轮 limh 取较小者
            k = min(("ZR[0].mat.limh", "ZR[1].mat.limh"), key=lambda kk: d["com"][kk])
            certs[name] = _file_cert(rel, _loc("com", k))
        elif _COM_RE.search(s):
            certs[name] = _file_cert(rel, _loc("com", _COM_RE.search(s).group(1)))
        else:
            raise NotImplementedError(f"{case}.{name}：证据来源无法定位到仓库文件字段：{s}")
    return certs


# ---------------------------------------------------------------- 转换
def _authored_view(model):
    """T_1（derived）以 evidence 存入（证书见 _t1_cert）；其余原样。返回浅拷贝模型视图，不改动传入模型。"""
    import copy
    v = copy.copy(model)
    v.inputs = dict(model.inputs)
    for k, i in model.inputs.items():
        if i.provenance == "derived":
            if k != "T_1":
                raise NotImplementedError(f"除 T_1 外不应有派生输入：{k}")
            v.inputs[k] = dataclasses.replace(
                i, provenance="evidence",
                source=i.source + "；v2 无名义功率输入，T_1 作为工具计算证据存入（数值逐位同 K 链），证书给出 P、n 的出处，可重算")
    return v


def convert_case(case):
    m, _ = reference_model(case)
    return MS.source_from_model(
        _authored_view(m), case, f"KISSsoft 商业工具案例 {case}（强度分册 ISO 6336:2019 对拍输入）", _certificates(case, _authored_view(m)),
        note="由 K 链（gear/kisssoft_case.py / kisssoft_multi.py）的装配结果经 gear/math_source_kisssoft.py 转换生成；"
             "只含作者输入与证据，派生量不存。T_1 的处理见 source 字段。")


def write_all():
    out = {}
    for case in CASES:
        doc = convert_case(case)
        source_path(case).write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        out[case] = doc
    return out


def load_doc(case):
    return json.loads(source_path(case).read_text(encoding="utf-8"))


def model_from_doc(case, doc=None):
    """文档 -> 模型。公式集沿用 K 链该案例的模型（清空其全部输入、版次、选择器），再只用文档的分区重新装配。"""
    doc = doc if doc is not None else load_doc(case)
    errs = MS.validate(doc)
    if errs:
        raise SD.SourceError(errs)
    m, _ = reference_model(case)
    m.inputs, m.editions, m.edition_sources, m.selectors, m.selector_sources = {}, {}, {}, {}, {}
    SD.apply_sections(m, doc)
    m.selectors = {k: r["value"] for k, r in doc["selectors"].items()}
    m.selector_sources = {k: r["source"] for k, r in doc["selectors"].items()}
    return m


if __name__ == "__main__":
    for c, doc in write_all().items():
        print(c, MS.source_sha256(doc), source_path(c).relative_to(ROOT))
