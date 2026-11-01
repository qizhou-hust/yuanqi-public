#!/usr/bin/env python3
"""把回传所需文件打成一个 zip：results.json、run.log、selfcheck.json，以及每个作业的
.dat / .sta / .cvg / .log / .meta.json / .record.json。默认不含 .frd 与 .inp（体积大，且 .inp 可由脚本重建）。

  python pack_results.py               # → results/M37-results-<日期>-<主机指纹>.zip
  python pack_results.py --with-frd    # 我们明确索要 .frd 时再用
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import zipfile
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")      # Windows 非 UTF-8 控制台下中文输出不致报错
    except Exception:  # noqa: BLE001
        pass
PACK = HERE.parent
KEEP = {".dat", ".sta", ".cvg", ".log"}
KEEP_SUFFIX = (".meta.json", ".record.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(PACK / "results"))
    ap.add_argument("--with-frd", action="store_true")
    ap.add_argument("--with-inp", action="store_true")
    a = ap.parse_args()
    res = Path(a.results)
    rj = res / "results.json"
    if not rj.is_file():
        raise SystemExit(f"没有 {rj}：请先运行 run_m37.py（非 --dry-run）")
    meta = json.loads(rj.read_text(encoding="utf-8"))
    tag = f"{dt.date.today():%Y%m%d}-{meta.get('machine', {}).get('hostname_sha8', 'host')}"
    out = res / f"M37-results-{tag}.zip"
    keep = set(KEEP) | ({".frd"} if a.with_frd else set()) | ({".inp"} if a.with_inp else set())
    n, size = 0, 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("results.json", "run.log", "selfcheck.json"):
            if (res / f).is_file():
                z.write(res / f, f); n += 1
        for f in sorted((res / "runs").rglob("*")):
            if f.is_file() and (f.suffix in keep or f.name.endswith(KEEP_SUFFIX)):
                z.write(f, str(f.relative_to(res))); n += 1; size += f.stat().st_size
    print(f"写出 {out}（{n} 个文件，未压缩 {size / 1e6:.1f} MB）。请把这个 zip 发回。")


if __name__ == "__main__":
    main()
