"""M34 闭环：真源 v2 文档 → 声明式优化问题 → 剪枝格搜索 + 精确梯度 NLP → 回写新的真源 v2 文档 → 统一校核独立复核。

齿轮知识只在这里（把文档装配成公式图、把声明里的量映射到公式图的输出、齿顶厚附加公式）；
变量 / 目标 / 约束的声明格式与求解都在 kernel（declared.py、gridprune.py），那里不出现齿轮概念。

声明（gearmath.problem_declaration/v1）的 parameters 区由本模块解释，全部必须显式给出，缺则阻断：
  model_family     "pair_model"（math_source.build_model，如 C001）或 "kisssoft_chain:<案例>"（K 链公式集，如 K01-spur）
  hold_evidence    文档 evidence 区全部条目的名字列表：显式承认这些证据值在设计变量变化时保持不变
                   （它们本应随几何/工况重新取证；见 REPORT 与 docs/M34-优化器主线.md 的局限说明）
  document_limits  {限值名: {value, unit, provenance, source}}：写入新文档 constraints 区的限值（统一校核用）；
                   与父文档同名限值不一致即阻断（不静默改限值）
约束量若是统一校核 CHECKS 中的量（S_H_1 等），其限值必须与（父文档 + document_limits 的）对应限值输入相等，否则阻断。
"""
from __future__ import annotations

import copy
import json
from dataclasses import replace as dc_replace
import pathlib
import time

from ..kernel import declared as DC
from ..kernel import gridprune as GP
from ..kernel import source_doc as SD
from ..kernel import units as U
from ..kernel.graph import Formula, InputError, Model
from . import factor_recompute as FR
from . import math_source as MS
from .rating import CHECKS, rate

ROOT = MS.ROOT
DECL_DIR = ROOT / "data" / "optimize"
FAMILIES = ("pair_model", "kisssoft_chain")

# 齿顶圆法向齿厚（相对法向模数）。经典渐开线几何推导，ISO 21771 原文不在证据包，未对照原文核验（独立实现对拍见测试）。
# 用 d_a/m_n = z/cosβ + 2(h_aP + x)、cos α_a = cos α_t /(1 + 2(h_aP + x)cosβ/z)（与库内 geo.d/geo.da/geo.db 代数等价）
# 写成只含 z、x、β、α 的形式，避免 d_a、d_b 相关性使区间求值越出 acos 定义域。
_TIP_NOTE = "经典渐开线几何推导（齿顶圆端面齿厚 × cos β_a，按法向模数归一）；标准原文不在证据包，未核验；仅供优化约束"
TIP_FORMULAS = tuple(
    [Formula(f"opt.s_an_rel.{i}", f"s_an_rel_{i}", "1",
             f"(z_{i}/cos(beta) + 2*(haP + x_{i}))*((pi/2 + 2*x_{i}*tan(alpha_n))/z_{i} + "
             f"(inv(alpha_t) - inv(acos(cos(alpha_t)/(1 + 2*(haP + x_{i})*cos(beta)/z_{i}))))/rad)"
             f"*cos(atan(tan(beta)*(1 + 2*(haP + x_{i})*cos(beta)/z_{i})))",
             _TIP_NOTE, (f"haP + x_{i} > 0", f"z_{i} > 0")) for i in ("1", "2")]
    + [Formula(f"opt.s_an.{i}", f"s_an_{i}", "mm", f"s_an_rel_{i}*m_n", _TIP_NOTE) for i in ("1", "2")])

_FORMULA_DERIVED = ("formulas", "standard_editions", "_exprs", "_dom", "_used", "specs", "_spec_dom", "_fingerprint")


class OptimizeBlocked(ValueError):
    """声明或文档不足以构成优化问题；errors 逐项给出（缺下限、缺系列、证据未声明保持等）。"""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("；".join(f"{e.get('path', '')}：{e['message']}" for e in self.errors[:6]))


