"""前向自动微分（对偶数）。任何公式都能顺带算出对所有输入的精确偏导数。"""
from __future__ import annotations

import math


class Dual:
    __slots__ = ("v", "d")

    def __init__(self, v, d=None):
        self.v = float(v)
        self.d = d or {}

    @staticmethod
    def lift(x):
        return x if isinstance(x, Dual) else Dual(x)

    def _combine(self, other, dv_self, dv_other, v):
        o = Dual.lift(other)
        d = {}
        for k, g in self.d.items():
            d[k] = d.get(k, 0.0) + dv_self * g
        for k, g in o.d.items():
            d[k] = d.get(k, 0.0) + dv_other * g
        return Dual(v, d)

    def __add__(self, o):
        o = Dual.lift(o)
        return self._combine(o, 1.0, 1.0, self.v + o.v)

    __radd__ = __add__

    def __sub__(self, o):
        o = Dual.lift(o)
        return self._combine(o, 1.0, -1.0, self.v - o.v)

    def __rsub__(self, o):
        return Dual.lift(o) - self

    def __mul__(self, o):
        o = Dual.lift(o)
        return self._combine(o, o.v, self.v, self.v * o.v)

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = Dual.lift(o)
        return self._combine(o, 1.0 / o.v, -self.v / (o.v * o.v), self.v / o.v)

    def __rtruediv__(self, o):
        return Dual.lift(o) / self

    def __neg__(self):
        return Dual(-self.v, {k: -g for k, g in self.d.items()})

    def __pow__(self, p):
        if isinstance(p, Dual):
            return exp(p * log(self))
        return self.unary(self.v ** p, p * self.v ** (p - 1) if self.v != 0 or p >= 1 else 0.0)

    def unary(self, v, dv):
        return Dual(v, {k: dv * g for k, g in self.d.items()})

    # 比较只看数值
    def __lt__(self, o): return self.v < Dual.lift(o).v
    def __le__(self, o): return self.v <= Dual.lift(o).v
    def __gt__(self, o): return self.v > Dual.lift(o).v
    def __ge__(self, o): return self.v >= Dual.lift(o).v

    def __repr__(self):
        return f"Dual({self.v!r})"


def _u(x):
    return Dual.lift(x)


def sqrt(x):
    x = _u(x); r = math.sqrt(x.v); return x.unary(r, 0.5 / r if r else 0.0)

def sin(x):
    x = _u(x); return x.unary(math.sin(x.v), math.cos(x.v))

def cos(x):
    x = _u(x); return x.unary(math.cos(x.v), -math.sin(x.v))

def tan(x):
    x = _u(x); t = math.tan(x.v); return x.unary(t, 1 + t * t)

def atan(x):
    x = _u(x); return x.unary(math.atan(x.v), 1 / (1 + x.v * x.v))


def atan2(y, x):
    y, x = _u(y), _u(x)
    scale = max(abs(x.v), abs(y.v))
    if scale == 0:
        if x.d or y.d:
            raise ArithmeticError('atan2 derivative is undefined at the origin')
        return Dual(math.atan2(y.v, x.v))
    sx, sy = x.v / scale, y.v / scale
    radius2 = sx * sx + sy * sy
    return y._combine(x, (sx / radius2) / scale, (-sy / radius2) / scale, math.atan2(y.v, x.v))

def _inverse_trig(x, fn, sign):
    x = _u(x)
    value = fn(x.v)
    if abs(x.v) == 1:
        if any(g != 0 for g in x.d.values()):
            raise ArithmeticError(f'{fn.__name__} derivative is undefined at the endpoint')
        return x.unary(value, 0.0)
    return x.unary(value, sign / math.sqrt(1 - x.v * x.v))

def acos(x):
    return _inverse_trig(x, math.acos, -1)

def asin(x):
    return _inverse_trig(x, math.asin, 1)

def exp(x):
    x = _u(x); e = math.exp(x.v); return x.unary(e, e)

def log(x):
    x = _u(x); return x.unary(math.log(x.v), 1 / x.v)

def fabs(x):
    x = _u(x); return x.unary(abs(x.v), 1.0 if x.v >= 0 else -1.0)


def inv(a):
    """渐开线函数 inv(α) = tan α − α。"""
    return tan(a) - a


def inv_inverse(y, tol=1e-15):
    """由 inv(α) 反求 α（牛顿法），导数用隐函数定理：dα/dy = 1/tan²α。"""
    y = _u(y)
    a = (3 * y.v) ** (1 / 3) if y.v > 0 else 0.0
    for _ in range(60):
        t = math.tan(a)
        step = (t - a - y.v) / (t * t)
        a -= step
        if abs(step) < tol:
            break
    t = math.tan(a)
    return y.unary(a, 1 / (t * t))


def solve_fixed_point(fn, x0, tol=1e-14, max_iter=200, *, derivative="implicit"):
    """x = fn(x) 的标量不动点（用于 ISO 6336-3 的 θ 迭代）。不追踪导数穿过迭代，
    而是在收敛点用隐函数定理：dx = ∂fn/∂p / (1 − ∂fn/∂x)。"""
    if derivative not in ("implicit", "finite_iteration"):
        raise ValueError(f"Unknown fixed point derivative strategy: {derivative}")
    if derivative == "finite_iteration":
        # The value is the finite algorithm, not the mathematical fixed point.
        # Differentiate the same executed steps; the stop decision uses values.
        x = Dual(float(x0))
        for _ in range(max_iter):
            nx = Dual.lift(fn(x))
            if abs(nx.v - x.v) < tol:
                return nx
            x = nx
        raise ArithmeticError("不动点迭代未收敛")
    x = float(x0)
    for _ in range(max_iter):
        nx = fn(Dual(x)).v
        if abs(nx - x) < tol:
            x = nx
            break
        x = nx
    else:
        raise ArithmeticError("不动点迭代未收敛")
    probe = fn(Dual(x, {"__x__": 1.0}))
    k = probe.d.pop("__x__", 0.0)
    return Dual(x, {name: g / (1 - k) for name, g in probe.d.items()})
