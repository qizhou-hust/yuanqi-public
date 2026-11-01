"""纯数学优化器。

它只认识：变量（整数 / 有序选项 / 无序选项 / 连续区间）、目标（min 或 max）、约束（g ≤ 0 为可行）、参数。
它不知道齿轮、标准、单位的含义。任何领域问题都要先由"问题编译器"翻译成这里的 Problem。

结果的三类性质分开报告，互不合并（见 solve 返回的 assurance）：
  - search_claim：只描述搜索覆盖做了什么（穷举 / 网格 / 抽样 / 局部细化），不描述最优性；
  - optimality：可选的 KKT 一阶条件检查（只是必要条件的残差，不证明局部或全局最优）；
  - solver_convergence：数值过程的停止或收敛记录（不表示结果正确）；
  - evidence_level：不由优化器计算，来自公式注册表（E0–E6），这里默认 not_assessed。
结果中不存在一个合并的"可信 / 已验证"标记。
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import dual as _D
from . import nlp as _nlp

IR_SCHEMA = "gearmath.problem_ir/v1"
ASSURANCE_SCHEMA = "gearmath.assurance/v1"

VARIABLE_KINDS = ("integer", "ordered_choice", "unordered_choice", "continuous")
OBJECTIVE_SENSES = ("min", "max")
CONSTRAINT_SENSES = ("le_zero",)          # 只有一种号向：g(x) ≤ 0 为可行

# 搜索覆盖声明：固定枚举，不允许自由文本冒充
SEARCH_COVERAGE = (
    "exhaustive_over_declared_domain",    # 全部变量离散且全枚举：在声明域内穷举
    "exhaustive_over_declared_grid",      # 全枚举，但连续变量只取了网格点
    "sampled",                            # 带种子的随机抽样
    "local_nlp_from_start_point",         # solve_nlp：无离散变量，从一个起点做局部 NLP
    "exhaustive_discrete_with_local_nlp", # solve_nlp：离散组合全枚举，每个组合内连续变量做局部 NLP
    "selected_discrete_with_local_nlp",   # solve_nlp：只在调用方指定的离散组合上做局部 NLP
    "branch_and_bound_over_relaxation",   # solve_nlp：整数/有序选项连续松弛 + 分支定界
    "interval_pruned_lattice",            # gridprune：全离散，区间分支定界剪枝后逐点求值
    "interval_pruned_lattice_with_local_nlp",  # gridprune：离散格区间剪枝，剩余格点上连续变量做局部 NLP
)
SEARCH_REFINEMENT = ("none", "local_refined", "nlp_local_solve")   # local_refined：连续变量坐标搜索，非 KKT 求解
CLAIM_SCOPES = ("local",)                 # solve_nlp 的结论范围：至多是局部（一阶 KKT）候选，不声称全局
SEARCH_OUTCOME = ("feasible_found", "no_feasible_found")   # no_feasible_found ≠ 已证明不可行
OPTIMALITY_STATUS = ("not_checked", "kkt_satisfied", "kkt_violated")
GRADIENT_SOURCES = ("analytic", "finite_difference_central", "forward_mode_dual")
CONVERGENCE_STATUS = ("not_applicable", "stopped_by_step_tolerance", "converged", "not_converged")
EVIDENCE_LEVELS = ("not_assessed", "E0", "E1", "E2", "E3", "E4", "E5", "E6")

# 结果里禁止出现的合并标签（测试会检查）
FORBIDDEN_MERGED_KEYS = ("trusted", "verified", "certified", "proven", "可信")


# ---------------------------------------------------------------- 变量

@dataclass(frozen=True)
class Integer:
    name: str
    lo: int
    hi: int

    kind = "integer"

    def grid(self, n):
        return list(range(self.lo, self.hi + 1))

    def to_dict(self):
        return {"name": self.name, "kind": self.kind, "lo": self.lo, "hi": self.hi}


@dataclass(frozen=True)
class Choice:
    """离散选项。ordered=True 表示值之间有序（如一组候选数值），否则只是类别。"""
    name: str
    values: tuple
    ordered: bool = False

    @property
    def kind(self):
        return "ordered_choice" if self.ordered else "unordered_choice"

    def grid(self, n):
        return list(self.values)

    def to_dict(self):
        return {"name": self.name, "kind": self.kind, "values": list(self.values)}


@dataclass(frozen=True)
class Continuous:
    name: str
    lo: float
    hi: float

    kind = "continuous"

    def grid(self, n):
        return [self.lo + (self.hi - self.lo) * i / (n - 1) for i in range(n)]

    def to_dict(self):
        return {"name": self.name, "kind": self.kind, "lo": float(self.lo), "hi": float(self.hi)}


def variable_from_dict(d):
    k = d.get("kind")
    if k == "integer":
        return Integer(d["name"], int(d["lo"]), int(d["hi"]))
    if k in ("ordered_choice", "unordered_choice"):
        return Choice(d["name"], tuple(d["values"]), ordered=(k == "ordered_choice"))
    if k == "continuous":
        return Continuous(d["name"], float(d["lo"]), float(d["hi"]))
    raise ValueError(f"未知变量类型 {k!r}；允许 {VARIABLE_KINDS}")


# ---------------------------------------------------------------- 目标与约束

@dataclass(frozen=True)
class Objective:
    name: str
    sense: str = "min"

    def __post_init__(self):
        if self.sense not in OBJECTIVE_SENSES:
            raise ValueError(f"目标 {self.name} 的 sense={self.sense!r} 不在 {OBJECTIVE_SENSES}")

    def to_dict(self):
        return {"name": self.name, "sense": self.sense}


@dataclass(frozen=True)
class Constraint:
    name: str
    sense: str = "le_zero"
    note: str = ""

    def __post_init__(self):
        if self.sense not in CONSTRAINT_SENSES:
            raise ValueError(f"约束 {self.name} 的 sense={self.sense!r} 不在 {CONSTRAINT_SENSES}")

    def to_dict(self):
        return {"name": self.name, "sense": self.sense, "note": self.note}


def _as_objective(o):
    return o if isinstance(o, Objective) else Objective(str(o))


def _as_constraint(c):
    return c if isinstance(c, Constraint) else Constraint(str(c))


# ---------------------------------------------------------------- Problem IR v1（纯数据）

def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


@dataclass
class ProblemIR:
    """可 JSON 序列化的问题描述。求值函数不在 IR 里，只用 evaluator_id 指名。"""
    variables: list
    objectives: list
    constraints: list = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    description: str = ""
    evaluator_id: str = ""

    def __post_init__(self):
        names = [v.name for v in self.variables]
        if len(set(names)) != len(names):
            raise ValueError(f"变量重名：{names}")
        for v in self.variables:
            if v.kind not in VARIABLE_KINDS:
                raise ValueError(f"未知变量类型 {v.kind!r}")
            if v.kind in ("integer", "continuous") and not v.lo <= v.hi:
                raise ValueError(f"变量 {v.name} 下界大于上界")
            if v.kind.endswith("choice") and not v.values:
                raise ValueError(f"变量 {v.name} 没有选项")
        self.objectives = [_as_objective(o) for o in self.objectives]
        self.constraints = [_as_constraint(c) for c in self.constraints]
        if not self.objectives:
            raise ValueError("至少需要一个目标")

    def to_dict(self):
        return {"schema": IR_SCHEMA,
                "variables": [v.to_dict() for v in self.variables],
                "objectives": [o.to_dict() for o in self.objectives],
                "constraints": [c.to_dict() for c in self.constraints],
                "parameters": dict(self.parameters),
                "description": self.description,
                "evaluator_id": self.evaluator_id}

    @classmethod
    def from_dict(cls, d):
        if d.get("schema") != IR_SCHEMA:
            raise ValueError(f"schema 应为 {IR_SCHEMA}，得到 {d.get('schema')!r}")
        return cls([variable_from_dict(v) for v in d["variables"]],
                   [Objective(o["name"], o.get("sense", "min")) for o in d["objectives"]],
                   [Constraint(c["name"], c.get("sense", "le_zero"), c.get("note", "")) for c in d.get("constraints", [])],
                   dict(d.get("parameters", {})), d.get("description", ""), d.get("evaluator_id", ""))

    def to_json(self):
        return _canonical(self.to_dict())

    def sha256(self):
        """规范 JSON（键排序、紧凑分隔、UTF-8）的 sha256；与字典键顺序无关。"""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 可求值问题（IR + 求值函数）

@dataclass
class Problem:
    variables: list
    evaluate: Callable[[dict], dict]   # x -> {"objectives": {..}, "constraints": {..}, "info": {..}}
    objectives: list                   # 名字字符串（默认 min）或 Objective
    description: str = ""
    constraints: list = field(default_factory=list)   # 可选：声明的约束名；为空表示未声明
    parameters: dict = field(default_factory=dict)
    evaluator_id: str = ""
    # 可选解析梯度：x -> {"objectives": {k: {变量: ∂}}, "constraints": {g: {变量: ∂}}}，只对连续变量
    gradient: Optional[Callable[[dict], dict]] = None

    def ir(self) -> ProblemIR:
        return ProblemIR(list(self.variables), list(self.objectives), list(self.constraints),
                         dict(self.parameters), self.description, self.evaluator_id)

    @classmethod
    def from_ir(cls, ir, evaluate, gradient=None):
        if isinstance(ir, dict):
            ir = ProblemIR.from_dict(ir)
        return cls(list(ir.variables), evaluate, list(ir.objectives), ir.description,
                   list(ir.constraints), dict(ir.parameters), ir.evaluator_id, gradient)

    @property
    def objective_specs(self):
        return [_as_objective(o) for o in self.objectives]


@dataclass
class Solution:
    x: dict
    objectives: dict
    constraints: dict
    info: dict = field(default_factory=dict)
    feasibility_tol: float = 0.0     # 默认严格 g ≤ 0；solve_nlp 的点按 NLP 的原始可行容差判定（并在 assurance 里报告残差）

    @property
    def feasible(self):
        return all(g <= self.feasibility_tol for g in self.constraints.values())


def _signed(sol, specs):
    return tuple(sol.objectives[o.name] * (1 if o.sense == "min" else -1) for o in specs)


def dominates(a: Solution, b: Solution, keys, senses=None):
    s = [1 if (senses or {}).get(k, "min") == "min" else -1 for k in keys]
    return (all(si * a.objectives[k] <= si * b.objectives[k] for si, k in zip(s, keys))
            and any(si * a.objectives[k] < si * b.objectives[k] for si, k in zip(s, keys)))


def pareto(solutions, keys, senses=None):
    front = [s for s in solutions if not any(dominates(o, s, keys, senses) for o in solutions if o is not s)]
    sg = [1 if (senses or {}).get(k, "min") == "min" else -1 for k in keys]
    return sorted(front, key=lambda s: tuple(si * s.objectives[k] for si, k in zip(sg, keys)))


def _evaluate(problem, x):
    out = problem.evaluate(x)
    sol = Solution(x, out["objectives"], out["constraints"], out.get("info", {}))
    declared = {_as_constraint(c).name for c in problem.constraints}
    missing = declared - set(sol.constraints)
    if missing:
        raise ValueError(f"求值结果缺少声明的约束：{sorted(missing)}")
    return sol


def solve(problem: Problem, *, grid_points=7, max_evals=20000, refine=True, seed=0, weights=None,
          kkt_check=False, kkt_options=None):
    specs = problem.objective_specs
    keys = [o.name for o in specs]
    senses = {o.name: o.sense for o in specs}
    axes = [v.grid(grid_points) for v in problem.variables]
    total = 1
    for a in axes:
        total *= len(a)
    rng = random.Random(seed)
    has_cont = any(isinstance(v, Continuous) for v in problem.variables)
    if total <= max_evals:
        points = itertools.product(*axes)
        coverage = "exhaustive_over_declared_grid" if has_cont else "exhaustive_over_declared_domain"
    else:
        points = (tuple(rng.choice(a) for a in axes) for _ in range(max_evals))
        coverage = "sampled"
    names = [v.name for v in problem.variables]
    evaluated, n = [], 0
    for p in points:
        evaluated.append(_evaluate(problem, dict(zip(names, p))))
        n += 1
    feasible = [s for s in evaluated if s.feasible]
    front = pareto(feasible, keys, senses)
    w = weights or {k: 1.0 for k in keys}
    refined_done = False
    stop_records = []
    if refine and front and has_cont:
        refined = []
        for s in front:
            r, extra, rec = _local_refine(problem, s, w, senses)
            n += extra
            refined.append(r)
            stop_records.append(rec)
        front = pareto(refined + front, keys, senses)
        refined_done = True

    search_claim = {
        "coverage": coverage,
        "refinement": "local_refined" if refined_done else "none",
        "outcome": "feasible_found" if feasible else "no_feasible_found",
        "grid_points_per_continuous_variable": grid_points if has_cont else None,
        "seed": seed if coverage == "sampled" else None,
        "statement": _search_statement(coverage, refined_done, bool(feasible)),
        "not_claimed": ["global_optimality", "local_optimality", "proven_infeasibility"],
    }
    if kkt_check:
        optimality = [dict(kkt_first_order(problem, s.x, weights=w, **(kkt_options or {})), point=i)
                      for i, s in enumerate(front)]
    else:
        optimality = [{"point": i, "status": "not_checked", "reason": "未请求 KKT 检查（solve(kkt_check=True) 可开启）"}
                      for i in range(len(front))]
    convergence = {
        "kind": "optimizer_termination",
        "status": "stopped_by_step_tolerance" if refined_done else "not_applicable",
        "criterion": "坐标步长 < 1e-6 × 变量区间宽度" if refined_done else None,
        "meaning": "只说明局部坐标搜索已停止，不表示最优，也不表示结果正确",
        "per_point": stop_records,
    }
    assurance = {
        "schema": ASSURANCE_SCHEMA,
        "search_claim": search_claim,
        "optimality": optimality,
        "solver_convergence": convergence,
        "evidence_level": evidence_level_placeholder(),
    }
    validate_assurance(assurance)
    return {"coverage": coverage, "evaluations": n, "grid_size": total,
            "feasible": len(feasible), "pareto": front,
            "claim": search_claim["statement"],
            "problem_ir_sha256": problem.ir().sha256(),
            "assurance": assurance}


def _search_statement(coverage, refined, found):
    s = {"exhaustive_over_declared_domain": "在声明的离散域内穷举",
         "exhaustive_over_declared_grid": "在声明网格上穷举（连续变量只取网格点）",
         "sampled": "带种子随机抽样，未覆盖全部组合"}[coverage]
    if refined:
        s += "，再对连续变量做坐标搜索细化"
    s += "；给出的是已评估点中的非支配解" if found else "；未找到可行点（不等于已证明不可行）"
    return s + "。不声称全局或局部最优。"


def evidence_level_placeholder():
    return {"value": "not_assessed", "source": "formula_registry", "scale": "E0–E6",
            "note": "证据等级由公式注册表按依赖链给出，优化器不计算、不提升它"}


def validate_assurance(a):
    """检查 assurance 记录只用固定枚举，且没有合并的可信标签。"""
    sc = a["search_claim"]
    if sc["coverage"] not in SEARCH_COVERAGE:
        raise ValueError(f"search_claim.coverage={sc['coverage']!r} 不在 {SEARCH_COVERAGE}")
    if sc["refinement"] not in SEARCH_REFINEMENT:
        raise ValueError(f"search_claim.refinement={sc['refinement']!r} 不在 {SEARCH_REFINEMENT}")
    if sc["outcome"] not in SEARCH_OUTCOME:
        raise ValueError(f"search_claim.outcome={sc['outcome']!r} 不在 {SEARCH_OUTCOME}")
    if "claim_scope" in sc and sc["claim_scope"] not in CLAIM_SCOPES:
        raise ValueError(f"search_claim.claim_scope={sc['claim_scope']!r} 不在 {CLAIM_SCOPES}")
    for rec in a["optimality"]:
        if rec["status"] not in OPTIMALITY_STATUS:
            raise ValueError(f"optimality.status={rec['status']!r} 不在 {OPTIMALITY_STATUS}")
        if rec.get("gradient_source") not in (None,) + GRADIENT_SOURCES:
            raise ValueError(f"gradient_source={rec['gradient_source']!r} 不在 {GRADIENT_SOURCES}")
        so = rec.get("second_order_check")
        if so is not None and so.get("status") not in _nlp.SECOND_ORDER_STATUS:
            raise ValueError(f"second_order_check.status={so.get('status')!r} 不在 {_nlp.SECOND_ORDER_STATUS}")
    if a["solver_convergence"]["status"] not in CONVERGENCE_STATUS:
        raise ValueError(f"solver_convergence.status 不在 {CONVERGENCE_STATUS}")
    term = a["solver_convergence"].get("termination")
    if term is not None and term not in _nlp.TERMINATION + _nlp.BNB_TERMINATION:
        raise ValueError(f"solver_convergence.termination={term!r} 不在 {_nlp.TERMINATION + _nlp.BNB_TERMINATION}")
    if a["evidence_level"]["value"] not in EVIDENCE_LEVELS:
        raise ValueError(f"evidence_level 不在 {EVIDENCE_LEVELS}")
    bad = [k for k in _all_keys(a) if any(f in str(k).lower() for f in FORBIDDEN_MERGED_KEYS)]
    if bad:
        raise ValueError(f"assurance 不允许合并的可信标签：{bad}")
    return a


def _all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _all_keys(v)


def _local_refine(problem, s: Solution, w, senses):
    """只动连续变量的坐标搜索；保持可行，按加权目标下降。这不是 KKT 求解器。"""
    cont = [v for v in problem.variables if isinstance(v, Continuous)]
    best, evals = s, 0
    score = lambda q: sum(w[k] * (1 if senses.get(k, "min") == "min" else -1) * q.objectives[k] for k in w)
    for v in cont:
        step = (v.hi - v.lo) / 8
        while step > (v.hi - v.lo) * 1e-6:
            moved = False
            for sgn in (-1, 1):
                x = dict(best.x)
                x[v.name] = min(v.hi, max(v.lo, x[v.name] + sgn * step))
                cand = _evaluate(problem, x)
                evals += 1
                if cand.feasible and score(cand) < score(best) - 1e-12:
                    best, moved = cand, True
                    break
            if not moved:
                step /= 2
    return best, evals, {"evaluations": evals, "sweeps": 1 if cont else 0}


# ---------------------------------------------------------------- KKT 一阶条件检查

def kkt_first_order(problem: Problem, x: dict, *, weights=None, fd_step=1e-6, active_tol=1e-4,
                    tol_stationarity=1e-4, tol_primal=1e-8, tol_complementarity=1e-4, max_active=12):
    """在给定点检查 KKT 一阶必要条件（整数与选项变量固定，只对连续变量）。

    多目标按 weights 加权标量化（max 目标取负）。变量上下界作为约束一并处理。
    报告驻点残差、原始可行残差、互补松弛残差、积极集与乘子。
    kkt_satisfied 只表示一阶必要条件在容差内成立：不检查约束规范（LICQ 等）和二阶条件，
    不证明局部或全局最优；在非光滑约束处没有意义。
    """
    cont = [v for v in problem.variables if isinstance(v, Continuous)]
    fixed = {v.name: x[v.name] for v in problem.variables if not isinstance(v, Continuous)}
    base = {"property": "kkt_first_order", "fixed_variables": fixed, "gradient_source": None,
            "meaning": "一阶必要条件残差；不检查约束规范与二阶条件，不证明局部或全局最优"}
    if not cont:
        return dict(base, status="not_checked", reason="没有连续变量，KKT 不适用")
    specs = problem.objective_specs
    w = weights or {o.name: 1.0 for o in specs}
    sg = {o.name: (1.0 if o.sense == "min" else -1.0) for o in specs}
    sol = _evaluate(problem, dict(x))
    cnames = sorted(sol.constraints)
    g = {c: float(sol.constraints[c]) for c in cnames}
    names = [v.name for v in cont]

    if problem.gradient is not None:
        src = _supplied_gradient_source(problem.gradient)
        gr = problem.gradient(dict(x))
        df = [sum(w[k] * sg[k] * gr["objectives"][k].get(n, 0.0) for k in w) for n in names]
        dg = {c: [gr["constraints"][c].get(n, 0.0) for n in names] for c in cnames}
    else:
        src = "finite_difference_central"
        df = [0.0] * len(names)
        dg = {c: [0.0] * len(names) for c in cnames}
        for i, v in enumerate(cont):
            h = fd_step * max(1.0, abs(x[v.name]))
            up, dn = min(v.hi, x[v.name] + h), max(v.lo, x[v.name] - h)
            if up == dn:
                continue
            xu, xd = dict(x), dict(x)
            xu[v.name], xd[v.name] = up, dn
            su, sd = _evaluate(problem, xu), _evaluate(problem, xd)
            df[i] = sum(w[k] * sg[k] * (su.objectives[k] - sd.objectives[k]) for k in w) / (up - dn)
            for c in cnames:
                dg[c][i] = (su.constraints[c] - sd.constraints[c]) / (up - dn)
    # 变量界：lo - x ≤ 0，x - hi ≤ 0
    for i, v in enumerate(cont):
        e = [0.0] * len(names)
        e[i] = -1.0
        g[f"{v.name}.lower_bound"] = v.lo - x[v.name]
        dg[f"{v.name}.lower_bound"] = e
        e = [0.0] * len(names)
        e[i] = 1.0
        g[f"{v.name}.upper_bound"] = x[v.name] - v.hi
        dg[f"{v.name}.upper_bound"] = e

    primal = max(0.0, max(g.values()))
    active = [c for c in g if g[c] >= -active_tol]
    base.update(gradient_source=src, active_set=active,
                tolerances={"active": active_tol, "stationarity": tol_stationarity,
                            "primal": tol_primal, "complementarity": tol_complementarity},
                scalarization={k: w[k] * sg[k] for k in w})
    if len(active) > max_active:
        return dict(base, status="not_checked", reason=f"积极集 {len(active)} 个 > {max_active}，未做乘子枚举")
    lam, resid = _nnls_enumerate([dg[c] for c in active], [-d for d in df])
    r = [df[i] + sum(lam[j] * dg[c][i] for j, c in enumerate(active)) for i in range(len(names))]
    # 驻点与互补残差都按 max(1, ‖∇f‖∞) 归一化，使判据与目标的量级无关；绝对值一并报告
    scale = max(1.0, max(abs(t) for t in df))
    stat_abs = max(abs(t) for t in r)
    comp_abs = max([abs(lam[j] * g[c]) for j, c in enumerate(active)] or [0.0])
    stat_rel, comp = stat_abs / scale, comp_abs / scale
    ok = stat_rel <= tol_stationarity and primal <= tol_primal and comp <= tol_complementarity
    return dict(base, status="kkt_satisfied" if ok else "kkt_violated",
                multipliers={c: lam[j] for j, c in enumerate(active)},
                residuals={"stationarity": stat_rel, "stationarity_abs": stat_abs,
                           "primal_feasibility": primal, "complementarity": comp, "complementarity_abs": comp_abs,
                           "normalization": scale,
                           "dual_feasibility": 0.0})


def _nnls_enumerate(cols, b):
    """min ‖Σ λ_j a_j − b‖₂，λ ≥ 0。积极集很小，直接枚举支撑集（零依赖）。"""
    k = len(cols)
    best, best_r = [0.0] * k, math.sqrt(sum(t * t for t in b))
    for size in range(1, k + 1):
        for S in itertools.combinations(range(k), size):
            sol = _lstsq([cols[j] for j in S], b)
            if sol is None or any(s < 0 for s in sol):
                continue
            res = [b[i] - sum(sol[t] * cols[j][i] for t, j in enumerate(S)) for i in range(len(b))]
            rn = math.sqrt(sum(t * t for t in res))
            if rn < best_r - 1e-15:
                best_r = rn
                best = [0.0] * k
                for t, j in enumerate(S):
                    best[j] = sol[t]
    return best, best_r


def _lstsq(cols, b):
    """正规方程 + 部分主元消去；奇异返回 None。"""
    m = len(cols)
    A = [[sum(cols[p][i] * cols[q][i] for i in range(len(b))) for q in range(m)]
         + [sum(cols[p][i] * b[i] for i in range(len(b)))] for p in range(m)]
    for c in range(m):
        piv = max(range(c, m), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-14:
            return None
        A[c], A[piv] = A[piv], A[c]
        for r in range(m):
            if r != c:
                f = A[r][c] / A[c][c]
                A[r] = [A[r][t] - f * A[c][t] for t in range(m + 1)]
    return [A[i][m] / A[i][i] for i in range(m)]


# ---------------------------------------------------------------- 局部 NLP（kernel/nlp.py）接入

NLP_NOT_CLAIMED = ["global_optimality", "second_order_local_optimality", "proven_infeasibility"]


PIECEWISE_INFO_KEY = "piecewise_branches"   # 可选：求值 info 中的分支签名 [(节点标识, 命中分支), …]


class _RegimeLog:
    """记录求值点处分段/取整节点的命中分支（若求值函数在 info[PIECEWISE_INFO_KEY] 中给出）。
    只做记录：松弛求值用的是精确分段公式（命中分支的值与导数），不做光滑化。"""

    def __init__(self):
        self.evaluations = 0
        self.first = None
        self.seen = {}
        self.signatures = set()

    def add(self, info):
        sig = info.get(PIECEWISE_INFO_KEY) if isinstance(info, dict) else None
        if sig is None:
            return
        sig = tuple(tuple(t) for t in sig)
        self.evaluations += 1
        self.signatures.add(sig)
        for node, branch in sig:
            self.seen.setdefault(node, set()).add(branch)

    def report(self):
        if not self.evaluations:
            return None
        switched = sorted(k for k, v in self.seen.items() if len(v) > 1)
        return {"evaluations_recorded": self.evaluations, "distinct_regimes": len(self.signatures),
                "nodes_recorded": len(self.seen), "nodes_switched": switched,
                "meaning": ("求值使用精确分段公式（命中分支的值与导数，未光滑化）；nodes_switched 非空表示"
                            "求解过程中跨越了分段边界，该处函数不光滑，KKT/松弛界在跨越处无意义")}


def _supplied_gradient_source(gradient):
    """A supplied callable may declare numerical provenance; never relabel it."""
    source = getattr(gradient, 'gradient_source', 'analytic')
    if source not in GRADIENT_SOURCES:
        raise ValueError(f'Unknown supplied gradient source: {source!r}')
    return source


def _problem_oracle(problem, names, fixed, w, sg, cnames, regimes=None):
    """Problem（离散变量已固定）→ nlp oracle。优先用 problem.gradient（解析），否则对偶数前向求导。"""
    def point(v):
        x = dict(fixed)
        x.update(zip(names, v))
        return x

    if problem.gradient is not None:
        def oracle(v):
            x = point([float(t) for t in v])
            sol = _evaluate(problem, x)
            if regimes is not None:
                regimes.add(sol.info)
            gr = problem.gradient(dict(x))
            f = sum(w[k] * sg[k] * float(sol.objectives[k]) for k in w)
            df = [sum(w[k] * sg[k] * gr["objectives"].get(k, {}).get(n, 0.0) for k in w) for n in names]
            g = [float(sol.constraints[c]) for c in cnames]
            Jg = [[float(gr["constraints"].get(c, {}).get(n, 0.0)) for n in names] for c in cnames]
            return f, g, [], df, Jg, []
        oracle.gradient_source = _supplied_gradient_source(problem.gradient)
        return oracle

    def fun(xs):
        sol = _evaluate(problem, point(xs))
        if regimes is not None:
            regimes.add(sol.info)
        return (sum(w[k] * sg[k] * sol.objectives[k] for k in w), [sol.constraints[c] for c in cnames])
    return _nlp.dual_oracle(fun)


def _gradient_self_check(oracle, x, lb, ub, rel_tol=1e-4):
    """精确导数 vs 中心差分（只作自检，不用作求解梯度）。"""
    f, g, _, df, Jg, _ = oracle(list(x))
    worst = 0.0
    for k in range(len(x)):
        h = 1e-6 * max(1.0, abs(x[k]))
        up, dn = min(ub[k], x[k] + h), max(lb[k], x[k] - h)
        if up == dn:
            continue
        xu, xd = list(x), list(x)
        xu[k], xd[k] = up, dn
        fu, gu, *_ = oracle(xu)
        fd_, gd, *_ = oracle(xd)
        pairs = [(df[k], (fu - fd_) / (up - dn))] + [(Jg[i][k], (gu[i] - gd[i]) / (up - dn)) for i in range(len(g))]
        for a, b in pairs:
            worst = max(worst, abs(a - b) / max(1.0, abs(a), abs(b)))
    return {"method": "central_difference_vs_exact", "max_rel_diff": worst, "rel_tol": rel_tol,
            "status": "consistent" if worst <= rel_tol else "inconsistent",
            "meaning": "仅自检导数实现；差分值不参与求解"}


def solve_nlp(problem: Problem, *, weights=None, x0=None, discrete_assignments=None, relax_discrete=False,
              max_discrete=500, gradient_check=True, kkt_crosscheck=True, second_order=True, **nlp_options):
    """用零依赖局部 NLP 求解器（增广拉格朗日 + 带界拟牛顿，精确导数）求解 Problem。

    多目标按 weights 加权标量化（max 目标取负），得到单个点。
    离散变量：
      - relax_discrete=False（默认）：离散组合全枚举（或只取 discrete_assignments），每个组合内对连续变量做局部 NLP；
      - relax_discrete=True：整数与有序选项连续松弛 + 分支定界（求值函数必须接受非整数值），无序选项枚举。
    second_order=True：在最终 KKT 点做二阶条件数值检查（nlp.second_order_check），作为
    optimality[].second_order_check 独立字段报告，不改变一阶 status，也不进入 not_claimed 以外的任何结论。
    assurance 四项分开：search_claim（claim_scope=local）、optimality（KKT 残差 + 独立复核）、
    solver_convergence（停止原因）、evidence_level（不由优化器给出）。
    """
    specs = problem.objective_specs
    keys = [o.name for o in specs]
    w = weights or {k: 1.0 for k in keys}
    sg = {o.name: (1.0 if o.sense == "min" else -1.0) for o in specs}
    x0 = dict(x0 or {})
    cont = [v for v in problem.variables if isinstance(v, Continuous)]
    disc = [v for v in problem.variables if not isinstance(v, Continuous)]
    relaxed = [v for v in disc if relax_discrete and (isinstance(v, Integer) or (isinstance(v, Choice) and v.ordered))]
    enumerated = [v for v in disc if v not in relaxed]

    if discrete_assignments is not None:
        assignments = [{v.name: a[v.name] for v in enumerated} for a in discrete_assignments]
        coverage = "selected_discrete_with_local_nlp"
    else:
        total = 1
        for v in enumerated:
            total *= len(v.grid(0))
        if total > max_discrete:
            raise ValueError(f"离散组合 {total} 个 > max_discrete={max_discrete}；请给 discrete_assignments 或 relax_discrete=True")
        assignments = [dict(zip([v.name for v in enumerated], p)) for p in itertools.product(*[v.grid(0) for v in enumerated])]
        coverage = ("branch_and_bound_over_relaxation" if relaxed else
                    "exhaustive_discrete_with_local_nlp" if enumerated else "local_nlp_from_start_point")
    if relaxed and discrete_assignments is not None:
        coverage = "branch_and_bound_over_relaxation"

    nvars = cont + relaxed
    names = [v.name for v in nvars]
    lb = [float(v.lo) if not isinstance(v, Choice) else float(min(v.values)) for v in nvars]
    ub = [float(v.hi) if not isinstance(v, Choice) else float(max(v.values)) for v in nvars]
    start = [float(x0.get(n, 0.5 * (l + u))) for n, l, u in zip(names, lb, ub)]
    int_idx = [i for i, v in enumerate(nvars) if isinstance(v, Integer)]
    set_idx = {i: tuple(float(t) for t in v.values) for i, v in enumerate(nvars) if isinstance(v, Choice)}

    def scalar(sol):
        return sum(w[k] * sg[k] * sol.objectives[k] for k in w)

    records, evaluations, bnb_records = [], 0, []
    grad_check = None
    regimes = _RegimeLog()
    for a in assignments:
        if not names:
            sol = _evaluate(problem, dict(a))
            evaluations += 1
            records.append({"assignment": a, "x": dict(a), "solution": sol, "nlp": None, "value": scalar(sol)})
            continue
        probe = dict(a)
        probe.update(zip(names, start))
        cnames = sorted(_evaluate(problem, probe).constraints)
        evaluations += 1
        oracle = _problem_oracle(problem, names, a, w, sg, cnames, regimes)
        if gradient_check and grad_check is None:
            grad_check = _gradient_self_check(oracle, start, lb, ub)
            evaluations += 1 + 2 * len(names)
        if relaxed:
            t0 = time.perf_counter()
            mr = _nlp.minimize_mixed(x0=start, lb=lb, ub=ub, oracle=oracle, integers=int_idx, discrete=set_idx,
                                     **nlp_options)
            evaluations += mr.evaluations
            bnb_records.append({"assignment": a, "termination": mr.termination, "nodes": mr.nodes,
                                "lower_bound": mr.lower_bound, "gap_abs": mr.gap_abs, "gap_rel": mr.gap_rel,
                                "pruned": mr.pruned, "evaluations": mr.evaluations,
                                "wall_time_s": time.perf_counter() - t0})
            r = mr.nlp
            if r is None:
                records.append({"assignment": a, "x": None, "solution": None, "nlp": None, "value": None,
                                "termination": mr.termination})
                continue
        else:
            r = _nlp.minimize(x0=start, lb=lb, ub=ub, oracle=oracle, **nlp_options)
            evaluations += r.evaluations
        x = dict(a)
        for v, t in zip(nvars, r.x):
            x[v.name] = int(round(t)) if isinstance(v, Integer) else (
                min(v.values, key=lambda c: abs(c - t)) if isinstance(v, Choice) else t)
        sol = _evaluate(problem, x)
        sol.feasibility_tol = r.tolerances["tol_feasibility"]
        evaluations += 1
        if relaxed:
            fix_lb = [t if i in int_idx or i in set_idx else l for i, (t, l) in enumerate(zip(r.x, lb))]
            fix_ub = [t if i in int_idx or i in set_idx else u for i, (t, u) in enumerate(zip(r.x, ub))]
        else:
            fix_lb, fix_ub = lb, ub
        records.append({"assignment": a, "x": x, "solution": sol, "nlp": r, "value": scalar(sol),
                        "names": names, "cnames": cnames, "termination": r.termination,
                        "oracle": oracle, "lb": fix_lb, "ub": fix_ub})

    feas = [rec for rec in records if rec["solution"] is not None and rec["solution"].feasible]
    best = min(feas, key=lambda rec: (not (rec["nlp"] is None or rec["nlp"].converged), rec["value"])) if feas else None

    optimality = []
    if best is not None:
        r = best["nlp"]
        if r is None:
            optimality.append({"point": 0, "status": "not_checked", "reason": "没有连续变量，KKT 不适用"})
        else:
            fixed_names = {v.name for v in relaxed}
            mult = {c: lam for c, lam in zip(best["cnames"], r.multipliers["ineq"])}
            for n, nl, nu in zip(best["names"], r.multipliers["lower"], r.multipliers["upper"]):
                if n in fixed_names:
                    continue
                mult[f"{n}.lower_bound"] = nl
                mult[f"{n}.upper_bound"] = nu
            rec = {"point": 0, "property": "kkt_first_order",
                   "status": "kkt_satisfied" if r.kkt_satisfied else "kkt_violated",
                   "gradient_source": r.gradient_source, "multipliers": mult,
                   "multiplier_convention": r.convention, "residuals": dict(r.residuals), "tolerances": dict(r.tolerances),
                   "fixed_variables": {k: best["x"][k] for k in best["x"] if k not in {v.name for v in cont}},
                   "scalarization": {k: w[k] * sg[k] for k in w},
                   "gradient_self_check": grad_check,
                   "meaning": "一阶必要条件残差（原始量纲复算）；不检查约束规范与二阶条件，不证明局部或全局最优"}
            if kkt_crosscheck:
                ind = kkt_first_order(problem, best["x"], weights=w)
                rec["independent_check"] = {"method": "kkt_first_order（积极集 NNLS 重估乘子）",
                                            "status": ind["status"], "gradient_source": ind.get("gradient_source"),
                                            "residuals": ind.get("residuals"), "multipliers": ind.get("multipliers")}
            if second_order:
                so = _nlp.second_order_check(best["oracle"], r.x, best["lb"], best["ub"], r.multipliers)
                so["variables"] = list(best["names"])
                so["applies_to"] = "最终点（整数/选项已固定，只对连续变量的切空间）" if relaxed else "最终点"
                rec["second_order_check"] = so
            optimality.append(rec)

    nb = best["nlp"] if best is not None else next((rec["nlp"] for rec in records if rec["nlp"] is not None), None)
    termination = nb.termination if nb is not None else None
    search_claim = {
        "coverage": coverage, "refinement": "nlp_local_solve",
        "outcome": "feasible_found" if feas else "no_feasible_found",
        "claim_scope": "local",
        "grid_points_per_continuous_variable": None, "seed": None,
        "discrete_assignments_solved": len(assignments),
        "branch_and_bound": ({"per_assignment": bnb_records, "bound_assumption": _nlp.BNB_BOUND_ASSUMPTION}
                             if relaxed else None),
        "nonsmooth_regimes": regimes.report(),
        "statement": ("连续变量由局部 NLP（增广拉格朗日 + 带界拟牛顿，精确导数）求解"
                      + {"local_nlp_from_start_point": "，单起点",
                         "exhaustive_discrete_with_local_nlp": "，离散组合在声明域内全枚举",
                         "selected_discrete_with_local_nlp": "，只在指定离散组合上求解",
                         "branch_and_bound_over_relaxation": "，整数/有序选项经松弛分支定界（gap 仅在松弛为凸时是有效界）"}[coverage]
                      + ("；给出点至多是一阶 KKT 局部候选" if feas else "；未找到可行点（局部不可行不等于已证明不可行）")
                      + ("。二阶条件只作独立数值检查（见 optimality[].second_order_check），不并入一阶结论"
                         if second_order else "。未检查二阶条件")
                      + "，不声称全局最优。"),
        "not_claimed": list(NLP_NOT_CLAIMED),
    }
    convergence = {
        "kind": "optimizer_termination",
        "status": "converged" if termination == "kkt_tolerances_met" else ("not_converged" if nb is not None else "not_applicable"),
        "termination": termination,
        "criterion": "原始量纲 KKT 残差：stationarity、primal、dual、complementarity 均 ≤ 容差",
        "outer_iterations": nb.outer_iterations if nb else 0,
        "inner_iterations": nb.inner_iterations if nb else 0,
        "per_assignment": [{"assignment": rec["assignment"], "termination": rec.get("termination"),
                            "scalarized_objective": rec["value"],
                            "outer_iterations": rec["nlp"].outer_iterations if rec["nlp"] else 0,
                            "evaluations": rec["nlp"].evaluations if rec["nlp"] else 0} for rec in records],
        "meaning": "只说明数值过程为何停止；KKT 达标不表示结果正确，也不表示全局最优",
    }
    assurance = {"schema": ASSURANCE_SCHEMA, "search_claim": search_claim, "optimality": optimality,
                 "solver_convergence": convergence, "evidence_level": evidence_level_placeholder()}
    validate_assurance(assurance)
    return {"coverage": coverage, "evaluations": evaluations, "feasible": len(feas),
            "pareto": [best["solution"]] if best else [], "solution": best["solution"] if best else None,
            "scalarized_objective": best["value"] if best else None, "nlp": best["nlp"] if best else nb,
            "claim": search_claim["statement"], "problem_ir_sha256": problem.ir().sha256(),
            "assurance": assurance}
