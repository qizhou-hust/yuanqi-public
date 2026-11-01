"""Geometry-dependent DIN 3967 lower tooth thickness allowances.

Diameter thresholds are intentionally excluded in the graph adapter because the
step function has no derivative there. The direct DIN table API retains (lo,hi].
"""
from ..kernel.graph import Formula, InputSpec
from .backlash_din3967 import D_LIMITS, ALLOWANCE_SERIES, TOLERANCE_SERIES, allowances, parse_designation

CODES = tuple(f'{series}{grade}' for series in ALLOWANCE_SERIES for grade in TOLERANCE_SERIES)

def formulas(codes):
    if set(codes) != {1, 2} or any(code not in CODES for code in codes.values()):
        raise ValueError('DIN 3967 designations must be explicitly supplied for both gears')
    out=[]
    for i in (1,2):
        code=codes[i]; parts=parse_designation(code)
        values=[allowances(d=hi,**parts)['A_sni'] for hi in D_LIMITS]
        expr=f'({values[-1]}*0.001)*root_mm'
        for hi,value in reversed(list(zip(D_LIMITS[:-1], values[:-1]))):
            expr=f'where(d_{i}/root_mm <= {hi}, ({value}*0.001)*root_mm, {expr})'
        domain=(f'd_{i} > 0', f'd_{i}/root_mm <= 10000') + tuple(
            f'abs(d_{i}/root_mm - {hi}) > 1e-9' for hi in D_LIMITS[:-1])
        out.append(Formula(f'din3967.lower.{code}.{i}',f'A_sn_i_{i}','mm',expr,
            'DIN 3967:1978 Tables 1, 2 and clause 3.2; PDF2-3; signed lower allowance',domain,
            note='Explicit designation; piecewise constant in diameter; 1e-9 mm around interior bin boundaries rejected due to nondifferentiability'))
    return out, [InputSpec('root_mm','mm','Fixed length unit, 1 mm',('root_mm >= 1','root_mm <= 1'))]
