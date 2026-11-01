"""剪枝格搜索（零依赖，纯数学）：离散格上的区间分支定界 + 叶子上的精确梯度局部 NLP。

输入：optimize.Problem（整数 / 有序选项 / 无序选项 / 连续变量）与一个保证包含的界函数 bounds(box)
（box：{变量: (lo, hi)}；离散变量给出当前子格的取值包络，连续变量给出区间；返回目标与约束的区间，
None 表示给不出保证界）。本模块不知道变量与量的含义。

算法：
  1. 根节点 = 全部离散变量的完整取值下标区间；按"父节点下界"最佳优先出队（计数器保证确定性）。
  2. 每个节点调用一次 bounds：
       - 某约束区间下端 > 可行容差 → 整个子格被证明不可行，剪去（原因 = infeasible:<约束名>，取声明顺序第一条）；
       - 目标加权下界 > 当前最优（严格大于；相等不剪，以免丢并列最优）→ 剪去（原因 = bound）。
  3. 未剪且只含一个格点（叶子）：可选地对连续变量做有限次二分，再按 2 的规则逐子盒剪；
     仍存活则在该格点上求解：有连续变量 → optimize.solve_nlp（该离散组合，精确导数）；全离散 → 逐点求值。
  4. 否则按"无序选项优先、取值个数最多者"二分该变量的下标区间。
不变量：被剪的格点 + 求解的格点 = 格点总数（结果中核对）。

剪枝的正确性只依赖 bounds 的保证包含：被"不可行"剪去的格点在盒内任一点约束值都 > 容差，叶子 NLP 也给不出可行点；
被"下界"剪去的格点在盒内任一点目标都 > 当前可行解目标值。故与"逐格点求解后取最优"（exhaustive_lattice_search）
得到同一最优值与同一格点（并列时按格点下标字典序取第一个，两者规则相同）。这是与同一 NLP 的逐格结果比较，
不是全局最优证明：叶子 NLP 是局部求解器，非凸时叶子内可能另有更优点。

结果的四类性质分开报告（证据等级 / KKT / 数值收敛 / 搜索覆盖），见 assurance。
"""
from __future__ import annotations

import hashlib
import heapq
import itertools
import math
import pathlib
import time

from . import nlp as _nlp
from . import optimize as _opt
from .optimize import Choice, Continuous

SOLVER_ID = "gearmath.kernel.gridprune/v1"
_FILES = ("gridprune.py", "nlp.py", "optimize.py", "declared.py", "interval.py", "dual.py")


def solver_fingerprint():
    """求解器身份：模块 id + 相关内核源码 sha256（按文件名排序拼接后再取 sha256）。写回真源时引用。"""
    here = pathlib.Path(__file__).resolve().parent
    h = hashlib.sha256()
    for f in sorted(_FILES):
        h.update(f.encode())
        h.update(hashlib.sha256((here / f).read_bytes()).digest())
    return {"solver": SOLVER_ID, "kernel_sources_sha256": h.hexdigest(), "files": list(sorted(_FILES))}


def _axes(problem):
    disc = [v for v in problem.variables if not isinstance(v, Continuous)]
    axes = []
    for v in disc:
        vals = list(v.grid(0))
        if isinstance(v, Choice) and v.ordered:
            vals = sorted(vals)
        axes.append(vals)
    cont = [v for v in problem.variables if isinstance(v, Continuous)]
    return disc, axes, cont


def _scalar_lb(b, specs, w):
    """目标区间 -> 加权标量化下界；任一目标无界 -> −inf。"""
    tot = 0.0
    for o in specs:
        iv = b["objectives"].get(o.name)
        if iv is None:
            return -math.inf
        s = 1.0 if o.sense == "min" else -1.0
        t = w[o.name] * (iv[0] if s > 0 else -iv[1])
        tot = math.nextafter(tot + t, -math.inf)          # 向下舍入累加，保持下界性质
    return tot


def _infeasible(b, cnames, tol):
    for c in cnames:
        iv = b["constraints"].get(c)
        if iv is not None and iv[0] > tol:
            return c
    return None


def _split_cont(boxes, cont):
    """把盒按相对宽度最大的连续变量二分。"""
    out = []
    for bx in boxes:
        v = max(cont, key=lambda c: (bx[c.name][1] - bx[c.name][0]) / ((c.hi - c.lo) or 1.0))
        lo, hi = bx[v.name]
        mid = 0.5 * (lo + hi)
        a, b = dict(bx), dict(bx)
        a[v.name], b[v.name] = (lo, mid), (mid, hi)
        out += [a, b]
    return out


