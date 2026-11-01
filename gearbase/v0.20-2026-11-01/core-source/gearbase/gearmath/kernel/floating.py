"""Explicit binary64 arithmetic profile, independent of vendor BLAS dispatch.

dot_fma folds s = fma(x[i], y[i], s) in ascending index order, with one
round-to-nearest/even binary64 rounding at each step. norm_fma applies a final
binary64 sqrt. This is an ordered reduction, not an exact-sum or scaled norm.
Inputs and every rounded intermediate must be finite; overflow raises instead
of silently selecting another arithmetic profile. Empty reductions return +0.
"""
from fractions import Fraction
import math

PROFILE_ID='binary64-ordered-fma-v1'
FMA_BACKEND='math.fma' if hasattr(math,'fma') else 'stdlib.Fraction-single-rounding'


def _finite(value):
    if type(value) not in (int,float):raise TypeError('binary64 real scalar required')
    value=float(value)
    if not math.isfinite(value):raise ValueError('finite binary64 scalar required')
    return value


def fma_finite(x,y,z):
    """Compute a finite x*y+z with one final binary64 rounding."""
    x,y,z=map(_finite,(x,y,z))
    if hasattr(math,'fma'):
        result=math.fma(x,y,z)
    else:
        exact=Fraction.from_float(x)*Fraction.from_float(y)+Fraction.from_float(z)
        if not exact:
            # Exact cancellation is +0 in nearest/even. Two negative zero
            # summands retain -0; Fraction alone cannot carry a zero sign.
            negative_product=(math.copysign(1.,x)!=math.copysign(1.,y))
            return -0. if (x==0. or y==0.) and z==0. and negative_product and math.copysign(1.,z)<0 else 0.
        result=float(exact)
    if not math.isfinite(result):raise OverflowError('ordered FMA intermediate exceeds finite binary64')
    return result


def dot_fma(xs,ys):
    """Ordered FMA reduction of any two equally sized finite real iterables."""
    total=0.
    for x,y in zip(xs,ys,strict=True):total=fma_finite(x,y,total)
    return total


def norm_fma(values):
    """Unscaled Euclidean norm under the explicitly ordered FMA profile."""
    values=tuple(values)
    return math.sqrt(dot_fma(values,values))
