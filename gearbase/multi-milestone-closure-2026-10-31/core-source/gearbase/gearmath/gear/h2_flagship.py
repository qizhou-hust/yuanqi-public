"""H2 旗舰（M31 SPEC §3 ②）最小回归：两级斜齿、中心距锁定、零变位整数几何的综合，改写为声明式问题 + 剪枝格搜索。

旗舰定义（legacy/m31/_docs/SPEC.md §3 ②，只读引用，不执行 legacy 代码）：
  一级 z=20/50、β=28.955°、a=80；二级 z=19/76、β=18.195°、a=100；总传动比 i=10；
  legacy/m31/L5/gears/solver.py::synthesize_h2 的文档串：mn∈{2, 2.5, 3}、beta_range=(8, 30)、tol=0.03 时可得到该金标对。
本最小版只覆盖 SPEC §2-A 的"零变位整数几何"层（与 legacy 同口径：无强度）：
  中心距锁定 ⇒ cos β = m_n (z_a + z_b)/(2a)（β 由整数齿数与模数唯一确定，不是自由变量）；
  约束 cos β ∈ [cos 30°, cos 8°]、|i − i_req|/i_req ≤ tol（拆成两条线性界）、各级 u ≥ 1；目标 = 总传动比相对误差最小。
compile_h2 保留较宽的矩形格点演示；search_seed_domain 才是原 Stage0 问题的兼容入口：
保留种子可达域与完整次级排序，由 tools.m34_closure 实际执行只读旧求解器对照计数。
原 Stage0 明确不含强度，强度集成与 W2W / P2 不属于此 H2 同问题对照的结论。
"""
from __future__ import annotations

import math

from ..kernel import declared as DC
from ..kernel import interval as IV
from ..kernel import units as U

GOLDEN = {"m_n_1": 2.0, "m_n_2": 2.0, "z_1": 20, "z_2": 50, "z_3": 19, "z_4": 76}
GOLDEN_BETA_DEG = (28.955, 18.195)          # SPEC 印刷值（3 位小数）
QUANTITIES = ("cos_beta_1", "cos_beta_2", "i_total", "ratio_error", "u_1", "u_2")