def load_declaration(name):
    return json.loads((DECL_DIR / f"{name}.decl.json").read_text(encoding="utf-8"))


def tip_formulas_for(model):
    """按模型选齿顶厚附加公式：基本齿条齿顶高用 haP（K01/C001）或 haP_i（K02–K05 两轮分列）；
    模型含齿顶缩短 k_X_i（输入或 adapter.tip_shortening 公式）时 h_a/m_n 取 haP + x_i + k_X_i/m_n（与 kisssoft_v014 P2 回归同式）。
    K01/C001 旧路径（haP、无 k_X）返回 TIP_FORMULAS 本身，结果逐位不变。"""
    has = lambda n: n in model.formulas or n in model.specs     # noqa: E731
    out = []
    for f in TIP_FORMULAS:
        i = f.id[-1]
        if not f.id.startswith("opt.s_an_rel."):
            out.append(f)
            continue
        hap = f"haP_{i}" if has(f"haP_{i}") else "haP"
        kx = f" + k_X_{i}/m_n" if has(f"k_X_{i}") else ""
        if hap == "haP" and not kx:
            out.append(f)
            continue
        out.append(dc_replace(f, expr=f.expr.replace(f"(haP + x_{i})", f"({hap} + x_{i}{kx})"),
                              domain=(f"{hap} + x_{i}{kx} > 0", f"z_{i} > 0")))
    return tuple(out)


def with_tip_formulas(model):
    """返回在原公式集上追加齿顶厚附加公式（tip_formulas_for）的新模型（输入、版次、选择器等状态照搬；原模型不变）。"""
    m2 = Model(list(model.formulas.values()) + list(tip_formulas_for(model)), inputs=list(model.specs.values()))
    for k, v in model.__dict__.items():
        if k not in _FORMULA_DERIVED:
            setattr(m2, k, copy.copy(v))
    return m2


def _family(decl):
    fam = (decl.get("parameters") or {}).get("model_family")
    if not isinstance(fam, str):
        return None, None
    if fam == "pair_model":
        return fam, None
    if fam.startswith("kisssoft_chain:"):
        return "kisssoft_chain", fam.split(":", 1)[1]
    return None, None


def build_family_model(doc, family, case=None):
    """按族把文档装配成公式图（不追加优化用公式）——统一校核用的就是它。
    文档 selectors 区含系数方法组（method.Z_LVR 等）或适配层（adapter.*）时，经 factor_recompute 装配：
    这些系数随设计变量由公式重算（v0.14 OPT2；旧文档不含这些选择器，装配路径与结果不变）。"""
    if FR.uses_recompute(doc):
        return FR.build_model(doc, family, case)
    if family == "pair_model":
        return MS.build_model(doc)
    from . import math_source_kisssoft as MK
    return MK.model_from_doc(case, doc)


TIP_PARAM = "tip_shortening"
EPSILON_ROLE = "epsilon_scan"
TIP_SELECTOR = "adapter.tip_shortening"


def require_tip_shortening(decl):
    """v0.15 OPT3 起的新入口（optimize_and_commit、多目标、K02/K04）要求声明显式给出 parameters.tip_shortening（无默认）。"""
    v = (decl.get("parameters") or {}).get(TIP_PARAM)
    if v not in FR.TIP_SHORTENING:
        raise OptimizeBlocked([{"path": f"$.parameters.{TIP_PARAM}", "code": "missing_tip_shortening",
                                "message": f"须显式给出齿顶缩短口径 tip_shortening ∈ {list(FR.TIP_SHORTENING)}（无默认）"}])
    return v


