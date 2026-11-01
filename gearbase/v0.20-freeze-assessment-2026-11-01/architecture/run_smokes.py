"""Capture the four audit recipes without writing inside the frozen package."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = Path(r"D:\my_Works\Gears\gearbase-v020-work")
OUT = HERE / "evidence"
OUT.mkdir(exist_ok=True)


def status():
    return subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, check=True).stdout


before = status()
rows = []
for case in ("mcp", "requirements", "flagships", "system"):
    cmd = [sys.executable, "-X", "utf8", "-B", str(HERE / "smoke_readonly.py"), case]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    env.pop("GEARBASE_STATE_DIR", None)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tic = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=180)
        stdout, stderr, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = str(exc.stdout or ""), str(exc.stderr or ""), "timeout_180s"
    (OUT / f"{case}.stdout.json").write_text(stdout, encoding="utf-8")
    (OUT / f"{case}.stderr.txt").write_text(stderr, encoding="utf-8")
    row = {"case": case, "command": cmd, "cwd": str(ROOT), "started_utc": started,
           "elapsed_s": time.monotonic() - tic, "returncode": code,
           "stdout": str(OUT / f"{case}.stdout.json"), "stderr": str(OUT / f"{case}.stderr.txt"),
           "stdout_text_utf8_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
           "stdout_sha256": hashlib.sha256((OUT / f"{case}.stdout.json").read_bytes()).hexdigest()}
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
after = status()
report = {"git_status_before": before, "git_status_after": after, "git_status_unchanged": before == after,
          "smokes": rows, "all_exit_zero": all(r["returncode"] == 0 for r in rows)}
(OUT / "commands.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
raise SystemExit(0 if report["all_exit_zero"] and report["git_status_unchanged"] else 1)
