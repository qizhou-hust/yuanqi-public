"""Stage the unchanged M31 caller environment around the new math kernel.

The three retired computational entry points route to the new kernel. Supported
NumPy norms use the declared ordered-FMA kernel profile. All archived assertions
and callers are copied byte for byte; the runtime never patches tests.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
ALIASES = {
    'cadbench.math_calculator': 'calculator',
    'cadbench.math_optimizer': 'optimizer',
    'gears.graph': 'graph',
}


def record_alias(alias, adapter):
    """Record the actual loaded module and kernel in every importing process."""
    import gearmath.kernel.expr as expr
    import gearmath.kernel.units as units
    path = os.environ.get('M31_PROVENANCE_LOG')
    if path:
        row = {'event': 'alias_import', 'pid': os.getpid(), 'alias': alias,
               'adapter_file': adapter.__file__, 'adapter_module': adapter.__name__,
               'kernel_files': [expr.__file__, units.__file__]}
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(row)+'\n')



def _runtime_event(event, **details):
    path = os.environ.get('M31_PROVENANCE_LOG')
    if path:
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(event=event, pid=os.getpid(), **details))+'\n')



def make_numpy_norm_adapter(np, original=None):
    """Apply the declared ordered-FMA norm to its generic supported API domain.

    This adapter is installed only in the staged regression environment. The
    product kernel owns numerical semantics; unsupported NumPy calls retain
    their original implementation, warnings, errors, and dtype conventions.
    """
    from gearmath.kernel import floating
    if original is None:
        original = np.linalg.norm
    used_pids = set()
    def norm(x, ord=None, axis=None, keepdims=False):
        supported_order = (ord is None or
                           isinstance(ord, (int, float, np.integer, np.floating)) and ord == 2)
        supported = (type(x) is np.ndarray and x.ndim == 1 and
                     x.dtype == np.dtype('float64') and x.dtype.isnative and
                     axis is None and supported_order and
                     isinstance(keepdims, (bool, np.bool_)))
        if supported and bool(np.isfinite(x).all()):
            try:
                value = floating.norm_fma(x.tolist())
            except OverflowError:
                # Preserve NumPy's own errstate/warning and non-finite result
                # behavior when the finite binary64 kernel domain is exceeded.
                return original(x, ord=ord, axis=axis, keepdims=keepdims)
            result = np.float64(value)
            pid = os.getpid()
            if pid not in used_pids:
                _runtime_event('numeric_profile', profile_id=floating.PROFILE_ID,
                               backend=floating.FMA_BACKEND, kernel_file=floating.__file__,
                               kernel_callable='gearmath.kernel.floating.norm_fma',
                               host_executable=sys.executable, numpy_version=np.__version__,
                               api_domain='native float64 ndarray, 1D, axis=None, ord=None or 2')
                used_pids.add(pid)
            return np.asarray([result], dtype=np.float64) if keepdims else result
        return original(x, ord=ord, axis=axis, keepdims=keepdims)
    norm.__name__ = 'norm'
    norm.__doc__ = original.__doc__
    norm._m31_numpy_norm_original = original
    norm._m31_numpy_norm_profile = floating.PROFILE_ID
    return norm


def _install_numpy_norm_loader():
    """Install lazily so pure-kernel workers acquire no NumPy dependency."""
    from importlib.machinery import PathFinder
    if any(getattr(finder, '_m31_numpy_norm_loader', False) for finder in sys.meta_path):
        return
    def install(module):
        np = sys.modules.get('numpy')
        norm = module.__dict__.get('norm')
        if np is not None and norm is not None and not hasattr(norm, '_m31_numpy_norm_profile'):
            module.norm = make_numpy_norm_adapter(np, norm)
    class NormLoader:
        def __init__(self, loader):
            self.loader = loader
        def create_module(self, spec):
            create = getattr(self.loader, 'create_module', None)
            return create(spec) if create else None
        def exec_module(self, module):
            self.loader.exec_module(module)
            install(module)
    class NormFinder:
        _m31_numpy_norm_loader = True
        @classmethod
        def find_spec(cls, fullname, path=None, target=None):
            if fullname != 'numpy.linalg':
                return None
            spec = PathFinder.find_spec(fullname, path, target)
            if spec is not None and spec.loader is not None:
                spec.loader = NormLoader(spec.loader)
            return spec
    sys.meta_path.insert(0, NormFinder)
    module = sys.modules.get('numpy.linalg')
    if module is not None:
        install(module)


def install_profile_compatibility():
    """Expose real native-worker metadata and the renamed OCP face cast.

    Never import CAD as part of startup: the pure-math workers must remain
    independent. Native distribution objects point to their installed paths;
    they do not claim that the native OCP distribution runs in the host.
    """
    import builtins
    import subprocess
    _install_numpy_norm_loader()
    from importlib import metadata
    native = os.environ.get('GEAR_NATIVE_PYTHON')
    requested = []
    if native:
        for name in ('cadquery', 'cadquery-ocp'):
            try:
                metadata.distribution(name)
            except metadata.PackageNotFoundError:
                requested.append(name)
    if requested:
        code = """import importlib.metadata as m,json,sys
