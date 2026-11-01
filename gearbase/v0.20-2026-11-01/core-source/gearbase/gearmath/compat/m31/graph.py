"""Legacy graph API translated to kernel expression and coupled solver."""
import ast
import math
from dataclasses import dataclass
from gearmath.kernel.expr import Expr

class FormulaError(ValueError): pass
FUNCS = {'sin','cos','tan','asin','acos','atan','atan2','sinr','cosr','tanr','asinr','acosr','atanr','sqrt','exp','log','abs','min','max','pow','inv','rad','deg','clamp'}
CONSTS = {'pi','e'}
class _Translate(ast.NodeTransformer):
    def visit_Name(self, n):
        if n.id == 'e': return ast.copy_location(ast.Constant(math.e), n)
        return n
    def visit_Call(self, n):
        if not isinstance(n.func, ast.Name) or n.func.id not in FUNCS or n.keywords:
            raise FormulaError('only whitelisted functions allowed')
        name = n.func.id
        args = [self.visit(x) for x in n.args]
        def call(name, args): return ast.Call(func=ast.Name(id=name,ctx=ast.Load()), args=args, keywords=[])
        def mul(a,b): return ast.BinOp(left=a,op=ast.Mult(),right=b)
        factor = ast.Constant(math.pi/180)
        if name in ('sin','cos','tan') and len(args)==1: return call(name,[mul(args[0], factor)])
        if name in ('asin','acos','atan','atan2') and len(args)==(2 if name == 'atan2' else 1): return mul(call(name,args),ast.Constant(180/math.pi))
        if name in ('sinr','cosr','tanr','asinr','acosr','atanr'): return call(name[:-1],args)
        if name == 'rad' and len(args)==1: return mul(args[0],factor)
        if name == 'deg' and len(args)==1: return mul(args[0],ast.Constant(180/math.pi))
        if name == 'clamp' and len(args)==3: return call('min',[call('max',[args[2],args[0]]),args[1]])
        if name == 'pow' and len(args)==2: return ast.BinOp(left=args[0],op=ast.Pow(),right=args[1])
        return call(name,args)

def compile_formula(expr):
    try:
        tree = ast.parse(expr, mode='eval')
        allowed = (ast.Expression,ast.BinOp,ast.UnaryOp,ast.Load,ast.Constant,ast.Name,ast.Call,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.USub,ast.UAdd)
        if any(not isinstance(n, allowed) for n in ast.walk(tree)): raise FormulaError('disallowed syntax')
        tree = ast.fix_missing_locations(_Translate().visit(tree))
        return Expr(ast.unparse(tree))
    except FormulaError: raise
    except Exception as e: raise FormulaError(str(e)) from e

def eval_formula(code, env):
    try:
        value = code.evaluate({k:v for k,v in env.items() if k not in FUNCS and k not in CONSTS})
        return float(getattr(value,'v',value))
    except Exception as e: raise FormulaError(str(e)) from e

def free_names(expr):
    tree = ast.parse(expr,mode='eval')
    return {n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and n.id not in FUNCS and n.id not in CONSTS}

@dataclass
class Artifact:
    id: str
    deps: tuple
    producer: object
    upstream: tuple = ()
    payload: object = None
    proj: str = ''
    status: str = 'pending'

class ArtifactDAG:
    def __init__(self): self.items = {}
    def add(self, aid, deps, producer, upstream=()):
        self.items[aid] = Artifact(aid, tuple(sorted(deps)), producer, tuple(sorted(upstream)))
    def run(self, values):
        import json, hashlib
        done = set()
        while len(done) < len(self.items):
            ready = [k for k in sorted(self.items) if k not in done and all(u in done for u in self.items[k].upstream)]
            if not ready: raise RuntimeError('artifact dependency cycle')
            aid = ready[0]; item = self.items[aid]
            projection = hashlib.sha256(json.dumps({k:values.get(k,'__MISSING__') for k in item.deps}, sort_keys=True, default=str).encode()).hexdigest()[:16]
            blocked = [u for u in item.upstream if self.items[u].status == 'blocked']
            if blocked: item.status, item.payload = 'blocked', {'blocked_by':blocked}
            elif projection == item.proj and item.status in ('recomputed','reused'): item.status = 'reused'
            else:
                try:
                    item.payload = item.producer({**values, **{k:self.items[k].payload for k in item.upstream}})
                    item.status = 'recomputed'
                except Exception as e: item.status, item.payload = 'blocked', {'error':str(e)}
            item.proj = projection
            done.add(aid)
        return self.items

from gearmath.kernel.coupled import solve_coupled, NotConverged

class ConstraintGraph:
    def __init__(self):
        self.inputs = {}; self.assigns = {}; self.residuals = {}; self.last_history = []
    def input(self, name, value):
        if name in FUNCS or name in CONSTS: raise FormulaError(f'{name} shadows an engine name')
        self.inputs[name] = float(value)
        return self
    def assign(self, var, expr):
        self.assigns[var] = (compile_formula(expr), free_names(expr))
        return self
    def residual(self, name, expr):
        deps = free_names(expr)
        bad = deps - set(self.inputs) - set(self.assigns)
        if bad: raise FormulaError(f'residual {name}: unknown symbols {sorted(bad)}')
        self.residuals[name] = (compile_formula(expr), deps, None)
        return self
    def _order(self):
        done = set(self.inputs); remaining = set(self.assigns); order = []
        while remaining:
            ready = {v for v in remaining if self.assigns[v][1] <= done}
            if not ready: ready = {min(remaining)}
            for v in sorted(ready):
                order.append(v); done.add(v); remaining.remove(v)
        return order
    def solve(self, tol=1e-12, max_iter=100):
        names = set(self.inputs) | set(self.assigns)
        for name, (_, deps) in self.assigns.items():
            if deps - names: raise FormulaError(f'assign {name}: unknown symbols {sorted(deps - names)}')
        order = self._order()
        assignments = [(name, lambda env, code=self.assigns[name][0]: eval_formula(code,env)) for name in order]
        try:
            values, self.last_history = solve_coupled(assignments, self.inputs, tol=tol, max_iter=max_iter, return_history=True)
        except NotConverged as exc:
            self.last_history = list(exc.history)
            for name, (code, deps, _) in self.residuals.items():
                self.residuals[name] = (code, deps, eval_formula(code, exc.values))
            raise
        for name, (code, deps, _) in self.residuals.items():
            self.residuals[name] = (code,deps,eval_formula(code,values))
        return {name:values[name] for name in self.assigns}
    def max_residual(self):
        return max((abs(row[2]) for row in self.residuals.values() if row[2] is not None),default=0.0)