def _apply_tip_shortening(work, doc, decl, errs):
    """声明 parameters.tip_shortening（可选；旧声明没有则不动文档）→ 工作文档 selectors.adapter.tip_shortening。
    父文档已有该选择器时必须相同（不静默改口径）；被公式锁定的 k_X_i 输入从工作文档移除（写回文档 note 列出）。"""
    p = decl.get("parameters") or {}
    if TIP_PARAM not in p:
        return
    v = p[TIP_PARAM]
    if v not in FR.TIP_SHORTENING:
        errs.append({"path": f"$.parameters.{TIP_PARAM}", "code": "invalid_tip_shortening",
                     "message": f"tip_shortening 须为 {list(FR.TIP_SHORTENING)}，得到 {v!r}"})
        return
    old = doc.get("selectors", {}).get(TIP_SELECTOR)
    if old is not None:
        if old["value"] != v:
            errs.append({"path": f"$.parameters.{TIP_PARAM}", "code": "tip_shortening_conflict",
                         "message": f"声明 tip_shortening={v} 与父文档 selectors.{TIP_SELECTOR}={old['value']} 不一致"})
        return
    work["selectors"][TIP_SELECTOR] = {"value": v, "source": f"问题声明 {decl.get('id')} parameters.tip_shortening={v}；"
                                                             f"{FR.TIP_SHORTENING_SOURCE}"}
    for i in ("1", "2"):
        row = work["inputs"].pop(f"k_X_{i}", None)
        if row is not None:
            work.setdefault("_removed_by_tip", []).append(f"k_X_{i}={row['value']} {row['unit']}")


def working_document(doc, decl):
    """父文档 + document_limits（只增不改；冲突阻断）+ 可选 tip_shortening 选择器。返回 (工作文档, 错误列表)。"""
    errs = []
    work = copy.deepcopy(doc)
    _apply_tip_shortening(work, doc, decl, errs)
    removed = work.pop("_removed_by_tip", None)
    if removed:
        work["note"] = work.get("note", "") + f"（齿顶缩短改由公式给出，移除输入：{'；'.join(removed)}）"
    lims = (decl.get("parameters") or {}).get("document_limits")
    if not isinstance(lims, dict):
        return work, [{"path": "$.parameters.document_limits", "code": "missing",
                       "message": "须显式给出 document_limits（可为空对象）：写入新文档 constraints 区的限值"}]
    for name, row in lims.items():
        if not (isinstance(row, dict) and all(k in row for k in ("value", "unit", "provenance", "source"))):
            errs.append({"path": f"$.parameters.document_limits.{name}", "code": "missing",
                         "message": f"{name} 须给出 value/unit/provenance/source"})
            continue
        old = doc["constraints"].get(name)
        if old is not None and U.to_canonical(old["value"], old["unit"]) != U.to_canonical(row["value"], row["unit"]):
            errs.append({"path": f"$.parameters.document_limits.{name}", "code": "limit_conflict",
                         "message": f"{name} 与父文档 constraints 中的值 {old['value']} {old['unit']} 不一致（不静默改限值）"})
            continue
        if old is None:
            work["constraints"][name] = {k: row[k] for k in ("value", "unit", "provenance", "source")}
    return work, errs


