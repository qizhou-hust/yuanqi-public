"""Bounded shaft-to-face contribution; not a complete ISO f_sh calculation."""
import math
from gearmath.system import shaft_beam
from gearmath.system._base import num, OutOfDomain, Unconfirmed


def face_components(*, model, x0, x1, direction_deg, torsion_delta_mm,
                    torsion_source, omitted_effects):
    """Signed high-x minus low-x projected displacement, in mm.

    The bending part is width times projected center slope. torsion_delta_mm
    is an externally computed signed face-end displacement in the same direction,
    not an angle. Both endpoints and the center must lie inside the shaft; center
    must be a solve node. Caller explicitly acknowledges omitted effects with the
    exact tuple below and identifies the independent torsion model.
    """
    a, b = num('x0', x0), num('x1', x1)
    direction = num('direction_deg', direction_deg)
    twist = num('torsion_delta_mm', torsion_delta_mm)
    if not isinstance(torsion_source, str) or not torsion_source.strip():
        raise Unconfirmed('torsion_source', 'identify the external torsional model')
    if omitted_effects != ('gear_body', 'housing', 'bearing_compliance', 'wheel'):
        raise Unconfirmed('omitted_effects', 'explicitly acknowledge gear_body, housing, bearing_compliance, wheel')
    if model.get('shear_model') != 'euler_bernoulli':
        raise Unconfirmed('shear_model', 'center section rotation is not the deflection slope for Timoshenko')
    lo, hi = model['segments'][0][0], model['segments'][-1][1]
    if not lo <= a < b <= hi:
        raise OutOfDomain('face', 'face endpoints must be ordered and within the shaft')
    center = a + (b - a) / 2.0
    d = shaft_beam.deflection_at(model=model, x=center)
    angle = math.radians(direction)
    bending = (b - a) * (d['psi_y_plane'] * math.cos(angle) + d['psi_z_plane'] * math.sin(angle))
    return {'x0': a, 'x1': b, 'center': center, 'direction_deg': direction,
            'bending_delta_mm': bending, 'torsion_delta_mm': twist,
            'signed_shaft_delta_mm': bending + twist, 'torsion_source': torsion_source,
            'omitted_effects': omitted_effects, 'status': 'partial; not ISO f_sh or KHbeta'}
