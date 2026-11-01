"""自检命令（零依赖）：检查 Python 版本、零第三方依赖、核心冒烟、MCP 握手。

    python3 -I gearmath/tools/doctor.py            # 默认：快速自检（数秒到十几秒）
    python3 -I gearmath/tools/doctor.py --json     # 机器可读输出
    python3 -I gearmath/tools/doctor.py --full     # 另外运行全部测试（run_tests.py，约两分钟）

退出码：0 全部通过；1 有失败项。每项输出 PASS / WARN / FAIL 与原因（WARN 不影响退出码：可选能力 ccx 与 ccx_strict.py 缺失时只警告）。本命令只检查本包自身，不连接任何外部程序（不检查 Claude Desktop 是否已配置）。
也可用 python3 -m gearmath.tools.doctor（需在包根目录且不加 -I，或已把包根加入 PYTHONPATH）。
"""
from __future__ import annotations

import ast
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIN_PY = (3, 10)


def check_python():
    ok = sys.version_info >= MIN_PY
    return ok, f"Python {sys.version.split()[0]}（需要 >= {MIN_PY[0]}.{MIN_PY[1]}）"


def check_zero_deps():
    """扫描包内全部 .py 的 import：只允许标准库与包内模块（legacy/ 与 tests/ 的可选适配器不计入核心）。"""
    std = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
    bad = []
    for d in ("gearmath",):
        for p in (ROOT / d).rglob("*.py"):
            if "adapters" in p.parts:               # 可选适配器（SciPy/pymoo）只在函数内延迟导入
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for n in tree.body:                     # 只看模块顶层 import：延迟导入属可选路径
                names = []
                if isinstance(n, ast.Import):
                    names = [a.name.split(".")[0] for a in n.names]
                elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                    names = [n.module.split(".")[0]]
                bad += [f"{p.relative_to(ROOT).as_posix()}: {m}" for m in names if m not in std and m != "gearmath"]
    return not bad, "核心模块顶层只导入标准库" if not bad else "发现第三方顶层导入：" + "; ".join(sorted(set(bad))[:8])


def check_smoke():
    try:
        from gearmath.tools import ai_tools
        ai_tools.reset_state()
        r = ai_tools.call("gear_rate", {})
        ids = [c["id"] for c in r.get("checks", [])]
        ok = r.get("status") in ("pass", "fail") and "pitting.pinion" in ids and r.get("design_id")
        c = ai_tools.call("requirement_compile", {"requirement": {}})
        ok = ok and c["status"] == "needs_clarification" and c["questions"]
        return bool(ok), f"gear_rate 基线状态 {r.get('status')}，校核项 {len(ids)} 个；requirement_compile 空需求 → {c['status']}"
    except Exception as e:                           # noqa: BLE001 自检要报告任何失败
        return False, f"冒烟异常：{type(e).__name__}: {e}"


def check_manifest():
    try:
        from gearmath.tools import package_hashes as ph
        stale = ph.update_manifest(ROOT, write=False)
        cur = (ROOT / ph.CONTENTS).read_text(encoding="utf-8") if (ROOT / ph.CONTENTS).exists() else ""
        ok = not stale and cur == ph.contents_text(ROOT)
        return ok, "MANIFEST 与 PACKAGE-CONTENTS 一致" if ok else "清单哈希不一致：运行 python3 -I gearmath/tools/package_hashes.py"
    except Exception as e:                           # noqa: BLE001
        return False, f"清单检查异常：{type(e).__name__}: {e}"


def check_mcp_handshake():
    """起子进程跑 mcp_server.py，做 initialize / tools/list / resources/list / prompts/list / 一次 tools/call 往返。"""
    proc = subprocess.Popen([sys.executable, "-I", str(ROOT / "mcp_server.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
    n = [0]

    def rpc(method, params=None):
        n[0] += 1
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": n[0], "method": method, "params": params or {}}) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("服务器无响应：" + proc.stderr.read()[:300])
        return json.loads(line)
    try:
        init = rpc("initialize")["result"]
        caps = init["capabilities"]
        tools = rpc("tools/list")["result"]["tools"]
        res = rpc("resources/list")["result"]["resources"]
        prm = rpc("prompts/list")["result"]["prompts"]
        call = rpc("tools/call", {"name": "gear_list_inputs", "arguments": {}})["result"]
        ok = (init["protocolVersion"] and {"tools", "resources", "prompts"} <= set(caps) and len(tools) >= 12 and res and prm
              and call["structuredContent"]["result"])
        return bool(ok), f"握手成功：协议 {init['protocolVersion']}，工具 {len(tools)}、资源 {len(res)}、提示词 {len(prm)}，tools/call 往返正常"
    except Exception as e:                           # noqa: BLE001
        return False, f"MCP 握手失败：{type(e).__name__}: {e}"
    finally:
        try:
            proc.stdin.close()
            proc.wait(timeout=15)
        except Exception:                            # noqa: BLE001
            proc.kill()
        for f in (proc.stdout, proc.stderr):
            f.close()


def check_ccx():
    """ccx（CalculiX）是否可用及版本。不可用只报 WARN（返回 ok=True, level=WARN），不算失败；本检查不运行任何分析。"""
    exe = shutil.which("ccx")
    if not exe:
        return True, "WARN: PATH 中未找到 ccx（FEA 为可选能力，不影响核心）", "WARN"
    try:
        p = subprocess.run([exe, "-v"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    except subprocess.TimeoutExpired:
        return True, f"WARN: {exe} -v 超过 10 秒无响应", "WARN"
    except Exception as e:                           # noqa: BLE001
        return True, f"WARN: 无法运行 {exe} -v：{type(e).__name__}: {e}", "WARN"
    out = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
    ver = next((ln.strip() for ln in out if "ersion" in ln), out[0].strip() if out else "")
    if not ver:
        return True, f"WARN: {exe} 已找到，但 -v 无版本输出", "WARN"
    return True, f"ccx 可用：{exe}；{ver}", "PASS"


def check_ccx_strict():
    """严格读取器 data/m37_fea_pack/scripts/ccx_strict.py（F1 路新增）是否已合入。"""
    f = ROOT / "data" / "m37_fea_pack" / "scripts" / "ccx_strict.py"
    if f.is_file():
        return True, "ccx_strict.py 存在", "PASS"
    return True, "WARN: data/m37_fea_pack/scripts/ccx_strict.py 未合入", "WARN"


def check_full_tests():
    p = subprocess.run([sys.executable, "-I", str(ROOT / "run_tests.py")], capture_output=True, text=True, encoding="utf-8")
    tail = (p.stderr or p.stdout).strip().splitlines()[-3:]
    return p.returncode == 0, " | ".join(tail)


def run(full=False):
    checks = [("python_version", check_python), ("zero_dependencies", check_zero_deps), ("smoke", check_smoke),
              ("manifest", check_manifest), ("mcp_handshake", check_mcp_handshake)]
    if full:
        checks.append(("full_tests", check_full_tests))
    checks += [("ccx", check_ccx), ("ccx_strict", check_ccx_strict)]
    rows = []
    for name, fn in checks:
        res = fn()
        ok, msg = res[0], res[1]
        level = res[2] if len(res) > 2 else ("PASS" if ok else "FAIL")
        rows.append({"check": name, "ok": ok, "level": level, "detail": msg})
    return rows


def main(argv):
    rows = run(full="--full" in argv)
    if "--json" in argv:
        print(json.dumps({"ok": all(r["ok"] for r in rows), "checks": rows}, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f"[{r['level']}] {r['check']}: {r['detail']}")
        print("自检通过" if all(r["ok"] for r in rows) else "自检未通过")
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
