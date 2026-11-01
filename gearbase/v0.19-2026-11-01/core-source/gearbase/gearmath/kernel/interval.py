"""区间算术 v0（零依赖）：对表达式白名单做保证包含的外向舍入求值，并与计算图对接。

保证的含义：对输入盒内的任意一点，用浮点点求值（Model.evaluate 同口径）得到的每个量，都落在对应区间内。
  - + − × ÷ √ 取绝对值/取小/取大 等 IEEE 754 基本运算：先按最近舍入算端点，再各外推一个 ulp（math.nextafter）；
  - exp / log / 三角 / 反三角 / 幂（非整数指数）等库函数不保证正确舍入：端点各外推两个 ulp（实用口径，非形式化证明）；
  - 十进制字面常量（非整数值）按其浮点数两侧各外推一个 ulp，以同时包住真实十进制值；
  - π 取 [math.pi, nextafter(math.pi, +inf)]（包含真值与浮点 math.pi）。
单调段：sin/cos 在盒内含极值点时取 ±1，否则端点即界；tan 盒内含极点则拒绝；整数次幂按奇偶分段。
where：条件三值判定（真/假/不确定）；不确定时两分支取并，任一分支在盒内无定义则拒绝（不静默跳过）。
不支持：fixed_point 公式（迭代定点的区间验证留待后续）。区间是保证外包，不保证紧；相关性（同一变量多次出现）会造成保守放大。
"""
from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field

from . import dual as D
from . import units as U
from .expr import FormulaError, _const

INF = math.inf


class IntervalError(ArithmeticError):
    """盒内存在无定义点（除以含零区间、开方负数、tan 极点……）或结果溢出。"""


def _dn(x):
    return math.nextafter(x, -INF)


def _up(x):
    return math.nextafter(x, INF)


def _dn2(x):
    return _dn(_dn(x))


def _up2(x):
    return _up(_up(x))


def _outward(lo, hi):
    """基本运算的外向舍入：最近舍入后的端点各外推一个 ulp。"""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise IntervalError("区间运算溢出")
    return Interval(_dn(lo), _up(hi))


class Interval:
    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi=None):
        hi = lo if hi is None else hi
        lo, hi = float(lo), float(hi)
        if math.isnan(lo) or math.isnan(hi) or lo > hi:
            raise IntervalError(f"非法区间 [{lo}, {hi}]")
        self.lo, self.hi = lo, hi

    @staticmethod
    def lift(x):
        return x if isinstance(x, Interval) else Interval(x)

    def width(self):
        return self.hi - self.lo

    def __contains__(self, x):
        return self.lo <= x <= self.hi

    def __repr__(self):
        return f"[{self.lo!r}, {self.hi!r}]"

    def __eq__(self, o):
        return isinstance(o, Interval) and (self.lo, self.hi) == (o.lo, o.hi)

    def __hash__(self):
        return hash((self.lo, self.hi))

    def __neg__(self):
        return Interval(-self.hi, -self.lo)

    def __add__(self, o):
        o = Interval.lift(o)
        return _outward(self.lo + o.lo, self.hi + o.hi)

    __radd__ = __add__

    def __sub__(self, o):
        o = Interval.lift(o)
        return _outward(self.lo - o.hi, self.hi - o.lo)

    def __rsub__(self, o):
        return Interval.lift(o) - self

    def __mul__(self, o):
        o = Interval.lift(o)
        ps = [self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi]
        return _outward(min(ps), max(ps))

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = Interval.lift(o)
        if o.lo <= 0.0 <= o.hi:
            raise IntervalError(f"除数区间 {o} 含 0")
        qs = [self.lo / o.lo, self.lo / o.hi, self.hi / o.lo, self.hi / o.hi]
        return _outward(min(qs), max(qs))

    def __rtruediv__(self, o):
        return Interval.lift(o) / self

    def __pow__(self, p):
        return ipow(self, p)


def hull(a, b):
    a, b = Interval.lift(a), Interval.lift(b)
    return Interval(min(a.lo, b.lo), max(a.hi, b.hi))


def _mono(f, x, inc=True, domain=None):
    """单调函数 f 的区间像；端点各外推两个 ulp。"""
    x = Interval.lift(x)
    if domain and not domain(x):
        raise IntervalError(f"区间 {x} 超出定义域")
    a, b = f(x.lo), f(x.hi)
    lo, hi = (a, b) if inc else (b, a)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise IntervalError("区间运算溢出")
    return Interval(_dn2(lo), _up2(hi))


