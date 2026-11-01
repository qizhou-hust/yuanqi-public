"""Read-only nearest feasible combination in an explicit bounded joint domain.

Weighted Hamming distance counts changed *record IDs*, not physical displacement.
The authoritative source-owned finite evaluator supplies feasibility; this layer
only validates the user edit problem and orders its feasible records.
"""
import copy
import re
from fractions import Fraction
from . import system_optimize as SO

AXES = ('gear', 'shaft', 'bearing')
DECIMAL = re.compile(r'^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$')


def _validate(request, domain):
    if not isinstance(request, dict) or set(request) != {'target', 'metric', 'constraints', 'source'}:
        raise ValueError('Explicit target, metric, constraints and source required; unknown fields forbidden')
    if not isinstance(request['source'], str) or not request['source'].strip():
        raise ValueError('Edit request source must be nonempty')
    target = request['target']
    if not isinstance(target, dict) or set(target) != set(AXES):
        raise ValueError('Target must explicitly identify every finite axis')
    for axis in AXES:
        if not isinstance(target[axis], str) or not target[axis].strip():
            raise ValueError('Target IDs must be nonempty strings')
        if target[axis] not in [row['id'] for row in domain[axis]]:
            raise ValueError('Target ID outside declared domain: '+axis)
    metric = request['metric']
    if not isinstance(metric, dict) or set(metric) != {'kind', 'weights'} or metric['kind'] != 'weighted_hamming':
        raise ValueError('Only explicit weighted_hamming metric supported')
    weights = metric['weights']
    if not isinstance(weights, dict) or set(weights) != set(AXES):
        raise ValueError('Explicit weights required for every finite axis')
    parsed = {}
    for axis, value in weights.items():
        if not isinstance(value, str) or len(value) > 128 or not DECIMAL.fullmatch(value):
            raise ValueError('Weights must be exact positive decimal strings (at most 128 characters)')
        parsed[axis] = Fraction(value)
        if parsed[axis] <= 0:
            raise ValueError('Weights must be strictly positive')
    constraints = request['constraints']
    if not isinstance(constraints, dict) or set(constraints) != {'pass_scopes'} or constraints['pass_scopes'] != list(SO.SCOPES):
        raise ValueError('Explicit ordered gear_rating, shaft, bearing, key pass scopes required')
    return parsed


def propose(design_doc, system_input, domain, request, *, expected_problem_sha256=None):
    """Evaluate freshly, return exact nearest feasible IDs without applying edits.

    domain is the existing finite system_optimize declaration, including explicit
    physical inputs, evidence holds, search bound and its volume objective (used
    only by that evaluator, never as a nearest-edit tie break). The request binds
    the target, categorical metric and feasibility constraints to the identity.
    expected_problem_sha256 can revalidate a previous proposal; changed source,
    certificates, domain, request or evaluator output rejects it. It is not a
    gear_commit preview token and grants no write authority.
    """
    out = {'status': 'blocked', 'read_only': True, 'nearest': None, 'ties': [],
           'feasible': [], 'target_feasible': None, 'problem_sha256': None,
           'errors': [], 'limitations': [
               'Finite categorical IDs only; distance is not physical displacement.',
               'No continuous optimum, real C001 completion or system gate3 claim.',
               'No changes are applied; this identity is not a commit token.']}
    try:
        d, s, p, req = copy.deepcopy((design_doc, system_input, domain, request))
        weights = _validate(req, p)
        if expected_problem_sha256 is not None and (not isinstance(expected_problem_sha256, str) or
                not re.fullmatch('[0-9a-f]{64}', expected_problem_sha256)):
            raise ValueError('expected_problem_sha256 must be a lowercase SHA256')
        evaluated = SO.optimize(d, s, p)
        out['evaluation'] = evaluated
        if evaluated['status'] != 'completed':
            out['errors'] = evaluated['errors']
            return out
        out['problem_sha256'] = SO._hash([evaluated, req])
        if expected_problem_sha256 is not None and expected_problem_sha256 != out['problem_sha256']:
            out['status'] = 'rejected_stale_proposal'
            out['errors'] = [{'code': 'stale_proposal', 'message': 'Source, domain, evidence or request identity changed'}]
            return out
        ranked = []
        for candidate in evaluated['feasible']:
            distance = sum((weights[axis] for axis, identity in zip(AXES, candidate['ids'])
                            if identity != req['target'][axis]), Fraction())
            ranked.append((distance, candidate['ids'], candidate))
        ranked.sort(key=lambda item: (item[0], item[1]))
        out['feasible'] = [dict(candidate, distance=str(distance)) for distance, ids, candidate in ranked]
        out['nearest'] = out['feasible'][0] if ranked else None
        out['ties'] = [row for row in out['feasible'] if row['distance'] == out['nearest']['distance']] if ranked else []
        out['target_feasible'] = bool(ranked and ranked[0][0] == 0)
        out['request'] = req
        out['status'] = 'completed'
    except Exception as exc:
        out['errors'].append({'code': type(exc).__name__, 'message': str(exc)})
    return out
