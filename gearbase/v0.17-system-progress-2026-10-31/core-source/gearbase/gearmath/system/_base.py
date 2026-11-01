"""系统层（轴、轴承、键、过盈）新模块的公共底座：错误类型、输入校验、公式登记。

口径与 din743.py 一致（din743.py 仍自带同名错误类型；v0.15 EXTM36 起其 _formula 亦支持同口径 external E5）：
  - 全部计算函数参数仅限关键字、无默认值；缺输入（None）抛 MissingInput；越出条文适用域抛 OutOfDomain；
    原图无法确认或条文未覆盖的取值抛 Unconfirmed（阻断，不猜）。
  - 公式登记 ref 必须写"原图已核"与 PDF 页码；evidence_level 默认 None（无外部算例）。
    仅当测试中逐值复现了标准本身的配套算例时，登记 evidence 为 E4（标准配套算例复现），并写明算例页码与测试名；
    正式等级仍以 O/D 维护的 data/registry 评定为准（见 REPORT）。
  - 外部商业软件对拍（v0.14 EXTC 起）：同输入逐字段一致的 KISSsoft 结果另登记 external（仅 E5，source 须含
    "KISSsoft" 与 "sha256"，test 为 path::Class）；evidence_level 字段保持标准算例口径（E4/None）不变，
    evidence_level_effective = 两者取高（沿用注册表"多个对拍取最高"）。正式等级仍以 data/registry 评定为准。
  - 本子包不 import gearmath.gear，也不放进 gearmath/kernel/；只依赖 Python 标准库。
"""
from __future__ import annotations

import math


class SystemCalcError(ValueError):
    """系统层计算输入/适用域错误。code：missing_input | bad_input | out_of_domain | unconfirmed。"""

    def __init__(self, name, code, message):
        super().__init__(f"{name}：{message}")
        self.name, self.code = name, code


class MissingInput(SystemCalcError):
    def __init__(self, name):
        super().__init__(name, "missing_input", "缺少输入（系统层计算不设隐式默认）")


class OutOfDomain(SystemCalcError):
    def __init__(self, name, message):
        super().__init__(name, "out_of_domain", message)


class Unconfirmed(SystemCalcError):
    def __init__(self, name, message):
        super().__init__(name, "unconfirmed", "无法确认：" + message)


def bad(name, message):
    return SystemCalcError(name, "bad_input", message)


def num(name, v):
    if v is None:
        raise MissingInput(name)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise bad(name, f"应为数值，收到 {type(v).__name__}")
    v = float(v)
    if not math.isfinite(v):
        raise bad(name, "应为有限数值")
    return v


def pos(name, v):
    v = num(name, v)
    if v <= 0:
        raise OutOfDomain(name, f"须 > 0，收到 {v}")
    return v


def nonneg(name, v):
    v = num(name, v)
    if v < 0:
        raise OutOfDomain(name, f"须 ≥ 0，收到 {v}")
    return v


def flag(name, v):
    if v is None:
        raise MissingInput(name)
    if not isinstance(v, bool):
        raise bad(name, "应为 True/False")
    return v


def choice(name, v, options):
    if v is None:
        raise MissingInput(name)
    if v not in options:
        raise bad(name, f"应为 {sorted(map(str, options))} 之一，收到 {v!r}")
    return v


def make_registry(prefix_re, null_reason):
    """返回 (FORMULAS, formula 装饰器)。prefix_re 仅作文档用途；ref 须含"原图已核"（工程力学通用关系除外，见 basis）。"""
    formulas: dict = {}

    def formula(fid, ref, note="", evidence=None, basis="standard", external=None):
        if basis == "standard" and "原图已核" not in ref:
            raise AssertionError(f"{fid} 的 ref 必须注明原图已核")
        if evidence is not None and (evidence.get("level") != "E4" or not evidence.get("source") or not evidence.get("test")):
            raise AssertionError(f"{fid}：evidence 仅允许 E4（标准配套算例复现）且须给 source 与 test")
        if external is not None:
            src, tst = external.get("source") or "", external.get("test") or ""
            if external.get("level") != "E5" or "KISSsoft" not in src or "sha256" not in src or "::" not in tst:
                raise AssertionError(f"{fid}：external 仅允许 E5（KISSsoft 同输入逐字段一致），source 须含 KISSsoft 与 sha256，test 为 path::Class")

        def deco(fn):
            meta = {"id": fid, "ref": ref, "note": note, "basis": basis,
                    "source_check": "pdf_image_checked" if basis == "standard" else "not_a_standard_clause",
                    "evidence_level": evidence["level"] if evidence else None,
                    "evidence_source": evidence["source"] if evidence else None,
                    "evidence_test": evidence["test"] if evidence else None,
                    "evidence_level_null_reason": None if evidence else null_reason,
                    "external_evidence_level": external["level"] if external else None,
                    "external_evidence_source": external["source"] if external else None,
                    "external_evidence_test": external["test"] if external else None,
                    "evidence_level_effective": "E5" if external else (evidence["level"] if evidence else None)}
            fn.REF = meta
            if fid in formulas:
                raise AssertionError(f"公式 id 重复：{fid}")
            formulas[fid] = dict(meta, function=fn.__name__)
            return fn
        return deco

    return formulas, formula
