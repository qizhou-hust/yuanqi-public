"""证据等级沿依赖链传播（只读附加信息，不参与数值计算）。

等级刻度 E0–E6 沿用顶层设计：E0 未验证草稿 … E6 实测或台架。
规则：一个输出的有效等级 = 其依赖链（自身公式、所有上游公式、所有上游输入）上"最弱一环"。
  - 公式的等级来自注册表（Model.evidence_levels：公式 id → 等级）；注册表没有记录 = "unassessed"（未评估），
    它比 E0 更弱：没有记录不能被当作"已验证到 E0"，也不能被忽略；
  - 输入按来源类别（provenance）折算上限（PROVENANCE_CAP）；None = 不构成上限（不弱化）；
  - 弱化来源 = 链上等级恰等于有效等级的那些环节（约束环节）；有效等级为 E6 时无弱化来源。
"""
from __future__ import annotations

EVIDENCE_LEVELS = ("E0", "E1", "E2", "E3", "E4", "E5", "E6")
UNASSESSED = "unassessed"

# 输入来源类别 → 等级上限。None = 不构成上限。
#   user / standard_constant：由使用者或标准常数给定，其可靠性不属于公式链，不弱化；
#   optimizer：优化器给的试探值，只是被评估的设计点，不弱化（优化器本身只填 not_assessed）；
#   derived：由模型外部先行推导，上游链不可见 → 至多 E1（仅自洽）；
#   evidence：外部证据（收据、证书、他方软件结果），本库无法重放 → 至多 E2（独立实现交叉）；
#   agent_proposed / assumption：未经人确认的建议值或假设 → E0。
PROVENANCE_CAP = {"user": None, "standard_constant": None, "optimizer": None,
                  "derived": "E1", "evidence": "E2", "agent_proposed": "E0", "assumption": "E0"}


def rank(level):
    """等级 → 序数：unassessed = -1，E0..E6 = 0..6；非法值抛 ValueError。"""
    if level == UNASSESSED:
        return -1
    if level in EVIDENCE_LEVELS:
        return EVIDENCE_LEVELS.index(level)
    raise ValueError(f"未知证据等级 {level!r}；可用 {UNASSESSED}、{'、'.join(EVIDENCE_LEVELS)}")


def label(r):
    return UNASSESSED if r < 0 else EVIDENCE_LEVELS[r]


def check_levels(mapping):
    for k, v in mapping.items():
        if v != UNASSESSED and v not in EVIDENCE_LEVELS:
            raise ValueError(f"公式 {k} 的证据等级 {v!r} 非法")
    return dict(mapping)


def propagate(order, formulas, deps, inputs, levels, caps=None):
    """order：求值顺序（公式输出名）；deps(name)：数值依赖名；inputs：名称 → 带 provenance 的输入。
    返回 {输出名: {"level", "own_level", "weakened_by": [...], "chain_size"}}。"""
    caps = PROVENANCE_CAP if caps is None else caps
    memo = {}       # 名称 → (序数 | None, frozenset 约束环节, 链上环节数)

    def node(n):
        if n in memo:
            return memo[n]
        if n in inputs:
            p = inputs[n].provenance
            cap = caps.get(p)
            out = (None, frozenset(), 1) if cap is None else (rank(cap), frozenset({("input", n, p, cap)}), 1)
        else:
            f = formulas[n]
            own = rank(levels.get(f.id, UNASSESSED))
            best, links, size = own, {("formula", n, f.id, label(own))}, 1
            for d in deps(n):
                r, ls, sz = node(d)
                size += sz
                if r is None:
                    continue
                if r < best:
                    best, links = r, set(ls)
                elif r == best:
                    links |= ls
            out = (best, frozenset(links), size)
        memo[n] = out
        return out

    res = {}
    for n in order:
        r, links, size = node(n)
        own = label(rank(levels.get(formulas[n].id, UNASSESSED)))
        weak = [] if r == len(EVIDENCE_LEVELS) - 1 else \
            [{"kind": k, "name": nm, ("id" if k == "formula" else "provenance"): x, "level": lv}
             for k, nm, x, lv in sorted(links)]
        res[n] = {"level": label(r), "own_level": own, "weakened_by": weak, "chain_size": size}
    return res
