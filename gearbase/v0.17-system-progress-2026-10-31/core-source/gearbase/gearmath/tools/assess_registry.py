"""规则评定：生成 data/registry/assessments-v1.json（证据等级 + 来源核对状态 + 依据，零依赖、可复现）。

用法（在包根目录）：
    python3 -I gearmath/tools/assess_registry.py           # 重写 data/registry/assessments-v1.json
    python3 -I gearmath/tools/assess_registry.py --check   # 只核对

规则（不手填、不推断；拿不准一律 null 并写明原因，见 docs/注册表-schema-v1.md「评定规则」）：
  evidence_level：公式出现在某条"通过"的对拍行的求值链上，才取该对拍对应的等级（C001 收据 E2、TR30 配套算例 E4、
                  KISSsoft 同输入 E5）；多个对拍取最高；没有任何通过的对拍用到它则为 null。
  source_check：只有公式文本（clause/note）明确写了"原图已核/核图/…"才给 pdf_image_checked；写明"原文不在证据包"
                给 not_in_evidence；ocr_only / from_memory 无文本依据，不给；其余 null。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gearmath.kernel import evidence as EV                 # noqa: E402
from gearmath.kernel.registry import ASSESSMENT_SCHEMA     # noqa: E402
from gearmath.tools import benchmarks as BM                # noqa: E402
from gearmath.tools import export_registry as X            # noqa: E402

OUT = ROOT / "data" / "registry" / "assessments-v1.json"
# 明确的"核对过原图"措辞；不含孤立的"核实"（可能是"未核实"或核实别的内容）
_IMAGE_OK = re.compile(r"核图|图核|原图已核|原图核实|原图[^；。，,]{0,3}已核|已并核[^；。]{0,60}原图")
_NEG = re.compile(r"(未|没有|不曾|尚未)(并)?(核图|图核|核)[^；。，,]{0,2}$")
_NOT_IN_EVIDENCE = re.compile(r"不在证据包|source_not_in_evidence_pack|not_in_evidence")
RULES = {
    "evidence_level": "公式出现在某条通过的对拍行的求值链上才取对应对拍的等级：C001 收据 E2（独立实现交叉）、"
                      "ISO/TR 6336-30 配套算例 E4（逐行通过）、KISSsoft 同输入逐行一致 E5；多个对拍取最高；"
                      "无任何通过的对拍用到则为 null。E0/E1/E3/E6 无自动依据，不给。",
    "support": "direct = 该行比较量就是这条公式的输出；chain = 仅作为该行求值链的上游被用到。两者都给对应等级。",
    "scope": "与库公式逐字相同（Formula 相等）的计入库级；案例适配器改写或新增的公式计入案例级（case_id），"
             "不把改写版的证据记到库公式上。",
    "source_check": "仅当公式文本（clause/note）明确写了核图措辞才给 pdf_image_checked；写明原文不在证据包给 not_in_evidence；"
                    "ocr_only / from_memory 无文本依据，不给；其余 null。",
    "caveat": "公式级 E4 不等于整例/M33 验收（docs/M33-验收记录.md：例1–4 的 e4_gate 仍为 false，例5–8 0 例验收）；"
              "有效等级还受输入来源上限约束（assumption=E0、evidence=E2）。",
}


def source_check_of(text):
    """(状态 | None, 依据片段 | None)。"""
    for m in _IMAGE_OK.finditer(text):
        if not _NEG.search(text[max(0, m.start() - 6):m.end()]):
            a, b = max(0, m.start() - 12), min(len(text), m.end() + 12)
            return "pdf_image_checked", text[a:b].replace("\n", " ")
    m = _NOT_IN_EVIDENCE.search(text)
    if m:
        return "not_in_evidence", text[max(0, m.start() - 12):m.end() + 12].replace("\n", " ")
    return None, None


def _uniq(xs):
    return list(dict.fromkeys(xs))


def assess(f, target, benchmarks, *, case_id=None):
    level = BM.level_of(target, benchmarks) if target else None
    sc, sc_basis = source_check_of(f"{f.ref} {f.note}")
    by = {b["id"]: b for b in benchmarks}
    supports = []
    for bid, s in (target["supports"] if target else {}).items():
        supports.append({"benchmark": bid, "level": by[bid]["level"], "n_direct": len(s["direct"]), "n_chain": len(s["chain"]),
                         "direct_rows": s["direct"][:5]})
    supports.sort(key=lambda s: (-EV.rank(s["level"]), s["benchmark"]))
    basis = None
    if supports:
        parts = []
        for lv in sorted({s["level"] for s in supports}, key=lambda x: -EV.rank(x)):
            ss = [s for s in supports if s["level"] == lv]
            parts.append(f"{lv}：" + "、".join(s["benchmark"] for s in ss) + f"（直接 {sum(s['n_direct'] for s in ss)} 行 / "
                         f"求值链 {sum(s['n_chain'] for s in ss)} 行次）")
        basis = "；".join(parts) + "。取最高等级；等级来自对拍行通过，不代表整例验收。"
    a = {"id": f.id, "evidence_level": level, "source_check": sc, "basis": basis, "supports": supports,
         "evidence_level_null_reason": None if level else "无通过的对拍行用到该公式",
         "source_check_basis": sc_basis,
         "source_check_null_reason": None if sc else "公式文本未标明核图/来源状态"}
    if case_id is not None:
        a = {"case_id": case_id, **a}
    return a


def build():
    ex = BM.extract()
    benchmarks = ex["benchmarks"]
    pairs, _ = X.collect()
    formulas = [assess(f, ex["library"].get(f.id), benchmarks) for f, _ in pairs]
    case_rows = []
    for cid in sorted(ex["cases"]):
        for fid, t in sorted(ex["cases"][cid]["targets"].items()):
            case_rows.append(assess(t["formula"], t, benchmarks, case_id=cid))

    def cov(rows):
        lv = {}
        for r in rows:
            lv[r["evidence_level"] or "null"] = lv.get(r["evidence_level"] or "null", 0) + 1
        sc = {}
        for r in rows:
            sc[r["source_check"] or "null"] = sc.get(r["source_check"] or "null", 0) + 1
        return {"count": len(rows), "evidence_level": dict(sorted(lv.items())), "source_check": dict(sorted(sc.items()))}

    return {"schema": ASSESSMENT_SCHEMA, "generated_by": "gearmath/tools/assess_registry.py", "rules": RULES,
            "benchmarks": [{k: b[k] for k in ("id", "kind_text", "level", "description", "rows_passed")} for b in benchmarks],
            "coverage": {"library": cov(formulas), "case_formulas": cov(case_rows)},
            "formulas": formulas, "case_formulas": case_rows}


def render(doc=None):
    return json.dumps(doc or build(), ensure_ascii=False, indent=1) + "\n"


def main(argv):
    text = render()
    if "--check" in argv:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        print("一致" if cur == text else "不一致：请运行 python3 -I gearmath/tools/assess_registry.py")
        return 0 if cur == text else 2
    OUT.write_text(text, encoding="utf-8")
    print(f"已写入 {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
