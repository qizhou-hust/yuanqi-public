"""gearbase Windows 便携包构建脚本（Python 版，仅标准库）。语义与 build_portable.ps1 相同。

    python3 -I packaging/windows/build_portable.py --python-version 3.12.x --sha256 <你核对的哈希> [--embed-zip 已下载.zip]

哈希必须由用户核对后传入；不匹配即失败。本仓库不含任何二进制，也不内置任何哈希。
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import shutil
import sys
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIRS = ["gearmath", "data", "docs", "tests", "bank", "vendor"]
FILES = ["mcp_server.py", "run_tests.py", "conftest.py", "demo.py", "README.md", "VERSION", "CHANGELOG.md", "MANIFEST.json",
         "PACKAGE-CONTENTS.sha256"]
PRIVATE = ("tr30", "iso18265", "kisssoft", "registry")


def verify_sha256(path, expected):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected or ""):
        raise SystemExit("sha256 必须是你核对过的 64 位十六进制，不接受占位符")
    h = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
    if h != expected.lower():
        raise SystemExit(f"sha256 不匹配：期望 {expected}，实际 {h}。已中止。")


def bats(out):
    py = r'"%~dp0python\python.exe"'
    (out / "run_tests.bat").write_text(f"@echo off\r\ncd /d %~dp0gearbase\r\n{py} -I run_tests.py %*\r\n", encoding="ascii")
    (out / "doctor.bat").write_text(f"@echo off\r\ncd /d %~dp0gearbase\r\n{py} -I gearmath\\tools\\doctor.py %*\r\n", encoding="ascii")
    (out / "mcp_server.bat").write_text(f"@echo off\r\n{py} -I %~dp0gearbase\\mcp_server.py --state-dir %~dp0state %*\r\n", encoding="ascii")


def copy_core(app, include_private=False):
    ign = shutil.ignore_patterns("__pycache__", "*.pyc")
    for d in DIRS:
        src = ROOT / d
        if not src.is_dir():
            continue

        def ig(cur, names, d=d):
            skip = set(ign(cur, names))
            if not include_private and d == "data" and pathlib.Path(cur) == src:
                skip |= set(PRIVATE) & set(names)
            return skip
        shutil.copytree(src, app / d, ignore=ig)
    for f in FILES:
        if (ROOT / f).is_file():
            shutil.copy2(ROOT / f, app / f)
    if include_private:
        manifest = json.loads((app / 'MANIFEST.json').read_text(encoding='utf-8'))
        for row in manifest['legacy']:
            rel = pathlib.PurePosixPath(row['path'])
            if rel.is_absolute() or '..' in rel.parts or rel.parts[0] != 'legacy':
                raise ValueError(f"invalid legacy path: {rel}")
            dst = app.joinpath(*rel.parts)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT.joinpath(*rel.parts), dst)
        spec = importlib.util.spec_from_file_location('package_hashes', app / 'gearmath/tools/package_hashes.py')
        ph = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ph)
        stale = ph.update_manifest(app, write=False)
        if stale:
            raise ValueError(f"MANIFEST hash mismatch: {stale}")
        (app / ph.CONTENTS).write_text(ph.contents_text(app), encoding='utf-8', newline='\n')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--python-version", required=True)
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--embed-zip")
    ap.add_argument("--out", default=str(ROOT / "dist" / "gearbase-portable"))
    ap.add_argument("--include-private", action="store_true")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    zp = pathlib.Path(a.embed_zip) if a.embed_zip else out / "python-embed.zip"
    if not a.embed_zip:
        url = f"https://www.python.org/ftp/python/{a.python_version}/python-{a.python_version}-embed-amd64.zip"
        print("Downloading", url)
        urllib.request.urlretrieve(url, zp)
    verify_sha256(zp, a.sha256)
    with zipfile.ZipFile(zp) as z:
        z.extractall(out / "python")
    if not a.embed_zip:
        zp.unlink()
    app = out / "gearbase"
    app.mkdir()
    copy_core(app, a.include_private)
    bats(out)
    print("Complete:", out)


if __name__ == "__main__":
    sys.exit(main())
