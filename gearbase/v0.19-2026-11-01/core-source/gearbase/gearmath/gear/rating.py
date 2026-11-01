"""统一校核计算器：所有校核都是"公式图里的一个量 + 一个限值"，结果格式统一。

用户输入缺失或不合格时，rate 返回 blocked_* 状态（不抛异常、不给"通过"）：
  blocked_invalid_inputs   量纲不符、未被使用的输入等
  blocked_edition_mismatch 版次配置与公式库该分册的版次不一致
  blocked_missing_inputs   缺输入（含校核限值）或缺某分册的版次配置（missing_editions）
  blocked_missing_selectors 方法选择器未选（如 method.K_V），errors 与 options 列出可选项；不使用默认方法
  blocked_evaluation_error 求值失败（如超出函数定义域）
"""
from __future__ import annotations

from dataclasses import dataclass

from ..kernel.expr import FormulaError
from ..kernel.graph import Model
from ..kernel.select import external, specialize, variant
from .formulas import CYLINDRICAL_PAIR, ROOT_GENERATING, ROOT_SHIFT_OUTPUTS
from .inputs import input_specs


@dataclass(frozen=True)
class Check:
    id: str
    quantity: str          # 图中的量
    limit: str             # 限值所在的输入名
    sense: str             # ">=" 或 "<="
    ref: str               # 标准分册（不含版次；版次取自模型的版次配置），空 = 非标准规则


CHECKS = [
    Check("pitting.pinion", "S_H_1", "S_Hmin", ">=", "ISO 6336-2"),
    Check("pitting.wheel", "S_H_2", "S_Hmin", ">=", "ISO 6336-2"),
    Check("bending.pinion", "S_F_1", "S_Fmin", ">=", "ISO 6336-3"),
    Check("bending.wheel", "S_F_2", "S_Fmin", ">=", "ISO 6336-3"),
    Check("geometry.contact_ratio", "eps_alpha", "eps_alpha_min", ">=", "ISO 21771"),
]

# 本公式库各分册按以下版次编写；案例装配时须显式声明版次配置（不作为隐式默认值）
LIBRARY_EDITIONS = {"ISO 21771": "2007", "ISO 6336-1": "2019", "ISO 6336-2": "2019", "ISO 6336-3": "2019"}


# 方法选择器（K3）：选择器名 → 可选取值与含义。没有隐式默认值：不选则模型求值阻断（blocked_missing_selectors）
SELECTOR_OPTIONS = {
    "method.K_V": {"B": "ISO 6336-1:2019 方法B：K_V 由 gear/dynamic.py 公式推出（派生量），需要方法B 的输入",
                   "external": "K_V 作为 evidence 输入提供（如 M31 收据回放），不由本库公式计算"},
    "method.m_red": {"eq30": "ISO 6336-1:2019 6.5.9 式(30)：标准给出的近似式，隐含 dm2/dm1 = u（PDF 45 页）",
                     "exact": "ISO 6336-1:2019 6.5.3 式(7)(8)：两轮各自 m* = J*/rb² 再折算（PDF 37 页）"},
    "method.f_pb": {"fpt": "ISO 6336-1:2019 表2：fpb 可用 fpt 代替（PDF 14 页）",
                    "fpbT": "基节公差 fpbT = fpT·cosαt（TR30:2022正式版4.2.1式(1)，不圆整；PDF12原图已核）"},
    "method.K_Hbeta": {"C": "ISO 6336-1:2019 7.5 方法C：K_Hβ 由 gear/load_distribution.py 公式推出（需 method.K_V=B）",
                       "external": "K_Hβ 作为 evidence 输入提供，不由本库公式计算"},
    "method.K_Halpha": {"B": "ISO 6336-1:2019 8.3 方法B：K_Hα、K_Fα 由 gear/load_distribution.py 公式推出（需 method.K_V=B）",
                        "external": "K_Hα、K_Fα 作为 evidence 输入提供，不由本库公式计算"},
    "method.root_shift": {"nominal": "齿根 YF/YS 式(24)(27) 用名义变位 x（ISO 6336-3:2019 6.1 d) 齿厚余量可忽略；偏不安全）",
                          "generating": "用最小产形变位 xE,min = x + Asn,i/(2mn·tanαn)（ISO 6336-3:2019 6.1 推荐；需 A_sn_i_1/2）"},
}
# 只在另一选择器取某值时才需要（也才允许）的选择器
SELECTOR_REQUIRES = {"method.m_red": ("method.K_V", "B"), "method.f_pb": ("method.K_V", "B")}
# 公式路径的前提：K_Hβ 方法C、K_Hα 方法B 复用方法B 的 cγ、Fm/b（gear/dynamic.py），故要求 method.K_V=B
SELECTOR_NEEDS_KVB = {"method.K_Hbeta": "C", "method.K_Halpha": "B"}
# 缺选择器时只为装配（让调用方能设输入）所用的占位取值；模型仍阻断求值，不是默认方法
_PLACEHOLDER = {"method.m_red": "eq30", "method.f_pb": "fpt", "method.K_Hbeta": "external",
                "method.K_Halpha": "external", "method.root_shift": "nominal"}


