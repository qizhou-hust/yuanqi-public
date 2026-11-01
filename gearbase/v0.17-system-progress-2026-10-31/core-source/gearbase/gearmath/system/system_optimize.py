"""L2 physical objective for the finite cylindrical system capability probe.

Gear blank volume is supplied by the source-owned geo.volume formula. Shaft
volume is the sum of explicit annular cylinders; no material or safety defaults.
This objective excludes bearings, keys, housings and actual tooth-space removal.
"""
import math
from ._base import num, OutOfDomain


def total_volume_mm3(*, gear_blank_mm3, shafts):
    volume = num('gear_blank_mm3', gear_blank_mm3)
    if volume <= 0:
        raise OutOfDomain('gear_blank_mm3', 'must be positive')
    for shaft in shafts:
        end = None
        for segment in shaft['segments']:
            vals = {}
            for name in ('x0', 'x1', 'd', 'd_i'):
                leaf = segment[name]
                if leaf.get('unit') != 'mm' or not leaf.get('source'):
                    raise ValueError('Volume requires sourced explicit mm segments')
                vals[name] = num(name, leaf.get('value'))
            x0, x1, d, di = (vals[k] for k in ('x0','x1','d','d_i'))
            if x1 <= x0 or d <= 0 or di < 0 or di >= d or (end is not None and x0 < end):
                raise OutOfDomain('segments', 'ordered nonoverlapping positive annular cylinders required')
            volume += math.pi / 4 * (d*d-di*di) * (x1-x0)
            end = x1
    return volume
