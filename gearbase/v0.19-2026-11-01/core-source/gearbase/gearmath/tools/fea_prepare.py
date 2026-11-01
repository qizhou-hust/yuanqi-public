"""Prepare strict-read declarations from a canonical M37 deck; no solver verdict."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

PACK = Path(__file__).resolve().parents[2] / 'data' / 'm37_fea_pack'
def _bundled_module(name):
    """Load this package's stdlib-only script by exact path, without sys.path edits."""
    spec=importlib.util.spec_from_file_location('gearbase_m37_'+name,PACK/'scripts'/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    # Registered data stays read-only: SourceFileLoader would create .pyc here.
    path=Path(spec.origin)
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module
deck_state=_bundled_module('deck_state')
ccx_strict=_bundled_module('ccx_strict')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


PROBE_HASHES = {
    'L0_patch_CPE6_h0.inp': 'cbc2e56fcda1db254e0ea159e8185152506856af5da20a9aa24f925da7e13d53',
    'L0_patch_CPE6_h0.dat': '4c8112b394bca0cac239da0c87a4b14f4ff4eca4564b41d0b9fd59dc17584c6b',
    'L0_patch_CPE6_h0.sta': '01e324ec0ea28f4d1fd7f5e2da1277af53812b873e218be1604c17a4c8e4990d',
}
SOLVER_HASH = '31be21fc2f0902bd9a05acc2651dbac6dc2a2573dabbf235e39a38cb6f458862'


def verified_profile(probe_dir, solver_path):
    """Isolated reader instance, enabled only for the measured binary and probe bytes."""
    if sha(solver_path) != SOLVER_HASH:
        raise ValueError('solver binary hash differs from probe')
    for name, expected in PROBE_HASHES.items():
        if sha(Path(probe_dir) / name) != expected:
            raise ValueError('probe identity changed: ' + name)
    reader = _bundled_module('ccx_strict')
    reader.IP_REGISTRY = dict(reader.IP_REGISTRY, **{})
    reader.IP_REGISTRY[('2.23', 'CPE6')] = 9
    reader.REGISTRY_EVIDENCE = dict(reader.REGISTRY_EVIDENCE, ip_v017={'solver_sha256': SOLVER_HASH, 'probe_sha256': PROBE_HASHES})
    return reader


def prepare(inp, solver_version='2.23', *, probe_dir=None, solver_path=None):
    inp = Path(inp)
    if (probe_dir is None) != (solver_path is None):
        raise ValueError('probe and solver paths must be supplied together')
    if probe_dir is not None and solver_version != '2.23':
        raise ValueError('verified probe profile requires solver version 2.23')
    reader = verified_profile(probe_dir, solver_path) if probe_dir is not None else ccx_strict
    state, report = deck_state.check_file(inp)
    if not report['pass']:
        raise ValueError('deck state invalid: ' + str(report['errors']))
    requests = state.strict_requests()
    if not requests:
        raise ValueError('deck has no strict field requests')
    problems = []
    groups = {}
    for element, kind in state.elem_type.items():
        groups.setdefault(kind, []).append(element)
    for kind in groups:
        if (solver_version, kind) not in reader.IP_REGISTRY:
            problems.append({'code': 'registry_missing', 'message': f'ccx {solver_version} {kind} integration-point numbering/count unregistered'})
    surfaces = {name: [[e, side] for e, side in entries] for name, entries in state.surfaces.items()}
    for request in requests:
        issues, _ = reader._validate_request(request, solver_version)
        problems.extend(issues)
    return json.loads(json.dumps({'input_sha256': sha(inp), 'solver_version': solver_version,
            'profile': 'v017_verified_probe' if probe_dir is not None else 'canonical',
            'reader_version': ccx_strict.READER_VERSION, 'state_version': deck_state.STATE_VERSION,
            'preparer_sha256': sha(__file__),
            'solver_binary_sha256': sha(PACK.parents[1] / 'vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23') if solver_version == '2.23' else None,
            'case_sha256': {p.name: sha(p) for p in sorted((PACK / 'cases').glob('L[23]*.json'))},
            'tool_sha256': {name: sha(PACK / 'scripts' / name) for name in ('deck_state.py','ccx_strict.py','cases.py','study.py','mesh_gmsh.py','inp_writer.py')},
            'element_groups': groups, 'deck_surfaces': surfaces,
            'observed_ip_probe': ({'element_type': 'CPE6', 'ip_keys_per_element': list(range(1,10)),
                'input_sha256': 'cbc2e56fcda1db254e0ea159e8185152506856af5da20a9aa24f925da7e13d53',
                'dat_sha256': '4c8112b394bca0cac239da0c87a4b14f4ff4eca4564b41d0b9fd59dc17584c6b',
                'solver_sha256': '31be21fc2f0902bd9a05acc2651dbac6dc2a2573dabbf235e39a38cb6f458862',
                'scope': 'synthetic CPE6 stress and coordinates; not reader registration'}
                if solver_version == '2.23' and 'CPE6' in groups else None),
            'requests': requests, 'registration': 'blocked' if problems else 'ready',
            'registration_problems': problems, 'contact_file_requirement': 'undecided',
            'notice': 'Preparation only; no raw solver output or acceptance verdict.'},allow_nan=False))


def verify(inp, manifest, *, probe_dir=None, solver_path=None):
    if sha(inp) != manifest['input_sha256']:
        raise ValueError('input identity changed')
    actual = prepare(inp, manifest['solver_version'], probe_dir=probe_dir, solver_path=solver_path)
    if actual != manifest:
        raise ValueError('declaration or tool identity changed')
    return True