def _leaf_solve(problem, a, has_cont, w, nlp_options):
    """在一个格点上求解；返回记录。求值异常不吞掉结果，记为 evaluation_error。"""
    t0 = time.perf_counter()
    try:
        if has_cont:
            r = _opt.solve_nlp(problem, weights=w, discrete_assignments=[a], gradient_check=False,
                               kkt_crosscheck=False, second_order=False, **(nlp_options or {}))
            sol = r["solution"]
            nl = r["nlp"]
            rec = {"assignment": dict(a), "solution": sol, "value": r["scalarized_objective"] if sol else None,
                   "feasible": sol is not None, "evaluations": r["evaluations"],
                   "termination": nl.termination if nl is not None else None,
                   "kkt_satisfied": bool(nl.kkt_satisfied) if nl is not None else None}
        else:
            sol = _opt._evaluate(problem, dict(a))
            val = sum(w[o.name] * (1 if o.sense == "min" else -1) * sol.objectives[o.name] for o in problem.objective_specs)
            rec = {"assignment": dict(a), "solution": sol if sol.feasible else None, "value": val if sol.feasible else None,
                   "feasible": sol.feasible, "evaluations": 1, "termination": None, "kkt_satisfied": None}
    except (RuntimeError, ArithmeticError, ValueError) as ex:
        rec = {"assignment": dict(a), "solution": None, "value": None, "feasible": False, "evaluations": 0,
               "termination": "evaluation_error", "kkt_satisfied": None, "error": str(ex)[:300]}
    rec["wall_time_s"] = time.perf_counter() - t0
    return rec


def _better(rec, key, best, best_key):
    if not rec["feasible"]:
        return False
    if best is None:
        return True
    return rec["value"] < best["value"] or (rec["value"] == best["value"] and key < best_key)


def exhaustive_lattice_search(problem, *, weights=None, nlp_options=None):
    """对拍参照：逐格点求解（不剪枝），取最优；并列取格点下标字典序第一个。"""
    specs = problem.objective_specs
    w = weights or {o.name: 1.0 for o in specs}
    disc, axes, cont = _axes(problem)
    best, best_key, n, evals, records = None, None, 0, 0, []
    for key in itertools.product(*[range(len(a)) for a in axes]):
        a = {v.name: axes[i][k] for i, (v, k) in enumerate(zip(disc, key))}
        rec = _leaf_solve(problem, a, bool(cont), w, nlp_options)
        n += 1
        evals += rec["evaluations"]
        records.append(rec)
        if _better(rec, key, best, best_key):
            best, best_key = rec, key
    return {"lattice_points_total": n, "leaves_solved": n, "evaluations": evals, "best": best,
            "best_index": best_key, "records": records}


