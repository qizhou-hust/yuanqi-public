"""统一核算结果 → 中文 Markdown 报告（总览 + 明细 + 证据分布 + 未验证项 + 外部复核请求汇总 + 假设清单）。

只读投影：不重算、不改结果。数值按有效数字显示，原值以 JSON 结果为准。
"""
from __future__ import annotations

STATUS_ZH = {"pass": "通过", "fail": "不通过", "blocked": "阻断", "not_in_scope": "不在范围", "info": "信息"}
SCOPE_ZH = {"gear_rating": "齿轮强度（ISO 6336）", "manufacturing": "制造参数（ISO 1328-1）", "scuffing": "胶合（ISO/TS 6336-21）",
            "micropitting": "微点蚀（ISO/TS 6336-22）", "shaft": "轴（DIN 743）", "bearing": "轴承（ISO 281）",
            "key": "平键（DIN 6892）", "fit": "过盈（DIN 7190-1）", "thermal": "热功率（ISO/TR 14179-1）"}


def _f(x, sig=6):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{sig}g}"
    return str(x)


def _esc(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def _key_item(c):
    rows = [i for i in c["items"] if i["status"] in ("pass", "fail", "blocked") and i["sense"]]
    if not rows:
        return "—"
    worst = min(rows, key=lambda i: (i["margin"] is None, i["margin"] if i["margin"] is not None else 0.0))
    return f"{worst['id'].split('.', 1)[-1]}：{_f(worst['value'], 5)} / {_f(worst['limit'], 5)}（裕度 {_f(worst['margin'], 4)}）"


def render_markdown(result):
    r = result
    L = [f"# 统一核算报告：{r['design_id']}", "",
         f"> **{r['disclaimer']}**", "",
         f"- 结果模式：`{r['schema']}`；包版本 {r['package_version']}",
         f"- 设计真源：`{r['design_id']}`（sha256 `{_f(r['design_sha256'])}`）",
         f"- 系统层输入：`{r['system_input_id']}`（sha256 `{r['system_input_sha256']}`）",
         f"- 请求范围：{', '.join(r['scope_requested'])}", ""]
    if r["input_errors"]:
        L += ["**系统层输入校验失败：**", ""] + [f"- `{e['path']}` {e['code']}：{_esc(e['message'])}" for e in r["input_errors"]] + [""]
    comp = r["computation"]
    L += ["## 1. 总览", "",
          f"**计算结果：{STATUS_ZH[comp['status']]}**（通过 {comp['counts']['pass']}、不通过 {comp['counts']['fail']}、"
          f"阻断 {comp['counts']['blocked']}、不在范围 {comp['counts']['not_in_scope']}）。{comp['note']}。", "",
          "| 子检查 | 状态 | 最小裕度条目（值 / 限值） | 条目证据等级 | 缺项数 | 外部对拍引用 |",
          "|---|---|---|---|---|---|"]
    for s, c in r["checks"].items():
        lv = sorted({i["evidence_level"] for i in c["items"] if i["status"] != "blocked"})
        ext = len(c["external_refs"]) if c["status"] != "not_in_scope" else 0
        same = sum(1 for x in c["external_refs"] if x["relation"] == "same_design") if c["status"] != "not_in_scope" else 0
        L.append(f"| {SCOPE_ZH[s]} | {STATUS_ZH[c['status']]} | {_esc(_key_item(c))} | {', '.join(lv) or '—'} | "
                 f"{len(c['missing'])} | {ext}（同设计 {same}） |")
    L += ["", "## 2. 明细", ""]
    for s in r["scope_requested"]:
        c = r["checks"][s]
        L += [f"### 2.{r['scope_requested'].index(s) + 1} {SCOPE_ZH[s]} —— {STATUS_ZH[c['status']]}", "",
              f"模块：`{c['module']}`" + (f"；{c['reason']}" if c["reason"] else ""), ""]
        if c["items"]:
            L += ["| 条目 | 量 | 值 | 单位 | 限值 | 关系 | 裕度 | 状态 | 公式 id | 证据 |", "|---|---|---|---|---|---|---|---|---|---|"]
            for i in c["items"]:
                L.append(f"| {_esc(i['id'])} | {i['quantity']} | {_f(i['value'])} | {i['unit']} | {_f(i['limit'])} | "
                         f"{i['sense'] or '—'} | {_f(i['margin'], 4)} | {STATUS_ZH[i['status']]} | "
                         f"{_esc(', '.join(i['formula_ids'][:4]) or '—')} | {i['evidence_level']} |")
            L.append("")
        if c["missing"]:
            L += ["缺项（无来源，未补默认值）：", ""] + [f"- `{_esc(m)}`" for m in c["missing"]] + [""]
        if c["unconfirmed"]:
            L += ["条文未确认 / 适用域：", ""] + [f"- {_esc(u)}" for u in c["unconfirmed"]] + [""]
        if c["errors"]:
            L += ["输入错误：", ""] + [f"- `{_esc(e.get('path', ''))}` {e.get('code', '')}：{_esc(e.get('message', ''))}"
                                     for e in c["errors"]] + [""]
    ev = r["evidence_qualification"]
    L += ["## 3. 证据分布（与计算结果分开）", "", ev["note"] + "。", "",
          "已算出条目（pass/fail/info）的证据等级：" +
          ("、".join(f"{k} {v} 条" for k, v in ev["item_level_distribution"].items()) or "无"), "",
          "| 子检查 | 模块公式注册表等级分布 |", "|---|---|"]
    for s, d in ev["module_registry_distribution"].items():
        L.append(f"| {SCOPE_ZH[s]} | {'、'.join(f'{k}: {v}' for k, v in d.items())} |")
    L += ["", f"外部对拍引用文件（data/kisssoft_v014，私有）：{len(ev['external_ref_files'])} 个", ""]
    for x in ev["external_refs"]:
        L.append(f"- [{SCOPE_ZH.get(x.get('scope'), x.get('scope'))}] `{x['file']}` —— {x['relation']}：{x['note']}")
    L += ["", "## 4. 未验证项", "", "证据等级低于 E5（无同输入外部一致）或未算出的条目：", ""]
    if ev["unverified_items"]:
        L += ["| 子检查 | 条目 | 状态 | 证据 |", "|---|---|---|---|"]
        L += [f"| {SCOPE_ZH[u['scope']]} | {_esc(u['id'])} | {STATUS_ZH[u['status']]} | {u['evidence_level']} |"
              for u in ev["unverified_items"]]
    else:
        L.append("无。")
    L += ["", "## 5. 外部复核请求汇总", ""]
    if r["external_review_requests"]:
        for q in r["external_review_requests"]:
            L += [f"- **{SCOPE_ZH[q['scope']]}** → {q['kisssoft_module']}：{len(q['items'])} 条目"
                  f"（{_esc(', '.join(q['items'][:6]))}{' …' if len(q['items']) > 6 else ''}）；"
                  f"已有同设计引用：{', '.join(q['existing_same_design_refs']) or '无'}。{q['purpose']}。"]
    else:
        L.append("无（没有已算出且证据低于 E5 的子检查）。")
    blocked = [s for s in r["scope_requested"] if r["checks"][s]["status"] == "blocked"]
    if blocked:
        L += ["", "阻断子检查须先补输入（见第 2 节缺项）再提外部复核：" + "、".join(SCOPE_ZH[s] for s in blocked) + "。"]
    L += ["", "## 6. 假设清单", ""]
    L += [f"- [{a['scope']}] {_esc(a['text'])}（来源：{_esc(a['source'])}）" for a in r["assumptions"]] or ["无。"]
    L += ["", "---", "", f"*{r['disclaimer']}*", ""]
    return "\n".join(L)