# ---------------------------------------------------------------- 初等函数
def sqrt(x):
    x = Interval.lift(x)
    if x.lo < 0:
        raise IntervalError(f"开方区间 {x} 含负数")
    return Interval(max(0.0, _dn(math.sqrt(x.lo))), _up(math.sqrt(x.hi)))


def iabs(x):
    x = Interval.lift(x)
    if x.lo >= 0:
        return x
    if x.hi <= 0:
        return -x
    return Interval(0.0, max(-x.lo, x.hi))


def imin(*xs):
    xs = [Interval.lift(x) for x in xs]
    return Interval(min(x.lo for x in xs), min(x.hi for x in xs))


def imax(*xs):
    xs = [Interval.lift(x) for x in xs]
    return Interval(max(x.lo for x in xs), max(x.hi for x in xs))


def exp(x):
    return _mono(math.exp, x)


def log(x):
    x = Interval.lift(x)
    if x.lo <= 0:
        raise IntervalError(f"对数区间 {x} 含非正数")
    return _mono(math.log, x)


def atan(x):
    return _mono(math.atan, x)


def asin(x):
    return _mono(math.asin, x, domain=lambda v: -1.0 <= v.lo and v.hi <= 1.0)


def acos(x):
    return _mono(math.acos, x, inc=False, domain=lambda v: -1.0 <= v.lo and v.hi <= 1.0)


_TWO_PI = 2.0 * math.pi


def _has_point(a, b, offset, period):
    """[a, b]（两侧略放宽，只会多报）内是否存在 offset + k·period。"""
    eps = 1e-12 * max(1.0, abs(a), abs(b))
    a, b = a - eps, b + eps
    k = math.ceil((a - offset) / period)
    return offset + k * period <= b


def sin(x):
    x = Interval.lift(x)
    if x.width() >= _TWO_PI:
        return Interval(-1.0, 1.0)
    lo, hi = sorted((math.sin(x.lo), math.sin(x.hi)))
    lo, hi = _dn2(lo), _up2(hi)
    if _has_point(x.lo, x.hi, math.pi / 2, _TWO_PI):
        hi = 1.0
    if _has_point(x.lo, x.hi, 3 * math.pi / 2, _TWO_PI):
        lo = -1.0
    return Interval(max(-1.0, lo), min(1.0, hi))


def cos(x):
    x = Interval.lift(x)
    if x.width() >= _TWO_PI:
        return Interval(-1.0, 1.0)
    lo, hi = sorted((math.cos(x.lo), math.cos(x.hi)))
    lo, hi = _dn2(lo), _up2(hi)
    if _has_point(x.lo, x.hi, 0.0, _TWO_PI):
        hi = 1.0
    if _has_point(x.lo, x.hi, math.pi, _TWO_PI):
        lo = -1.0
    return Interval(max(-1.0, lo), min(1.0, hi))


def tan(x):
    x = Interval.lift(x)
    if x.width() >= math.pi or _has_point(x.lo, x.hi, math.pi / 2, math.pi):
        raise IntervalError(f"区间 {x} 含 tan 极点")
    return _mono(math.tan, x)


def _inv_point(a):
    """点区间上的 inv(α) = tan α − α，经区间运算得到保证包含。"""
    return tan(Interval(a)) - Interval(a)


def inv(x):
    x = Interval.lift(x)
    if not (-math.pi / 2 < x.lo and x.hi < math.pi / 2):
        raise IntervalError(f"inv 的自变量区间 {x} 超出 (−π/2, π/2)")
    return Interval(_inv_point(x.lo).lo, _inv_point(x.hi).hi)      # inv 在 (−π/2, π/2) 上单调增


def inv_inverse(y):
    y = Interval.lift(y)
    if not y.lo > 0:
        raise IntervalError(f"inv_inverse 的自变量区间 {y} 须为正")

    top = 1.5707963267           # 略小于 π/2

    def below(v):               # 最大的 a，使 inv(a) 的保证上界 <= v（故 a <= inv⁻¹(v)）
        lo, hi = 0.0, top
        while math.nextafter(lo, INF) < hi:
            mid = 0.5 * (lo + hi)
            if _inv_point(mid).hi <= v:
                lo = mid
            else:
                hi = mid
        return lo

    def above(v):               # 最小的 a，使 inv(a) 的保证下界 >= v（故 a >= inv⁻¹(v)）
        if _inv_point(top).lo < v:
            raise IntervalError(f"inv_inverse 的自变量 {v} 过大")
        lo, hi = 0.0, top
        while math.nextafter(lo, INF) < hi:
            mid = 0.5 * (lo + hi)
            if _inv_point(mid).lo >= v:
                hi = mid
            else:
                lo = mid
        return hi

    return Interval(below(y.lo), above(y.hi))


