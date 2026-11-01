"""证据资格汇总：只读取各模块已有的证据元数据，不评定、不提升等级。

  - 齿轮副公式图（gear/rating）：Result.evidence[量]["level"]（依赖链最弱一环，来自 data/registry 评估；未评估 = unassessed）。
  - 摩擦学/系统层模块：FORMULAS 注册表与函数 REF 元数据（evidence_level_effective → evidence_level；None = 无外部算例）。
  - 外部对拍引用：data/kisssoft_v014/*.json 文件名（私有资料，只引用文件名与 id，不复制内容）。
正式证据等级仍以 O/D 维护的 data/registry 评定为准。
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
KS_DIR = ROOT / "data" / "kisssoft_v014"
LEVELS = ("E0", "E1", "E2", "E3", "E4", "E5", "E6")
NONE_LEVEL = "none"            # 无等级（模块登记 None 或注册表 unassessed）


def norm_level(lv):
    return lv if lv in LEVELS else NONE_LEVEL


def weakest(levels):
    """最弱一环：任一为 none 则 none；否则取最低 E 级。空列表 → none。"""
    ls = [norm_level(x) for x in levels]
    if not ls or NONE_LEVEL in ls:
        return NONE_LEVEL
    return min(ls, key=LEVELS.index)


def ref_of(fn):
    """已有函数的 REF 元数据 → (公式 id, 等级)。无 REF → (None, none)。"""
    ref = getattr(fn, "REF", None)
    if not ref:
        return None, NONE_LEVEL
    lv = ref.get("evidence_level_effective", ref.get("evidence_level"))
    return ref.get("id"), norm_level(lv)


def item_evidence(fns):
    """子检查条目：最终公式（若干）的 id 与最弱等级。返回 (ids, level, basis)。"""
    ids, lvs = [], []
    for fn in fns:
        fid, lv = ref_of(fn)
        if fid:
            ids.append(fid)
            lvs.append(lv)
    return ids, weakest(lvs), "所列主链公式 REF 元数据的最弱一环（不是完整依赖图；全链追踪 TODO）"


def module_distribution(formulas):
    """模块 FORMULAS 注册表 → {等级: 条数}。"""
    out = {}
    for meta in formulas.values():
        lv = norm_level(meta.get("evidence_level_effective", meta.get("evidence_level")))
        out[lv] = out.get(lv, 0) + 1
    return dict(sorted(out.items()))


def merge_distributions(ds):
    out = {}
    for d in ds:
        for k, v in d.items():
            out[k] = out.get(k, 0) + v
    return dict(sorted(out.items()))


# data/kisssoft_v014 文件名前缀 → 相关子检查（P1：TR30 例7 齿轮强度；P2：K01 优化几何；P3：K01–K05 胶合/微点蚀；P4：系统层方法算例）
_KS_SCOPES = (("P1-", ("gear_rating",)), ("P2-", ("gear_rating",)), ("P3-", ("gear_rating", "scuffing", "micropitting")),
              ("P4-fit-", ("fit",)), ("P4-key-", ("key",)), ("P4-shaft-", ("shaft", "bearing")))


def kisssoft_files():
    return sorted(p.name for p in KS_DIR.glob("*.json")) if KS_DIR.is_dir() else []


def external_refs(scope, design_id):
    """返回 [{"file", "relation", "note"}]。relation：same_design（文件 id 含设计 id，如 P3-K01-spur ↔ K01-spur）、
    related_design（同一厂商例的修订几何，如 P2-K01-opt）、method_only（同方法的其它算例，不是本设计）。"""
    out = []
    for name in kisssoft_files():
        scopes = next((s for pre, s in _KS_SCOPES if name.startswith(pre)), ())
        if scope not in scopes:
            continue
        stem = name[:-5]
        if design_id and stem.endswith(design_id):
            rel, note = "same_design", "同一设计输入的 KISSsoft 2026 结果（对拍见 tests/test_m39_kisssoft_v014.py 等）"
        elif design_id and design_id.split("-")[0] in stem.split("-") and name.startswith("P2-"):
            rel, note = "related_design", "同一厂商例的优化修订几何，不是本设计"
        else:
            rel, note = "method_only", "同方法的其它算例：只说明方法级外部一致，不构成本设计的对拍"
        out.append({"file": f"data/kisssoft_v014/{name}", "relation": rel, "note": note})
    return out

