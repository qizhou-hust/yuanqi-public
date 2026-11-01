"""Deterministic M32 AST/import boundary gate (stdlib only).

Ownership follows docs/顶层设计.html sections 3, 6, 15: gear and system
own L2 domain calculations; kernel is generic; product/tools only assemble,
compare and report. Frozen legacy/archive/vendor are not active implementations.
This is a conservative syntactic gate, not a proof of arbitrary program semantics.
"""
from __future__ import annotations
import argparse
import ast
import importlib.util
import json
import pathlib
import re

# Semantic signals, not exceptions: every matching executable formula is rejected.
# Single-letter mathematical names (x, y, z, alpha, beta, sigma) are generic.
DOMAIN = re.compile(r"(?:\b(?:gear|gears|tooth|teeth|pinion|helical|worm|planetary)(?:\b|_)|齿|模数|压力角|螺旋角|变位|\b(?:m_n|alpha_[ntw]\w*|beta_b|eps_(?:alpha|beta)|sigma_[HF]\w*|[SZY]_[HF]\w*|F_t|d_[12]|z_?[12])\b)", re.I)
OWNERS = {'gear', 'system'}
LAYERS = {'kernel', 'gear', 'system', 'product', 'tools', 'compat'}


def _domain(text):
    return bool(DOMAIN.search(text))


def _atoms(node):
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            yield n.id
        elif isinstance(n, ast.Attribute):
            yield n.attr
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.value


def _imports(tree, path):
    package = '.'.join(pathlib.PurePosixPath(path).parts[:-1])
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                yield n, a.name
        elif isinstance(n, ast.ImportFrom):
            module = n.module or ''
            if n.level:
                try:
                    module = importlib.util.resolve_name('.' * n.level + module, package)
                except (ImportError, ValueError):
                    yield n, '<invalid-relative-import>'
                    continue
            yield n, module
            for a in n.names:
                yield n, module + '.' + a.name
        elif isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute)):
            name = n.func.id if isinstance(n.func, ast.Name) else n.func.attr
            if name in {'__import__', 'import_module'}:
                if n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                    yield n, n.args[0].value
                else:
                    yield n, '<unresolved-dynamic-import>'


def check_source(source, path):
    """Return ordered, JSON-compatible diagnostics for one repository-relative file."""
    path = str(path).replace('\\', '/')
    parts = pathlib.PurePosixPath(path).parts
    if not parts or parts[0] != 'gearmath':
        return []
    layer = parts[1] if len(parts) > 2 else '<package>' if path == 'gearmath/__init__.py' else '<root-module>'
    if layer not in LAYERS and layer != '<package>':
        return [{'path': path, 'line': 1, 'rule': 'unclassified-layer', 'detail': layer}]
    findings = set()
    def bad(node, rule, detail):
        findings.add((getattr(node, 'lineno', 1), rule, detail))
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return [{'path': path, 'line': exc.lineno, 'rule': 'syntax', 'detail': str(exc)}]
    constructors = {'Formula', 'Expr', 'compile_expr', 'eval'}
    formula_names = constructors | {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names if a.name in constructors}
    for n, module in _imports(tree, path):
        bits = module.split('.')
        target = bits[1] if len(bits) > 1 and bits[0] == 'gearmath' else None
        if bits[0] in {'legacy', 'archive', 'cadbench', 'gears'}:
            bad(n, 'legacy-import', module)
        if layer == 'kernel' and (target in LAYERS - {'kernel'} or module.startswith('<')):
            bad(n, 'upward-import', module)
        if layer in OWNERS and target in {'product', 'tools'}:
            bad(n, 'upward-import', module)
    docs = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
    if layer == 'kernel':
        for n in ast.walk(tree):
            texts = []
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.arg)):
                texts = [n.arg if isinstance(n, ast.arg) else n.name]
            elif isinstance(n, ast.Name):
                texts = [n.id]
            elif isinstance(n, ast.Attribute):
                texts = [n.attr]
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs:
                texts = [n.value]
            for value in texts:
                if _domain(value):
                    bad(n, 'kernel-domain-code', value[:100])
    if layer not in OWNERS:
        for n in ast.walk(tree):
            if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)) and any(_domain(a.id if isinstance(a, ast.Name) else a.attr) for a in ast.walk(n) if isinstance(a, (ast.Name, ast.Attribute))):
                # Formatting strings is presentation, not a physical computation.
                if isinstance(n.op, (ast.Add, ast.Mod)) and any(isinstance(c, ast.Constant) and isinstance(c.value, str) for c in (n.left, n.right)):
                    continue
                bad(n, 'formula-outside-l2', ast.unparse(n)[:160])
            if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Mult, ast.Div, ast.Pow, ast.Sub)):
                keys = [a.slice.value for a in ast.walk(n) if isinstance(a, ast.Subscript) and isinstance(a.slice, ast.Constant) and isinstance(a.slice.value, str)]
                if any(_domain(k) for k in keys):
                    bad(n, 'formula-outside-l2', ast.unparse(n)[:160])
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and n.value is not None:
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                if any(_domain(a) for t in targets for a in _atoms(t)) and any(isinstance(a, ast.BinOp) and isinstance(a.op, (ast.Mult, ast.Div, ast.Pow, ast.Sub)) for a in ast.walk(n.value)):
                    bad(n, 'formula-outside-l2', ast.unparse(n)[:160])
            if isinstance(n, ast.Call):
                name = n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) else ''
                if name in formula_names and any(_domain(a) for a in _atoms(n)):
                    bad(n, 'formula-outside-l2', 'domain Formula declaration')
    return [{'path': path, 'line': line, 'rule': rule, 'detail': detail} for line, rule, detail in sorted(findings)]


def scan(root):
    root = pathlib.Path(root)
    files = sorted((root / 'gearmath').rglob('*.py'))
    violations = [v for p in files for v in check_source(p.read_text(encoding='utf-8-sig'), p.relative_to(root).as_posix())]
    return {'schema': 'gearbase.architecture-gate/1', 'passed': not violations,
            'files_checked': len(files), 'l2_owners': sorted(OWNERS), 'violations': violations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2])
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    report = scan(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else '\n'.join(f"{v['path']}:{v['line']} {v['rule']}: {v['detail']}" for v in report['violations']) or 'architecture gate passed')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