class H2Evaluator:
    """kernel.declared 的量求值器（点值与保证包含的区间）。参数 a_1、a_2、total_ratio 须在声明 parameters 中显式给出。"""

    def __init__(self, decl):
        p = decl.get("parameters") or {}
        errs = []
        for k, unit_dim in (("a_1", "mm"), ("a_2", "mm"), ("total_ratio", "1")):
            r = p.get(k)
            if not (isinstance(r, dict) and isinstance(r.get("value"), (int, float)) and r.get("unit") and r.get("source")):
                errs.append({"path": f"$.parameters.{k}", "code": "missing", "message": f"须显式给出 {k} = {{value, unit, source}}"})
        if errs:
            from .source_optimize import OptimizeBlocked
            raise OptimizeBlocked(errs)
        self.a1 = U.from_canonical(U.to_canonical(p["a_1"]["value"], p["a_1"]["unit"]), "mm")
        self.a2 = U.from_canonical(U.to_canonical(p["a_2"]["value"], p["a_2"]["unit"]), "mm")
        self.i_req = float(p["total_ratio"]["value"])
        self.units = {v["name"]: v["unit"] for v in decl["variables"]}
        for n in ("m_n_1", "m_n_2"):
            if U.unit(self.units.get(n, "1"))[0] != U.unit("mm")[0]:
                raise ValueError(f"{n} 须为长度单位")
        self.point_calls = self.interval_calls = 0

    def _mm(self, n, v):
        return U.from_canonical(U.to_canonical(v, self.units[n]), "mm")

    def point(self, x, wrt=()):
        self.point_calls += 1
        m1, m2 = self._mm("m_n_1", x["m_n_1"]), self._mm("m_n_2", x["m_n_2"])
        z1, z2, z3, z4 = (float(x[k]) for k in ("z_1", "z_2", "z_3", "z_4"))
        c1 = m1 * (z1 + z2) / (2 * self.a1)
        c2 = m2 * (z3 + z4) / (2 * self.a2)
        i = (z2 / z1) * (z4 / z3)
        vals = {"cos_beta_1": c1, "cos_beta_2": c2, "i_total": i, "ratio_error": abs(i - self.i_req) / self.i_req,
                "u_1": z2 / z1, "u_2": z4 / z3}
        return {"status": "ok", "values": vals, "derivatives": {q: {} for q in vals},
                "applicability_violated": not (c1 <= 1.0 and c2 <= 1.0)}

    def interval(self, box, quantities=None):
        self.interval_calls += 1
        I = IV.Interval
        m1 = I(self._mm("m_n_1", box["m_n_1"][0]), self._mm("m_n_1", box["m_n_1"][1]))
        m2 = I(self._mm("m_n_2", box["m_n_2"][0]), self._mm("m_n_2", box["m_n_2"][1]))
        z = {k: I(*box[k]) for k in ("z_1", "z_2", "z_3", "z_4")}
        u1, u2 = z["z_2"] / z["z_1"], z["z_4"] / z["z_3"]
        i = u1 * u2
        vals = {"cos_beta_1": m1 * (z["z_1"] + z["z_2"]) / I(2 * self.a1),
                "cos_beta_2": m2 * (z["z_3"] + z["z_4"]) / I(2 * self.a2),
                "i_total": i, "ratio_error": IV.iabs(i - I(self.i_req)) / I(self.i_req), "u_1": u1, "u_2": u2}
        viol = vals["cos_beta_1"].lo > 1.0 or vals["cos_beta_2"].lo > 1.0
        want = quantities if quantities is not None else QUANTITIES
        return {"values": {q: (vals[q].lo, vals[q].hi) for q in want}, "unsupported": {}, "applicability_violated": viol}


def beta_deg(x, ev):
    """由锁定中心距反算的螺旋角（度），仅报告用。"""
    v = ev.point(x)["values"]
    return tuple(math.degrees(math.acos(v[k])) for k in ("cos_beta_1", "cos_beta_2"))


def compile_h2(decl):
    ev = H2Evaluator(decl)
    problem, bounds = DC.compile_declaration(decl, ev)
    return problem, bounds, ev