def ipow(x, p):
    """x ** p，p 为数值常量。"""
    x = Interval.lift(x)
    if isinstance(p, Interval):
        if p.lo != p.hi:
            raise IntervalError("幂指数必须是常量")
        p = p.lo
    if p == int(p):
        n = int(p)
        if n == 0:
            return Interval(1.0)
        if n < 0:
            return Interval(1.0) / ipow(x, -n)
        if n == 1:
            return x
        pw = lambda v: math.pow(v, n)
        if n % 2 == 1:
            return _mono(pw, x)
        if x.lo >= 0:
            return _mono(pw, x)
        if x.hi <= 0:
            return _mono(pw, x, inc=False)
        m = max(pw(x.lo), pw(x.hi))
        return Interval(0.0, _up2(m))
    if x.lo < 0 or (p < 0 and x.lo == 0):
        raise IntervalError(f"非整数次幂 {p} 的底数区间 {x} 含负数或零")
    return _mono(lambda v: math.pow(v, p), x, inc=p > 0)


def round_to(x, q):
    """取到 q 的最近整数倍（同 Expr 口径，半格进位）；对 x 单调不减，q 须为点区间且 > 0。"""
    x, q = Interval.lift(x), Interval.lift(q)
    if q.lo != q.hi or not q.lo > 0:
        raise IntervalError("round_to 的量子必须是 > 0 的常量")

    def rt(v):
        r = v / q.lo
        return math.floor(abs(r) + 0.5) * (1 if r >= 0 else -1) * q.lo

    return Interval(rt(x.lo), rt(x.hi))


# ---------------------------------------------------------------- 三值比较
def _cmp(op, a, b):
    if isinstance(op, ast.Lt):
        return True if a.hi < b.lo else False if a.lo >= b.hi else None
    if isinstance(op, ast.LtE):
        return True if a.hi <= b.lo else False if a.lo > b.hi else None
    if isinstance(op, ast.Gt):
        return True if a.lo > b.hi else False if a.hi <= b.lo else None
    return True if a.lo >= b.hi else False if a.hi < b.lo else None      # GtE


_PI = Interval(math.pi, _up(math.pi))


def _lit(v):
    f = float(v)
    return Interval(f) if f == int(f) and abs(f) < 2.0 ** 53 else Interval(_dn(f), _up(f))


def eval_expr(expr, env):
    """对编译后的表达式（graph.Expr）做区间求值。env：名称 → Interval（或数）。返回 Interval；
    比较式返回 True/False/None（None = 盒内不确定）。"""
    return _ev(expr.tree, env)


def _ev(n, env):
    if isinstance(n, ast.Constant):
        return _lit(n.value)
    if isinstance(n, ast.Name):
        if n.id == "pi":
            return _PI
        if n.id == "rad":
            return Interval(1.0)
        return Interval.lift(env[n.id])
    if isinstance(n, ast.UnaryOp):
        v = _ev(n.operand, env)
        return -v if isinstance(n.op, ast.USub) else v
    if isinstance(n, ast.BinOp):
        if isinstance(n.op, ast.Pow):
            return ipow(_ev(n.left, env), _const(n.right))
        a, b = _ev(n.left, env), _ev(n.right, env)
        op = n.op
        return a + b if isinstance(op, ast.Add) else a - b if isinstance(op, ast.Sub) else \
            a * b if isinstance(op, ast.Mult) else a / b
    if isinstance(n, ast.Compare):
        vals = [_ev(x, env) for x in (n.left, *n.comparators)]
        rs = [_cmp(op, a, b) for op, a, b in zip(n.ops, vals, vals[1:])]
        return False if any(r is False for r in rs) else True if all(r is True for r in rs) else None
    if isinstance(n, ast.BoolOp):
        rs = [_ev(x, env) for x in n.values]
        if isinstance(n.op, ast.And):
            return False if any(r is False for r in rs) else True if all(r is True for r in rs) else None
        return True if any(r is True for r in rs) else False if all(r is False for r in rs) else None
    if isinstance(n, ast.Call):
        fn = n.func.id
        if fn == "where":
            c = _ev(n.args[0], env)
            if c is True:
                return _ev(n.args[1], env)
            if c is False:
                return _ev(n.args[2], env)
            return hull(_ev(n.args[1], env), _ev(n.args[2], env))       # 不确定：两侧取并（任一侧无定义则 IntervalError）
        if fn == "round_to" and isinstance(n.args[1], ast.Constant):      # 量子是字面常量：取其精确点值
            return round_to(_ev(n.args[0], env), Interval(float(n.args[1].value)))
        args = [_ev(a, env) for a in n.args]
        return _FUNCS[fn](*args)
    raise FormulaError("无法做区间求值")