def pair_variants():
    """圆柱齿轮副的全部公式变体：通用公式 + 各方法选择器下的公式 / 外部证据（external）。"""
    from .dynamic import DYNAMIC_B, F_PB_VARIANTS, M_RED_VARIANTS       # 延迟导入：避免循环
    from .load_distribution import KHALPHA, KHBETA
    kvb = {"method.K_V": "B"}
    rows = [variant(f, {"method.root_shift": "nominal"} if f.output in ROOT_SHIFT_OUTPUTS else {})
            for f in CYLINDRICAL_PAIR]
    rows += [variant(f, {"method.root_shift": "generating"}) for f in ROOT_GENERATING]
    rows += [variant(f, kvb) for f in DYNAMIC_B]
    rows += [variant(f, {**kvb, "method.m_red": k}) for k, fs in M_RED_VARIANTS.items() for f in fs]
    rows += [variant(f, {**kvb, "method.f_pb": k}) for k, fs in F_PB_VARIANTS.items() for f in fs]
    rows += [external("K_V", "1", {"method.K_V": "external"}, ref="ISO 6336-1:2019 K_V 由证据输入提供")]
    # Fm/b 同时供 K_Hβ 方法C 与 K_Hα 方法B，随方法B 出现
    rows += [variant(f, kvb if f.output == "Fm_b" else {"method.K_Hbeta": "C"}) for f in KHBETA]
    rows += [external("K_Hbeta", "1", {"method.K_Hbeta": "external"}, ref="ISO 6336-1:2019 K_Hβ 由证据输入提供")]
    rows += [variant(f, {"method.K_Halpha": "B"}) for f in KHALPHA]
    rows += [external(q, "1", {"method.K_Halpha": "external"}, ref=f"ISO 6336-1:2019 {q} 由证据输入提供")
             for q in ("K_Halpha", "K_Falpha")]
    return rows


def _options_text(names=None):
    return "；".join(f"{k} ∈ {{{', '.join(f'{v}（{d}）' for v, d in opts.items())}}}"
                    for k, opts in SELECTOR_OPTIONS.items() if names is None or k in names)


def required_selectors(sel):
    """在已选取值 sel 下必须选择的选择器（K_V 未选时，其从属选择器暂不列出）。"""
    return [k for k in SELECTOR_OPTIONS
            if k not in SELECTOR_REQUIRES or sel.get(SELECTOR_REQUIRES[k][0]) == SELECTOR_REQUIRES[k][1]]