rows=[]
for name in sys.argv[1:]:
 d=m.distribution(name)
 rows.append(dict(name=name,version=d.version,metadata_path=str(d._path)))
print(json.dumps(dict(executable=sys.executable,prefix=sys.prefix,distributions=rows)))
"""
        result = subprocess.run([native, '-I', '-c', code, *requested], check=True,
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        profile = json.loads(result.stdout)
        distributions = {}
        for row in profile['distributions']:
            path = Path(row['metadata_path'])
            distribution = metadata.PathDistribution(path)
            if distribution.version != row['version'] or distribution.metadata['Name'].lower().replace('_','-') != row['name']:
                raise RuntimeError('native metadata query disagrees with installed distribution')
            distributions[row['name']] = distribution
        class NativeMetadataFinder(metadata.DistributionFinder):
            @classmethod
            def find_distributions(cls, context=metadata.DistributionFinder.Context()):
                name = (context.name or '').lower().replace('_', '-')
                return iter((distributions[name],)) if name in distributions else iter(())
            @classmethod
            def find_spec(cls, fullname, path=None, target=None):
                return None
        host_packages = dependency_inventory()['packages']
        sys.meta_path.append(NativeMetadataFinder)
        _runtime_event('native_metadata_bridge', host_executable=sys.executable,
                       host_prefix=sys.prefix, host_packages=host_packages,
                       native_profile=profile, requested_missing_host_distributions=requested)
    original_import = builtins.__import__
    if not getattr(original_import, '_m31_face_cast_compatibility', False):
        def compatible_import(name, globals=None, locals=None, fromlist=(), level=0):
            module = original_import(name, globals, locals, fromlist, level)
            if name == 'OCP.TopoDS':
                topods_module = sys.modules.get('OCP.TopoDS')
                casts = getattr(topods_module, 'TopoDS', None)
                if casts is not None and not hasattr(casts, 'Face_s') and hasattr(casts, 'Face'):
                    casts.Face_s = casts.Face
                    ocp = sys.modules.get('OCP')
                    _runtime_event('ocp_api_alias', alias='TopoDS.Face_s', target='TopoDS.Face',
                                   ocp_version=getattr(ocp, '__version__', None),
                                   ocp_file=getattr(ocp, '__file__', None), host_executable=sys.executable)
            return module
        compatible_import._m31_face_cast_compatibility = True
        builtins.__import__ = compatible_import


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy(source, destination):
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache'))
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def stage_environment(stage):
    stage = Path(stage).resolve()
    # src is sufficient even when unchanged tests explicitly reset PYTHONPATH.
    return dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (stage/'src', stage, stage/'tools'))),
                PYTHONUTF8='1', M31_PROVENANCE_LOG=str(stage/'provenance.jsonl'))


def dependency_inventory():
    names = ('pytest', 'numpy', 'scipy', 'cadquery', 'cadquery-ocp',
             'build123d', 'gmsh', 'shapely', 'reportlab', 'ezdxf', 'npTDMS',
             'cadquery-ocp-novtk', 'cadquery-ocp-proxy')
    values = {}
    for name in names:
        try:
            values[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            values[name] = None
    return {'python': sys.version, 'executable': sys.executable, 'platform': sys.platform,
            'packages': values}


def verify_sources(stage, root=ROOT):
    archive = Path(root)/'archive'/'m31'
    frozen = json.loads((Path(root)/'gearmath'/'tools'/'m31_source_manifest.json').read_text(encoding='utf-8'))['files']
    rows = []
    for name in ('tests', 'cadbench_tests'):
        for source in sorted((archive/name).rglob('*')):
            if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
                relative = source.relative_to(archive)
                target = Path(stage)/relative
                rows.append({'path': relative.as_posix(), 'frozen_sha256': frozen.get(relative.as_posix()), 'source_sha256': _sha(source),
                             'stage_sha256': _sha(target) if target.is_file() else None})
    mismatches = [r['path'] for r in rows if r['source_sha256'] != r['stage_sha256'] or r['source_sha256'] != r['frozen_sha256']]
    mismatches += sorted(set(frozen) - {r['path'] for r in rows})
    return {'files': rows, 'source_files': len(rows), 'mismatches': mismatches,
            'test_modules': sum(r['path'].split('/')[-1].startswith('test_') and r['path'].endswith('.py') for r in rows)}


def prepare_stage(stage, root=ROOT):
    stage, root = Path(stage).resolve(), Path(root).resolve()
    stage.mkdir(parents=True, exist_ok=True)
    archive = root/'archive'/'m31'
    for source in archive.iterdir():
        if source.name != '__pycache__':
            _copy(source, stage/source.name)
    _copy(root/'gearmath', stage/'src'/'gearmath')
    bank = root/'bank'/'benchmark50'
    for source in bank.rglob('*'):
        if source.is_file():
            destination = stage/'benchmark50'/source.relative_to(bank)
            if destination.is_file() and _sha(source) != _sha(destination):
                raise RuntimeError('M31 context/bank version collision: '+source.relative_to(bank).as_posix())
    _copy(bank, stage/'benchmark50')
    # Recreate original vendor paths, retaining source and data without executing
    # any bundled solver or interpreter. Old callers own their dependency policy.
    for category in ('cad', 'fea'):
        vendor = root/'vendor'/category/'vendor'
        if vendor.is_dir():
            for source in vendor.iterdir():
                _copy(source, stage/'vendor'/source.name)
    for module, adapter in ALIASES.items():
        target = stage/'src'/Path(*module.split('.')).with_suffix('.py')
        target.write_text('import sys\nfrom gearmath.compat.m31 import '+adapter+' as _adapter\n'
                          'from gearmath.tools.m31_runtime import record_alias as _record_alias\n'
                          '_record_alias(__name__, _adapter)\n'
                          'sys.modules[__name__] = _adapter\n', encoding='utf-8')
    # Preserve access to tools for child processes whose PYTHONPATH is src only.
    # sitecustomize runs for ordinary workers; -I callers already insert src.
    (stage/'src'/'sitecustomize.py').write_text(_SITECUSTOMIZE, encoding='utf-8')
    if sys.platform == 'win32':
        (stage/'src'/'fcntl.py').write_text(_WINDOWS_FCNTL, encoding='utf-8')
    hashes = verify_sources(stage, root)
    cases = sorted((stage/'benchmark50'/'cases').glob('C*.json'))
    if hashes['mismatches'] or hashes['test_modules'] != 73 or len(cases) != 50:
        raise RuntimeError('Invalid M31 stage: '+json.dumps({'hashes': hashes, 'cases': len(cases)}))
    report = {'stage': str(stage), 'source_integrity': hashes, 'benchmark_cases': len(cases),
              'dependencies': dependency_inventory(), 'aliases': ALIASES}
    (stage/'runtime-stage.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


_SITECUSTOMIZE = '''import atexit,json,os,pathlib,sys
from gearmath.tools.m31_runtime import install_profile_compatibility
install_profile_compatibility()
_root=pathlib.Path(__file__).resolve().parents[1]
for _p in (_root,_root/'tools'):
    if str(_p) not in sys.path: sys.path.append(str(_p))
def _record():
    _mods={}
    for _n in ('cadbench.math_calculator','cadbench.math_optimizer','gears.graph'):
        _m=sys.modules.get(_n)
        if _m is not None:
            _mods[_n]={'file':getattr(_m,'__file__',None),'name':getattr(_m,'__name__',None)}
    _row={'pid':os.getpid(),'argv':sys.argv,'modules':_mods}
    _p=os.environ.get('M31_PROVENANCE_LOG')
    if _p:
        with open(_p,'a',encoding='utf-8') as _f: _f.write(json.dumps(_row)+'\\n')
atexit.register(_record)
'''

_WINDOWS_FCNTL = '''"""Windows byte-range locking implementation of the used flock subset."""
import os,msvcrt
LOCK_SH=1
LOCK_EX=2
LOCK_NB=4
LOCK_UN=8
def flock(stream,operation):
    fd=stream if isinstance(stream,int) else stream.fileno()
    position=os.lseek(fd,0,os.SEEK_CUR)
    try:
        os.lseek(fd,0,os.SEEK_SET)
        mode=msvcrt.LK_UNLCK if operation & LOCK_UN else (msvcrt.LK_NBLCK if operation & LOCK_NB else msvcrt.LK_LOCK)
        msvcrt.locking(fd,mode,1)
    finally:
        os.lseek(fd,position,os.SEEK_SET)
'''
