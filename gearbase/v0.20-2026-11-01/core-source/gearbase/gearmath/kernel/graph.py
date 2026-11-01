"""计算图：公式（数据）+ 输入（带来源）→ 有序求值、量纲校核、适用域校核、溯源、灵敏度。

本模块不知道齿轮。它只认识"变量、公式、单位、来源、适用域、输入声明、标准分册版次"。
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import re
from dataclasses import dataclass, field

from . import dual as D
from . import evidence as EV
from . import units as U
from .expr import Expr, FormulaError

PROVENANCE = {"user", "standard_constant", "derived", "evidence", "optimizer", "agent_proposed", "assumption"}

# 条款引用开头的"分册:年份"，如 "ISO 6336-2:2019 …" → ("ISO 6336-2", "2019")
_STD_REF = re.compile(r"^([A-Z][A-Z/]*(?: [A-Z]+)? \d[\d.]*(?:-\d+)*):(\d{4})(?!\d)")


@functools.lru_cache(maxsize=8192)
def compile_expr(text: str) -> Expr:
    """按文本缓存编译结果（Expr 编译后不可变），避免每次装配模型都重新解析。"""
    return Expr(text)


# 已通过量纲校核的 (公式集与声明指纹, 求值顺序, 输入量纲)；模型实例间共享
_DIM_OK: set = set()


def parse_standard_ref(ref: str):
    """从引用文本解析 (标准分册, 版次)；非标准引用返回 ("", "")。"""
    m = _STD_REF.match(ref or "")
    return (m.group(1), m.group(2)) if m else ("", "")


class InputError(ValueError):
    """用户输入不合格（未声明、量纲不符、超出取值域……）。code 供工具层结构化返回。"""

    def __init__(self, name, code, message):
        super().__init__(message)
        self.name, self.code = name, code

    def as_dict(self):
        return {"name": self.name, "code": self.code, "message": str(self)}


@dataclass(frozen=True)
class Formula:
    """一条公式。kind="explicit"：output = expr；kind="fixed_point"：output = expr(output)，从 start 迭代。"""
    id: str
    output: str
    unit: str
    expr: str
    ref: str                      # 标准条款引用（只引用编号，不复制原文）
    domain: tuple = ()            # 适用域谓词，如 "z1 >= 18"
    kind: str = "explicit"
    start: float = 0.0
    tol: float = 1e-14            # 不动点迭代停止阈值（相邻两次迭代值之差的绝对值）；非默认值进入 model_sha256
    note: str = ""
    standard: str = ""            # 标准分册，如 "ISO 6336-2"；空 = 非标准公式。缺省时从 ref 解析
    edition: str = ""             # 该分册版次（年份）
    fixed_point_derivative: str = "implicit"  # finite_iteration: AD of the stopped value map

    def __post_init__(self):
        if self.fixed_point_derivative not in ("implicit", "finite_iteration"):
            raise FormulaError(f"{self.id}：未知不动点导数策略 {self.fixed_point_derivative!r}")
        if not self.standard and not self.edition:
            std, ed = parse_standard_ref(self.ref)
            object.__setattr__(self, "standard", std)
            object.__setattr__(self, "edition", ed)
        if bool(self.standard) != bool(self.edition):
            raise FormulaError(f"{self.id}：标准分册与版次必须同时给出（{self.standard!r} / {self.edition!r}）")

    def compiled(self) -> Expr:
        if U.is_affine(self.unit):   # K9：公式内一律用 K，degC 只在 set/get 边界
            raise FormulaError(f"{self.id}：公式声明单位不能是仿射单位 {self.unit}，请用 K")
        return compile_expr(self.expr)


@dataclass(frozen=True)
class InputSpec:
    """输入声明：期望单位（只比较量纲，同量纲的其它单位可用）、含义、取值域（规范单位谓词）、角色。"""
    name: str
    unit: str
    description: str = ""
    domain: tuple = ()
    role: str = "input"           # input | limit（限值：只被校核使用）


@dataclass
class Input:
    value: float                  # 规范单位
    unit: str
    provenance: str
    source: str = ""


@dataclass
class Result:
    # ok | out_of_domain | blocked_missing_inputs | blocked_invalid_inputs | blocked_edition_mismatch
    # | blocked_missing_selectors（方法选择器未选）| blocked_evaluation_error
    status: str
    values: dict = field(default_factory=dict)       # 名称 -> 规范单位数值
    duals: dict = field(default_factory=dict)        # 名称 -> Dual
    missing: list = field(default_factory=list)
    missing_editions: list = field(default_factory=list)   # 用到但未配置版次的标准分册
    errors: list = field(default_factory=list)
    domain_violations: list = field(default_factory=list)
    editions: dict = field(default_factory=dict)     # 本次求值使用的版次配置
    model_sha256: str = ""
    # 每个派生输出的有效证据等级（依赖链最弱一环）：名称 → {"level","own_level","weakened_by","chain_size"}；
    # 只是附加信息，不影响数值与 status；规则见 evidence.py
    evidence: dict = field(default_factory=dict)

    def get(self, name, unit=None, model=None):
        v = self.values[name]
        if unit:
            return U.from_canonical(v, unit)
        return v


class Model:
    """inputs：输入声明（InputSpec 序列）；给出后，未声明的输入与量纲不符的单位在 set 时即被拒绝。
    editions：按标准分册的版次配置，如 {"ISO 6336-2": "2019", "ISO 6336-3": "2006"}；
    用到某分册而未配置版次时求值阻断，不使用默认值。"""

    def __init__(self, formulas, inputs=None, editions=None):
        self.formulas = {}
        for f in formulas:
            if f.output in self.formulas:
                raise FormulaError(f"输出 {f.output} 被多条公式定义（唯一真源冲突）：{self.formulas[f.output].id} / {f.id}")
            self.formulas[f.output] = f
        # 同一模型内，同一分册的公式只能来自同一版次；不同分册可以不同
        by_part: dict[str, dict[str, list]] = {}
        for f in self.formulas.values():
            if f.standard:
                by_part.setdefault(f.standard, {}).setdefault(f.edition, []).append(f.id)
        for part, eds in by_part.items():
            if len(eds) > 1:
                detail = "；".join(f"{part}:{e}（{ids[0]} 等 {len(ids)} 条）" for e, ids in sorted(eds.items()))
                raise FormulaError(f"标准分册 {part} 在同一模型中混用了多个版次：{detail}")
        self.standard_editions = {part: next(iter(eds)) for part, eds in by_part.items()}
        self.inputs: dict[str, Input] = {}
        self._exprs = {k: f.compiled() for k, f in self.formulas.items()}
        self._dom = {k: [compile_expr(p) for p in f.domain] for k, f in self.formulas.items()}
        self._used = set()
        for k in self.formulas:
            self._used |= set(self._exprs[k].names)
            for p in self._dom[k]:
                self._used |= set(p.names)
        self.specs: dict[str, InputSpec] = {}
        self._spec_dom = {}
        for s in inputs or ():
            if s.name in self.formulas:
                raise FormulaError(f"{s.name} 既被声明为输入，又由公式 {self.formulas[s.name].id} 输出")
            if s.name in self.specs:
                raise FormulaError(f"输入 {s.name} 被重复声明")
            U.unit(s.unit)
            doms = [compile_expr(p) for p in s.domain]
            for p in doms:
                if set(p.names) - {s.name}:
                    raise FormulaError(f"输入 {s.name} 的取值域只能引用自身：{p.text}")
            self.specs[s.name], self._spec_dom[s.name] = s, doms
        self.editions: dict[str, str] = {}
        self.edition_sources: dict[str, str] = {}
        # 方法选择器（K3）：由装配层（specialize）写入；取值进入 sha256。unresolved 非空 = 有选择器未选，求值阻断
        self.selectors: dict[str, str] = {}
        self.selector_sources: dict[str, str] = {}
        self.unresolved: list = []
        self.evidence_levels: dict = {}        # 公式 id → 证据等级（来自注册表）；不进入 model_sha256；缺省 = 未评估
        self.provenance_caps: dict = dict(EV.PROVENANCE_CAP)
        self.required_evidence: dict = {}      # external 选择器要求的 evidence 输入：量 → {"unit","ref",...}
        if editions:
            self.set_editions(editions)
        self._fingerprint = hash((tuple(self.formulas.values()), tuple(self.specs.values())))

    # ---- 版次配置 ----
    def set_edition(self, part, edition, source=""):
        if not isinstance(part, str) or not part.strip() or not isinstance(edition, str) or not edition.strip():
            raise InputError(f"edition:{part}", "invalid_edition", f"版次配置必须是 分册名 → 版次 的非空字符串：{part!r} → {edition!r}")
        self.editions[part], self.edition_sources[part] = edition, source
        return self

    def set_editions(self, editions, source=""):
        for part, ed in dict(editions).items():
            self.set_edition(part, ed, source)
        return self

    def set_evidence_levels(self, mapping):
        """登记公式的证据等级（公式 id → "E0".."E6" | "unassessed"），供 evaluate 传播；不改变数值与模型指纹。"""
        self.evidence_levels.update(EV.check_levels(mapping))
        return self

    # ---- 输入 ----
    def set(self, name, value, unit, provenance="user", source=""):
        if provenance not in PROVENANCE:
            raise InputError(name, "unknown_provenance", f"未知来源类别 {provenance}")
        if name in self.formulas:
            raise InputError(name, "derived_locked", f"{name} 是派生量，不能作为输入锁定（{self.formulas[name].id}）")
        spec = self.specs.get(name)
        if self.specs and spec is None:
            raise InputError(name, "undeclared_input", f"{name} 不是本模型声明的输入（拼写错误，或未在输入声明表中登记）")
        if unit not in U.UNITS:
            raise InputError(name, "unknown_unit", f"{name}：未登记的单位 {unit}")
        dim, k = U.unit(unit)
        if spec is not None and dim != U.unit(spec.unit)[0]:
            want = U.unit(spec.unit)[0]
            raise InputError(name, "unit_dimension_mismatch",
                             f"{name}（{spec.description or spec.name}）期望量纲 {U.show(want)}（如 {spec.unit}），"
                             f"收到单位 {unit}（量纲 {U.show(dim)}）")
        if isinstance(value, bool):
            raise InputError(name, "not_a_number", f"{name}：数值不能是布尔值")
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise InputError(name, "not_a_number", f"{name}：数值无法解析 {value!r}") from None
        if not math.isfinite(v):
            raise InputError(name, "not_a_number", f"{name}：数值必须有限，收到 {value!r}")
        v = U.to_canonical(v, unit)
        for p in self._spec_dom.get(name, ()):
            if not p.evaluate({name: v}):
                raise InputError(name, "out_of_domain", f"{name} = {value} {unit} 超出取值域 {p.text}（规范单位）")
        self.inputs[name] = Input(v, unit, provenance, source)
        return self

    def unused_inputs(self, also_used=()):
        """已设置、但既没有被公式引用、也没有被声明、也不在 also_used（如校核限值）中的输入。"""
        return sorted(k for k in self.inputs if k not in self._used and k not in self.specs and k not in set(also_used))

    def inputs_by_provenance(self):
        out = {}
        for k, i in sorted(self.inputs.items()):
            out.setdefault(i.provenance, []).append(k)
        return out

    # ---- 编译期：依赖与量纲 ----
    def _deps(self, name):
        e = self._exprs[name]
        return [n for n in e.names if n != name]

    def order(self, targets):
        seen, out, stack = set(), [], set()

        def visit(n):
            if n in seen or n not in self.formulas:
                return
            if n in stack:
                raise FormulaError(f"循环依赖：{n}")
            stack.add(n)
            for d in self._deps(n):
                visit(d)
            for p in self._dom[n]:
                for d in p.names:
                    if d != n:
                        visit(d)
            stack.discard(n)
            seen.add(n)
            out.append(n)

        for t in targets:
            visit(t)
        return out

    def check_dimensions(self, targets=None):
        dims = {k: U.unit(s.unit)[0] for k, s in self.specs.items()}
        dims.update({k: U.unit(i.unit)[0] for k, i in self.inputs.items()})
        for k, f in self.formulas.items():
            dims.setdefault(k, U.unit(f.unit)[0])
        for name in self.order(targets or list(self.formulas)):
            f = self.formulas[name]
            got = self._exprs[name].dimension(dims)
            want = U.unit(f.unit)[0]
            if got != want:
                raise FormulaError(f"{f.id}：推断量纲 {U.show(got)} 与声明单位 {f.unit} 不符")
        return True

    def sha256(self):
        payload = {"formulas": sorted((f.id, f.output, f.unit, f.expr, f.ref, f.domain, f.kind, f.standard, f.edition)
                                      + (() if f.tol == 1e-14 else (f.tol,))
                                      + (() if f.fixed_point_derivative == "implicit" else (f.fixed_point_derivative,))
                                      for f in self.formulas.values()),
                   "inputs": sorted((k, i.value, i.unit, i.provenance) for k, i in self.inputs.items()),
                   "input_specs": sorted((s.name, s.unit, s.domain, s.role) for s in self.specs.values()),
                   "editions": sorted(self.editions.items()),
                   "selectors": sorted(self.selectors.items())}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    # ---- 求值 ----
    def evaluate(self, targets, wrt=()):
        if self.unresolved:
            return Result(status="blocked_missing_selectors", errors=[dict(e) for e in self.unresolved],
                          model_sha256=self.sha256(), editions=dict(self.editions))
        order = self.order(targets)
        needed = set()
        for n in order:
            needed |= set(self._deps(n))
            for p in self._dom[n]:
                needed |= set(p.names)
        needed |= {t for t in targets if t not in self.formulas}
        missing = sorted(n for n in needed if n not in self.formulas and n not in self.inputs)
        parts = sorted({self.formulas[n].standard for n in order if self.formulas[n].standard})
        res = Result(status="ok", model_sha256=self.sha256(), editions=dict(self.editions))
        res.missing_editions = [p for p in parts if p not in self.editions]
        if missing or res.missing_editions:
            res.status, res.missing = "blocked_missing_inputs", missing
            return res
        for p in parts:
            if self.editions[p] != self.standard_editions[p]:
                res.errors.append({"name": f"edition:{p}", "code": "edition_mismatch",
                                   "message": f"版次配置为 {p}:{self.editions[p]}，但本模型中该分册的公式按 "
                                              f"{p}:{self.standard_editions[p]} 编写"})
        if res.errors:
            res.status = "blocked_edition_mismatch"
            return res
        # 量纲校核在求值路径上强制执行（按输入量纲缓存）
        key = (self._fingerprint, tuple(order),
               tuple(sorted((k, U.unit(i.unit)[0]) for k, i in self.inputs.items() if k in needed)))
        if key not in _DIM_OK:
            try:
                self.check_dimensions(order)
            except FormulaError as e:
                res.status, res.errors = "blocked_invalid_inputs", [{"name": "", "code": "dimension_mismatch", "message": str(e)}]
                return res
            _DIM_OK.add(key)
        env = {}
        for k, i in self.inputs.items():
            env[k] = D.Dual(i.value, {k: 1.0} if k in wrt else {})
        for n in order:
            f, e = self.formulas[n], self._exprs[n]
            try:
                if f.kind == "explicit":
                    env[n] = e.evaluate(env)
                elif f.kind == "fixed_point":
                    env[n] = D.solve_fixed_point(lambda x: e.evaluate({**env, n: x}), f.start, tol=f.tol,
                                                derivative=f.fixed_point_derivative)
                else:
                    raise FormulaError(f"未知公式类型 {f.kind}")
                v = D.Dual.lift(env[n]).v
                if not isinstance(v, (int, float)) or not math.isfinite(v):
                    raise ArithmeticError(f"结果不是有限实数：{v!r}")
                for p in self._dom[n]:
                    if not p.evaluate(env):
                        res.domain_violations.append({"formula": f.id, "predicate": p.text})
            except (ArithmeticError, ValueError, TypeError) as ex:
                res.status = "blocked_evaluation_error"
                res.errors.append({"name": n, "code": "evaluation_error", "formula": f.id, "message": f"{f.id}：{ex}"})
                return res
        if res.domain_violations:
            res.status = "out_of_domain"
        res.duals = {k: D.Dual.lift(v) for k, v in env.items()}
        res.values = {k: v.v for k, v in res.duals.items()}
        res.evidence = EV.propagate(order, self.formulas, self._deps, self.inputs, self.evidence_levels, self.provenance_caps)
        return res

    def evaluate_interval(self, targets, input_boxes):
        """区间求值：input_boxes = {输入名: (lo, hi, unit)}，返回保证包含盒内任意点求值结果的区间（见 interval.py）。"""
        from . import interval as IV
        return IV.evaluate(self, targets, input_boxes)

    def gradient(self, result: Result, name, wrt):
        """∂name/∂wrt（规范单位）。"""
        return result.duals[name].d.get(wrt, 0.0)

    def explain(self, result: Result, name, depth=0, seen=None):
        """输出 name 的完整公式链：每一步的公式、标准条款、数值、单位、来源。"""
        seen = seen if seen is not None else set()
        if name in seen:
            return []
        seen.add(name)
        if name in self.inputs:
            i = self.inputs[name]
            return [{"depth": depth, "name": name, "value": U.from_canonical(i.value, i.unit), "unit": i.unit,
                     "provenance": i.provenance, "source": i.source}]
        f = self.formulas[name]
        rows = [{"depth": depth, "name": name, "value": U.from_canonical(result.values[name], f.unit), "unit": f.unit,
                 "formula": f.expr, "ref": f.ref, "standard": f.standard, "edition": f.edition, "id": f.id,
                 "provenance": "derived"}]
        for d in self._deps(name):
            rows += self.explain(result, d, depth + 1, seen)
        return rows