_FUNCS = {"sin": sin, "cos": cos, "tan": tan, "atan": atan, "acos": acos, "asin": asin, "inv": inv,
          "inv_inverse": inv_inverse, "sqrt": sqrt, "abs": iabs, "min": imin, "max": imax, "exp": exp, "log": log,
          "round_to": round_to}


# ---------------------------------------------------------------- 与计算图对接
@dataclass
class IntervalResult:
    # ok | out_of_domain（盒内所有点都违反某适用域谓词）| blocked_missing_selectors | blocked_missing_inputs
    # | blocked_edition_mismatch | blocked_invalid_inputs | blocked_evaluation_error
    status: str
    intervals: dict = field(default_factory=dict)             # 名称 -> Interval（规范单位）
    boxes: dict = field(default_factory=dict)                 # 输入盒（规范单位）
    missing: list = field(default_factory=list)
    missing_editions: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    domain_violations: list = field(default_factory=list)     # 盒内必然违反
    domain_undetermined: list = field(default_factory=list)   # 盒内可能违反（需缩小盒再判）
    model_sha256: str = ""

    def get(self, name, unit):
        """区间换算到用户单位（只支持正比例/仿射正斜率单位，换算端点各外推一个 ulp）。"""
        iv = self.intervals[name]
        a, b = U.from_canonical(iv.lo, unit), U.from_canonical(iv.hi, unit)
        return Interval(_dn(a), _up(b))


def _parse_box(name, box):
    if isinstance(box, dict):
        box = (box.get("lo"), box.get("hi"), box.get("unit"))
    if not isinstance(box, (tuple, list)) or len(box) != 3:
        raise ValueError("输入盒须为 (lo, hi, unit) 或 {lo, hi, unit}；单位必须显式给出")
    lo, hi, unit = box
    if unit not in U.UNITS:
        raise ValueError(f"未登记的单位 {unit!r}")
    for v in (lo, hi):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"盒端点必须是有限实数：{lo!r}, {hi!r}")
    if lo > hi:
        raise ValueError(f"盒下界 {lo} 大于上界 {hi}")
    # 到规范单位的换算对正斜率单位单调，端点换算后仍包住盒内所有点的换算值
    return Interval(U.to_canonical(lo, unit), U.to_canonical(hi, unit)), unit