def pruned_lattice_search(problem, bounds, *, weights=None, feasibility_tol=None, leaf_subboxes=0, max_nodes=1_000_000,
                          nlp_options=None, final_checks=True, keep_records=False, keep_pruned=False):
    """剪枝格搜索。返回计数、剪枝原因分布、最优解与分开报告的 assurance（见模块说明）。

    feasibility_tol：区间判不可行的门槛（约束区间下端 > 它才剪）。缺省 = 叶子判可行所用容差
    （有连续变量时为 NLP 的原始可行容差，全离散时为 0），保证不会剪掉叶子求解会判为可行的格点。
    leaf_subboxes：叶子上连续变量最多二分到的子盒数（0 = 不细分）。
    keep_records / keep_pruned：保留每个叶子的求解记录 / 每个被剪子格（下标区间 + 原因），供对拍与审计。"""
    t_start = time.perf_counter()
    specs = problem.objective_specs
    w = weights or {o.name: 1.0 for o in specs}
    disc, axes, cont = _axes(problem)
    has_cont = bool(cont)
    if feasibility_tol is None:
        feasibility_tol = float((nlp_options or {}).get("tol_feasibility", _nlp.DEFAULTS["tol_feasibility"])) if has_cont else 0.0
    cnames = [_opt._as_constraint(c).name for c in problem.constraints]
    total = 1
    for a in axes:
        total *= len(a)
    cbox = {v.name: (float(v.lo), float(v.hi)) for v in cont}

    def box_of(node):
        bx = dict(cbox)
        for v, vals, (lo, hi) in zip(disc, axes, node):
            sub = vals[lo:hi + 1]
            bx[v.name] = (min(sub), max(sub))
        return bx

    def size(node):
        s = 1
        for lo, hi in node:
            s *= hi - lo + 1
        return s

    pruned_points, pruned_nodes = {}, {}
    unsupported = {}
    best, best_key = None, None
    nodes = interval_calls = leaves = nlp_calls = evals = 0
    leaf_fail = {}
    records = []
    counter = itertools.count()
    root = tuple((0, len(a) - 1) for a in axes)
    heap = [(-math.inf, next(counter), root)]

    pruned_log = []

    def prune(node, reason):
        pruned_points[reason] = pruned_points.get(reason, 0) + size(node)
        pruned_nodes[reason] = pruned_nodes.get(reason, 0) + 1
        if keep_pruned:
            pruned_log.append({"node": node, "reason": reason,
                               "incumbent": best["value"] if best is not None else None})

    def judge(b):
        c = _infeasible(b, cnames, feasibility_tol)
        if c is not None:
            return "infeasible:" + c, None
        lb = _scalar_lb(b, specs, w)
        if best is not None and lb > best["value"]:
            return "bound", lb
        return None, lb

    while heap:
        key_lb, _, node = heapq.heappop(heap)
        if best is not None and key_lb > best["value"]:
            prune(node, "bound")
            continue
        nodes += 1
        if nodes > max_nodes:
            raise RuntimeError(f"节点数超过 max_nodes={max_nodes}")
        need_split = [i for i, (v, (lo, hi)) in enumerate(zip(disc, node))
                      if hi > lo and isinstance(v, Choice) and not v.ordered]
        if need_split:                      # 无序选项不做区间包络，先拆开
            i = need_split[0]
            lo, hi = node[i]
            for k in range(lo, hi + 1):
                child = list(node)
                child[i] = (k, k)
                heapq.heappush(heap, (key_lb, next(counter), tuple(child)))
            continue
        b = bounds(box_of(node))
        interval_calls += 1
        for q, why in b.get("unsupported", {}).items():
            unsupported.setdefault(q, why)
        reason, lb = judge(b)
        if reason:
            prune(node, reason)
            continue
        if size(node) > 1:
            i = max(range(len(node)), key=lambda j: (node[j][1] - node[j][0], -j))
            lo, hi = node[i]
            mid = (lo + hi) // 2
            for part in ((lo, mid), (mid + 1, hi)):
                child = list(node)
                child[i] = part
                heapq.heappush(heap, (lb, next(counter), tuple(child)))
            continue
        # 叶子：可选的连续子盒细分剪枝
        if has_cont and leaf_subboxes > 1:
            boxes, reasons = [box_of(node)], {}
            while len(boxes) * 2 <= leaf_subboxes:
                boxes = _split_cont(boxes, cont)
                alive = []
                for bx in boxes:
                    bb = bounds(bx)
                    interval_calls += 1
                    rs, _ = judge(bb)
                    if rs:
                        reasons[rs] = reasons.get(rs, 0) + 1
                    else:
                        alive.append(bx)
                boxes = alive
                if not boxes:
                    break
            if not boxes:
                tag = ("subdivision:" + max(reasons, key=lambda r: (reasons[r], r)) if len(reasons) == 1
                       else "subdivision:mixed")
                prune(node, tag)
                continue
        a = {v.name: axes[i][lo] for i, (v, (lo, _)) in enumerate(zip(disc, node))}
        idx = tuple(lo for lo, _ in node)
        rec = _leaf_solve(problem, a, has_cont, w, nlp_options)
        leaves += 1
        nlp_calls += 1 if has_cont else 0
        evals += rec["evaluations"]
        if not rec["feasible"]:
            t = rec["termination"] or "infeasible_point"
            leaf_fail[t] = leaf_fail.get(t, 0) + 1
        if keep_records:
            records.append(rec)
        if _better(rec, idx, best, best_key):
            best, best_key = rec, idx

    accounted = sum(pruned_points.values()) + leaves
    if accounted != total:
        raise AssertionError(f"格点计数不守恒：剪 {sum(pruned_points.values())} + 解 {leaves} ≠ 总 {total}")

    final = None
    if best is not None and has_cont and final_checks:
        final = _opt.solve_nlp(problem, weights=w, discrete_assignments=[best["assignment"]], **(nlp_options or {}))
        nlp_calls_final = 1
    else:
        nlp_calls_final = 0
    if final is not None:
        optimality = final["assurance"]["optimality"]
        convergence = dict(final["assurance"]["solver_convergence"])
        same = (final["solution"] is not None and best["solution"] is not None
                and final["solution"].x == best["solution"].x)
        convergence["final_resolve_identical_to_leaf"] = same
    else:
        optimality = [{"point": 0, "status": "not_checked",
                       "reason": "没有连续变量，KKT 不适用" if not has_cont else "未找到可行点或未请求复核"}]
        convergence = {"kind": "optimizer_termination", "status": "not_applicable", "termination": None,
                       "meaning": "全离散问题逐点求值，无数值迭代"}
    coverage = "interval_pruned_lattice_with_local_nlp" if has_cont else "interval_pruned_lattice"
    search_claim = {
        "coverage": coverage, "refinement": "nlp_local_solve" if has_cont else "none",
        "outcome": "feasible_found" if best is not None else "no_feasible_found",
        "grid_points_per_continuous_variable": None, "seed": None,
        "statement": ("离散格上区间分支定界：被剪格点经保守区间证明不可行，或其目标下界严格劣于已知可行解；"
                      + ("剩余格点上连续变量由局部 NLP（精确导数）求解，结果与逐格点同一 NLP 求解后取最优一致；"
                         "叶子 NLP 是局部的，不声称全局最优。" if has_cont else
                         "剩余格点逐点求值；在区间包含保证成立的前提下，与在声明离散域内穷举等价。")
                      + ("" if best is not None else "未找到可行点（不等于已证明不可行，除非全部格点都被区间判为不可行）。")),
        "not_claimed": list(_opt.NLP_NOT_CLAIMED),
        "lattice": {"points_total": total, "points_pruned": sum(pruned_points.values()), "points_solved": leaves,
                    "pruned_points_by_reason": dict(sorted(pruned_points.items())),
                    "pruned_nodes_by_reason": dict(sorted(pruned_nodes.items())),
                    "nodes_visited": nodes, "interval_bound_calls": interval_calls,
                    "feasibility_tol_for_pruning": feasibility_tol, "leaf_subboxes": leaf_subboxes,
                    "bound_rule": "目标下界 > 当前可行解目标值（严格）才剪；相等保留"},
        "interval_unsupported_quantities": unsupported,
    }
    if has_cont:
        search_claim["claim_scope"] = "local"
    assurance = {"schema": _opt.ASSURANCE_SCHEMA, "search_claim": search_claim, "optimality": optimality,
                 "solver_convergence": convergence, "evidence_level": _opt.evidence_level_placeholder()}
    _opt.validate_assurance(assurance)
    return {"lattice_points_total": total, "pruned_points_by_reason": dict(sorted(pruned_points.items())),
            "points_pruned": sum(pruned_points.values()), "leaves_solved": leaves,
            "nlp_solves": nlp_calls, "nlp_solves_final_check": nlp_calls_final, "evaluations": evals,
            "interval_bound_calls": interval_calls, "nodes_visited": nodes, "leaf_failures": leaf_fail,
            "best": best, "best_index": best_key, "final": final,
            "solution": (final["solution"] if final is not None and final["solution"] is not None
                         else (best["solution"] if best else None)),
            "assurance": assurance, "problem_ir_sha256": problem.ir().sha256(),
            "solver": solver_fingerprint(), "wall_time_s": time.perf_counter() - t_start,
            "records": records, "pruned": pruned_log, "axes": [(v.name, list(a)) for v, a in zip(disc, axes)]}