def check_against_document(doc, decl):
    """声明与文档的交叉检查。返回 (工作文档, 族, 案例, 错误列表)。"""
    errs = DC.validate_declaration(decl)
    if errs:
        return None, None, None, errs
    fam, case = _family(decl)
    if fam is None:
        errs.append({"path": "$.parameters.model_family", "code": "missing",
                     "message": "须显式给出 model_family：'pair_model' 或 'kisssoft_chain:<案例>'"})
    p = decl.get("parameters") or {}
    hold = p.get("hold_evidence")
    have = set(doc.get("evidence", {}))
    if not isinstance(hold, list) or set(hold) != have:
        miss = sorted(have - set(hold or []))
        errs.append({"path": "$.parameters.hold_evidence", "code": "evidence_hold_not_declared",
                     "message": f"须显式列出保持不变的全部证据条目（缺 {miss}）；证据值不会随设计变量自动重新取证"})
    errs += _check_hold_rationale(doc, p, hold)
    for v in decl["variables"]:
        n = v["name"]
        row = doc["inputs"].get(n)
        if row is None:
            sec = "evidence" if n in doc.get("evidence", {}) else "constraints" if n in doc.get("constraints", {}) else None
            errs.append({"path": f"$.variables.{n}", "code": "variable_not_author_input",
                         "message": f"设计变量 {n} 须是文档 inputs 区的作者输入" + (f"（它在 {sec} 区）" if sec else "（文档中没有）")})
        elif U.unit(row["unit"])[0] != U.unit(v["unit"])[0]:
            errs.append({"path": f"$.variables.{n}.unit", "code": "unit_dimension_mismatch",
                         "message": f"{n} 声明单位 {v['unit']} 与文档单位 {row['unit']} 量纲不同"})
    if errs:
        return None, fam, case, errs
    work, e2 = working_document(doc, decl)
    errs += e2
    # 约束限值与统一校核限值一致
    limit_of = {c.quantity: (c.limit, c.sense) for c in CHECKS}
    for c in decl["constraints"]:
        if c["quantity"] in limit_of:
            lname, sense = limit_of[c["quantity"]]
            row = work["constraints"].get(lname)
            if c.get("role") == EPSILON_ROLE and row is not None:
                # ε-约束扫描（kernel/epsilon.py）：在统一校核限值之外另加的更严下限/上限；只允许比文档限值更严
                lim, doc_lim = U.to_canonical(c["limit"]["value"], c["limit"]["unit"]), U.to_canonical(row["value"], row["unit"])
                if sense != c["sense"] or (lim < doc_lim if sense == ">=" else lim > doc_lim):
                    errs.append({"path": f"$.constraints.{c['id']}", "code": "epsilon_looser_than_check",
                                 "message": f"ε-约束 {c['id']} 须与统一校核 {lname} 同向且不宽于 {row['value']}"})
                continue
            if row is None:
                errs.append({"path": f"$.constraints.{c['id']}", "code": "missing_document_limit",
                             "message": f"{c['quantity']} 的统一校核限值 {lname} 既不在文档也不在 document_limits 中"})
            elif sense != c["sense"] or U.to_canonical(row["value"], row["unit"]) != U.to_canonical(c["limit"]["value"], c["limit"]["unit"]):
                errs.append({"path": f"$.constraints.{c['id']}", "code": "limit_conflict_with_check",
                             "message": f"约束 {c['quantity']} {c['sense']} {c['limit']['value']} 与统一校核 {lname}={row['value']} 不一致"})
    return work, fam, case, errs


def _check_hold_rationale(doc, p, hold):
    """可选的 hold_rationale（{证据名: 理由}）须与 hold_evidence 逐项对应且理由非空；
    可选的 geometry_coupled_held（{输入名: 理由}）只能列文档 inputs 区的作者输入。旧声明两者皆无：不报错，报告里理由记为"未给出"。"""
    errs = []
    why = p.get("hold_rationale")
    if why is not None:
        if not isinstance(why, dict) or set(why) != set(hold or []) or \
                not all(isinstance(t, str) and t.strip() for t in why.values()):
            miss = sorted(set(hold or []) - set(why or {})) if isinstance(why, dict) else hold
            errs.append({"path": "$.parameters.hold_rationale", "code": "hold_rationale_incomplete",
                         "message": f"hold_rationale 须对 hold_evidence 逐项给出非空理由（缺 {miss}）"})
    geo = p.get("geometry_coupled_held")
    if geo is not None:
        bad = [n for n in (geo if isinstance(geo, dict) else [None]) if n not in doc.get("inputs", {})]
        if not isinstance(geo, dict) or bad or not all(isinstance(t, str) and t.strip() for t in geo.values()):
            errs.append({"path": "$.parameters.geometry_coupled_held", "code": "geometry_coupled_held_invalid",
                         "message": f"geometry_coupled_held 须为 {{inputs 区输入名: 非空理由}}（无效项 {bad}）"})
    return errs