def seed_domain(a, modules, seeds, beta_range):
    """Stage0 reachable domain, including the original best-explaining seed rule.

    Enumerate each tooth sum once, rather than calling a full geometry verifier
    again for every seed. No strength or unconstrained tooth domain is implied.
    """
    found = {}
    for mn in modules:
        lo = max(20, math.ceil(2*a*math.cos(math.radians(beta_range[1]))/mn-1e-6))
        hi = math.floor(2*a*math.cos(math.radians(beta_range[0]))/mn+1e-6)
        for n in range(lo, hi+1):
            c = mn*n/(2*a)
            if not 0 < c <= 1:
                continue
            beta = math.degrees(math.acos(c))
            if not beta_range[0]-1e-9 <= beta <= beta_range[1]+1e-9:
                continue
            for seed in seeds:
                z = max(10, min(round(n/(1+seed)), n//2))
                ratio = (n-z)/z
                key = (float(mn), n, z)
                old = found.get(key)
                if old is None or abs(ratio-seed) < abs(old['seed_ratio']-ratio):
                    found[key] = dict(mn_mm=float(mn), teeth_sum=n, z1=z, z2=n-z,
                                      ratio=ratio, ratio_error_rel=abs(ratio-seed)/seed,
                                      seed_ratio=seed, beta_deg=beta, a_mm=float(a))
    return found


def stage0_rank(c):
    one, two = c['stage1'], c['stage2']
    return (c['ratio_error_rel'], c['sum_stage_errors'], c['volume_proxy_mm2'],
            one['mn_mm'], two['mn_mm'], one['teeth_sum'], two['teeth_sum'], one['z1'], two['z1'])


def verify_stage0_geometry(candidate, a1, a2, total_ratio, beta_range, tolerance):
    """Direct L2 mesh recheck, independent of sampled search bookkeeping.

    Does not establish strength, rank or completeness of the sampled domain.
    """
    product = 1.
    for stage, center in ((candidate['stage1'], a1), (candidate['stage2'], a2)):
        cosine = stage['mn_mm']*(stage['z1']+stage['z2'])/(2*center)
        if not 0 < cosine <= 1:return False
        beta = math.degrees(math.acos(cosine))
        mesh_sum = 2*center*math.cos(math.radians(beta))/stage['mn_mm']
        if not (stage['z1'] >= 10 and stage['z2'] >= stage['z1']
                and beta_range[0] <= beta <= beta_range[1]
                and abs(mesh_sum-round(mesh_sum)) <= 1e-6):return False
        product *= stage['z2']/stage['z1']
    return abs(product-total_ratio)/total_ratio <= tolerance and product == candidate['i_total']


def search_seed_domain(a1=80., a2=100., total_ratio=10., mn_series=(2., 2.5, 3.),
                       ratio_splits=None, beta_range=(8., 30.), tol=.03, max_candidates=40, prune=True):
    """Same Stage0 sampled problem and lexicographic ranking; prune ratio boxes.

    The existing rectangular declaration remains a wider-domain demonstration.
    This entry point is the compatibility closure for the original H2 problem.
    """
    from bisect import bisect_left, bisect_right
    if (min(a1,a2) <= 0 or total_ratio < 1 or tol <= 0 or not mn_series
            or min(mn_series) <= 0 or not 0 < beta_range[0] <= beta_range[1] < 45):
        raise ValueError('invalid H2 geometry inputs')
    if ratio_splits:
        seeds = sorted({float(v) for s in ratio_splits for v in (s if isinstance(s,(tuple,list)) else [s]) if v >= 1})
    else:
        lo = max(1., math.ceil(total_ratio/8/.05)*.05)
        hi = min(8., total_ratio)
        seeds = [round(lo+k*.05,6) for k in range(max(0,math.floor((hi-lo)/.05)+1))]
    # Match original cap rather than silently broadening the sampled domain.
    if len(mn_series)*len(seeds) > 8000:
        raise ValueError('H2 seed request exceeds original verifier-call cap')
    one = seed_domain(a1,mn_series,seeds,beta_range)
    two = seed_domain(a2,mn_series,seeds,beta_range)
    if len(one)*len(two) > 1_000_000:
        raise ValueError('H2 request exceeds original pair cap')
    rows = sorted(two.values(),key=lambda r:r['ratio'])
    ratios = [r['ratio'] for r in rows]
    candidates, calls = [], 0
    for s1 in one.values():
        # Outward margins only enlarge the selected interval; exact test below
        # retains the original floating predicate, including boundary points.
        lower = total_ratio*(1-tol)/s1['ratio']
        upper = total_ratio*(1+tol)/s1['ratio']
        margin = 1e-12*max(1,abs(lower),abs(upper))
        subset = rows[bisect_left(ratios,lower-margin):bisect_right(ratios,upper+margin)] if prune else rows
        for s2 in subset:
            calls += 1
            actual = s1['ratio']*s2['ratio']
            error = abs(actual-total_ratio)/total_ratio
            if error > tol:
                continue
            candidates.append(dict(i_total=actual,ratio_error_rel=error,
                                   sum_stage_errors=s1['ratio_error_rel']+s2['ratio_error_rel'],
                                   volume_proxy_mm2=a1*a1+a2*a2,stage1=s1,stage2=s2))
    candidates.sort(key=stage0_rank)
    return dict(candidates=candidates[:max(0,int(max_candidates))], feasible=len(candidates),
                pair_evaluations=calls, pair_boxes_rejected=len(one)*len(two)-calls,
                stage_domains=[sorted(one),sorted(two)], seed_count=len(seeds))
