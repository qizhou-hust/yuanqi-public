"""调用 CalculiX 与读取其输出（.dat / .frd / .sta）。零依赖。

求解器路径来源（按优先级）：命令行 --ccx、环境变量 M37_CCX、PATH 中的 ccx / ccx.exe / ccx_static / ccx_2.23 等。
本脚本不下载、不安装任何东西。
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

CANDIDATES = ["ccx", "ccx.exe", "ccx_2.23", "ccx_2.22", "ccx_2.21", "ccx_static", "ccx_static.exe",
              "ccx_dynamic", "ccx_dynamic.exe", "ccx_MT", "ccx_MT.exe"]


def find_ccx(explicit=None):
    for c in [explicit, os.environ.get("M37_CCX")]:
        if c:
            p = Path(c).expanduser()
            if p.is_file():
                return p.resolve()
            w = shutil.which(c)
            if w:
                return Path(w).resolve()
            raise FileNotFoundError(f"找不到 CalculiX 可执行文件：{c}")
    for c in CANDIDATES:
        w = shutil.which(c)
        if w:
            return Path(w).resolve()
    raise FileNotFoundError("PATH 中没有 ccx；请用 --ccx 指定，或设置环境变量 M37_CCX")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def solver_env(threads):
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(threads)
    env["CCX_NPROC_EQUATION_SOLVER"] = str(threads)
    env["CCX_NPROC_RESULTS"] = str(threads)
    env["GFORTRAN_UNBUFFERED_ALL"] = "1"
    return env


def ccx_version(exe, threads=1):
    """返回 (原样输出, 解析出的版本号或 None)。ccx -v 在部分版本中返回码非 0，只看输出。"""
    try:
        r = subprocess.run([str(exe), "-v"], capture_output=True, text=True, timeout=30, env=solver_env(threads))
        out = (r.stdout or "") + (r.stderr or "")
    except Exception as ex:      # noqa: BLE001  —— 记录原因，不中断
        return f"ccx -v 调用失败: {ex}", None
    m = re.search(r"Version\s+(\d+\.\d+)", out)
    return out.strip(), (m.group(1) if m else None)


def run_job(exe, inp, threads=1, timeout_s=3600):
    """在 .inp 所在目录运行 ccx -i <job>；stdout 写 <job>.log。返回 dict（ok、耗时、错误摘要）。"""
    inp = Path(inp)
    t0 = time.perf_counter()
    try:
        r = subprocess.run([str(exe), "-i", inp.stem], cwd=inp.parent, env=solver_env(threads),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout_s,
                           errors="replace")
        out, code, timeout = r.stdout, r.returncode, False
    except subprocess.TimeoutExpired as ex:
        out = ex.stdout.decode(errors="replace") if isinstance(ex.stdout, bytes) else (ex.stdout or "")
        code, timeout = None, True
    wall = time.perf_counter() - t0
    (inp.parent / f"{inp.stem}.log").write_text(out + ("\n[M37] 超时，结果不采用\n" if timeout else ""), encoding="utf-8")
    errs = [ln.strip() for ln in out.splitlines() if "*ERROR" in ln.upper()]
    warns = [ln.strip() for ln in out.splitlines() if "*WARNING" in ln.upper()]
    finished = "Job finished" in out
    dat = inp.with_suffix(".dat")
    ok = (not timeout) and finished and not errs and dat.is_file()
    return {"ok": ok, "returncode": code, "timeout": timeout, "wall_s": round(wall, 3), "finished_marker": finished,
            "errors": errs[:20], "warnings_count": len(warns), "warnings_head": warns[:10],
            "log_tail": out[-3000:] if not ok else ""}


# ------------------------------------------------------------------ .dat
def _num(tok):
    return float(tok.replace("D", "E").replace("d", "e"))


def parse_dat(path):
    """把 .dat 切成块：[{header, rows}]。header 为小写原文；rows 为全数值行（每行 float 列表）。"""
    blocks, cur = [], None
    for line in Path(path).read_text(errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        toks = s.split()
        try:
            vals = [_num(t) for t in toks]
            if cur is not None:
                cur["rows"].append(vals)
            continue
        except ValueError:
            pass
        cur = {"header": s.lower(), "rows": []}
        blocks.append(cur)
    return blocks


def header_info(h):
    m = re.search(r"for set\s+(\S+)", h)
    t = re.search(r"time\s+([-+0-9.eEdD]+)", h)
    return (m.group(1).upper() if m else None), (_num(t.group(1)) if t else None)


def last_block(blocks, key, set_name=None):
    """最后一个（即最后时刻）header 含 key 且（可选）集合名匹配的块。"""
    found = None
    for b in blocks:
        if key in b["header"]:
            if set_name is None or header_info(b["header"])[0] == set_name.upper():
                found = b
    return found


def nodal(blocks, key, set_name):
    b = last_block(blocks, key, set_name)
    if b is None:
        return None
    return {int(r[0]): r[1:] for r in b["rows"] if len(r) >= 4}


def ip_table(blocks, key, set_name):
    """单元积分点表：{(elem, ip): values}。"""
    b = last_block(blocks, key, set_name)
    if b is None:
        return None
    return {(int(r[0]), int(r[1])): r[2:] for r in b["rows"] if len(r) >= 3}


def contact_tables(blocks):
    """接触输出（CCX 2.2x 面-面：按 从面单元+积分点 打印）。缺失时返回 None 字段。"""
    def rows(key):
        b = last_block(blocks, key)
        return b["rows"] if b else None
    stress = rows("contact stress")
    disp = rows("relative contact displacement")
    def stat(key, n):
        b = last_block(blocks, key)
        if not b or not b["rows"]:
            return None
        r = b["rows"][-1]
        return r if len(r) == n else r[-n:] if len(r) > n else None
    return {"stress_rows": stress, "disp_rows": disp,
            "force_moment": stat("total surface force", 6),
            "cog_normal": stat("center of gravity and mean normal", 6),
            "area_normal_shear": stat("area", 3)}


# ------------------------------------------------------------------ .frd（仅节点块，定宽格式）
def parse_frd(path, want=("CONTACT", "DISP")):
    """返回 {'nodes': {id:(x,y,z)}, blocks: {name: {'comps':[...], 'data':{id:[...]}}}}（同名块取最后一个）。"""
    nodes, blocks = {}, {}
    mode, name, comps, data = None, None, [], {}
    with open(path, errors="replace") as f:
        for line in f:
            key = line[:3].strip()
            if line.startswith("    2C"):
                mode = "nodes"; continue
            if line.startswith("  100C"):
                mode = "res"; name = None; comps = []; data = {}; continue
            if key == "-4" and mode == "res":
                name = line[5:13].strip().upper(); continue
            if key == "-5" and mode == "res":
                comps.append(line[5:13].strip().upper()); continue
            if key == "-1":
                try:
                    nid = int(line[3:13])
                    vals = []
                    rest = line[13:].rstrip("\n")
                    for k in range(0, len(rest), 12):
                        chunk = rest[k:k + 12].strip()
                        if chunk:
                            vals.append(float(chunk))
                except ValueError:
                    continue
                if mode == "nodes":
                    nodes[nid] = tuple(vals[:3])
                elif mode == "res" and name:
                    data[nid] = vals
                continue
            if key == "-3":
                if mode == "res" and name and (not want or name in want):
                    blocks[name] = {"comps": comps, "data": data}
                mode = None
    return {"nodes": nodes, "blocks": blocks}


def parse_sta(path):
    p = Path(path)
    if not p.is_file():
        return {"present": False}
    lines = [ln for ln in p.read_text(errors="replace").splitlines() if ln.strip()]
    inc = [ln for ln in lines if ln.split() and ln.split()[0].isdigit()]
    cut = sum(1 for ln in inc if "U" in ln.split()[-1:] or "cut" in ln.lower())
    return {"present": True, "increments": len(inc), "lines": len(lines), "tail": lines[-5:]}
