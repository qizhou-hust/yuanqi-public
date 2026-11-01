"""Bracketed oil-temperature balance using existing ISO/TR 14179-1 equations.

Inputs are explicitly authored; temperatures are degrees C and powers kW.
This numerical orchestration is not an external validation of the equations.
"""
import math
from gearmath.gear import micropitting as MP
from gearmath.system import thermal_14179 as TH


def _number(x, name):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError(f'{name} must be a finite number')
    return x


def _finite_tree(x):
    if isinstance(x, dict):
        for v in x.values(): _finite_tree(v)
    elif isinstance(x, (list, tuple)):
        for v in x: _finite_tree(v)
    elif isinstance(x, float) and not math.isfinite(x):
        raise ValueError('non-finite input')


def solve(spec):
    """Solve within an explicit bracket. Never extrapolates past the bracket."""
    result = {'status': 'invalid', 'temperature_C': None, 'residual_kW': None,
              'iterations': 0, 'bracket_C': None, 'reason': None}
    try:
        _finite_tree(spec)
        a = _number(spec['A_c'], 'A_c'); k = _number(spec['k'], 'k')
        ambient = _number(spec['ambient_C'], 'ambient_C')
        lo, hi = spec['bracket_C']
        lo = _number(lo, 'bracket low'); hi = _number(hi, 'bracket high')
        tt = _number(spec['temperature_tolerance_C'], 'temperature tolerance')
        rt = _number(spec['residual_tolerance_kW'], 'residual tolerance')
        count = spec['max_iterations']
        if a <= 0 or k <= 0 or lo >= hi or tt <= 0 or rt <= 0 or isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError('invalid physical inputs, bracket, tolerances or iteration limit')
        model = spec['loss_model']; fixed = _number(model['fixed_kW'], 'fixed_kW')
        if fixed < 0: raise ValueError('fixed_kW must be nonnegative')
        components = model['components']
        if not isinstance(components, list): raise ValueError('components must be a list')
        result['bracket_C'] = [lo, hi]
        def residual(t):
            losses = fixed
            for component in components:
                args = dict(component); kind = args.pop('type')
                visc = model['viscosity']
                nu = MP.nu_theta(nu_40=visc['nu_40'], nu_100=visc['nu_100'], theta=t)
                if kind == 'mesh':
                    fm = TH.mesh_friction(nu=nu, K=args.pop('K'), V=args.pop('V'))
                    loss = TH.mesh_loss(f_m=fm, **args)
                elif kind == 'bearing_churning':
                    m0 = TH.bearing_no_load_torque(f0=args.pop('f0'), nu=nu, n=args['n'], d_m=args.pop('d_m'))
                    loss = TH.bearing_churning_loss(M0=m0, **args)
                elif kind == 'windage_smooth_od':
                    loss = TH.windage_smooth_od(nu=nu, **args)
                else: raise ValueError('unsupported component: ' + str(kind))
                losses += _number(loss, 'component loss')
            val = TH.heat_balance_residual(P_Q=TH.P_Q(A_c=a,k=k,delta_T=t-ambient), P_N=losses, P_L=0)
            return _number(val, 'residual')
        fl, fh = residual(lo), residual(hi)
        for t, f in ((lo, fl), (hi, fh)):
            if abs(f) <= rt:
                result.update(status='converged', temperature_C=t, residual_kW=f, reason=None)
                return result
        if (fl < 0) == (fh < 0):
            result.update(status='no_bracket', reason='endpoint residuals have the same sign', endpoint_residuals_kW=[fl,fh])
            return result
        for i in range(1, count+1):
            mid = lo + (hi-lo)/2; fm = residual(mid)
            result.update(temperature_C=mid, residual_kW=fm, iterations=i, bracket_C=[lo,hi])
            if abs(fm) <= rt and (hi-lo)/2 <= tt:
                result.update(status='converged', reason=None); return result
            if (fl < 0) == (fm < 0): lo, fl = mid, fm
            else: hi, fh = mid, fm
        result.update(status='nonconvergence', reason='iteration limit reached', bracket_C=[lo,hi])
    except (KeyError, TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        result.update(status='invalid', reason=str(exc), temperature_C=None, residual_kW=None)
    return result
