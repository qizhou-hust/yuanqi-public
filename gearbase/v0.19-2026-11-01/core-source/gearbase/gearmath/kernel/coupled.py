"""Ordered scalar-assignment fixed point, sharing the kernel expression boundary.

Callers supply compiled numerical producers; this module has no domain equations
or expression interpreter. Derivatives of a converged coupled system are not
promised by this numerical compatibility primitive.
"""
from __future__ import annotations
import math
from .dual import Dual


class NotConverged(RuntimeError):
    def __init__(self,residual,iterations,history,*,values=None):
        self.residual=residual;self.iterations=iterations;self.history=list(history)
        self.values=dict(values or {})
        super().__init__(f'fixed point not converged: last delta={residual:.3e} after {iterations} iters')


def _number(value):
    if isinstance(value,Dual):value=value.v
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ArithmeticError('finite numeric value required')
    return float(value)


def solve_coupled(assignments,inputs,*,tol=1e-12,max_iter=100,return_history=False):
    """Gauss-Seidel in caller-specified deterministic order, unknowns seeded zero.

    Stop when absolute maximum assignment change <= tol * max(1, |all values|).
    Return a fresh value mapping; optional history exposes the actual iterations.
    Non-convergence and non-finite arithmetic fail rather than returning a point.
    """
    if isinstance(max_iter,bool) or not isinstance(max_iter,int) or max_iter<=0:
        raise ValueError('max_iter must be a positive integer')
    if isinstance(tol,bool) or not isinstance(tol,(int,float)) or not math.isfinite(tol) or tol<0:
        raise ValueError('tol must be finite and nonnegative')
    producers=list(assignments);names=[name for name,_ in producers]
    if len(set(names))!=len(names) or any(not isinstance(n,str) or not n for n in names):
        raise ValueError('assignment names must be distinct nonempty strings')
    if any(not callable(fn) for _,fn in producers):raise TypeError('assignment producer must be callable')
    values={name:_number(value) for name,value in inputs.items()}
    for name in names:values.setdefault(name,0.0)
    history=[]
    if not names:return (values,history) if return_history else values
    for _ in range(max_iter):
        old={name:values[name] for name in names}
        for name,producer in producers:values[name]=_number(producer(values))
        delta=max(abs(values[name]-old[name]) for name in names)
        if not math.isfinite(delta):raise ArithmeticError('finite numeric change required')
        history.append(delta)
        if delta<=tol*max(1.0,max(abs(v) for v in values.values())):
            return (values,history) if return_history else values
    raise NotConverged(history[-1],len(history),history,values=values)
