"""M31 optimization API backed by the kernel search and Pareto routines."""
import math
from gearmath.kernel import optimize as K
from .calculator import MathInputError, _finite

BLACKBOX_VERSION = 'cadbench.math-blackbox-optimizer/1'
PARETO_VERSION = 'cadbench.finite-pareto/1'
VERSION = 'cadbench.math-optimizer/1'

def optimize_blackbox(variables, evaluator, *, max_combinations=1000, keep=5):
    if not isinstance(variables, dict) or not variables or not callable(evaluator):
        raise MathInputError('discrete domains and callable evaluator required')
    if isinstance(max_combinations, bool) or not isinstance(max_combinations, int) or max_combinations < 1:
        raise MathInputError('positive search budget required')
    if isinstance(keep, bool) or not isinstance(keep, int) or not 1 <= keep <= 100:
        raise MathInputError('keep must be 1..100')
    choices = []
    for name, values in variables.items():
        if not isinstance(name, str) or not name.isidentifier() or not isinstance(values, list) or not values:
            raise MathInputError('invalid variable or empty discrete domain')
        choices.append(K.Choice(name, tuple(sorted(set(_finite(v) for v in values)))))
    n = math.prod(len(v.values) for v in choices)
    if n > max_combinations: raise MathInputError('search budget exceeded')
    entries = []
    def evaluate(x):
        result = evaluator(x.copy())
        if not isinstance(result, dict) or set(result) != {'objective','margins'} or not isinstance(result['margins'], dict):
            raise MathInputError('oracle must return objective and margins exactly')
        objective = _finite(result['objective'])
        margins = {}
        for name, value in result['margins'].items():
            if not isinstance(name, str) or not name.isidentifier(): raise MathInputError('finite objective and named margins required')
            margins[name] = _finite(value)
        entries.append(dict(variables=x.copy(), objective=objective, margins=dict(sorted(margins.items()))))
        return {'objectives': {'objective': objective}, 'constraints': {k:-v for k,v in margins.items()}}
    K.solve(K.Problem(choices, evaluate, ['objective']), max_evals=n, refine=False)
    accepted = [e for e in entries if all(v >= 0 for v in e['margins'].values())]
    accepted.sort(key=lambda e: (e['objective'], tuple(sorted(e['variables'].items()))))
    return dict(schema=BLACKBOX_VERSION, status='feasible_math_candidate' if accepted else 'no_feasible_candidate', candidates=accepted[:keep], evaluations=n, feasible_count=len(accepted), infeasible_count=n-len(accepted), scope='mathematical_discrete_candidates_only_domain_validation_required')

def optimize(program, variables, objective, *, max_combinations=1000, max_iter=200):
    import copy
    from .calculator import calculate
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in (max_combinations, max_iter)):
        raise MathInputError('positive integer search budgets required')
    if not isinstance(variables, dict) or not variables or not isinstance(objective, str) or not objective.isidentifier():
        raise MathInputError('design variables and objective required')
    if any(isinstance(spec, dict) and set(spec) == {'lower','upper','initial'} for spec in variables.values()):
        return _continuous(program, variables, objective, max_combinations, max_iter)
    domains = {}
    for name, spec in variables.items():
        if name not in program['inputs'] or not isinstance(spec, dict) or set(spec) != {'choices'}:
            raise MathInputError('unsupported or invalid design variable')
        domains[name] = spec['choices']
    calculations = {}
    def evaluate(x):
        trial = copy.deepcopy(program)
        for name, value in x.items(): trial['inputs'][name]['value'] = value
        calc = calculate(trial)
        if calc['status'] == 'blocked_missing_inputs': raise MathInputError('calculator missing inputs')
        outputs = {row['id']:row['value'] for row in calc['outputs']}
        if objective not in outputs: raise MathInputError('objective not an output')
        calculations[tuple(sorted(x.items()))] = calc
        return {'objective':outputs[objective], 'margins':{r['id']:r['margin'] for r in calc['checks']}}
    result = optimize_blackbox(domains, evaluate, max_combinations=max_combinations)
    candidates = []
    for c in result['candidates']:
        calc = calculations[tuple(sorted(c['variables'].items()))]
        candidates.append(dict(objective=c['objective'], variables=c['variables'], calculator_program_sha256=calc['program_sha256'], checks=calc['checks']))
    return dict(schema=VERSION, status=result['status'], candidates=candidates, evaluations=result['evaluations'], combinations=result['evaluations'], numerical_converged=True, strict_feasibility_boundary_repairs=0, optimality='exhaustive declared discrete combinations; no continuous global certificate', scope='mathematical_candidates_only_no_domain_release')