def check_selectors(sel):
    """取值合法性与组合规则；不合法 → FormulaError（列出可选项）。"""
    bad = [f"{k}={v!r}" for k, v in sel.items() if k not in SELECTOR_OPTIONS or v not in SELECTOR_OPTIONS[k]]
    if bad:
        raise FormulaError(f"选择器取值无效：{'、'.join(bad)}；可选：{_options_text()}")
    for k, (dep, val) in SELECTOR_REQUIRES.items():
        if k in sel and dep in sel and sel[dep] != val:
            raise FormulaError(f"选择器 {k} 只在 {dep}={val} 时适用，当前 {dep}={sel[dep]}")
    for k, val in SELECTOR_NEEDS_KVB.items():
        if sel.get(k) == val and sel.get("method.K_V", "B") != "B":
            raise FormulaError(f"{k}={val} 复用方法B 的 cγ 与 Fm/b，需要 method.K_V=B（当前 {sel['method.K_V']}）；该组合未实现")


def pair_model(editions=None, formulas=None, selectors=None, selector_sources=None, extra_formulas=(), extra_inputs=(),
               factor_selectors=None, factor_selector_sources=None):
    """圆柱齿轮副模型：带输入声明表；editions 为按分册的版次配置（缺省为空 → 求值时阻断）。

    formulas 缺省 = 本库全部变体，由 selectors（如 {"method.K_V": "B" | "external"}）特化成一个输出一条公式；
    选择器不在 SELECTOR_OPTIONS 内、取值非法 → FormulaError；缺选择器 → 返回的模型求值/校核时阻断
    （blocked_missing_selectors，列出可选项），不使用默认方法。选择器取值写入 model_sha256 与校核输出。
    formulas 显式给出 = 自带公式库（测试、自定义），不经选择器，selectors 仅作记录。
    extra_formulas / extra_inputs：案例专用附加公式及其输入声明（如 KISSsoft 案例的轮坯 C_R 式(87)），
    其输出不得与特化后的库公式重名（重名 → Model 装配报错）。
    factor_selectors=None 保持 v0.4 回放接口；传入映射（包括 {}）启用新增系数方法组，
    三组都必须显式选择（缺项阻断）。公式子集原文核验状态另列 factor_validation。"""
    sel = {str(k): str(v) for k, v in (selectors or {}).items()}
    src = dict(selector_sources or {})
    if formulas is not None:
        if factor_selectors is not None:
            raise FormulaError("自带 formulas 与 factor_selectors 不可同时使用；请显式装配公式集")
        m = Model(formulas, inputs=input_specs(formulas), editions=editions)
        m.selectors, m.selector_sources = sel, src
        return m
    check_selectors(sel)
    missing = [k for k in required_selectors(sel) if k not in sel]
    # 缺选择器时仍按占位取值装配（K_V 缺省形态为外部证据），只为让调用方能设输入；它不能求值
    fill = dict(_PLACEHOLDER)
    fill["method.K_V"] = "B" if any(sel.get(k) == v for k, v in SELECTOR_NEEDS_KVB.items()) else "external"
    full = {**sel, **{k: fill[k] for k in missing}}
    full.update({k: fill[k] for k in required_selectors(full) if k not in full})
    spec = specialize(pair_variants(), full, prune=True)
    factor_spec, factor_table, factor_missing = [], [], []
    factor_validation = {}
    if factor_selectors is not None:
        from .factor_methods import compile_factors, validation_status
        factor_spec, factor_table, factor_missing = compile_factors(factor_selectors)
        fsel = {str(k): str(v) for k, v in factor_selectors.items()}
        sel.update(fsel)
        src.update(factor_selector_sources or {})
        factor_validation = validation_status(fsel)
    base = list(spec)
    if factor_selectors is not None and "method.Z_BD" in factor_selectors:
        # 显式表3方法（含fZCa）替换主图隐含fZCa=1.0的pit.Z_B/Z_D；只在调用方明确选择时发生
        base = [f for f in base if f.output not in ("Z_B", "Z_D")]
    fs = base + list(factor_spec) + list(extra_formulas)
    table = None
    if extra_inputs or factor_table:
        from .inputs import full_input_table
        table = full_input_table() + list(factor_table) + list(extra_inputs)
    m = Model(fs, inputs=input_specs(fs, table), editions=editions)
    m.selectors, m.selector_sources = sel, src
    m.required_evidence = {} if missing else dict(spec.required_evidence)
    if factor_selectors is not None:
        m.required_evidence.update(factor_spec.required_evidence)
        m.factor_validation = factor_validation
    m.unresolved = [{"name": k, "code": "missing_selector",
                     "message": f"未选择方法：{_options_text([k])}；请显式选择，库不提供隐式默认"} for k in missing]
    m.unresolved.extend(factor_missing)
    return m