def held_not_updated(model, decl):
    """优化结果须报告的"未随几何更新"清单：模型中仍为输入的系数/几何耦合量（含理由）。"""
    return [r for r in FR.coefficient_status(model, decl) if r["status"] == "held"]


class SourceEvaluator:
    """kernel.declared 的量求值器：在文档装配出的公式图上点求值（含前向对偶数导数）与区间求值。"""

    def __init__(self, doc, decl):
        work, fam, case, errs = check_against_document(doc, decl)
        if errs:
            raise OptimizeBlocked(errs)
        self.work, self.family, self.case = work, fam, case
        try:
            base = build_family_model(work, fam, case)
        except SD.SourceError as e:
            raise OptimizeBlocked(e.errors) from e
        self.model = with_tip_formulas(base)
        self.req = DC.requested_quantities(decl)
        bad = [q for q in self.req if q not in self.model.formulas and q not in self.model.inputs]
        if bad:
            raise OptimizeBlocked([{"path": "$.constraints", "code": "unknown_quantity", "message": f"公式图中没有量 {bad}"}])
        self.vars = {v["name"]: v for v in decl["variables"]}
        self.point_calls = self.interval_calls = 0

    def _set(self, x):
        for n, val in x.items():
            self.model.set(n, val, self.vars[n]["unit"], "optimizer", "优化试算点")

    @staticmethod
    def _k(unit):
        return U.to_canonical(1.0, unit) - U.to_canonical(0.0, unit)

    def point(self, x, wrt=()):
        self.point_calls += 1
        try:
            self._set(x)
        except InputError as e:
            return {"status": "error", "message": str(e)}
        res = self.model.evaluate(list(self.req), wrt=tuple(wrt))
        if res.status not in ("ok", "out_of_domain"):
            return {"status": "error", "message": f"{res.status}：{(res.errors or res.missing)[:2]}"}
        vals, ders = {}, {}
        for q, u in self.req.items():
            vals[q] = U.from_canonical(res.values[q], u)
            d = res.duals[q].d
            ders[q] = {n: d.get(n, 0.0) * self._k(self.vars[n]["unit"]) / self._k(u) for n in wrt}
        return {"status": "ok", "values": vals, "derivatives": ders,
                "applicability_violated": bool(res.domain_violations),
                "domain_violations": list(res.domain_violations)}

    def interval(self, box, quantities=None):
        """逐量区间求值（一个量不可区间求值不连累其它量）。盒内必然违反公式适用域或整体越出输入取值域 -> applicability_violated。"""
        boxes = {n: (lo, hi, self.vars[n]["unit"]) for n, (lo, hi) in box.items()}
        out, uns, viol = {}, {}, False
        for q in (quantities if quantities is not None else list(self.req)):
            self.interval_calls += 1
            r = self.model.evaluate_interval([q], boxes)
            if r.status == "out_of_domain" or (r.status == "blocked_invalid_inputs"
                                               and any(e.get("code") == "out_of_domain" for e in r.errors)):
                viol = True
            if r.status in ("ok", "out_of_domain"):
                iv = r.get(q, self.req[q])
                out[q] = (iv.lo, iv.hi)
            else:
                out[q] = None
                e = (r.errors or [{}])[0]
                uns[q] = f"{r.status}:{e.get('code', '')}:{e.get('formula', '')}"
        return {"values": out, "unsupported": uns, "applicability_violated": viol}


def _unit_value(v, kind):
    return float(v)


