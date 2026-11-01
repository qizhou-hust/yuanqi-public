"""Fail-closed static import identity for the M36 controlled replay profile."""
import ast
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTRY = 'gearmath.tools.system_closure'
# Validation and evidence registry consulted by the controlled replay.
DATA = ('data/source/gears.math-source-2.schema.json',
        'data/schema/gears.system-input-1.schema.json',
        'data/schema/gears.design-check-result-1.schema.json',
        'data/registry/formulas-v1.json')

def implementation_sha256(root=ROOT):
    root = Path(root)
    todo = [ENTRY, 'gearmath.tools.m36_identity']
    seen = set()
    files = {}
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        parts = name.split('.')
        path = root.joinpath(*parts).with_suffix('.py')
        if not path.is_file():
            path = root.joinpath(*parts, '__init__.py')
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        files[rel] = raw
        tree = ast.parse(raw, filename=rel)
        package = name if path.name == '__init__.py' else name.rpartition('.')[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                todo.extend(a.name for a in node.names if a.name.startswith('gearmath'))
            elif isinstance(node, ast.ImportFrom):
                base = importlib.util.resolve_name('.' * node.level + (node.module or ''), package) if node.level else (node.module or '')
                if base == 'gearmath' or base.startswith('gearmath.'):
                    todo.append(base)
                    todo.extend(base + '.' + a.name for a in node.names if a.name != '*')
                    if any(a.name == '*' for a in node.names):
                        raise ValueError('Star import in M36 dependency: ' + rel)
            elif isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
                fn = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                if fn in ('__import__', 'import_module'):
                    raise ValueError('Dynamic import in M36 dependency: ' + rel)
        for i in range(1, len(parts)):
            todo.append('.'.join(parts[:i]))
    for rel in DATA:
        files[rel] = (root / rel).read_bytes()
    h = hashlib.sha256()
    for rel, raw in sorted(files.items()):
        h.update(rel.encode()); h.update(hashlib.sha256(raw).digest())
    return h.hexdigest()