def evaluate(model, targets, input_boxes):
    """对 Model 做区间求值。input_boxes：{输入名: (lo, hi, unit)}；未给盒的输入取模型里的点值。
    检查顺序与 Model.evaluate 一致：选择器 → 缺输入/缺版次 → 版次不符 → 输入盒合法性（声明、量纲、取值域）→ 量纲校核 → 求值。
    不设默认；fixed_point 公式不支持，返回 blocked_evaluation_error。"""
    res = IntervalResult(status="ok", model_sha256=model.sha256())
    if model.unresolved:
        res.status, res.errors = "blocked_missing_selectors", [dict(e) for e in model.unresolved]
        return res
    targets = list(targets)
    order = model.order(targets)
    boxes, bunits, errs = {}, {}, []
    for name, box in input_boxes.items():
        if name in model.formulas:
            errs.append({"name": name, "code": "derived_locked", "message": f"{name} 是派生量，不能给输入盒（{model.formulas[name].id}）"})
            continue
        spec = model.specs.get(name)
        if model.specs and spec is None:
            errs.append({"name": name, "code": "undeclared_input", "message": f"{name} 不是本模型声明的输入"})
            continue
        try:
            iv, unit = _parse_box(name, box)
        except ValueError as e:
            errs.append({"name": name, "code": "invalid_box", "message": f"{name}：{e}"})
            continue
        want = U.unit(spec.unit)[0] if spec is not None else (U.unit(model.inputs[name].unit)[0] if name in model.inputs else None)
        if want is not None and U.unit(unit)[0] != want:
            errs.append({"name": name, "code": "unit_dimension_mismatch",
                         "message": f"{name} 期望量纲 {U.show(want)}，收到单位 {unit}（量纲 {U.show(U.unit(unit)[0])}）"})
            continue
        boxes[name], bunits[name] = iv, unit
    if errs:
        res.status, res.errors = "blocked_invalid_inputs", errs
        return res
    needed = set()
    for n in order:
        needed |= set(model._deps(n))
        for p in model._dom[n]:
            needed |= set(p.names)
    needed |= {t for t in targets if t not in model.formulas}
    have = set(model.inputs) | set(boxes)
    res.missing = sorted(n for n in needed if n not in model.formulas and n not in have)
    parts = sorted({model.formulas[n].standard for n in order if model.formulas[n].standard})
    res.missing_editions = [p for p in parts if p not in model.editions]
    if res.missing or res.missing_editions:
        res.status = "blocked_missing_inputs"
        return res
    for p in parts:
        if model.editions[p] != model.standard_editions[p]:
            res.errors.append({"name": f"edition:{p}", "code": "edition_mismatch",
                               "message": f"版次配置为 {p}:{model.editions[p]}，但本模型中该分册的公式按 {p}:{model.standard_editions[p]} 编写"})
    if res.errors:
        res.status = "blocked_edition_mismatch"
        return res
    # 输入取值域：盒内必然违反 -> 拒绝；可能违反 -> 记录
    env = {k: Interval(i.value) for k, i in model.inputs.items()}
    env.update(boxes)
    for name, iv in boxes.items():
        for p in model._spec_dom.get(name, ()):
            r = eval_expr(p, {name: iv})
            if r is False:
                res.errors.append({"name": name, "code": "out_of_domain", "message": f"{name} 的输入盒 {iv} 整体超出取值域 {p.text}（规范单位）"})
            elif r is None:
                res.domain_undetermined.append({"name": name, "predicate": p.text})
    if res.errors:
        res.status = "blocked_invalid_inputs"
        return res
    # 量纲校核（输入盒的单位量纲覆盖模型里的点输入）
    dims = {k: U.unit(s.unit)[0] for k, s in model.specs.items()}
    dims.update({k: U.unit(i.unit)[0] for k, i in model.inputs.items()})
    dims.update({k: U.unit(u)[0] for k, u in bunits.items()})
    for k, f in model.formulas.items():
        dims.setdefault(k, U.unit(f.unit)[0])
    try:
        for name in order:
            f = model.formulas[name]
            got = model._exprs[name].dimension(dims)
            if got != U.unit(f.unit)[0]:
                raise FormulaError(f"{f.id}：推断量纲 {U.show(got)} 与声明单位 {f.unit} 不符")
    except FormulaError as e:
        res.status, res.errors = "blocked_invalid_inputs", [{"name": "", "code": "dimension_mismatch", "message": str(e)}]
        return res
    for n in order:
        f = model.formulas[n]
        if f.kind != "explicit":
            res.status = "blocked_evaluation_error"
            res.errors.append({"name": n, "code": "interval_unsupported", "formula": f.id,
                               "message": f"{f.id}：区间求值 v0 不支持 {f.kind} 公式"})
            return res
        try:
            env[n] = eval_expr(model._exprs[n], env)
            for p in model._dom[n]:
                r = eval_expr(p, env)
                if r is False:
                    res.domain_violations.append({"formula": f.id, "predicate": p.text})
                elif r is None:
                    res.domain_undetermined.append({"formula": f.id, "predicate": p.text})
        except (IntervalError, ArithmeticError, ValueError, TypeError) as ex:
            res.status = "blocked_evaluation_error"
            res.errors.append({"name": n, "code": "interval_domain", "formula": f.id, "message": f"{f.id}：{ex}"})
            return res
    if res.domain_violations:
        res.status = "out_of_domain"
    res.boxes = dict(boxes)
    res.intervals = {k: v for k, v in env.items() if isinstance(v, Interval)}
    return res