def writeback(parent_doc, work_doc, decl, x, run):
    """生成新的真源 v2 文档：设计变量写入 inputs（provenance=optimizer，source 带父文档 sha256、声明 sha256、求解器指纹），
    document_limits 写入 constraints；其余条目（含 hold_evidence 的证据）原样保留。不修改父文档。"""
    new = copy.deepcopy(work_doc)
    psha = MS.source_sha256(parent_doc)
    dsha = DC.declaration_sha256(decl)
    # v0.17：文档来源串不再内嵌包版本号（求解器身份由内核源码指纹确定；包版本只记在运行报告 package_version 中），
    # 否则每次升版都会改变写回文档 sha256、使存档确定性比较失效。
    tag = (f"optimizer {run['solver']['solver']}（内核源码 sha256 {run['solver']['kernel_sources_sha256'][:16]}…）；"
           f"父文档 {parent_doc['id']} sha256={psha}；问题声明 {decl['id']} sha256={dsha}")
    for v in decl["variables"]:
        n = v["name"]
        old = parent_doc["inputs"][n]
        res = f"；制造分辨率 {v['resolution']} {v['unit']} 回圆后严格复核" if v["kind"] == "continuous" else ""
        new["inputs"][n] = {"value": _unit_value(x[n], v["kind"]), "unit": v["unit"], "provenance": "optimizer",
                            "source": f"{tag}；原值 {old['value']} {old['unit']}（{old['provenance']}）{res}"}
    new["id"] = f"{parent_doc['id']}.opt-{dsha[:8]}"
    new["title"] = f"{parent_doc['title']} —— 优化修订（{decl['id']}）"
    held = ", ".join(sorted(parent_doc.get("evidence", {})))
    new["note"] = (f"由 {parent_doc['id']}（sha256={psha}）经问题声明 {decl['id']}（sha256={dsha}）与 {run['solver']['solver']} 求解生成。"
                   f"证据区按声明 hold_evidence 原样保持（{held}）：这些值未随新几何重新取证，强度结论受此限制。"
                   f"派生量不存；回执/参数表是投影。")
    if run.get("coefficient_status") is not None:
        rec = ", ".join(r["name"] for r in run["coefficient_status"] if r["status"] == "recomputed")
        hel = ", ".join(r["name"] for r in run["coefficient_status"] if r["status"] == "held")
        new["note"] += f"随设计变量由公式重算：{rec}。未随几何更新（理由见声明 hold_rationale / geometry_coupled_held）：{hel or '无'}。"
    tip = new.get("selectors", {}).get(TIP_SELECTOR)
    if tip is not None and TIP_PARAM in (decl.get("parameters") or {}):
        new["note"] += f"齿顶缩短口径（几何口径选择器）：{tip['value']}。"
    errs = MS.validate(new)
    if errs:
        raise SD.SourceError(errs)
    return new


def verify_writeback(new_doc, decl):
    """独立复核：从新文档重新装配（不复用优化过程中的模型、缓存或求值器），
    (1) 统一校核 rate() 全部 CHECKS 通过；(2) 声明里的每条约束在零容差下满足；(3) 文档校验通过（K 链另核 T_1 守门）。"""
    fam, case = _family(decl)
    out = {"schema_errors": MS.validate(new_doc)}
    m = build_family_model(new_doc, fam, case)
    r = rate(m, extra=())
    out["unified_check_status"] = r["status"]
    out["unified_checks"] = [{k: c[k] for k in ("id", "quantity", "value", "limit", "sense", "margin_ratio", "pass")}
                             for c in r["checks"]]
    m2 = with_tip_formulas(build_family_model(new_doc, fam, case))
    req = DC.requested_quantities(decl)
    res = m2.evaluate(list(req))
    rows = []
    for c in decl["constraints"]:
        q = U.from_canonical(res.values[c["quantity"]], c["limit"]["unit"])
        lim = c["limit"]["value"]
        ok = q >= lim if c["sense"] == ">=" else q <= lim
        rows.append({"id": c["id"], "quantity": c["quantity"], "value": q, "sense": c["sense"], "limit": lim, "satisfied": ok})
    out["declared_constraints"] = rows
    out["domain_violations"] = list(res.domain_violations)
    o = decl["objective"]
    out["objective"] = {"quantity": o["quantity"], "value": U.from_canonical(res.values[o["quantity"]], o["unit"]), "unit": o["unit"]}
    if fam == "kisssoft_chain":
        from . import math_source_kisssoft as MK
        out["t1_guard_errors"] = MK.t1_guard_errors(case, new_doc)
    out["coefficient_status"] = FR.coefficient_status(m, decl)
    out["held_not_updated"] = [r for r in out["coefficient_status"] if r["status"] == "held"]
    out["all_confirmed"] = (not out["schema_errors"] and r["status"] == "pass" and all(x["satisfied"] for x in rows)
                            and not out["domain_violations"] and not out.get("t1_guard_errors"))
    return out


