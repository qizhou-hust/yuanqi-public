"""A11 exact-byte solver origin allowance. Read-only; never launches a process.

This records the user's v0.18 authorization rule after an independent direct
download. It does not register element/contact readers or accept FEA results.
"""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path

ARCHIVE_SHA256 = '35d426fed5eb164fbbaaafa20819d13d22e30bc2b9bc9c6c4ed957e9468355dd'
BINARY_SHA256 = '31be21fc2f0902bd9a05acc2651dbac6dc2a2573dabbf235e39a38cb6f458862'
MEMBER = './CalculiX/ccx_2.23/src/ccx_2.23'
URL = 'https://www.dhondt.de/ccx_2.23.tar.bz2'
REGISTRY = Path(__file__).resolve().parents[2] / 'data/solver/ccx-2.23-allowance.json'


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def record():
    """Validate immutable identities and the recorded download proof."""
    row = json.loads(REGISTRY.read_text(encoding='utf8'))
    expected = {
        'schema': 'gearbase.solver-allowance/1',
        'solver_id': 'calculix-ccx-2.23-linux-x86_64',
        'archive_url': URL, 'archive_sha256': ARCHIVE_SHA256,
        'archive_member': MEMBER, 'executable_sha256': BINARY_SHA256,
        'scope': 'explicit-local-verification',
        'numerical_gear_qualification': 'not_granted',
    }
    if any(row.get(k) != v for k, v in expected.items()):
        raise ValueError('solver allowance identity differs from verified exact version')
    name = row['origin_proof_file']
    if not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name:
        raise ValueError('invalid origin proof path')
    path = REGISTRY.parent / name
    if _sha(path) != row['origin_proof_sha256']:
        raise ValueError('origin proof hash mismatch')
    proof = json.loads(path.read_text(encoding='utf8'))
    checks = {
        'schema': 'gearbase.solver-origin-verification/1', 'requested_url': URL,
        'final_url': URL, 'archive_sha256': ARCHIVE_SHA256,
        'archive_expected': ARCHIVE_SHA256, 'member': MEMBER,
        'executable_sha256': BINARY_SHA256, 'vendored_sha256': BINARY_SHA256,
        'passed': True, 'executed_during_origin_verification': False,
    }
    if any(proof.get(k) != v for k, v in checks.items()):
        raise ValueError('origin proof identity or verification state mismatch')
    return dict(row, origin_proof=proof)


def verify(solver_path, *, archive=None):
    """Check current binary bytes; optionally recheck the complete upstream tar.

    The archive member is streamed without extracting paths onto the filesystem.
    Permission applies to this Linux executable only; it does not make a Windows
    host capable of launching it, and no input deck or process is run here.
    """
    row = record()
    if _sha(solver_path) != BINARY_SHA256:
        raise ValueError('solver binary hash differs from the allowed exact executable')
    if archive is not None:
        if _sha(archive) != ARCHIVE_SHA256:
            raise ValueError('official archive hash mismatch')
        with tarfile.open(archive, 'r:bz2') as package:
            matches = [m for m in package.getmembers() if m.name == MEMBER]
            if len(matches) != 1 or not matches[0].isfile():
                raise ValueError('official executable member missing, duplicate or not regular')
            with package.extractfile(matches[0]) as stream:
                digest = hashlib.sha256(stream.read()).hexdigest()
        if digest != BINARY_SHA256:
            raise ValueError('archive member hash mismatch')
    return {
        'schema': 'gearbase.solver-permission-check/1', 'allowed': True,
        'solver_id': row['solver_id'], 'executable_sha256': BINARY_SHA256,
        'archive_sha256': ARCHIVE_SHA256, 'archive_rechecked': archive is not None,
        'scope': row['scope'], 'origin_proof_sha256': row['origin_proof_sha256'],
        'solver_executed': False, 'numerical_gear_qualification': 'not_granted',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--solver', required=True)
    parser.add_argument('--archive')
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    result = verify(args.solver, archive=args.archive)
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        Path(args.out).write_text(text, encoding='utf8')
    print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
