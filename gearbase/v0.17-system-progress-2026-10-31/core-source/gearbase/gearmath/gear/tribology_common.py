"""M39 失效模式/热 各模块共用：错误类型、输入校验、公式登记装饰器（纯 Python，不依赖 kernel 图模型）。

约定（与 gearmath/system/din743.py 一致）：
  - 全部公开计算函数参数为仅限关键字且无默认值；缺输入（None）抛 MissingInput；越出条文适用域抛 OutOfDomain；
    原图无法确认或条文未覆盖的取值抛 Unconfirmed（阻断，不猜）。
  - 每个公式函数用 formula_registry(...) 生成的装饰器登记：ref 必须注明"原图已核"与 PDF 页码；evidence_level 默认 None，
    只有经外部对拍测试设门通过的公式由 grant_external_evidence(...) 升为 E5（KISSsoft 同输入逐字段一致）。
  - 本文件只含输入校验与登记机制，不含任何标准公式；不放在 gearmath/kernel/ 中，kernel 不 import 本文件。
  - 这些模块的公式为普通 Python 函数，不是 kernel.graph.Formula 对象，因此不会被 tools/export_registry 收集进
    data/registry（是否转写为 Formula 并登记由 O/D 决定）。
"""
from __future__ import annotations

import math


class TribError(ValueError):
    """code：missing_input | bad_input | out_of_domain | unconfirmed。"""

    def __init__(self, name, code, message):
        super().__init__(f"{name}：{message}")
        self.name, self.code = name, code


class MissingInput(TribError):
    def __init__(self, name):
        super().__init__(name, "missing_input", "缺少输入（不设隐式默认）")


class OutOfDomain(TribError):
    def __init__(self, name, message):
        super().__init__(name, "out_of_domain", message)


class Unconfirmed(TribError):
    def __init__(self, name, message):
        super().__init__(name, "unconfirmed", "无法确认：" + message)


def formula_registry(registry, prefix, null_reason):
    """返回装饰器工厂 _formula(fid, ref, note="")；ref 必须以 prefix 开头且含"原图已核"和 PDFn。"""

    def _formula(fid, ref, note=""):
        if "原图已核" not in ref or "PDF" not in ref or not ref.startswith(prefix):
            raise AssertionError(f"{fid} 的 ref 必须以 {prefix} 开头并注明 PDF 页与原图已核")

        def deco(fn):
            meta = {"id": fid, "ref": ref, "note": note, "source_check": "pdf_image_checked",
                    "evidence_level": None, "evidence_level_null_reason": null_reason}
            fn.REF = meta
            if fid in registry:
                raise AssertionError(f"公式 id 重复：{fid}")
            registry[fid] = dict(meta, function=fn.__name__)
            return fn
        return deco
    return _formula


# 证据等级（沿用 gearmath/kernel/evidence.py 的 E0–E6 刻度与 tools/assess_registry.py 的规则：
#   "KISSsoft 同输入逐行一致 E5"）。只有外部对拍测试（tests/test_m39_kisssoft_v014.py）设门且通过的公式才可登记。
EXTERNAL_LEVEL_KISSSOFT = "E5"
KISSSOFT_V014_BASIS = "外部商业工具逐字段一致（KISSsoft 2026，K01–K05）"


def grant_external_evidence(registry, namespace, grants, *, level, basis):
    """把 grants（公式 id → 依据说明）登记为外部证据等级：同时更新注册表条目与函数的 REF 元数据。

    level 只接受 EXTERNAL_LEVEL_KISSSOFT（E5）；依据须写明对拍案例与比较量。未列入 grants 的公式保持 null。"""
    if level != EXTERNAL_LEVEL_KISSSOFT:
        raise AssertionError(f"外部对拍只能登记 {EXTERNAL_LEVEL_KISSSOFT}")
    for fid, note in grants.items():
        if fid not in registry:
            raise AssertionError(f"未知公式 id：{fid}")
        if not note:
            raise AssertionError(f"{fid} 缺少依据说明")
        upd = {"evidence_level": level, "evidence_basis": f"{basis}：{note}", "evidence_level_null_reason": None}
        registry[fid].update(upd)
        namespace[registry[fid]["function"]].REF.update(upd)


# ------------------------------------------------------------------ 输入校验
def num(name, v):
    if v is None:
        raise MissingInput(name)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TribError(name, "bad_input", f"应为数值，收到 {type(v).__name__}")
    v = float(v)
    if not math.isfinite(v):
        raise TribError(name, "bad_input", "应为有限数值")
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


def choice(name, v, options):
    if v is None:
        raise MissingInput(name)
    if v not in options:
        raise TribError(name, "bad_input", f"应为 {sorted(options)} 之一，收到 {v!r}")
    return v


def flag(name, v):
    if v is None:
        raise MissingInput(name)
    if not isinstance(v, bool):
        raise TribError(name, "bad_input", "应为 True/False")
    return v


def missing_keys(inputs, required):
    """返回 required 中在 inputs 里缺失或为 None 的键（保持顺序），用于主流程一次性列出全部阻断项。"""
    return [k for k in required if inputs.get(k) is None]