def rate(model: Model, checks=CHECKS, wrt=(), extra=()):
    targets = [c.quantity for c in checks] + list(extra)
    res = model.evaluate(targets, wrt=wrt)
    limits = {c.limit for c in checks}
    head = {"model_sha256": res.model_sha256, "editions": dict(model.editions),
            "edition_sources": dict(model.edition_sources), "inputs_by_provenance": model.inputs_by_provenance(),
            "selectors": dict(model.selectors), "selector_sources": dict(model.selector_sources),
            "domain_violations": res.domain_violations}
    if res.status == "blocked_missing_selectors":
        from .factor_methods import FACTOR_OPTIONS
        return {"status": res.status, "errors": list(res.errors),
                "options": {**SELECTOR_OPTIONS, **FACTOR_OPTIONS}, "checks": [], **head}
    if hasattr(model, "factor_validation"):
        head["factor_validation"] = model.factor_validation
    unused = model.unused_inputs(limits)
    errors = list(res.errors) + [{"name": k, "code": "unused_input", "message": f"输入 {k} 未被任何公式或校核使用（拼写错误？）"}
                                 for k in unused]
    for q, req in model.required_evidence.items():    # external 选择器：该量必须是 evidence 输入
        i = model.inputs.get(q)
        if i is not None and i.provenance != "evidence":
            errors.append({"name": q, "code": "external_requires_evidence",
                           "message": f"{q} 选择了 external，来源必须是 evidence，实际为 {i.provenance}"})
    if res.status in ("blocked_invalid_inputs", "blocked_edition_mismatch") or unused or \
            any(e["code"] == "external_requires_evidence" for e in errors):
        status = res.status if res.status in ("blocked_invalid_inputs", "blocked_edition_mismatch") else "blocked_invalid_inputs"
        return {"status": status, "errors": errors, "checks": [], **head}
    missing = sorted(set(res.missing) | {k for k in limits if k not in model.inputs})
    missing_ed = sorted(set(res.missing_editions) | {c.ref for c in checks if c.ref and c.ref not in model.editions})
    if missing or missing_ed:
        return {"status": "blocked_missing_inputs", "missing": missing, "missing_editions": missing_ed, "checks": [], **head}
    if res.status == "blocked_evaluation_error":
        return {"status": res.status, "errors": errors, "checks": [], **head}
    rows = []
    for c in checks:
        v = res.values[c.quantity]
        lim = model.inputs[c.limit].value
        margin = v / lim if c.sense == ">=" else (lim / v if v else float("inf"))
        ed = model.editions.get(c.ref, "")
        rows.append({"id": c.id, "quantity": c.quantity, "value": v, "limit": lim, "sense": c.sense,
                     "margin_ratio": margin, "pass": margin >= 1.0,
                     "ref": f"{c.ref}:{ed}" if c.ref else "", "standard": c.ref, "edition": ed})
    status = "out_of_domain" if res.status == "out_of_domain" else ("pass" if all(r["pass"] for r in rows) else "fail")
    return {"status": status, "checks": rows, **head, "result": res}


# M31 C001 第一级（G1）：几何与工况来自 M31 案例；以下"证据系数"取自 M31 收据
# benchmark50/results/m31/workflow/gear-rating.json（python-gearbox 计算），本原型不重算它们。
C001_G1_EVIDENCE = {
    "K_A": 1.25, "K_V": 1.0391660518198986, "K_Hbeta": 2.5744814242724336,
    "K_Halpha": 1.0180576156848296, "K_Falpha": 1.0180576156848296,
    "Z_L": 0.9967176032217998, "Z_V": 0.9632050832991362, "Z_R": 0.9626793277278641,
    "Z_W": 1.0, "Z_X": 1.0, "Z_NT_1": 0.8986828885438193, "Z_NT_2": 0.9088190004202857,
    "Y_ST": 2.0, "Y_NT_1": 0.9011881827603812, "Y_NT_2": 0.9118636156617996,
    "Y_drelT_1": 0.9628281561600809, "Y_drelT_2": 0.9758190332859351,
    "Y_RrelT_1": 1.014789805373408, "Y_RrelT_2": 1.014789805373408,
    "Y_X": 1.0, "Y_B": 1.0, "Y_DT": 1.0,
}


