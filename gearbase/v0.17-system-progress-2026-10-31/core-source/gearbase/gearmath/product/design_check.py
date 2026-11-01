"""统一核算入口：check(design_doc, system_input, scope) → gears.design-check-result/1。

不新增物理公式。各子检查只调用已有模块：
  gear_rating   gear/source_optimize.build_family_model + gear/rating.rate（ISO 6336-2/-3、ISO 21771 统一 CHECKS）
  manufacturing gear/parameter_sheet（ISO 1328-1:2013 公差、ISO 21771 测量尺寸；只读投影）
  scuffing      gear/scuffing_integral.rate（ISO/TS 6336-21 积分温度法）
  micropitting  gear/micropitting.rate（ISO/TS 6336-22 方法 B 七点）
  shaft         system/drivetrain_check 静定兼容求解及截面校核
  bearing       system/drivetrain_check ISO 281（支反力来自静定求解，或系统层输入显式给出）
  key           system/din6892.method_c（DIN 6892 方法 C）
  fit           system/din7190.elastic_check_for_interference（DIN 7190-1 方法 2，纯弹性）
  thermal       system/thermal_14179 既有热功率路线；显式 equilibrium 路线调用 thermal_balance 温度迭代
缺输入：该子检查 blocked + 缺项清单；不影响其它子检查；不默认补值。
"计算结果"（computation）与"证据资格"（evidence_qualification）分开给出；两者都不等于工程验收。
"""
from __future__ import annotations

import json
import math
import pathlib

from ..gear import math_source as MS
from ..gear import micropitting as MP
from ..gear import parameter_sheet as PSH
from ..gear import rating as RT
from ..gear import scuffing_integral as SI
from ..gear import source_optimize as SO
from ..kernel import source_doc as SD
from ..kernel import units as U
from ..system import din6892 as KEY
from ..system import din743 as D743
from ..system import din7190 as FIT
from ..system import iso281 as BRG
from ..system import shaft_line as SL
from ..system import drivetrain_check as DT
from ..system import thermal_14179 as TH
from ..system import thermal_balance as TB
from . import evidence as EV
from . import system_input as SIN

RESULT_SCHEMA_ID = "gears.design-check-result/1"
ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULT_SCHEMA_PATH = ROOT / "data" / "schema" / "gears.design-check-result-1.schema.json"
SCOPES = ("gear_rating", "manufacturing", "scuffing", "micropitting", "shaft", "bearing", "key", "fit", "thermal")
STATUSES = ("pass", "fail", "blocked", "not_in_scope")
DISCLAIMER = ("本结果是按所列标准公式与所给输入得到的计算结果，不等于工程验收：输入来源、方法选择、证据等级与"
              "未验证项须由工程师逐项复核；blocked 项表示缺输入或条文未确认，不是通过。")
MODULES = {"gear_rating": "gearmath.gear.rating", "manufacturing": "gearmath.gear.parameter_sheet",
           "scuffing": "gearmath.gear.scuffing_integral", "micropitting": "gearmath.gear.micropitting",
           "shaft": "gearmath.system.drivetrain_check", "bearing": "gearmath.system.drivetrain_check",
           "key": "gearmath.system.din6892", "fit": "gearmath.system.din7190", "thermal": "gearmath.system.thermal_14179"}
REGISTRIES = {"scuffing": (SI.FORMULAS,), "micropitting": (MP.FORMULAS,), "shaft": (SL.FORMULAS, D743.FORMULAS),
              "bearing": (BRG.FORMULAS,), "key": (KEY.FORMULAS,), "fit": (FIT.FORMULAS,), "thermal": (TH.FORMULAS,)}
KISSSOFT_MODULE = {
    "gear_rating": "KISSsoft 圆柱齿轮副 ISO 6336:2019（Z12）", "manufacturing": "KISSsoft 圆柱齿轮副 ISO 1328-1:2013 公差/测量尺寸",
    "scuffing": "KISSsoft 圆柱齿轮副 胶合 ISO/TS 6336-21:2022", "micropitting": "KISSsoft 圆柱齿轮副 微点蚀 ISO/TS 6336-22:2018",
    "shaft": "KISSsoft 轴计算 DIN 743:2012（W10）", "bearing": "KISSsoft 轴计算内 ISO 281:2007 轴承寿命",
    "key": "KISSsoft 连接 DIN 6892:2012 平键", "fit": "KISSsoft 连接 DIN 7190-1:2017 过盈", "thermal": "ISO/TR 14179-1 热功率（KISSsoft 齿轮箱热计算）"}

# 设计模型 → -21 输入的命名适配（同一物理量、换到 -21 的单位；不是默认值）
SCUFF_FROM_MODEL = {"z1": ("z_1", "1"), "z2": ("z_2", "1"), "a": ("a_w", "mm"), "alpha_n": ("alpha_n", "rad"),
                    "alpha_t": ("alpha_t", "rad"), "alpha_wt": ("alpha_wt", "rad"), "beta": ("beta", "rad"),
                    "beta_b": ("beta_b", "rad"), "d_a1": ("da_1", "mm"), "d_a2": ("da_2", "mm"), "d_b1": ("db_1", "mm"),
                    "d_b2": ("db_2", "mm"), "eps_beta": ("eps_beta", "1"), "b": ("b", "mm"), "F_t": ("F_t", "N"),
                    "v": ("v", "m/s"), "K_A": ("K_A", "1"), "K_v": ("K_V", "1"), "K_Hbeta": ("K_Hbeta", "1"),
                    "K_Halpha": ("K_Halpha", "1")}
MICRO_FROM_MODEL = {"u": ("u", "1"), "d_a1": ("da_1", "mm"), "d_a2": ("da_2", "mm"), "d_b1": ("db_1", "mm"),
                    "d_b2": ("db_2", "mm"), "alpha_wt": ("alpha_wt", "rad"), "beta_b": ("beta_b", "rad"),
                    "n1": ("n_1", "rpm")}
