"""M32–M40 进度表：读取仓库实际状态，按验收门条目完成数输出（JSON + Markdown）。口径见 docs/里程碑口径.md。

  python3 -I gearmath/tools/milestones.py            Markdown
  python3 -I gearmath/tools/milestones.py --json     JSON
  （--no-test-count 跳过测试发现计数；--no-probe 跳过需运行统一核算的探针）

每个里程碑的验收门（docs/顶层设计.html 第 15 节）拆成条目；条目状态 done / partial / open：
  - probe：由本脚本从仓库实际状态自动判定（可编译、文件计数、统一核算子检查是否全部非阻断等）；
  - manual：人工判定，必须写依据（docs 中的文件与位置）；本脚本不自行提升人工条目。
完成度 = done 条目数 / 条目总数（partial 不计入，单列）。本表不是工程验收，也不改写接力交接中的估计（并列显示）。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
HANDOFF = ROOT / "docs" / "接力交接-2026-10-30.md"
HO = "docs/接力交接-2026-10-30.md"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ------------------------------------------------------------------ 仓库状态
def test_count():
    """unittest 发现的用例数（未运行；skip 在运行时才确定）。"""
    import unittest
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    return suite.countTestCases()


def compiles():
    import py_compile
    bad = []
    for p in sorted((ROOT / "gearmath").rglob("*.py")):
        try:
            py_compile.compile(str(p), cfile=None, doraise=True, optimize=-1)
        except py_compile.PyCompileError as e:
            bad.append(f"{p.relative_to(ROOT)}: {e.msg}")
    return bad


def formula_modules():
    """各模块公式数与证据等级分布（只读已有元数据）。"""
    from gearmath.product import evidence as EV
    from gearmath.gear import micropitting, scuffing_flash, scuffing_integral
    from gearmath.gear.formulas import CYLINDRICAL_PAIR
    from gearmath.kernel.registry import evidence_levels, load_registry
    from gearmath.system import din6892, din6892_b, din7190, din743, iso281, shaft_beam, shaft_line, thermal_14179
    out = {}
    try:
        lv = evidence_levels(load_registry(ROOT / "data" / "registry" / "formulas-v1.json"))
    except (OSError, ValueError):
        lv = {}
    dist = {}
    for f in CYLINDRICAL_PAIR:
        k = EV.norm_level(lv.get(f.id))
        dist[k] = dist.get(k, 0) + 1
    out["gear.formulas（CYLINDRICAL_PAIR，等级取 data/registry）"] = {"count": len(CYLINDRICAL_PAIR), "levels": dict(sorted(dist.items()))}
    for name, mod in (("gear.scuffing_integral", scuffing_integral), ("gear.scuffing_flash", scuffing_flash),
                      ("gear.micropitting", micropitting), ("system.thermal_14179", thermal_14179),
                      ("system.din743", din743), ("system.din6892", din6892), ("system.din6892_b", din6892_b),
                      ("system.din7190", din7190), ("system.iso281", iso281), ("system.shaft_line", shaft_line),
                      ("system.shaft_beam", shaft_beam)):
        out[name] = {"count": len(mod.FORMULAS), "levels": EV.module_distribution(mod.FORMULAS)}
    return out


def external_files():
    out = {}
    for d in ("kisssoft", "kisssoft_v014", "kisssoft_v015"):
        p = ROOT / "data" / d
        out[f"data/{d}"] = len(list(p.glob("*.json"))) if p.is_dir() else 0
    return out


def pending_user_decisions():
    """接力交接最新一条"需要用户"行中带圈序号的条目数；另计各系统层输入 user_decisions_pending 条目数。"""
    txt = HANDOFF.read_text(encoding="utf-8") if HANDOFF.exists() else ""
    line = next((ln for ln in txt.splitlines() if "需要用户" in ln), "")
    circled = re.findall(r"[①②③④⑤⑥⑦⑧⑨⑩]", line)
    sysdec = {}
    for p in sorted((ROOT / "data" / "system").glob("*.system-input.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        sysdec[d["id"]] = len(d.get("user_decisions_pending") or [])
    return {"handoff_latest_entries": len(circled), "handoff_line": line.strip()[:200], "system_input": sysdec}


def handoff_estimates():
    """接力交接 v0.15 表中各里程碑的估计（并列显示，不参与本表计算）。"""
    txt = HANDOFF.read_text(encoding="utf-8") if HANDOFF.exists() else ""
    out = {}
    for ln in txt.splitlines():
        m = re.match(r"^>\s*\|\s*(M3\d)[^|]*\|\s*([^|]*)\|\s*([^|]*)\|", ln)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(3).strip()
    return out


def bench_pending():
    p = ROOT / "data" / "bench" / "v1" / "requirements.json"
    return p.read_text(encoding="utf-8").count("pending_engineer_label") if p.exists() else None


def _design_check_ok(design, scopes):
    from gearmath.product import design_check as DC
    r = DC.check_files(design, design, scopes)
    st = {s: r["checks"][s]["status"] for s in scopes}
    return all(v in ("pass", "fail") for v in st.values()), st


# ------------------------------------------------------------------ 验收门条目
def gates(state, probe=True):
    def P(ok, basis, partial=False):
        return {"kind": "probe", "status": "done" if ok else ("partial" if partial else "open"), "basis": basis}

    def M(status, basis):
        return {"kind": "manual", "status": status, "basis": basis}

    ext = state["external_files"]
    # Reviewable evidence receipts, not file counts or pending-gold labels.
    def receipt(path):
        try:return json.loads((ROOT/path).read_text(encoding='utf-8'))
        except (OSError,ValueError):return {}
    m33=receipt('output/m33/closure.json')
    m34=receipt('output/m34/closure/closure.json')
    m38=receipt('output/m38/closure.json')
    m39=receipt('output/m39/closure.json')
    g = {}
    g["M32"] = [
        ("原型 21 项测试全绿", M("done", "docs/M32-验收报告.md：双系统真实 CI 原型 21 项通过")),
        ("M31 旧测试经适配器回归", M("done", "docs/M32-验收报告.md：原 73 模块 678 项全过、零跳过；原 81 文件哈希与真实导入来源已验证")),
        ("守门在 CI 生效", M("done", "docs/M32-验收报告.md：托管 CI 守门及真实破坏性反例通过，附源码提交与运行链接")),
        ("全库可编译", P(not state["compile_errors"], f"py_compile gearmath/**/*.py：{len(state['compile_errors'])} 个错误")),
        ("通过量纲校核", M("done", "docs/M32-验收报告.md：双系统输入/内核/注册表与全量测试门通过")),
    ]
    g["M33"] = [
        ("22 个证据系数中 ≥20 个改为公式", M("done" if m33.get('prototype22',{}).get('passed') else "partial", "docs/M33-closure-current.md；output/m33/closure.json 逐项映射20/22，KA为输入、YST为标准常数")),
        ("ISO/TR 6336-30 全部示例逐系数复现（E4）", M("partial", "docs/M33-验收报告.md：例1–4 数值验收、例5–8 全链；例7 HB→HV 待用户")),
        ("主链误差 ≤1%", M("partial", f"{HO}：几何门 2/6 明细待用户")),
        ("C001 新链重算并逐项解释与 M31 差异", M("done" if m33.get('c001',{}).get('iteration_reproduction_passed') else "partial", "docs/M33-closure-current.md；18项旧链收据对照，九次迭代重建与当前收敛结果差异已解释")),
    ]
    g["M34"] = [
        ("一个设计只有一个可编辑文档", M("done" if m34.get('passed') else "partial", "docs/M34-closure.md；真源所有权/CAS/元数据token及导入、优化真源读取回归")),
        ("梯度与中心差分一致到 1e-6", M("done" if m34.get('passed') else "partial", "output/m34/closure/closure.json：120个AD/FD比较，最差1.22e-8")),
        ("H2 旗舰结果一致且评估次数下降", M("done" if m34.get('h2',{}).get('same_candidates') and m34.get('passed') else "partial", "docs/M34-closure.md；原始Stage0同域同排序，378216→9948次，不另加未规定强度门")),
        ("Claude Desktop / Code 实连可用", M("partial", "真实Claude Code已连接MCP发现工具，模型HTTP403额度不足，尚无真实tools/call，不能关闭")),
    ]
    ks_cases = sorted(p.name for p in (ROOT / "data" / "kisssoft").glob("K[0-9][0-9]-*.json")
                      if re.fullmatch(r"K\d\d-[A-Za-z][A-Za-z0-9-]*\.json", p.name) and "known-divergences" not in p.name
                      and not re.match(r"K\d\d-K\d\d", p.name))
    n_ks = len(ks_cases)
    g["M35"] = [
        ("独立对标 ≥5 例（E5），误差 ≤1% 且可解释", P(n_ks >= 5, f"data/kisssoft 案例文件 {n_ks} 个（{', '.join(ks_cases)}）；误差 ≤1% 与可解释性见 docs/M33-对拍契约.md（人工）",
                                              partial=n_ks > 0)),
        ("经外部工艺人员审阅的变位斜齿制造图", M("open", f"{HO} 第2节 M35 缺口：外部工艺审阅")),
    ]
    if probe:
        ok36, st36 = _design_check_ok("C001", ["gear_rating", "shaft", "bearing", "key"])
        ok39, st39 = _design_check_ok("K01-spur", ["gear_rating", "scuffing", "micropitting"])
        b36 = f"design_check(C001) 子检查状态 {st36}"
        b39 = f"design_check(K01-spur，代高速例) 子检查状态 {st39}"
    else:
        ok36 = ok39 = False
        b36 = b39 = "未运行探针（--no-probe）"
    g["M36"] = [
        ("C001 全系统（齿轮、轴、轴承、键）由同一张图校核", P(ok36, b36, partial=True)),
        ("系统优化结果与小规模全枚举一致", M("open", "系统层优化未开工")),
        ("三个旗舰与编辑用例回归一致", M("open", "系统层旗舰回归未建立")),
    ]
    g["M37"] = [
        ("斜齿副峰值落在 Hertz 估算 ±15%", M("open", f"{HO}：L2/L3 未完成（L1 仅二维 Hertz penalty 冒烟）")),
        ("YFS FE/ISO ∈ [0.90, 1.10]", M("open", "模块 B 原包缺失")),
        ("σH0 ∈ [0.92, 1.08]", M("open", "L3 *CONTACT FILE 待用户")),
        ("优化器内环 → 最终 FE 复核闭环，代理误差 <3%", M("open", "未开工")),
    ]
    bp = state["bench_pending"]
    g["M38"] = [
        ("凭空数字率为 0（原40题数字追溯口径）", M("done" if m38.get('gates',{}).get('number_traceability') else "partial", "docs/M38-bench-closure.md；规则与两实际模型重评，未标注题只评数字追溯，不冒称语义准确率")),
        ("三个旗舰需求端到端跑通", M("done" if m38.get('gates',{}).get('original_flagships') else "partial", "docs/M38-closure.md；原H2/W2W/P2显式需求→真实MCP编译→求解→复查；保留Stage0范围及W2W热失败")),
        ("新机 10 分钟内接通", M("done" if m38.get('gates',{}).get('fresh_windows') else "partial", "docs/M38-closure.md；私有GitHub托管全新Windows VM、嵌入Python、实际MCP工具调用，详见receipt")),
        ("首轮多模型评测报告", M("done" if m38.get('gates',{}).get('first_multi_model_report') else "partial", "docs/M38-bench-closure.md；真实terra/sol输出与原始收据、完整限制，无人工金标")),
    ]
    g["M39"] = [
        ("高速齿轮可完成全失效模式校核", P(ok39, b39, partial=True)),
        ("体积—中心距—安全系数三目标前沿", M("done" if m39.get('frontier_passed') else "partial", "docs/M39-source-frontier-closure.md；同源12点有限域前沿，非全局最优")),
        ("公差下可行率报告", M("done" if m39.get('tolerance_report_passed') else "partial", "docs/M39-source-frontier-closure.md；每点3个显式公差情景，明确分母与blocked，不作概率外推")),
    ]
    fam = [p.name for p in (ROOT / "gearmath" / "gear").glob("*.py") if re.search(r"planet|worm|bevel", p.name)]
    g["M40"] = [
        ("行星至少 1 题完整校核 + 1 例独立对标", P(any("planet" in x for x in fam), f"gearmath/gear 族模块：{fam or '无'}")),
        ("蜗杆至少 1 题完整校核 + 1 例独立对标", P(any("worm" in x for x in fam), f"gearmath/gear 族模块：{fam or '无'}")),
        ("锥齿轮单独立项评估", M("open", "未立项")),
    ]
    return g


def collect(count_tests=True, probe=True):
    state = {"test_cases_discovered": test_count() if count_tests else None, "compile_errors": compiles(),
             "formula_modules": formula_modules(), "external_files": external_files(),
             "pending_user_decisions": pending_user_decisions(), "bench_pending": bench_pending(),
             "handoff_estimates": handoff_estimates()}
    rows = []
    for ms, items in gates(state, probe).items():
        n = len(items)
        done = sum(1 for _, it in items if it["status"] == "done")
        part = sum(1 for _, it in items if it["status"] == "partial")
        rows.append({"milestone": ms, "gate_items": n, "done": done, "partial": part, "open": n - done - part,
                     "progress": done / n, "handoff_estimate": state["handoff_estimates"].get(ms),
                     "items": [{"text": t, **it} for t, it in items]})
    return {"schema": "gearbase.milestones/1", "basis": "docs/里程碑口径.md（验收门条目完成数；partial 不计入）",
            "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(), "state": state, "milestones": rows}


def render_markdown(d):
    s = d["state"]
    L = [f"# M32–M40 进度表（gearbase {d['version']}）", "", f"口径：{d['basis']}。不是工程验收。", "",
         "| 里程碑 | 验收门条目 | done | partial | open | 完成度（done/总） | 接力交接估计 |", "|---|---|---|---|---|---|---|"]
    for r in d["milestones"]:
        L.append(f"| {r['milestone']} | {r['gate_items']} | {r['done']} | {r['partial']} | {r['open']} | "
                 f"{r['progress'] * 100:.0f}% | {r['handoff_estimate'] or '—'} |")
    L += ["", "## 仓库状态", "",
          f"- 测试用例（发现数，未运行）：{s['test_cases_discovered'] if s['test_cases_discovered'] is not None else '未计数'}",
          f"- 编译错误：{len(s['compile_errors'])}",
          f"- 外部对拍文件：{'、'.join(f'{k} {v}' for k, v in s['external_files'].items())}",
          f"- 未决用户决定：接力交接最新'需要用户' {s['pending_user_decisions']['handoff_latest_entries']} 条；"
          f"系统层输入 {s['pending_user_decisions']['system_input']}",
          f"- bench 金标待标注：{s['bench_pending']}", "", "| 模块 | 公式数 | 证据等级分布 |", "|---|---|---|"]
    for k, v in s["formula_modules"].items():
        L.append(f"| {k} | {v['count']} | {'、'.join(f'{a}: {b}' for a, b in v['levels'].items())} |")
    L += ["", "## 条目明细", ""]
    for r in d["milestones"]:
        L.append(f"### {r['milestone']}")
        L += [f"- [{it['status']}] {it['text']}（{it['kind']}：{it['basis']}）" for it in r["items"]]
        L.append("")
    return "\n".join(L)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    d = collect(count_tests="--no-test-count" not in argv, probe="--no-probe" not in argv)
    sys.stdout.write(json.dumps(d, ensure_ascii=False, indent=1) if "--json" in argv else render_markdown(d))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