def snap_to_resolution(problem, x, resolution, *, weights=None):
    """把连续变量回圆到声明分辨率的整数倍（逐变量取下/上两个格点，组合枚举 ≤ 2^k），
    只接受严格可行（g ≤ 0，零容差）且仍在变量界内的组合，取加权目标最好者。
    返回 {"x", "solution", "candidates_checked", "shift"}；无严格可行组合 -> {"x": None, ...}。"""
    specs = problem.objective_specs
    w = weights or {o.name: 1.0 for o in specs}
    cont = [v for v in problem.variables if isinstance(v, Continuous)]
    if len(cont) > 10:
        raise ValueError("回圆组合枚举只支持 ≤ 10 个连续变量")
    opts = []
    for v in cont:
        q = resolution[v.name]
        t = x[v.name] / q
        cand = sorted({math.floor(t) * q, math.ceil(t) * q})
        cand = [round(c, 12) for c in cand]
        cand = [c for c in cand if v.lo <= c <= v.hi] or [x[v.name]]
        opts.append(cand)
    best, checked = None, 0
    for combo in itertools.product(*opts):
        xx = dict(x)
        xx.update({v.name: c for v, c in zip(cont, combo)})
        try:
            sol = _opt._evaluate(problem, xx)
        except (RuntimeError, ArithmeticError, ValueError):
            continue
        checked += 1
        if not all(g <= 0.0 for g in sol.constraints.values()):
            continue
        val = sum(w[o.name] * (1 if o.sense == "min" else -1) * sol.objectives[o.name] for o in specs)
        if best is None or val < best[0]:
            best = (val, xx, sol)
    if best is None:
        return {"x": None, "solution": None, "candidates_checked": checked, "shift": None}
    return {"x": best[1], "solution": best[2], "candidates_checked": checked,
            "shift": {v.name: best[1][v.name] - x[v.name] for v in cont}}