def pareto_frontier(points, objectives):
    import copy
    if (not isinstance(points, list) or not isinstance(objectives, list) or not objectives or
        any(not isinstance(k, str) or not k.isidentifier() for k in objectives) or len(set(objectives)) != len(objectives)):
        raise MathInputError('finite points and distinct named objectives required')
    solutions = []
    for p in points:
        if not isinstance(p, dict) or set(p) != {'variables','objectives'} or not isinstance(p['variables'], dict) or not isinstance(p['objectives'], dict) or set(p['objectives']) != set(objectives):
            raise MathInputError('point fields must be numeric variables and objective vector')
        for values in (p['variables'], p['objectives']):
            for name, value in values.items():
                if not isinstance(name, str) or not name.isidentifier(): raise MathInputError('finite named numbers required')
                _finite(value)
        solutions.append(K.Solution(copy.deepcopy(p['variables']), copy.deepcopy(p['objectives']), {}))
    front = K.pareto(solutions, objectives)
    rows = [dict(variables=s.x, objectives=s.objectives) for s in front]
    rows.sort(key=lambda p:(tuple(p['objectives'][k] for k in objectives), tuple(sorted(p['variables'].items()))))
    return dict(schema=PARETO_VERSION, objective_sense={k:'minimize' for k in objectives}, evaluated_points=len(points), front=rows, optimality='nondominated within the supplied finite set only')

def _continuous(program, variables, objective, max_combinations, max_iter):
    import copy
    from .calculator import calculate
    choices = []; start = {}; calls = 0; cache = {}; recorded = []
    for name, spec in variables.items():
        if name not in program['inputs'] or not isinstance(spec, dict): raise MathInputError('invalid variable')
        if set(spec) == {'choices'} and isinstance(spec['choices'], list) and spec['choices']:
            choices.append(K.Choice(name, tuple(sorted(set(_finite(x) for x in spec['choices'])))))
        elif set(spec) == {'lower','upper','initial'}:
            lo, hi, x = (_finite(spec[k]) for k in ('lower','upper','initial'))
            if not lo < hi or not lo <= x <= hi: raise MathInputError('finite ordered bounds and initial required')
            choices.append(K.Continuous(name, lo, hi)); start[name] = x
        else: raise MathInputError('invalid variable')
    combinations = math.prod(len(v.values) for v in choices if isinstance(v,K.Choice))
    if combinations > max_combinations: raise MathInputError('search budget exceeded')
    def calc(x):
        nonlocal calls
        key = tuple(sorted((k,float(v)) for k,v in x.items()))
        if key not in cache:
            calls += 1
            trial = copy.deepcopy(program)
            for k,v in x.items(): trial['inputs'][k]['value'] = float(v)
            r = calculate(trial)
            if r['status'] == 'blocked_missing_inputs': raise MathInputError('calculator missing inputs')
            outputs = {row['id']:row['value'] for row in r['outputs']}
            if objective not in outputs: raise MathInputError('objective not an output')
            cache[key] = (outputs[objective], r)
        return cache[key]
    def evaluate(x):
        f,r = calc(x)
        recorded.append((dict(x),f,r))
        return {'objectives':{'objective':f}, 'constraints':{row['id']:-row['margin'] for row in r['checks']}}
    def gradient(x):
        df={}; dc={r['id']:{} for r in program['checks']}
        for v in choices:
            if not isinstance(v,K.Continuous): continue
            h=1e-6*max(1.,abs(x[v.name])); a=dict(x); b=dict(x)
            a[v.name]=min(v.hi,x[v.name]+h); b[v.name]=max(v.lo,x[v.name]-h)
            fa,ra=calc(a); fb,rb=calc(b); d=a[v.name]-b[v.name]
            df[v.name]=(fa-fb)/d
            for ca,cb in zip(ra['checks'],rb['checks']): dc[ca['id']][v.name]=-(ca['margin']-cb['margin'])/d
        return {'objectives':{'objective':df},'constraints':dc}
    gradient.gradient_source = 'finite_difference_central'
    problem = K.Problem(choices,evaluate,['objective'],gradient=gradient)
    result=K.solve_nlp(problem, x0=start, max_discrete=max_combinations, gradient_check=False, kkt_crosscheck=False, second_order=False, max_inner=max_iter)
    repairs=0
    sol=result.get('solution')
    if sol:
        x=dict(sol.x); f,r=calc(x)
        if r['status'] != 'pass':
            for old,_,oldr in recorded:
                if oldr['status'] != 'pass': continue
                for fraction in (1e-12,1e-10,1e-8,1e-6,1e-4):
                    repaired={k:x[k]+fraction*(old[k]-x[k]) for k in x}
                    rf,rr=calc(repaired)
                    if rr['status']=='pass': recorded.append((repaired,rf,rr)); repairs+=1; break
                if repairs: break
        else: recorded.append((x,f,r))
    valid=[(x,f,r) for x,f,r in recorded if r['status']=='pass']
    valid.sort(key=lambda t:(t[1],tuple(sorted(t[0].items()))))
    candidates=[]; seen=set()
    for x,f,r in valid:
        key=tuple(sorted((k,round(v,10)) for k,v in x.items()))
        if key in seen: continue
        seen.add(key); candidates.append(dict(objective=f,variables=x,calculator_program_sha256=r['program_sha256'],checks=r['checks']))
        if len(candidates)==5: break
    return dict(schema=VERSION,status='feasible_math_candidate' if candidates else 'no_feasible_candidate',candidates=candidates,evaluations=calls,combinations=combinations,numerical_converged=bool(result.get('nlp') and result['nlp'].converged),strict_feasibility_boundary_repairs=repairs,optimality='local continuous search with exhaustive declared discrete combinations; no global optimum certificate',scope='mathematical_candidates_only_no_domain_release')

