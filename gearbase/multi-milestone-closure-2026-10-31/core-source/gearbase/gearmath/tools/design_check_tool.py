"""MCP 工具 design_check（只读）：对白名单内的设计（data/source/<id>.math-source.json）与系统层输入
（data/system/<id>.system-input.json）运行统一核算（gearmath.product.design_check），返回 gears.design-check-result/1，
可选附中文 Markdown 报告。只接受白名单 id、scope 名与输出格式；不接受文档内容、路径或数值覆盖；不写盘。
"""
from __future__ import annotations

from ..product import design_check as DC

# 设计 id -> 系统层输入 id（两者都在仓库数据目录中，带来源）
CASES = {"C001": "C001", "K01-spur": "K01-spur"}
FORMATS = ("json", "json+markdown")


def input_schema():
    return {"type": "object", "additionalProperties": False, "required": ["design", "scope"],
            "properties": {"design": {"type": "string", "enum": sorted(CASES),
                                      "description": "白名单设计 id（data/source/<id>.math-source.json；系统层输入 data/system/<id>.system-input.json）"},
                           "scope": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": ["all"] + list(DC.SCOPES)},
                                     "description": "子检查范围：['all'] 或 SCOPES 子集"},
                           "format": {"type": "string", "enum": list(FORMATS),
                                      "description": "json（默认）或 json+markdown（附中文报告）"}}}


TOOL = {"name": "design_check",
        "description": "统一核算（只读）：齿轮强度、制造参数、胶合、微点蚀、轴、轴承、键、过盈、热功率按所选范围逐项调用已有标准模块；"
                       "缺输入的子检查返回 blocked 与缺项清单（不补默认值），不影响其它子检查。结果把计算结果与证据资格分开，"
                       "列出公式 id、证据等级、外部对拍引用文件名与假设清单；不等于工程验收。",
        "annotations": {"readOnlyHint": True}, "inputSchema": input_schema()}


def run(args):
    if not isinstance(args, dict):
        return {"status": "blocked_invalid_inputs", "errors": [{"name": "arguments", "code": "invalid_argument", "message": "参数必须是对象"}]}
    errs = [{"name": k, "code": "unknown_argument", "message": f"不接受参数 {k!r}"}
            for k in sorted(set(args) - {"design", "scope", "format"})]
    d, scope, fmt = args.get("design"), args.get("scope"), args.get("format", "json")
    if d not in CASES:
        errs.append({"name": "design", "code": "unknown_design", "message": f"须是白名单之一 {sorted(CASES)}"})
    if fmt not in FORMATS:
        errs.append({"name": "format", "code": "invalid_argument", "message": f"format 须是 {list(FORMATS)}"})
    if not isinstance(scope, list) or not scope:
        errs.append({"name": "scope", "code": "invalid_argument", "message": "scope 须是非空数组"})
    else:
        try:
            scope = DC.normalize_scope("all" if scope == ["all"] else scope)
        except ValueError as e:
            errs.append({"name": "scope", "code": "invalid_argument", "message": str(e)})
    if errs:
        return {"status": "blocked_invalid_inputs", "errors": errs}
    res = DC.check_files(d, CASES[d], scope)
    out = {"status": "ok", "result": res}
    if fmt == "json+markdown":
        from ..product import report as R
        out["report_markdown"] = R.render_markdown(res)
    return out
