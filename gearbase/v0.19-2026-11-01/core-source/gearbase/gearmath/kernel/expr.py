"""公式表达式：白名单 AST，先做量纲推断（编译期），再求值（支持对偶数求导）。

公式是数据（字符串），不是代码；不允许属性访问、任意调用、import。

分段（K1）：where(cond, a, b)。cond 必须是比较式或 and/or 组合；a、b 量纲必须相同，结果取该量纲；
只求值命中分支（另一分支可以在当前点无定义），值和导数都取命中分支。
比较式两侧量纲必须相同（数值常量 0 与任意量纲相容）。
非光滑标记：evaluate(env, trace=[]) 记录每个 where/min/max 节点命中的分支和相对裕度，
near_kinks(model, result, rel_tol) 列出裕度在容差内的节点，供优化器判断"当前点靠近折点"。

阶跃（取整）：round_to(x, q) 把 x 取到 q 的最近整数倍，x 与 q 量纲必须相同（q 为数值常量时 x 须无量纲），
q 在求值点必须 > 0。半格平分点取远离零方向（|x|/q 的小数部分恰为 0.5 时进位）；平分点本身由调用方的
规则决定，故 trace 的裕度在平分点处为 0，near_kinks 会标出。导数恒为 0（分段常数），节点计为非光滑：
trace 记录 branch=取整后的整数倍 k、margin=到最近半格边界的相对距离。
"""
from __future__ import annotations

import ast
import math
from fractions import Fraction

from . import dual as D
from . import units as U

PI = math.pi

# 函数名 -> (参数量纲要求, 返回量纲规则)
_A = U.dim(A=1)
_FUNCS = {
    "sin": "angle->1", "cos": "angle->1", "tan": "angle->1",
    "atan": "1->angle", "acos": "1->angle", "asin": "1->angle",
    "atan2": "same->angle",
    "inv": "angle->angle", "inv_inverse": "angle->angle",
    "sqrt": "half", "abs": "same", "min": "same", "max": "same",
    "exp": "1->1", "log": "1->1",
    "where": "where",
    "round_to": "same",
}
_SWITCH = ("where", "min", "max", "round_to")       # 非光滑节点
_IMPL = {
    "sin": D.sin, "cos": D.cos, "tan": D.tan, "atan": D.atan, "acos": D.acos, "asin": D.asin,
    "atan2": D.atan2,
    "inv": D.inv, "inv_inverse": D.inv_inverse, "sqrt": D.sqrt, "abs": D.fabs,
    "exp": D.exp, "log": D.log,
    "min": lambda *a: D.Dual.lift(min(a, key=lambda x: D.Dual.lift(x).v)),
    "max": lambda *a: D.Dual.lift(max(a, key=lambda x: D.Dual.lift(x).v)),
}


class FormulaError(ValueError):
    pass