# C001 G1 回放契约：K 系数取自 M31 收据（python-gearbox 计算，evidence）；齿根用名义变位（M31 案例无齿厚公差，
# python-gearbox 亦用名义 x；相对 ISO 6336-3:2019 6.1 的推荐口径偏不安全，见 docs/接续文档.md）
C001_G1_SELECTORS = {"method.K_V": "external", "method.K_Hbeta": "external", "method.K_Halpha": "external",
                     "method.root_shift": "nominal"}
C001_G1_SELECTOR_SOURCES = {
    "method.K_V": "c001_g1 回放 M31 收据：K_V 取自 gear-rating.json（evidence）",
    "method.K_Hbeta": "c001_g1 回放 M31 收据：K_Hβ 取自 gear-rating.json（evidence；M31 案例无方法C 所需轴系输入）",
    "method.K_Halpha": "c001_g1 回放 M31 收据：K_Hα/K_Fα 取自 gear-rating.json（evidence）",
    "method.root_shift": "c001_g1：M31 案例无齿厚公差，按 python-gearbox 口径用名义变位",
}


def c001_g1(model=None, *, z1=20, z2=36, m_n=2.0, b=30.0, x1=0.0, x2=0.0, beta_deg=0.0):
    m = model or pair_model(selectors=C001_G1_SELECTORS, selector_sources=C001_G1_SELECTOR_SOURCES)
    src = "M31 C001 案例 benchmark50/results/m31/workflow/derived-candidate.json"
    m.set_editions(LIBRARY_EDITIONS, "M31 C001 engineering.standard = ISO6336-1/-2/-3:2019；ISO 21771 版次随本公式库")
    m.set("z_1", z1, "1", "user", src).set("z_2", z2, "1", "user", src)
    m.set("m_n", m_n, "mm", "user", src).set("alpha_n", 20, "deg", "user", src).set("beta", beta_deg, "deg", "user", src)
    m.set("x_1", x1, "1", "user", src).set("x_2", x2, "1", "user", src).set("b", b, "mm", "user", src)
    m.set("haP", 1.0, "1", "user", "M31 刀具 addendum_coefficient").set("hfP", 1.25, "1", "user", "M31 刀具 dedendum_coefficient")
    m.set("rhofP", 0.38, "1", "user", "M31 刀具 root_fillet_radius_coefficient")
    m.set("T_1", 25, "N*m", "user", src).set("n_1", 900, "rpm", "user", src)
    m.set("E", 206000, "MPa", "evidence", "M31 材料假设").set("nu", 0.3, "1", "evidence", "M31 材料假设")
    m.set("sigma_Hlim_1", 1500, "MPa", "assumption", "M31 材料假设 contact_stress_limit").set("sigma_Hlim_2", 1500, "MPa", "assumption", "同上")
    m.set("sigma_Flim_1", 460, "MPa", "assumption", "M31 材料假设 bending_stress_limit").set("sigma_Flim_2", 460, "MPa", "assumption", "同上")
    for k, v in C001_G1_EVIDENCE.items():
        if k in m.formulas:      # 所选方法下该系数是派生量（如 method.K_V=B 时的 K_V），不用收据值锁定
            continue
        m.set(k, v, "1", "evidence", "M31 gear-rating.json（python-gearbox）")
    m.set("S_Hmin", 1.1, "1", "user", "M31 operating.min_safety_pitting").set("S_Fmin", 1.2, "1", "user", "M31 operating.min_safety_bending")
    m.set("eps_alpha_min", 1.2, "1", "user", "设计规则（示例）")
    return m
