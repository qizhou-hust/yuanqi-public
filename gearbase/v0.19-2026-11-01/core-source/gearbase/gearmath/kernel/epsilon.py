"""ε-约束法多目标骨架（零依赖，纯数学；不知道任何领域）。

  主目标保持声明里的 objective；次目标"量 q 越大越好"（或越小越好）改写为约束 q ≥ ε（或 ≤ ε），对一列 ε 逐个求解单目标问题，
  每个可行解是候选 Pareto 点；最后用非支配筛选去掉被支配点（同一 ε 下的局部解可能被相邻 ε 的解支配）。
本模块只做两件事：
  epsilon_declarations(decl, ...)  在声明（gearmath.problem_declaration/v1）上追加 ε 约束（role="epsilon_scan"），返回一列新声明；
  nondominated(points, senses)     非支配筛选（全部目标逐项不劣且至少一项更优 = 支配；数值并列视为互不支配）。
求解、写回、统一校核复核在领域层完成。ε 列表必须显式给出（无默认网格）。
"""
from __future__ import annotations

import copy
import math

from .declared import validate_declaration

EPSILON_ROLE = "epsilon_scan"


def epsilon_declarations(decl, *, quantities, unit, sense, levels, source, tag):
    """quantities：同一 ε 下限/上限施加到的量列表（如两个齿轮的同类量，取其最小者 ≥ ε 等价于逐个 ≥ ε）。
    levels：显式 ε 列表（有限数值，严格单调）。返回 [(ε, 新声明)]。新声明 id = f"{decl['id']}.{tag}-{k}"。"""
    errs = validate_declaration(decl)
    if errs:
        raise ValueError(errs)
    if sense not in (">=", "<="):
        raise ValueError("sense 须为 '>=' 或 '<='")
    if not quantities or not all(isinstance(q, str) and q for q in quantities):
        raise ValueError("须显式给出 quantities")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("须给出 ε 列表的来源说明 source")
    if not levels or not all(isinstance(e, (int, float)) and math.isfinite(e) for e in levels):
        raise ValueError("须显式给出有限数值的 ε 列表 levels（无默认网格）")
    if any(b <= a for a, b in zip(levels, levels[1:])):
        raise ValueError("levels 须严格递增")
    out = []
    for k, eps in enumerate(levels):
        d = copy.deepcopy(decl)
        d["id"] = f"{decl['id']}.{tag}-{k}"
        d["description"] = f"{decl.get('description', '')}【ε-约束扫描 {tag}：{', '.join(quantities)} {sense} {eps:g} {unit}】"
        for q in quantities:
            d["constraints"].append({"id": f"{tag}.{q}", "quantity": q, "sense": sense, "role": EPSILON_ROLE,
                                     "limit": {"value": float(eps), "unit": unit, "source": source}})
        out.append((float(eps), d))
    return out


def dominates(a, b, senses):
    """a 支配 b：每个目标都不劣，且至少一个严格更优。senses：{名: "min"|"max"}。"""
    better = False
    for k, s in senses.items():
        x, y = (a[k], b[k]) if s == "min" else (-a[k], -b[k])
        if x > y:
            return False
        if x < y:
            better = True
    return better


def nondominated(points, senses):
    """返回非支配点的下标列表（保持输入顺序）。"""
    return [i for i, p in enumerate(points) if not any(dominates(q, p, senses) for j, q in enumerate(points) if j != i)]