class Expr:
    """编译后的表达式。"""

    def __init__(self, text: str):
        if not isinstance(text, str) or len(text) > 2000:
            raise FormulaError("表达式必须是长度有限的字符串")
        self.text = text
        self._trace = None
        try:
            self.tree = ast.parse(text, mode="eval").body
        except SyntaxError as e:
            raise FormulaError(f"语法错误：{text}") from e
        self.names = sorted({n.id for n in ast.walk(self.tree) if isinstance(n, ast.Name)
                             and n.id not in _FUNCS and n.id not in ("pi", "rad")})
        self._check(self.tree)
        self._switches = {id(n): i for i, n in enumerate(
            n for n in ast.walk(self.tree) if isinstance(n, ast.Call) and n.func.id in _SWITCH)}

    def _check(self, node):
        ok = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Call, ast.Load,
              ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd,
              ast.Compare, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.BoolOp, ast.And, ast.Or)
        for n in ast.walk(node):
            if not isinstance(n, ok):
                raise FormulaError(f"不允许的语法：{type(n).__name__}（{self.text}）")
            if isinstance(n, ast.Call):
                if not isinstance(n.func, ast.Name) or n.func.id not in _FUNCS or n.keywords:
                    raise FormulaError(f"不允许的函数调用（{self.text}）")
                if n.func.id == "where" and (len(n.args) != 3 or not isinstance(n.args[0], (ast.Compare, ast.BoolOp))):
                    raise FormulaError(f"where 需要 3 个参数且第一个是比较式（{self.text}）")
                if n.func.id == "round_to" and len(n.args) != 2:
                    raise FormulaError(f"round_to 需要 2 个参数 (x, q)（{self.text}）")
                if n.func.id == "atan2" and len(n.args) != 2:
                    raise FormulaError(f"atan2 needs two arguments ({self.text})")
                if n.func.id == "round_to" and isinstance(n.args[1], ast.Constant) and not n.args[1].value > 0:
                    raise FormulaError(f"round_to 的取整量子必须 > 0（{self.text}）")
                if n.func.id in ("min", "max") and not n.args:
                    raise FormulaError(f"{n.func.id} 至少需要一个参数（{self.text}）")
            if isinstance(n, ast.Constant) and not isinstance(n.value, (int, float)):
                raise FormulaError("只允许数值常量")

    # ---------- 量纲推断 ----------
    def dimension(self, dims: dict) -> tuple:
        return self._dim(self.tree, dims)

    def _dim(self, n, dims):
        if isinstance(n, ast.Constant):
            return U.ONE
        if isinstance(n, ast.Name):
            if n.id == "pi":
                return U.ONE
            if n.id == "rad":
                return _A
            if n.id not in dims:
                raise FormulaError(f"未知变量 {n.id}")
            return dims[n.id]
        if isinstance(n, ast.UnaryOp):
            return self._dim(n.operand, dims)
        if isinstance(n, ast.BinOp):
            a = self._dim(n.left, dims)
            if isinstance(n.op, ast.Pow):
                try:
                    p = _const(n.right)
                except FormulaError:
                    if a != U.ONE or self._dim(n.right, dims) != U.ONE:
                        raise FormulaError(f"variable powers require dimensionless operands ({self.text})")
                    return U.ONE
                else:
                    return U.power(a, p)
            b = self._dim(n.right, dims)
            if isinstance(n.op, (ast.Add, ast.Sub)):
                if a != b:
                    raise FormulaError(f"量纲不一致：{U.show(a)} 与 {U.show(b)}（{self.text}）")
                return a
            return U.mul(a, b) if isinstance(n.op, ast.Mult) else U.div(a, b)
        if isinstance(n, ast.Call):
            rule = _FUNCS[n.func.id]
            if rule == "where":
                self._dim(n.args[0], dims)
                a, b = self._dim(n.args[1], dims), self._dim(n.args[2], dims)
                if a != b:
                    raise FormulaError(f"where 两分支量纲不一致：{U.show(a)} 与 {U.show(b)}（{self.text}）")
                return a
            args = [self._dim(x, dims) for x in n.args]
            if rule == "same->angle":
                if len(args) != 2 or args[0] != args[1]:
                    raise FormulaError(f"atan2 operands need equal dimensions ({self.text})")
                return _A
            if rule == "angle->1":
                _need(args, _A, n.func.id, self.text); return U.ONE
            if rule == "1->angle":
                _need(args, U.ONE, n.func.id, self.text); return _A
            if rule == "angle->angle":
                _need(args, _A, n.func.id, self.text); return _A
            if rule == "1->1":
                _need(args, U.ONE, n.func.id, self.text); return U.ONE
            if rule == "half":
                return U.power(args[0], Fraction(1, 2))
            if rule == "same":
                if any(a != args[0] for a in args):
                    raise FormulaError(f"{n.func.id} 参数量纲不一致（{self.text}）")
                return args[0]
        if isinstance(n, ast.Compare):
            sides = [x for x in (n.left, *n.comparators) if not _is_zero(x)]
            ds = [self._dim(x, dims) for x in sides]
            if any(d != ds[0] for d in ds):
                raise FormulaError(f"比较式两侧量纲不一致：{' / '.join(U.show(d) for d in ds)}（{self.text}）")
            return U.ONE
        if isinstance(n, ast.BoolOp):
            for x in n.values:
                self._dim(x, dims)
            return U.ONE
        raise FormulaError(f"无法推断量纲（{self.text}）")

    # ---------- 求值 ----------
    def evaluate(self, env: dict, trace: list | None = None):
        """trace 为列表时，追加每个被求值的 where/min/max 节点：
        {"node": 序号, "fn", "text", "branch": 命中分支序号, "margin": 相对裕度}。"""
        self._trace = trace
        try:
            return self._eval(self.tree, env)
        finally:
            self._trace = None

    def _eval(self, n, env):
        if isinstance(n, ast.Constant):
            return float(n.value)
        if isinstance(n, ast.Name):
            return PI if n.id == "pi" else 1.0 if n.id == "rad" else env[n.id]
        if isinstance(n, ast.UnaryOp):
            v = self._eval(n.operand, env)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = self._eval(n.left, env), self._eval(n.right, env)
            op = n.op
            if isinstance(op, ast.Add): return a + b
            if isinstance(op, ast.Sub): return a - b
            if isinstance(op, ast.Mult): return a * b
            if isinstance(op, ast.Div): return a / b
            if isinstance(op, ast.Pow):
                try: exponent = _const(n.right)
                except FormulaError:
                    exponent = b.v if isinstance(b, D.Dual) and not b.d else b
                return D.Dual.lift(a) ** exponent
        if isinstance(n, ast.Call):
            fn = n.func.id
            if fn == "where":
                hit = bool(self._eval(n.args[0], env))
                if self._trace is not None:
                    self._record(n, 0 if hit else 1, _margin(self, n.args[0], env))
                return self._eval(n.args[1] if hit else n.args[2], env)
            args = [self._eval(x, env) for x in n.args]
            if fn == "round_to":
                return self._round_to(n, *args)
            out = _IMPL[fn](*args)
            if fn in ("min", "max") and self._trace is not None:
                vs = [_num(x) for x in args]
                k = vs.index(out.v)
                rest = [v for i, v in enumerate(vs) if i != k]
                self._record(n, k, min((_rel(out.v, v) for v in rest), default=math.inf))
            return out
        if isinstance(n, ast.Compare):
            left = _num(self._eval(n.left, env))
            for op, right in zip(n.ops, n.comparators):
                r = _num(self._eval(right, env))
                ok = {ast.Lt: left < r, ast.LtE: left <= r, ast.Gt: left > r, ast.GtE: left >= r}[type(op)]
                if not ok:
                    return False
                left = r
            return True
        if isinstance(n, ast.BoolOp):
            vals = [self._eval(x, env) for x in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        raise FormulaError("无法求值")


    def _round_to(self, n, x, q):
        xv, qv = _num(x), _num(q)
        if not (qv > 0) or not math.isfinite(xv):
            raise ValueError(f"round_to 需要有限 x 与 q > 0（{self.text}）")
        r = xv / qv
        k = math.floor(abs(r) + 0.5) * (1 if r >= 0 else -1)
        if self._trace is not None:
            lo, hi = (k - 0.5) * qv, (k + 0.5) * qv
            self._record(n, k, min(_rel(xv, lo), _rel(xv, hi)))
        return D.Dual(k * qv)          # 分段常数：值取整，导数恒 0

    def _record(self, n, branch, margin):
        self._trace.append({"node": self._switches[id(n)], "fn": n.func.id, "text": ast.unparse(n),
                            "branch": branch, "margin": margin})


def _rel(a, b):
    s = max(abs(a), abs(b))
    return abs(a - b) / s if s else 0.0


def _margin(e, cond, env):
    """条件式的相对裕度：所有比较中 |左−右|/max(|左|,|右|) 的最小值（越小越靠近切换边界）。"""
    if isinstance(cond, ast.BoolOp):
        return min(_margin(e, x, env) for x in cond.values)
    if isinstance(cond, ast.Compare):
        vals = [_num(e._eval(x, env)) for x in (cond.left, *cond.comparators)]
        return min(_rel(a, b) for a, b in zip(vals, vals[1:]))
    return math.inf


def _is_zero(n):
    return isinstance(n, ast.Constant) and n.value == 0


def near_kinks(model, result, rel_tol=1e-6, names=None):
    """列出结果点处裕度 ≤ rel_tol 的非光滑节点（where 条件、min/max 竞争项）。
    model 需提供 formulas / _exprs（与 graph.Model 相同的接口），result 需提供 values。
    返回 [{"quantity", "formula", "node", "fn", "text", "branch", "margin"}]，按裕度升序。"""
    return [r for r in switches(model, result, names) if r["margin"] <= rel_tol]


def switches(model, result, names=None):
    """结果点处所有已求值非光滑节点的分支记录（进 explain 用）。"""
    env = result.values
    rows = []
    for q in names or list(model.formulas):
        if q not in env:
            continue
        tr = []
        try:
            model._exprs[q].evaluate(env, trace=tr)
        except (KeyError, ArithmeticError, ValueError):
            continue
        rows += [{"quantity": q, "formula": model.formulas[q].id, **t} for t in tr]
    return sorted(rows, key=lambda r: r["margin"])


def _num(x):
    return D.Dual.lift(x).v if not isinstance(x, bool) else x


def _const(n):
    if isinstance(n, ast.Constant):
        return n.value
    if isinstance(n, ast.UnaryOp) and isinstance(n.operand, ast.Constant):
        return -n.operand.value
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) and all(isinstance(x, ast.Constant) for x in (n.left, n.right)):
        return n.left.value / n.right.value
    raise FormulaError("幂指数必须是数值常量")


def _need(args, want, fn, text):
    if len(args) != 1 or args[0] != want:
        raise FormulaError(f"{fn} 需要量纲 {U.show(want)}（{text}）")
