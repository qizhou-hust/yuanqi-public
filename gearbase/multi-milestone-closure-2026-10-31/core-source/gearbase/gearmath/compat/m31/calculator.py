"""Translate M31 quantities and programs to the canonical kernel."""
import ast
import hashlib
import json
import math
import re
from dataclasses import dataclass
from gearmath.kernel import units as U
from gearmath.kernel.expr import Expr

VERSION = 'cadbench.math-calculator/1'
class MathInputError(ValueError):
    pass

def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise MathInputError('finite numeric value required')
    return float(value)

def _unit(name):
    if name not in {'1','mm','N','N*mm','N*m','rpm','mm/min','deg','MPa'}:
        raise KeyError(name)
    return U.unit(name)

@dataclass(frozen=True)
class Quantity:
    value: float
    dim: tuple
    def converted(self, unit):
        try:
            dim, scale = _unit(unit)
            if dim != self.dim:
                raise MathInputError('incompatible dimensions')
            return _finite(self.value / scale)
        except KeyError as e:
            raise MathInputError('unknown unit: ' + str(unit)) from e

def quantity(value, unit):
    try:
        dim, scale = _unit(unit)
        return Quantity(_finite(_finite(value) * scale), dim)
    except KeyError as e:
        raise MathInputError('unknown unit: ' + str(unit)) from e

def formula(expr, env):
    try:
        if not isinstance(expr, str) or len(expr) > 500:
            raise MathInputError('bounded expression required')
        original = ast.parse(expr, mode='eval')
        for node in ast.walk(original):
            if isinstance(node, ast.Constant) and (isinstance(node.value, bool) or not isinstance(node.value, (int, float))):
                raise MathInputError('finite numeric value required')
            if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in {'sin_deg','cos_deg','tan_deg','sqrt','abs','min','max'} or node.keywords):
                raise MathInputError('function not permitted')
        function_names = {'sin_deg','cos_deg','tan_deg','sqrt','abs','min','max','pi'}
        missing = sorted({n.id for n in ast.walk(original) if isinstance(n, ast.Name) and n.id not in env and n.id not in function_names})
        if missing: raise MathInputError('missing input: ' + missing[0])
        expr = re.sub(r'\b(sin|cos|tan)_deg\b', r'\1', expr)
        tree = ast.parse(expr, mode='eval')
        class _Exponent(ast.NodeTransformer):
            def visit_BinOp(self, node):
                node = self.generic_visit(node)
                if isinstance(node.op, ast.Pow):
                    exponent = Expr(ast.unparse(node.right))
                    if exponent.dimension({k:v.dim for k,v in env.items()}) != U.ONE:
                        raise MathInputError('only bounded integer powers supported')
                    value = exponent.evaluate({k:v.value for k,v in env.items()})
                    value = _finite(getattr(value, 'v', value))
                    if int(value) != value or abs(value) > 4:
                        raise MathInputError('only bounded integer powers supported')
                    node.right = ast.Constant(int(value))
                return node
        compiled = Expr(ast.unparse(ast.fix_missing_locations(_Exponent().visit(tree))))
        # Old calculator requires exactly one argument to abs.
        for node in ast.walk(compiled.tree):
            if isinstance(node, ast.Call) and node.func.id in {'abs','sqrt','sin','cos','tan'} and len(node.args) != 1:
                raise MathInputError(node.func.id + ' needs exactly one argument')
            if isinstance(node, ast.Call) and node.func.id == 'sqrt':
                arg_dim = Expr(ast.unparse(node.args[0])).dimension({k:v.dim for k,v in env.items()})
                if any(component.denominator != 1 or component.numerator % 2 for component in arg_dim):
                    raise MathInputError('sqrt dimensions must be even')
        dim = compiled.dimension({k: v.dim for k, v in env.items()})
        value = compiled.evaluate({k: v.value for k, v in env.items()})
        return Quantity(_finite(getattr(value, 'v', value)), dim)
    except MathInputError:
        raise
    except Exception as e:
        raise MathInputError('incompatible dimensions or invalid arithmetic: ' + str(e)) from e

def _digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def calculate(program):
    if not isinstance(program, dict) or set(program) != {'schema', 'inputs', 'equations', 'checks', 'required_inputs'} or program['schema'] != VERSION:
        raise MathInputError('calculator schema/fields differ')
    env = {}
    for name, row in program['inputs'].items():
        if not name.isidentifier() or name == 'pi' or not isinstance(row, dict) or set(row) != {'value', 'unit'}:
            raise MathInputError('invalid input declaration: ' + name)
        env[name] = quantity(row['value'], row['unit'])
    missing = sorted(set(program['required_inputs']) - set(env))
    outputs, checks = [], []
    if missing:
        return dict(schema=VERSION, status='blocked_missing_inputs', missing=missing, outputs=[], checks=[], program_sha256=_digest(program))
    for row in program['equations']:
        if set(row) != {'id','expr','unit'} or not row['id'].isidentifier() or row['id'] in env or row['id'] == 'pi':
            raise MathInputError('invalid equation identity')
        q = formula(row['expr'], env)
        value = q.converted(row['unit'])
        env[row['id']] = q
        outputs.append(dict(id=row['id'], value=value, unit=row['unit'], expr=row['expr']))
    for row in program['checks']:
        if set(row) != {'id','lhs','op','rhs','unit','tolerance'} or row['op'] not in {'<=','>=','=='}:
            raise MathInputError('invalid check declaration')
        lhs = formula(row['lhs'], env).converted(row['unit'])
        rhs = formula(row['rhs'], env).converted(row['unit'])
        tol = _finite(row['tolerance'])
        if tol < 0: raise MathInputError('negative tolerance')
        margin = _finite({'<=': rhs-lhs+tol, '>=': lhs-rhs+tol, '==': tol-abs(lhs-rhs)}[row['op']])
        checks.append(dict(id=row['id'], status='pass' if margin >= 0 else 'fail', lhs=lhs, rhs=rhs, unit=row['unit'], margin=margin, tolerance=tol))
    return dict(schema=VERSION, status='pass' if all(r['status']=='pass' for r in checks) else 'failed_check', missing=[], outputs=outputs, checks=checks, program_sha256=_digest(program))