def _package_version():
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def optimize_source(doc, decl, *, leaf_subboxes=8, nlp_options=None, final_checks=True):
    """端到端：文档 + 声明 → 剪枝格搜索 → 回圆 → 回写新文档 → 独立复核。返回完整报告（新文档在 report["new_document"]）。"""
    t0 = time.perf_counter()
    ev = SourceEvaluator(doc, decl)
    problem, bounds = DC.compile_declaration(decl, ev)
    sr = GP.pruned_lattice_search(problem, bounds, leaf_subboxes=leaf_subboxes, nlp_options=nlp_options,
                                  final_checks=final_checks)
    rep = {"declaration_id": decl["id"], "declaration_sha256": DC.declaration_sha256(decl),
           "parent_id": doc["id"], "parent_sha256": MS.source_sha256(doc),
           "search": {k: sr[k] for k in ("lattice_points_total", "points_pruned", "pruned_points_by_reason", "leaves_solved",
                                         "nlp_solves", "nlp_solves_final_check", "evaluations", "interval_bound_calls",
                                         "nodes_visited", "leaf_failures", "wall_time_s")},
           "assurance": sr["assurance"], "solver": sr["solver"], "package_version": _package_version(),
           "evaluator_calls": None, "new_document": None, "verification": None, "status": None}
    sol = sr["solution"]
    if sol is None:
        rep["status"] = "no_feasible_found"
        rep["wall_time_s"] = time.perf_counter() - t0
        return rep
    rep["optimum"] = {"x": dict(sol.x), "objective": dict(sol.objectives), "constraints_g": dict(sol.constraints),
                      "quantities": sol.info.get("quantities")}
    snap = GP.snap_to_resolution(problem, sol.x, DC.resolutions(decl))
    rep["snap"] = {"x": snap["x"], "shift": snap["shift"], "candidates_checked": snap["candidates_checked"],
                   "objective": dict(snap["solution"].objectives) if snap["solution"] else None}
    if snap["x"] is None:
        rep["status"] = "blocked_rounding_infeasible"
        rep["wall_time_s"] = time.perf_counter() - t0
        return rep
    rep["coefficient_status"] = FR.coefficient_status(ev.model, decl)
    rep["held_not_updated"] = [r for r in rep["coefficient_status"] if r["status"] == "held"]
    new = writeback(doc, ev.work, decl, snap["x"], {"solver": sr["solver"], "package_version": rep["package_version"],
                                                    "coefficient_status": rep["coefficient_status"] if FR.uses_recompute(doc) else None})
    rep["new_document"] = new
    rep["new_sha256"] = MS.source_sha256(new)
    rep["verification"] = verify_writeback(new, decl)
    rep["evaluator_calls"] = {"point": ev.point_calls, "interval": ev.interval_calls}
    rep["status"] = "written_and_confirmed" if rep["verification"]["all_confirmed"] else "written_not_confirmed"
    rep["wall_time_s"] = time.perf_counter() - t0
    return rep


def provenance(rep, decl):
    """写回修订的来源记录（design_store.commit_optimization 用）。"""
    return {"parent_source_sha256": rep["parent_sha256"], "declaration_id": decl["id"],
            "declaration_sha256": rep["declaration_sha256"],
            "solver": {"solver": rep["solver"]["solver"], "kernel_sources_sha256": rep["solver"]["kernel_sources_sha256"]},
            "variables": [v["name"] for v in decl["variables"]]}
