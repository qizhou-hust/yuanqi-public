"""gear-agent-bench v1：自动评测器 + 规则基线（零依赖、确定性、不用 LLM）。

用法（包根目录）：
    python3 -I gearmath/tools/bench.py                 # 跑规则基线，打印报告 JSON
    python3 -I gearmath/tools/bench.py --write         # 同时写 data/bench/v1/baseline-rules-result.json
    python3 -I gearmath/tools/bench.py --check         # 重跑并与已写结果比对（不一致退出 2）

评测对象 system 是一个函数 text_zh -> 输出字典，输出约定：
    {"parsed_requirement": {…requirement_compile 的字段…}, "compile_result": {…requirement_compile 的结果…}, "reply_text": "…"}
规则基线 rule_baseline 是确定性正则抽取 + requirement_compile；LLM 系统按同一约定接入即可对比。

指标：
  hallucinated_number_rate  输出里出现、但无法追溯的数字占比（必须为 0）。可追溯 = 出现在输入原文；或是登记推导式（intent.DERIVATIONS）
                            的重算结果且操作数均可追溯；或是工具公开常量（问题模板的参数范围）。扫描范围：compile_result 的全部数值叶子
                            （不含 sha256/unit 等标识字段）、reply_text、questions[].question、errors[].message；静态说明性字段
                            （expr、why、reason、applicability、note 等工具固定文案）不扫字符串，但其数值叶子照扫。标准号（ISO 6336-2）与
                            证据等级（E0）先剔除再提取。
  compile_accuracy          仅对金标 status == "labeled" 的条目；无标注条目则为 null（不是 0）。
  clarification_recall/precision  同上，对 expected_questions。
  clarification_selfcheck   不依赖金标：对系统自己解析出的需求，intent.required_fields 判定应追问的字段中，输出 questions 实际覆盖的比例。
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gearmath.tools import intent as IT  # noqa: E402
from gearmath.tools import nlp_templates as NT  # noqa: E402

BENCH = ROOT / "data" / "bench" / "v1" / "requirements.json"
RESULT = ROOT / "data" / "bench" / "v1" / "baseline-rules-result.json"

# ---------------------------------------------------------------- 规则基线（确定性正则抽取）
_NUM = r"(\d+(?:\.\d+)?)"
_HEDGE = ("大概", "大约", "约", "左右", "上下", "差不多", "近似", "多转", "几")


def _norm(t):
    t = t.translate(str.maketrans("０１２３４５６７８９．％：（），；", "0123456789.%:(),;"))
    return t


def _hedged(t, m):
    around = t[max(0, m.start() - 3):m.start()] + t[m.end():m.end() + 3]
    return any(h in around for h in _HEDGE)


def _find(t, pat, group=1):
    for m in re.finditer(pat, t):
        if not _hedged(t, m):
            return float(m.group(group))
    return None


DERIVED = []      # 本次解析中经登记推导式换算的量（rule_baseline 取走并随输出声明）


def parse_requirement(text):
    """正则抽取：只提取原文里明确写出的"数字+单位"；含"大概/约/左右"等含糊词、中文数字、年/马力等单位一律不抽取（留给追问）。"""
    t = _norm(text)
    r = {}
    v = _find(t, _NUM + r"\s*(?:kW|KW|kw|千瓦)")
    if v is not None:
        r["power_kW"] = v
    else:
        v = _find(t, _NUM + r"\s*(?:W|瓦)(?![A-Za-z])")
        if v is not None:
            r["power_kW"] = IT.DERIVATIONS["w_to_kw"]["fn"](v)
            DERIVED.append(IT._derive("w_to_kw", "power_kW", power_W=v))
    v = _find(t, _NUM + r"\s*(?:N\s*[·.*]?\s*m|牛米|牛·米|牛顿米)(?![a-zA-Z])")
    if v is not None:
        r["torque_Nm"] = v
    v = _find(t, _NUM + r"\s*(?:rpm|r/min|转/分钟?|转每分)")
    if v is not None:
        r["speed_rpm"] = v
    v = _find(t, r"(?:传动比|减速比|速比)\s*(?:为|是|=|:|要求|取)?\s*" + _NUM + r"(?!\s*%)")
    if v is None:
        v = _find(t, r"\bi\s*=\s*" + _NUM)
    if v is not None:
        r["ratio"] = v
    v = _find(t, r"(?:传动比|减速比|速比)?(?:允许)?(?:相对)?(?:误差|偏差)\D{0,8}?" + _NUM + r"\s*%")
    if v is not None:
        r["ratio_tol_percent"] = v
    v = _find(t, r"(?:齿宽系数|b/d1|齿宽直径比)\D{0,8}?" + _NUM)
    if v is not None:
        r["max_b_over_d1"] = v
    v = _find(t, r"接触安全系数\D{0,6}?" + _NUM)
    if v is not None:
        r["min_S_H"] = v
    v = _find(t, r"弯曲安全系数\D{0,6}?" + _NUM)
    if v is not None:
        r["min_S_F"] = v
    v = _find(t, r"寿命\D{0,6}?" + _NUM + r"\s*(?:小时|h|hr)")
    if v is not None:
        r["life_h"] = v
    v = _find(t, r"中心距\D{0,8}?" + _NUM + r"\s*mm")
    if v is not None:
        r["max_center_distance_mm"] = v
    v = _find(t, r"齿宽(?!系数)\D{0,6}?" + _NUM + r"\s*mm")
    if v is not None:
        r["max_face_width_mm"] = v
    mats = re.findall(r"(20CrMnTi|17CrNiMo6|42CrMo|40Cr|45号?钢|渗碳淬火|调质|氮化)", t)
    if mats:
        r["material"] = "".join(dict.fromkeys(mats))
    if re.search(r"二级|两级|2级|三级|3级|多级", t):
        r["stages"] = 2
    elif re.search(r"一级|单级|1级", t):
        r["stages"] = 1
    if "斜齿" in t or "螺旋" in t:
        r["gear_type"] = "helical"
    elif "蜗杆" in t:
        r["gear_type"] = "worm"
    elif "行星" in t:
        r["gear_type"] = "planetary"
    elif "锥齿" in t:
        r["gear_type"] = "bevel"
    elif "直齿" in t:
        r["gear_type"] = "spur"
    return r


def _fmt(v):
    return repr(v) if isinstance(v, float) and not float(v).is_integer() else str(int(v)) if float(v).is_integer() else repr(v)


def rule_baseline(text):
    del DERIVED[:]
    req = parse_requirement(text)
    parser_der = list(DERIVED)
    res = IT.requirement_compile({"requirement": req})
    st = res["status"]
    if st == "needs_clarification":
        reply = "还需要向您确认：" + "；".join(q["question"] for q in res["questions"])
    elif st == "pass_pending_human_confirmation":
        tp = res["template_call"]["arguments"]["template_params"]
        reply = ("已编译（数值均为待人工确认）：目标传动比 " + _fmt(tp["target_ratio"]) + "，传动比允许偏差 " + _fmt(tp["ratio_tol"])
                 + "，齿宽系数上限 " + _fmt(tp["max_b_over_d1"]) + "。")
    elif st == "blocked_unsupported_scope":
        reply = "超出当前模板范围：" + "；".join(e["message"] for e in res["errors"])
    else:
        reply = "输入不合格：" + "；".join(e["message"] for e in res["errors"])
    return {"parsed_requirement": req, "parser_derivations": parser_der, "compile_result": res, "reply_text": reply}


# ---------------------------------------------------------------- 数字提取与可追溯性
_STD = re.compile(r"ISO(?:/(?:TR|TS))?\s*\d+(?:-\d+)?(?:/\d+)?(?::\d{4})?|DIN\s*\d+(?:-\d+)?(?::\d{4})?|E[0-6]\b|[A-Za-z_]+(?:_\d+)+|\b[A-Za-z]+\d+[A-Za-z]*\b|20CrMnTi|17CrNiMo6|42CrMo|2π/60")
_TOK = re.compile(r"(?<![A-Za-z0-9_.])[+-]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_SKIP_STR_KEYS = {"expr", "why", "reason", "applicability", "note", "how", "scope_assumptions", "formula_id", "unit", "claim",
                  "tool", "name", "code", "field", "quantity", "constraint", "check_quantity", "sense", "status", "message_static"}
_SKIP_KEYS = {"sha256", "problem_ir_sha256"}
_CN = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_DEC = re.compile(r"\.(\d+)")
_CN_DIGITS = dict(zip('零〇一二两三四五六七八九', (0,0,1,2,2,3,4,5,6,7,8,9)))
_LEXNUM = re.compile(r'(?<![A-Za-z0-9_.])[+\-负負]?(?:\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?[零〇一二两三四五六七八九十百千万亿负負]*|\.\d+(?:[eE][+-]?\d+)?[万亿]*|[零〇一二两三四五六七八九十百千万亿]+(?:点[零〇一二两三四五六七八九]+)?[\d负負]*)')
_NONFINITE = re.compile(r'(?<![A-Za-z])(?:NaN|[+-]?Infinity|[+-]?inf)(?![A-Za-z])',re.I)


def _chinese_cardinal(token):
    """A bounded cardinal grammar; malformed forms are not silently ignored."""
    sign=-1 if token.startswith(('负','負','-')) else 1
    token=token.lstrip('负負+-')
    whole,sep,fraction=token.partition('点')
    if not any(c in '十百千万亿' for c in whole):
        if len(whole)>1 and not any(c in '零〇' for c in whole):raise ValueError('ambiguous digit sequence')
        number=int(''.join(str(_CN_DIGITS[c]) for c in whole))
    else:
        total=section=n=0; last_small=10000; seen_big=set(); pending=False
        for c in whole:
            if c in _CN_DIGITS:
                if pending and n:raise ValueError('ambiguous adjacent digits')
                n=_CN_DIGITS[c];pending=True
            elif c in '十百千':
                unit={'十':10,'百':100,'千':1000}[c]
                if unit>=last_small:raise ValueError('unordered cardinal units')
                section+=(n if pending else 1)*unit;n=0;pending=False;last_small=unit
            else:
                unit={'万':10000,'亿':100000000}[c]
                if unit in seen_big:raise ValueError('repeated cardinal section')
                seen_big.add(unit);section+=n
                if unit==100000000:total=(total+section if total or section or pending else 1)*unit
                else:total+=(section if section or pending else 1)*unit
                section=n=0;pending=False;last_small=10000
        number=total+section+n
    tail=float('0.'+''.join(str(_CN_DIGITS[c]) for c in fraction)) if sep else 0.
    return sign*(number+tail)


def text_number_sources(text):
    """Numeric lexical evidence with original spans; no semantic defaults."""
    s=text.translate(str.maketrans('０１２３４５６７８９．−','0123456789.-'))
    s=_STD.sub(lambda m:' '*len(m.group()),s)
    # 千 in the unit 千瓦/千米/千赫 is a unit prefix, not another digit.
    s=re.sub(r'千(?=瓦|米|赫)', ' ', s)
    s=re.sub(r'百(?=分)', ' ', s)
    rows=[]
    # Consume complete numeric-looking tokens. Unsupported mixtures remain
    # untraceable, rather than lending their numeric subfragments as evidence.
    for m in _LEXNUM.finditer(s):
        token=m.group();normalized=token.replace('负','-').replace('負','-')
        arabic=re.fullmatch(r'([+-]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?)(万亿|万|亿)?',normalized)
        try:
            if arabic:
                number=arabic[1]
                if ',' in number and not re.fullmatch(r'[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:[eE][+-]?\d+)?',number):raise ValueError('invalid grouped number')
                value=float(number.replace(',',''))*{None:1.,'万':1e4,'亿':1e8,'万亿':1e12}[arabic[2]]
            elif not re.fullmatch(r'[+\-负負]?[零〇一二两三四五六七八九十百千万亿]+(?:点[零〇一二两三四五六七八九]+)?',token):value=None
            else:value=float(_chinese_cardinal(token))
            if value is not None and not math.isfinite(value):value=None
        except (KeyError,ValueError,OverflowError):value=None
        rows.append({'value':value,'token':m.group(),'span':[m.start(),m.end()],'quote':text[m.start():m.end()]})
    rows.extend({'value':None,'token':m.group(),'span':[m.start(),m.end()],'quote':text[m.start():m.end()]} for m in _NONFINITE.finditer(s))
    return rows


def _text_numbers(s):
    return [r['token'] if r['value'] is None or _TOK.fullmatch(r['token']) else format(r['value'],'.17g')
            for r in text_number_sources(s)]


def input_numbers(text):
    return [r['value'] for r in text_number_sources(text) if r['value'] is not None and math.isfinite(r['value'])]


def published_constants():
    out = set()
    for t in NT.TEMPLATES.values():
        for lo, hi, _d in t["params"].values():
            out.update((float(lo), float(hi)))
    return out


def _matches(token, allowed):
    """token（字符串，可含舍入）是否与 allowed 中某值一致：按 token 的小数位数四舍五入比较。"""
    try:v = float(token)
    except ValueError:return False
    m = _DEC.search(token)
    d = len(m.group(1)) if m and "e" not in token.lower() else None
    for a in allowed:
        if d is None:
            if math.isclose(a, v, rel_tol=1e-9, abs_tol=1e-12):
                return True
        elif abs(a - v) <= 0.5 * 10 ** (-d) + 1e-12 * max(1.0, abs(a)):
            return True
    return False


def _walk(o, path, leaves, texts):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in _SKIP_KEYS:
                continue
            _walk(v, path + (k,), leaves, texts)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _walk(v, path + (i,), leaves, texts)
    elif isinstance(o, bool) or o is None:
        return
    elif isinstance(o, (int, float)):
        leaves.append((path, float(o)))
    elif isinstance(o, str):
        last = next((p for p in reversed(path) if isinstance(p, str)), "")
        if last in ("question", "reply_text", "message") and not any(isinstance(p, str) and p in _SKIP_STR_KEYS for p in path[:-1]):
            texts.append((path, o))


def check_numbers(text_zh, output):
    """返回 (数字总数, 不可追溯列表)。"""
    allowed = set(input_numbers(text_zh)) | published_constants()
    res = output.get("compile_result") or {}
    # 登记推导式（编译结果与解析器声明的全部）：操作数可追溯且重算一致才放行；迭代到不动点（一条的结果可作为另一条的操作数）
    ders = []

    def collect(o):
        if isinstance(o, dict):
            if "formula_id" in o and "operands" in o and "value" in o:
                ders.append(o)
            for v in o.values():
                collect(v)
        elif isinstance(o, list):
            for v in o:
                collect(v)
    collect(output)
    pending, progress = list(ders), True
    while pending and progress:
        progress, rest = False, []
        for d in pending:
            ok = d["formula_id"] in IT.DERIVATIONS and all(_matches_val(v, allowed) for v in d["operands"].values())
            if ok:
                try:
                    ok = math.isclose(IT.recompute(d), d["value"], rel_tol=1e-9)
                except (KeyError, TypeError, ZeroDivisionError, ValueError):
                    ok = False
            if ok:
                allowed.add(float(d["value"]))
                progress = True
            else:
                rest.append(d)
        pending = rest
    bad_der = [d.get("quantity") for d in pending]
    leaves, texts = [], []
    _walk(res, ("compile_result",), leaves, texts)
    _walk({"parsed_requirement": output.get("parsed_requirement")}, (), leaves, texts)
    if "reply_text" in output:
        texts.append((("reply_text",), output["reply_text"]))
    total, bad = 0, []
    for path, v in leaves:
        total += 1
        if not _matches_val(v, allowed):
            bad.append({"path": "/".join(map(str, path)), "value": v})
    for path, s in texts:
        for tok in _text_numbers(s):
            total += 1
            if not _matches(tok, allowed):
                bad.append({"path": "/".join(map(str, path)), "token": tok})
    for q in bad_der:
        bad.append({"path": "derivation", "quantity": q, "reason": "操作数不可追溯或重算不一致"})
    return total, bad


def _matches_val(v, allowed):
    return any(math.isclose(a, float(v), rel_tol=1e-9, abs_tol=1e-12) for a in allowed)


# ---------------------------------------------------------------- 评测
def load_cases(path=BENCH):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _gold_labeled(c):
    return c["gold"].get("status") == "labeled"


def evaluate(system, cases_doc=None):
    doc = cases_doc or load_cases()
    per, tot_n, tot_bad = [], 0, 0
    outcomes = {}
    sc_asked = sc_need = 0
    comp_ok = comp_n = 0
    rec_num = rec_den = pre_num = pre_den = 0
    for c in doc["cases"]:
        out = system(c["text_zh"])
        res = out.get("compile_result") or {}
        n, bad = check_numbers(c["text_zh"], out)
        tot_n += n
        tot_bad += len(bad)
        st = res.get("status")
        outcomes[st] = outcomes.get(st, 0) + 1
        asked = {q["field"] for q in res.get("questions", [])}
        preq = out.get("parsed_requirement") or {}
        try:
            need = set(IT.required_fields(preq)) if st in ("needs_clarification", "pass_pending_human_confirmation") or res.get("questions") else set()
        except (KeyError, TypeError):
            need = set()
        if st in ("needs_clarification", "blocked_invalid_inputs") or asked:
            sc_need += len(need)
            sc_asked += len(need & asked)
        row = {"id": c["id"], "status": st, "numbers": n, "untraceable": bad, "asked_fields": sorted(asked),
               "gold": c["gold"]["status"]}
        if _gold_labeled(c):
            g = c["gold"]
            # The documented gold taxonomy calls successful compilation
            # "compiled"; the tool deliberately retains human confirmation.
            # Normalize only the scoring class, never the actual tool status.
            expected = g.get("expected_outcome")
            observed = "compiled" if st == "pass_pending_human_confirmation" and expected == "compiled" else st
            ok = (expected == observed and g.get("expected_structured_requirement") == preq)
            comp_n += 1
            comp_ok += int(ok)
            exp = set(g.get("expected_questions") or [])
            rec_num += len(exp & asked)
            rec_den += len(exp)
            pre_num += len(exp & asked)
            pre_den += len(asked)
            row["compile_correct"] = ok
        per.append(row)
    labeled = sum(1 for c in doc["cases"] if _gold_labeled(c))
    rate = (tot_bad / tot_n) if tot_n else 0.0
    return {
        "schema": "gearbase.agent-bench-result/1", "bench": doc["version"], "cases": len(doc["cases"]),
        "labeled_cases": labeled, "pending_engineer_label": len(doc["cases"]) - labeled,
        "metrics": {
            "hallucinated_number_rate": rate, "numbers_checked": tot_n, "numbers_untraceable": tot_bad,
            "hallucination_gate": "pass" if tot_bad == 0 else "FAIL",
            "compile_accuracy": (comp_ok / comp_n) if comp_n else None,
            "clarification_recall": (rec_num / rec_den) if rec_den else None,
            "clarification_precision": (pre_num / pre_den) if pre_den else None,
            "clarification_selfcheck": (sc_asked / sc_need) if sc_need else None,
            "clarification_selfcheck_fields": {"required": sc_need, "asked": sc_asked},
            "outcome_distribution": dict(sorted(outcomes.items())),
        },
        "scoring_note": "compile_accuracy / clarification_recall / clarification_precision 在无金标（pending_engineer_label）时为 null，不是 0；"
                        "基线分数中只有凭空数字率、结果分布与追问自洽是有效数字。",
        "per_case": per,
    }


def main(argv):
    r = evaluate(rule_baseline)
    r["system"] = "rule_baseline_v1（确定性正则抽取 + requirement_compile，无 LLM）"
    text = json.dumps(r, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if "--check" in argv:
        cur = RESULT.read_text(encoding="utf-8") if RESULT.exists() else ""
        print("一致" if cur == text else "不一致")
        return 0 if cur == text else 2
    if "--write" in argv:
        RESULT.write_text(text, encoding="utf-8")
    m = r["metrics"]
    print(json.dumps({k: v for k, v in r.items() if k != "per_case"}, ensure_ascii=False, indent=1))
    return 0 if m["hallucination_gate"] == "pass" else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