DESIGN_QUANTITIES = sorted({q for q, _ in list(SCUFF_FROM_MODEL.values()) + list(MICRO_FROM_MODEL.values())}
                           | {"T_1", "n_1", "d_1", "d_2", "u", "a_w", "c_s", "c_gamma_alpha", "eps_alpha", "m_n",
                              "haP", "hfP", "rhofP", "Q_grade", "E", "nu"})
ETA_ROUTES = ("explicit", "iso_ts_6336_22_rho15")


# ================================================================== 通用
def _finite(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def _item(iid, quantity, value, unit, limit=None, sense=None, *, formula_ids=(), level=EV.NONE_LEVEL,
          level_basis="", standard="", status=None, note=""):
    v, lim = _finite(value), _finite(limit)
    margin = None
    if v is not None and lim is not None and sense in (">=", "<="):
        margin = _finite(v / lim if sense == ">=" else (lim / v if v else None))
    if status is None:
        if lim is None and sense is None:
            status = "info"
        elif v is None or lim is None:
            status = "blocked"
        else:
            status = "pass" if (v >= lim if sense == ">=" else v <= lim) else "fail"
    return {"id": iid, "quantity": quantity, "value": v, "unit": unit, "limit": lim, "sense": sense, "margin": margin,
            "status": status, "formula_ids": list(formula_ids), "evidence_level": EV.norm_level(level),
            "evidence_basis": level_basis, "standard": standard, "note": note}


def _sub(scope, design_id):
    regs = REGISTRIES.get(scope, ())
    return {"scope": scope, "status": None, "module": MODULES[scope], "items": [], "missing": [], "unconfirmed": [],
            "errors": [], "assumptions": [], "inputs_sources": {},
            "external_refs": EV.external_refs(scope, design_id),
            "module_evidence_distribution": EV.merge_distributions(EV.module_distribution(r) for r in regs) if regs else None,
            "reason": ""}


def _finish(sub):
    st = [i["status"] for i in sub["items"]]
    if "fail" in st:
        sub["status"] = "fail"
    elif sub["missing"] or sub["unconfirmed"] or sub["errors"] or "blocked" in st or not st:
        sub["status"] = "blocked"
    else:
        sub["status"] = "pass"
    return sub


def _absorb(sub, exc, prefix=""):
    """已有模块抛出的阻断类异常（MissingInput/Unconfirmed/OutOfDomain/bad_input，各模块同名 code）→ 记入子检查。"""
    code, name = getattr(exc, "code", None), getattr(exc, "name", None)
    if code == "missing_input":
        sub["missing"].append(f"{prefix}{name}")
    elif code == "unconfirmed":
        sub["unconfirmed"].append(f"{prefix}{exc}")
    else:
        sub["errors"].append({"path": f"{prefix}{name or ''}", "code": code or type(exc).__name__, "message": str(exc)})


def _resolve(ctx, sub, section, node=None):
    r = SIN.Resolver(ctx["design_values"])
    node = ctx["si"].get(section) if node is None else node
    val = r.resolve(node, f"$.{section}")
    sub["inputs_sources"].update(r.sources)
    sub["errors"].extend(r.errors)
    return val, r


# ================================================================== 设计上下文
def _family(si):
    fam = ((si.get("design_ref") or {}).get("model_family"))
    if fam == "pair_model":
        return "pair_model", None
    if isinstance(fam, str) and fam.startswith("kisssoft_chain:"):
        return "kisssoft_chain", fam.split(":", 1)[1]
    return None, None


def _context(doc, si):
    ctx = {"doc": doc, "si": si, "model": None, "design_values": {}, "model_error": None, "shafts": None}
    fam, case = _family(si)
    if fam is None:
        ctx["model_error"] = {"path": "$.design_ref.model_family", "code": "missing_input",
                              "message": "须显式给出 model_family：'pair_model' 或 'kisssoft_chain:<案例>'"}
        return ctx
    try:
        m = SO.build_family_model(doc, fam, case)
    except SD.SourceError as e:
        ctx["model_error"] = {"path": "$design_doc", "code": "source_error", "message": str(e)}
        return ctx
    lim = (si.get("gear_rating") or {}).get("limits") or {}
    ctx["limit_sources"] = {}
    for k, leaf in lim.items():
        if SIN.is_leaf(leaf) and leaf.get("value") is not None:
            m.set(k, leaf["value"], leaf.get("unit", "1"), "user", leaf["source"])
            ctx["limit_sources"][k] = leaf["source"]
    ctx["model"] = m
    names = [n for n in DESIGN_QUANTITIES if n in m.formulas or n in m.inputs]
    res = m.evaluate(names)
    ctx["design_values"] = {k: v for k, v in res.values.items() if k in names}
    return ctx


def _model_blocked(sub, ctx):
    sub["errors"].append(ctx["model_error"])
    sub["reason"] = "设计模型无法装配"
    return _finish(sub)


# ================================================================== gear_rating
def _gear_rating(ctx):
    sub = _sub("gear_rating", ctx["doc"]["id"])
    if ctx["model"] is None:
        return _model_blocked(sub, ctx)
    m = ctx["model"]
    for k, s in ctx.get("limit_sources", {}).items():
        sub["inputs_sources"][f"$.gear_rating.limits.{k}"] = s
    r = RT.rate(m)
    lacking = []
    if r["status"] == "blocked_missing_inputs":
        limits = {c.limit for c in RT.CHECKS}
        lacking = [k for k in r["missing"] if k in limits]
        if set(r["missing"]) - set(lacking) or r["missing_editions"]:
            sub["missing"] += list(r["missing"]) + [f"edition:{e}" for e in r["missing_editions"]]
            return _finish(sub)
        r = RT.rate(m, checks=[c for c in RT.CHECKS if c.limit not in lacking])
    if r["status"] not in ("pass", "fail", "out_of_domain"):
        sub["errors"] += r.get("errors", [])
        sub["missing"] += r.get("missing", [])
        sub["reason"] = r["status"]
        return _finish(sub)
    ev = r["result"].evidence
    for c in r["checks"]:
        f = m.formulas.get(c["quantity"])
        e = ev.get(c["quantity"], {})
        sub["items"].append(_item(f"gear_rating.{c['id']}", c["quantity"], c["value"], "1", c["limit"], c["sense"],
                                  formula_ids=[f.id] if f else [], level=e.get("level"),
                                  level_basis="公式图依赖链最弱一环（data/registry 评估；unassessed 记为 none）",
                                  standard=c["ref"]))
    for c in RT.CHECKS:
        if c.limit in lacking:
            sub["missing"].append(f"$.gear_rating.limits.{c.limit}")
            sub["items"].append(_item(f"gear_rating.{c.id}", c.quantity, None, "1", None, c.sense, status="blocked",
                                      standard=c.ref, note=f"限值 {c.limit} 无来源（设计文档与系统层输入均未给出）"))
    if r["status"] == "out_of_domain":
        sub["unconfirmed"] += [f"适用域：{d}" for d in r.get("domain_violations", [])]
    sub["assumptions"].append(f"方法选择器来自设计文档 selectors：{json.dumps(r['selectors'], ensure_ascii=False)}")
    return _finish(sub)


# ================================================================== manufacturing
def _registry_level(fid):
    from ..kernel.registry import evidence_levels, load_registry
    global _REG_LEVELS
    if _REG_LEVELS is None:
        try:
            _REG_LEVELS = evidence_levels(load_registry(ROOT / "data" / "registry" / "formulas-v1.json"))
        except (OSError, ValueError):
            _REG_LEVELS = {}
    return _REG_LEVELS.get(fid)


_REG_LEVELS = None


def _manufacturing(ctx):
    sub = _sub("manufacturing", ctx["doc"]["id"])
    sec = ctx["si"].get("manufacturing")
    if sec is None:
        sub["missing"].append("$.manufacturing")
        return _finish(sub)
    val, r = _resolve(ctx, sub, "manufacturing")
    sub["missing"] += r.missing
    if r.missing or sub["errors"]:
        return _finish(sub)
    try:
        m, lay = PSH.build({int(k): v for k, v in val["gears"].items()}, tip_diameter=val["tip_diameter"],
                           groups=tuple(val["groups"]))
    except (ValueError, TypeError, KeyError) as e:
        sub["errors"].append({"path": "$.manufacturing", "code": "invalid", "message": str(e)})
        return _finish(sub)
    doc_inputs = ctx["doc"]["inputs"]
    copied = []
    for k, rec in doc_inputs.items():          # 同名同义：设计文档作者输入原样带入（不改名、不推断）
        if k in m.specs:
            m.set(k, rec["value"], rec["unit"], "user", rec.get("source", ""))
            copied.append(k)
    for k, leaf in (sec.get("inputs") or {}).items():
        if k in copied:
            sub["errors"].append({"path": f"$.manufacturing.inputs.{k}", "code": "conflict",
                                  "message": f"{k} 已由设计文档给出，系统层输入不得重复"})
            continue
        v = val["inputs"][k]
        m.set(k, v, leaf.get("unit", "1"), "user", leaf["source"])
    if copied:
        sub["assumptions"].append(f"设计文档同名作者输入直接带入制造参数表：{', '.join(sorted(copied))}")
    if sub["errors"]:
        return _finish(sub)
    sheet = PSH.project(m, lay, title=ctx["doc"]["id"])
    if sheet["status"] != "ok":
        sub["missing"] += [f"$.manufacturing.inputs.{k}" for k in sheet.get("missing", [])]
        sub["errors"] += sheet.get("errors", [])
        sub["reason"] = sheet["status"]
        return _finish(sub)
    for g, gd in sheet["gears"].items():
        for sname, rows in gd["sections"].items():
            for row in rows:
                if row.get("kind") == "input":
                    continue
                f = m.formulas.get(row["quantity"])
                fid = f.id if f else None
                sub["items"].append(_item(f"manufacturing.{g}.{sname}.{row['key']}", row["quantity"], row["value"],
                                          row["unit"], formula_ids=[fid] if fid else [], level=_registry_level(fid),
                                          level_basis="data/registry 评估（未登记记为 none）",
                                          standard=", ".join(f"{k}:{v}" for k, v in sheet["editions"].items()),
                                          note=row.get("label", "")))
    sub["assumptions"].append("制造参数表无验收限值：条目为 info；子检查 pass 仅表示参数表可在已登记公式与适用域内生成")
    return _finish(sub)


# ================================================================== scuffing / micropitting
def _from_model(ctx, sub, mapping):
    out = {}
    for k, (q, unit) in mapping.items():
        v = ctx["design_values"].get(q)
        if v is None:
            sub["missing"].append(f"设计模型量 {q}（→ {k}）")
            out[k] = None
        else:
            out[k] = U.from_canonical(v, unit)
            sub["inputs_sources"][f"model:{k}"] = f"设计模型 {q}（{unit}）"
    return out


def _paths(names, sections, null_paths):
    """已有模块报告的缺项输入名 → 系统层输入中留空叶子的路径；输入中根本没有该键的给名字并注明。"""
    out = []
    for k in names:
        p = next((f"$.{s}.{k}" for s in sections if f"$.{s}.{k}" in null_paths), None)
        out.append(p or f"{k}（系统层输入未给出）")
    return out


def _eta_oil(oil, sub):
    route = oil.get("eta_oil_route")
    if route not in ETA_ROUTES:
        sub["missing"].append("$.oil.eta_oil_route（'explicit' 或 'iso_ts_6336_22_rho15'）")
        return None
    if route == "explicit":
        if oil.get("eta_oil") is None:
            sub["missing"].append("$.oil.eta_oil")
        return oil.get("eta_oil")
    need = [k for k in ("nu_40", "nu_100", "rho_15", "theta_oil") if oil.get(k) is None]
    if need:
        sub["missing"] += [f"$.oil.{k}" for k in need]
        return None
    sub["assumptions"].append("ηoil 由 ISO/TS 6336-22 式(16)–(20)（ν40、ν100、数据表 ρ15，在 θoil 处）计算：-21 未规定 ηoil 求法，"
                              "为跨部分借用（与 tests/test_m39_kisssoft_v014.py 口径一致）")
    nu = MP.nu_theta(nu_40=oil["nu_40"], nu_100=oil["nu_100"], theta=oil["theta_oil"])
    return MP.eta_dynamic(nu=nu, rho=MP.rho_theta(rho_15=oil["rho_15"], theta=oil["theta_oil"])) * 1000.0


def _scuffing(ctx):
    sub = _sub("scuffing", ctx["doc"]["id"])
    if ctx["model"] is None:
        return _model_blocked(sub, ctx)
    if ctx["si"].get("scuffing") is None:
        sub["missing"].append("$.scuffing")
        return _finish(sub)
    sc, r1 = _resolve(ctx, sub, "scuffing")
    oil, r2 = _resolve(ctx, sub, "oil", ctx["si"].get("oil") or {})
    inp = _from_model(ctx, sub, SCUFF_FROM_MODEL)
    s_min = sc.pop("S_Smin", None)
    for k, v in sc.items():
        if k in inp:
            sub["errors"].append({"path": f"$.scuffing.{k}", "code": "conflict", "message": f"{k} 由设计模型提供，不得重复"})
        inp[k] = v
    for k in ("lubricant", "theta_oil", "lubrication", "nu_40"):
        if k in oil:
            inp[k] = oil[k]
    if sub["errors"]:
        return _finish(sub)
    inp["eta_oil"] = _eta_oil(oil, sub)
    res = SI.rate(inp)
    if res["status"] != "ok":
        sub["missing"] += _paths(res.get("missing", []), ("scuffing", "oil"), r1.missing + r2.missing)
        sub["unconfirmed"] += res.get("unconfirmed", [])
        sub["missing"] = sorted(set(sub["missing"]))
        return _finish(sub)
    t1t = inp.get("T1T_or_load_stage") or {}
    chain = [SI.S_intS, SI.theta_int, SI.theta_flaint, SI.mu_mC]
    if inp["scuffing_test"] != "explicit_theta_intS":
        chain += [SI.theta_intS] + ([SI.T1T_from_load_stage] if "load_stage" in t1t else
                                    [SI.T1T_from_figure7] if "load_stage_fig7" in t1t else [])
    ids, lv, basis = EV.item_evidence(chain)
    sub["items"].append(_item("scuffing.S_intS", "S_intS", res["S_intS"], "1", s_min, ">=", formula_ids=ids, level=lv,
                              level_basis=basis, standard=SI.P,
                              note="" if s_min is not None else "最小安全系数 S_Smin 无来源 → 无法判定"))
    if s_min is None:
        sub["missing"].append("$.scuffing.S_Smin")
    ids, lv, basis = EV.item_evidence([SI.theta_int, SI.theta_flaint, SI.mu_mC])
    sub["items"].append(_item("scuffing.theta_int", "theta_int", res["theta_int"], "degC", formula_ids=ids, level=lv,
                              level_basis=basis, standard=SI.P))
    return _finish(sub)


def _micropitting(ctx):
    sub = _sub("micropitting", ctx["doc"]["id"])
    if ctx["model"] is None:
        return _model_blocked(sub, ctx)
    if ctx["si"].get("micropitting") is None:
        sub["missing"].append("$.micropitting")
        return _finish(sub)
    mp, r1 = _resolve(ctx, sub, "micropitting")
    oil, r2 = _resolve(ctx, sub, "oil", ctx["si"].get("oil") or {})
    inp = _from_model(ctx, sub, MICRO_FROM_MODEL)
    s_min = mp.pop("S_lambda_min", None)
    for k, v in mp.items():
        if k in inp:
            sub["errors"].append({"path": f"$.micropitting.{k}", "code": "conflict", "message": f"{k} 由设计模型提供，不得重复"})
        inp[k] = v
    for k in ("nu_40", "nu_100", "rho_15"):
        if k in oil:
            inp[k] = oil[k]
    if sub["errors"]:
        return _finish(sub)
    res = MP.rate(inp)
    if res["status"] != "ok":
        sub["missing"] = sorted(set(sub["missing"]) | set(_paths(res.get("missing", []), ("micropitting", "oil"),
                                                                     r1.missing + r2.missing)))
        sub["unconfirmed"] += res.get("unconfirmed", [])
        return _finish(sub)
    ids, lv, basis = EV.item_evidence([MP.S_lambda])
    sub["items"].append(_item("micropitting.S_lambda", "S_lambda", res["S_lambda"], "1", s_min, ">=", formula_ids=ids,
                              level=lv, level_basis=basis, standard=MP.P))
    if s_min is None:
        sub["missing"].append("$.micropitting.S_lambda_min")
    return _finish(sub)


# ================================================================== 轴系（shaft / bearing）
def _shaft_backend():
    return "drivetrain_check.legacy_static"


def _mesh_load(ld):
    mf = SL.mesh_forces(F_tw=ld["F_tw"], alpha_wt_deg=ld["alpha_wt_deg"], beta_w_deg=ld["beta_w_deg"])
    return SL.mesh_point_load(name=ld["name"], x=ld["x"], F_t=mf["F_t"], F_r=mf["F_r"], F_a=mf["F_a"],
                              r_w=ld["d_w"] / 2.0, theta_deg=ld["theta_deg"], tangential_sign=ld["tangential_sign"],
                              axial_sign=ld["axial_sign"])


_LOAD_BUILDERS = {"mesh": _mesh_load,
                  "torque": lambda ld: SL.torque_load(name=ld["name"], x=ld["x"], T=ld["T"]),
                  "line": lambda ld: SL.line_load(name=ld["name"], x0=ld["x0"], x1=ld["x1"], F=ld["F"]),
                  "point": lambda ld: SL.point_load(name=ld["name"], x=ld["x"], y=ld["y"], z=ld["z"], F=ld["F"], C=ld["C"])}


def _solve_shafts(ctx):
    """每根轴：solve（两支承静定）。结果缓存在 ctx，供 shaft 与 bearing 子检查共用。"""
    if ctx["shafts"] is not None:
        return ctx["shafts"]
    out = {}
    shafts = ctx["si"].get("shafts")
    for i, sh in enumerate(shafts or []):
        sid = sh.get("id", f"S{i}")
        r = SIN.Resolver(ctx["design_values"])
        base = f"$.shafts[{i}]"
        v = {k: r.resolve(sh.get(k), f"{base}.{k}") for k in ("x_A", "x_B", "axial_support", "segments", "loads")}
        rec = {"id": sid, "index": i, "sources": dict(r.sources), "missing": list(r.missing), "errors": list(r.errors),
               "model": None, "raw": sh}
        for k in ("x_A", "x_B", "axial_support", "segments", "loads"):
            if sh.get(k) is None:
                rec["missing"].append(f"{base}.{k}")
        if not rec["missing"] and not rec["errors"]:
            try:
                loads = []
                for j, ld in enumerate(v["loads"]):
                    kind = ld.get("kind")
                    if kind not in _LOAD_BUILDERS:
                        raise SL.bad(f"loads[{j}].kind", f"须为 {sorted(_LOAD_BUILDERS)}")
                    loads.append(_LOAD_BUILDERS[kind](ld))
                rec["model"] = DT.legacy_static_solve(x_A=v["x_A"], x_B=v["x_B"], axial_support=v["axial_support"], loads=loads,
                                        segments=v["segments"])
            except Exception as e:  # noqa: BLE001 —— 已有模块的阻断类异常按 code 归类
                rec["exc"] = e
        out[sid] = rec
    ctx["shafts"] = out
    return out


def _shaft(ctx):
    sub = _sub("shaft", ctx["doc"]["id"])
    sub["assumptions"].append(f"轴系后端：{_shaft_backend()}（静定兼容路径）")
    if ctx["si"].get("shafts") is None:
        sub["missing"].append("$.shafts")
        return _finish(sub)
    for sid, rec in _solve_shafts(ctx).items():
        sub["inputs_sources"].update(rec["sources"])
        sub["missing"] += rec["missing"]
        sub["errors"] += rec["errors"]
        if "exc" in rec:
            _absorb(sub, rec["exc"], f"{sid}.")
        sections = rec["raw"].get("sections")
        if sections is None:
            sub["missing"].append(f"$.shafts[{rec['index']}].sections")
            continue
        for j, s in enumerate(sections):
            r = SIN.Resolver(ctx["design_values"])
            sv = r.resolve(s, f"$.shafts[{rec['index']}].sections[{j}]")
            sub["inputs_sources"].update(r.sources)
            name = sv.get("name") or f"S{j + 1}"
            iid = f"shaft.{sid}.{name}"
            if r.missing or r.errors or rec["model"] is None:
                sub["missing"] += r.missing
                sub["errors"] += r.errors
                sub["items"].append(_item(iid, "S", None, "1", None, ">=", status="blocked", standard="DIN 743:2012",
                                          note="截面输入缺项或轴系未求解"))
                continue
            try:
                out = DT.legacy_section_check(model=rec["model"], x=sv["x"], stress_state=sv["stress_state"],
                                       checks=tuple(sv["checks"]), fatigue=sv.get("fatigue"), static=sv.get("static"))
            except Exception as e:  # noqa: BLE001
                _absorb(sub, e, f"{iid}.")
                sub["items"].append(_item(iid, "S", None, "1", None, ">=", status="blocked", standard="DIN 743:2012"))
                continue
            if "fatigue" in out:
                ids, lv, basis = EV.item_evidence([D743.fatigue_proof, D743.safety_fatigue])
                f = out["fatigue"]
                sub["items"].append(_item(f"{iid}.fatigue", "S_D", f.get("S"), "1", sv["fatigue"]["S_min"], ">=",
                                          formula_ids=ids, level=lv, level_basis=basis, standard="DIN 743-1:2012"))
            if "static" in out:
                ids, lv, basis = EV.item_evidence([D743.safety_static])
                st = out["static"]
                sub["items"].append(_item(f"{iid}.static", "S_F", st["S"], "1", st["S_min"], ">=", formula_ids=ids,
                                          level=lv, level_basis=basis, standard="DIN 743-1:2012"))
    sub["missing"] = sorted(set(sub["missing"]))
    return _finish(sub)


def _bearing(ctx):
    sub = _sub("bearing", ctx["doc"]["id"])
    brs = ctx["si"].get("bearings")
    if brs is None:
        sub["missing"].append("$.bearings")
        return _finish(sub)
    loads = {}
    for sid, rec in _solve_shafts(ctx).items():
        refs = rec["raw"].get("bearings") or {}
        for pos_, bid in refs.items():
            loads[bid] = (sid, pos_, rec)
    for bid, spec in brs.items():
        r = SIN.Resolver(ctx["design_values"])
        b = r.resolve({k: v for k, v in spec.items()}, f"$.bearings.{bid}")
        sub["inputs_sources"].update(r.sources)
        iid = f"bearing.{bid}"
        req = b.pop("required_life_h", None)
        if spec.get("required_life_h") is None or spec["required_life_h"].get("value") is None:
            sub["missing"].append(f"$.bearings.{bid}.required_life_h")
        F = b.pop("loads", None)
        if F is None:
            if bid not in loads:
                sub["missing"].append(f"$.bearings.{bid}.loads（或由 shafts[].bearings 引用）")
            else:
                sid, pos_, rec = loads[bid]
                if rec["model"] is None:
                    sub["missing"].append(f"{bid}：轴 {sid} 未求解（支反力不可得，见 shaft 子检查缺项）")
                else:
                    F = rec["model"]["bearing_loads"][pos_]
                    sub["inputs_sources"][f"$.bearings.{bid}.loads"] = f"drivetrain_check 静定求解 轴 {sid} 支承 {pos_} 支反力"
        if r.missing or r.errors or F is None:
            sub["missing"] += r.missing
            sub["errors"] += r.errors
            sub["items"].append(_item(f"{iid}.L10h", "L10h", None, "h", None, ">=", status="blocked",
                                      standard=BRG.STD))
            continue
        try:
            out = DT.legacy_bearing_life(F_r=F["F_r"], F_a=F["F_a"], **b)
        except Exception as e:  # noqa: BLE001
            _absorb(sub, e, f"{iid}.")
            sub["items"].append(_item(f"{iid}.L10h", "L10h", None, "h", None, ">=", status="blocked", standard=BRG.STD))
            continue
        ids, lv, basis = EV.item_evidence([BRG.basic_rating_life, BRG.rating_life_hours])
        sub["items"].append(_item(f"{iid}.L10h", "L10h", out["L10h"], "h", req, ">=", formula_ids=ids, level=lv,
                                  level_basis=basis, standard=BRG.STD, note=f"P = {out['P']:.6g} N"))
        if out.get("Lnmh") is not None:
            ids, lv, basis = EV.item_evidence([BRG.modified_rating_life, BRG.a_iso])
            sub["items"].append(_item(f"{iid}.Lnmh", "Lnmh", out["Lnmh"], "h", req, ">=", formula_ids=ids, level=lv,
                                      level_basis=basis, standard=BRG.STD))
        else:
            sub["assumptions"].append(f"{bid}：{out.get('Lnm_note', '修正寿命未计算')}")
    sub["missing"] = sorted(set(sub["missing"]))
    return _finish(sub)


# ================================================================== key / fit / thermal
_KEY_ARGS = ("d", "h", "t1", "l_tr", "i", "torque_reversal", "Re_shaft", "Re_hub", "Re_key", "hub_brittle", "Rm_hub",
             "K_A", "M_tnenn", "M_tmax", "f_L", "M_tRmin")
_FIT_ARGS = ("U", "D_F", "D_aA", "D_iI", "l_F", "E_A", "E_I", "mu_A", "mu_I", "R_eLA", "R_eLI", "S_PA", "S_PI", "Rz_A",
             "Rz_I", "g_F", "nu_ru", "S_r")


def _list_check(ctx, scope, section, method_ok, run_one):
    sub = _sub(scope, ctx["doc"]["id"])
    raw = ctx["si"].get(section)
    if raw is None:
        sub["missing"].append(f"$.{section}")
        return _finish(sub)
    if raw == []:
        sub["status"] = "not_in_scope"
        sub["reason"] = f"系统层输入显式声明本设计无此类部件（{section}: []）"
        return sub
    for i, entry in enumerate(raw):
        r = SIN.Resolver(ctx["design_values"])
        v = r.resolve(entry, f"$.{section}[{i}]")
        sub["inputs_sources"].update(r.sources)
        iid = f"{scope}.{v.get('id') or i}"
        if v.get("method") not in method_ok:
            sub["missing" if v.get("method") is None else "unconfirmed"].append(
                f"$.{section}[{i}].method（已接入：{method_ok}）")
            sub["items"].append(_item(iid, "", None, "", None, None, status="blocked"))
            continue
        if r.missing or r.errors:
            sub["missing"] += r.missing
            sub["errors"] += r.errors
            sub["items"].append(_item(iid, "", None, "", None, None, status="blocked", note="输入缺项"))
            continue
        try:
            sub["items"] += run_one(iid, v, sub)
        except Exception as e:  # noqa: BLE001
            _absorb(sub, e, f"{iid}.")
            sub["items"].append(_item(iid, "", None, "", None, None, status="blocked"))
    sub["missing"] = sorted(set(sub["missing"]))
    return _finish(sub)


def _key_one(iid, v, sub):
    args = {k: v.get(k) for k in _KEY_ARGS}
    if "din6885_1_table" in (args["h"], args["t1"]):
        row = KEY.key_dimensions(d=args["d"])
        for k in ("h", "t1"):
            if args[k] == "din6885_1_table":
                args[k] = row[k]
                sub["assumptions"].append(f"{iid}.{k} 取 DIN 6885-1 表1（按 d 查表）= {row[k]}")
    out = KEY.method_c(**args)
    ids, lv, basis = EV.item_evidence([KEY.M_tzul, KEY.M_teq, KEY.p_zul])
    items = [_item(f"{iid}.M_teq", "M_teq", out["M_teq"], "N*mm", out["M_tzul"], "<=", formula_ids=ids, level=lv,
                   level_basis=basis, standard=KEY.STD)]
    if out.get("peak_check") not in (None, "not_requested"):
        ids, lv, basis = EV.item_evidence([KEY.M_tmax_permissible])
        items.append(_item(f"{iid}.M_tmax", "M_tmax", out["M_tmax"], "N*mm", out["M_tmax_perm"], "<=", formula_ids=ids,
                           level=lv, level_basis=basis, standard=KEY.STD))
    return items


def _fit_one(iid, v, sub):
    out = FIT.elastic_check_for_interference(**{k: v.get(k) for k in _FIT_ARGS})
    ids, lv, basis = EV.item_evidence([FIT.xi_limits, FIT.reference_effective_interference])
    items = [_item(f"{iid}.xi_outer", "xi_w", out["xi_w"], "1", out["xi_max_outer"], "<=", formula_ids=ids, level=lv,
                   level_basis=basis, standard=FIT.STD, note="外件纯弹性条件"),
             _item(f"{iid}.xi_inner", "xi_w", out["xi_w"], "1", out["xi_max_inner"], "<=", formula_ids=ids, level=lv,
                   level_basis=basis, standard=FIT.STD, note="内件纯弹性条件")]
    ids, lv, basis = EV.item_evidence([FIT.transferable_torque, FIT.pressure_from_xi])
    if out.get("T") is None:
        sub["unconfirmed"].append(f"{iid}：{out.get('note', '纯弹性条件不满足')}")
        items.append(_item(f"{iid}.T", "T", None, "N*mm", v.get("T_required"), ">=", status="blocked", standard=FIT.STD))
    else:
        items.append(_item(f"{iid}.T", "T", out["T"], "N*mm", v.get("T_required"), ">=", formula_ids=ids, level=lv,
                           level_basis=basis, standard=FIT.STD))
    return items


def _key(ctx):
    return _list_check(ctx, "key", "keys", ("C",), _key_one)


def _fit(ctx):
    return _list_check(ctx, "fit", "fits", ("elastic_interference",), _fit_one)


def _thermal_equilibrium(ctx, sub, t):
    """Explicit additional temperature solve; legacy power-rating route kept."""
    units={'method':'-','A_c':'m^2','k':'kW/(m^2*K)','ambient_C':'degC','bracket_C':'degC',
           'temperature_tolerance_C':'K','residual_tolerance_kW':'kW','max_iterations':'1',
           'loss_model':'-','temperature_limit_C':'degC'}
    raw=ctx['si']['thermal']
    for key in set(t)-set(units):
        sub['errors'].append({'path':'$.thermal.'+key,'code':'unknown_input','message':'Unsupported equilibrium input'})
    for key,unit in units.items():
        if t.get(key) is None:sub['missing'].append('$.thermal.'+key)
        elif raw[key].get('unit')!=unit:
            sub['errors'].append({'path':'$.thermal.'+key,'code':'unit_mismatch','message':'Explicit equilibrium unit must be '+unit})
    if sub['missing'] or sub['errors']:return _finish(sub)
    limit=_finite(t['temperature_limit_C'])
    if limit is None:
        sub['errors'].append({'path':'$.thermal.temperature_limit_C','code':'bad_input','message':'Finite temperature limit required'})
        return _finish(sub)
    solved=TB.solve({key:value for key,value in t.items() if key not in ('method','temperature_limit_C')})
    sub['assumptions'].append('Explicit authored loss-model coverage only; no missing loss or housing coefficients inferred; no maximum input-power rating.')
    sub['assumptions'].append('Thermal solver diagnostics: '+json.dumps(solved,ensure_ascii=False,allow_nan=False))
    if solved['status']!='converged':
        sub['errors'].append({'path':'$.thermal','code':'thermal_'+solved['status'],'message':solved.get('reason') or solved['status']})
        return _finish(sub)
    fns=[TH.P_Q,TH.heat_balance_residual]
    components=t['loss_model']['components']
    if components:fns.append(MP.nu_theta)
    fnmap={'mesh':[TH.mesh_friction,TH.mesh_loss],'bearing_churning':[TH.bearing_no_load_torque,TH.bearing_churning_loss],
           'windage_smooth_od':[TH.windage_smooth_od]}
    for c in components:fns+=fnmap[c['type']]
    ids,lv,basis=EV.item_evidence(fns)
    item=_item('thermal.temperature_C','temperature_C',solved['temperature_C'],'degC',limit,'<=',formula_ids=ids,level=lv,
               level_basis=basis,standard=TH.P,note='Oil equilibrium temperature within authored bracket; no ratio safety factor from Celsius values')
    item['margin']=None
    sub['items'].append(item)
    return _finish(sub)


def _thermal(ctx):
    sub = _sub("thermal", ctx["doc"]["id"])
    if ctx["si"].get("thermal") is None:
        sub["missing"].append("$.thermal")
        return _finish(sub)
    t, r = _resolve(ctx, sub, "thermal")
    if sub['errors']:return _finish(sub)
    if 'method' in ctx['si']['thermal'] and t.get('method') is None:
        sub['missing'].append('$.thermal.method')
        return _finish(sub)
    if t.get('method')=='equilibrium':return _thermal_equilibrium(ctx,sub,t)
    if t.get('method') not in (None,'thermal_rating'):
        sub['errors'].append({'path':'$.thermal.method','code':'unsupported_method','message':'Expected equilibrium or thermal_rating'})
        return _finish(sub)
    need = [k for k in ("P_A", "P_L", "P_N") if t.get(k) is None]
    pq_route = t.get("P_Q") is not None or all(t.get(k) is not None for k in ("A_c", "k", "delta_T"))
    sub["missing"] += [f"$.thermal.{k}" for k in need]
    if not pq_route:
        sub["missing"].append("$.thermal.P_Q（或 A_c、k、delta_T）")
    if sub["missing"] or sub["errors"]:
        sub["missing"] = sorted(set(sub["missing"]))
        return _finish(sub)
    try:
        pq = t["P_Q"] if t.get("P_Q") is not None else TH.P_Q(A_c=t["A_c"], k=t["k"], delta_T=t["delta_T"])
        eta = TH.efficiency(P_L=t["P_L"], P_N=t["P_N"], P_A=t["P_A"])
        pt = TH.thermal_rating(P_Q=pq, eta_percent=eta)
    except Exception as e:  # noqa: BLE001
        _absorb(sub, e, "thermal.")
        return _finish(sub)
    fns = [TH.efficiency, TH.thermal_rating] + ([] if t.get("P_Q") is not None else [TH.P_Q])
    ids, lv, basis = EV.item_evidence(fns)
    sub["items"].append(_item("thermal.P_T", "P_T", pt, "kW", t["P_A"], ">=", formula_ids=ids, level=lv,
                              level_basis=basis, standard=TH.P, note=f"η = {eta:.6g} %"))
    sub["assumptions"].append("损失 P_L、P_N 为系统层输入显式给出的总量（由啮合/轴承/密封/搅油分项求和尚未接入，TODO）")
    return _finish(sub)


RUNNERS = {"gear_rating": _gear_rating, "manufacturing": _manufacturing, "scuffing": _scuffing,
           "micropitting": _micropitting, "shaft": _shaft, "bearing": _bearing, "key": _key, "fit": _fit,
           "thermal": _thermal}


# ================================================================== 入口
def normalize_scope(scope):
    if scope == "all":
        return list(SCOPES)
    if isinstance(scope, str):
        scope = [scope]
    if not scope or not isinstance(scope, (list, tuple)):
        raise ValueError(f"scope 须显式给出：'all' 或 {SCOPES} 的非空子集")
    bad = [s for s in scope if s not in SCOPES]
    if bad:
        raise ValueError(f"未知 scope {bad}；可选 {SCOPES}")
    return [s for s in SCOPES if s in scope]


def _package_version():
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def check(design_doc, system_input, scope):
    """统一核算。design_doc：gears.math-source/2 文档；system_input：gears.system-input/1 文档；scope：'all' 或子集。"""
    scope = normalize_scope(scope)
    si_errors = SIN.validate(system_input)
    ref_id = (system_input.get("design_ref") or {}).get("source_id")
    if ref_id is not None and ref_id != design_doc.get("id"):
        si_errors.append({"path": "$.design_ref.source_id", "code": "design_mismatch",
                          "message": f"系统层输入指向 {ref_id!r}，设计文档为 {design_doc.get('id')!r}"})
    checks = {}
    if si_errors:
        for s in SCOPES:
            sub = _sub(s, design_doc.get("id"))
            if s in scope:
                sub["errors"] = list(si_errors)
                sub["reason"] = "系统层输入校验失败"
                _finish(sub)
            else:
                sub["status"], sub["reason"] = "not_in_scope", "未请求"
            checks[s] = sub
        ctx = None
    else:
        ctx = _context(design_doc, system_input)
        for s in SCOPES:
            if s not in scope:
                sub = _sub(s, design_doc.get("id"))
                sub["status"], sub["reason"] = "not_in_scope", "未请求"
                checks[s] = sub
                continue
            try:
                checks[s] = RUNNERS[s](ctx)
            except Exception as e:  # noqa: BLE001 —— 一个子检查失败不影响其它子检查
                sub = _sub(s, design_doc.get("id"))
                sub["errors"].append({"path": s, "code": type(e).__name__, "message": str(e)})
                checks[s] = _finish(sub)
    return _assemble(design_doc, system_input, scope, checks, si_errors)


def _assemble(doc, si, scope, checks, si_errors):
    counts = {k: 0 for k in STATUSES}
    for s in SCOPES:
        counts[checks[s]["status"]] += 1
    req = [checks[s]["status"] for s in scope]
    overall = "fail" if "fail" in req else ("blocked" if "blocked" in req else "pass")
    items = [i for s in scope for i in checks[s]["items"]]
    item_dist = {}
    for i in items:
        if i["status"] in ("pass", "fail", "info"):
            item_dist[i["evidence_level"]] = item_dist.get(i["evidence_level"], 0) + 1
    ext = [dict(r, scope=s) for s in scope for r in checks[s]["external_refs"]]
    unverified = [{"scope": s, "id": i["id"], "status": i["status"], "evidence_level": i["evidence_level"]}
                  for s in scope for i in checks[s]["items"] if i["evidence_level"] not in ("E5", "E6")]
    requests = []
    for s in scope:
        c = checks[s]
        if c["status"] in ("pass", "fail"):
            low = [i["id"] for i in c["items"] if i["evidence_level"] not in ("E5", "E6")]
            same = [r["file"] for r in c["external_refs"] if r["relation"] == "same_design"]
            if low:
                requests.append({"scope": s, "kisssoft_module": KISSSOFT_MODULE[s], "items": low,
                                 "existing_same_design_refs": same,
                                 "purpose": "本设计同输入外部复核（逐字段对齐输入后比较输出）；未经复核的条目证据等级不提升"})
    assumptions = [{"scope": "system_input", "text": a.get("text", ""), "source": a.get("source", "")}
                   for a in (si.get("assumptions") or [])]
    assumptions += [{"scope": s, "text": a, "source": "design_check 装配"} for s in scope for a in checks[s]["assumptions"]]
    try:
        dsha = MS.source_sha256(doc)
    except (TypeError, ValueError):
        dsha = None
    return {
        "schema": RESULT_SCHEMA_ID, "package_version": _package_version(),
        "design_id": doc.get("id"), "design_sha256": dsha,
        "system_input_id": si.get("id"), "system_input_sha256": SIN.sha256(si),
        "scope_requested": list(scope), "disclaimer": DISCLAIMER,
        "input_errors": list(si_errors),
        "computation": {"status": overall, "counts": counts,
                        "note": "计算结果：pass/fail 只就所给输入与所列标准公式而言；blocked = 缺输入或条文未确认"},
        "evidence_qualification": {
            "item_level_distribution": dict(sorted(item_dist.items())),
            "module_registry_distribution": {s: checks[s]["module_evidence_distribution"] for s in scope
                                             if checks[s]["module_evidence_distribution"] is not None},
            "external_refs": ext, "external_ref_files": sorted({r["file"] for r in ext}),
            "unverified_items": unverified,
            "note": "证据资格与计算结果分开：等级只读各模块已有元数据（E5 = KISSsoft 同输入逐字段一致；none = 无外部算例/未评估），"
                    "正式等级以 data/registry 评定为准；证据资格高也不等于工程验收"},
        "external_review_requests": requests,
        "assumptions": assumptions,
        "checks": checks,
    }


# ================================================================== 结果模式
_RSCHEMA = None


def result_schema():
    global _RSCHEMA
    if _RSCHEMA is None:
        _RSCHEMA = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _RSCHEMA


def validate_result(result):
    """结果 JSON（先经 JSON 往返，确保可序列化）对照 data/schema/gears.design-check-result-1.schema.json。"""
    return SD.validate_schema(json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False)), result_schema())


def check_files(design_id, system_input_id, scope):
    """按 id 读取 data/source/<id>.math-source.json 与 data/system/<id>.system-input.json 后核算（MCP/CLI 用）。"""
    doc = MS.load_file(ROOT / "data" / "source" / f"{design_id}.math-source.json")
    return check(doc, SIN.load(system_input_id), scope)
