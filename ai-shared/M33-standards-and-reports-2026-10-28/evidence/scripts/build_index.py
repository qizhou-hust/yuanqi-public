from pathlib import Path
from urllib.parse import quote
import csv
import hashlib
import html
import json
import math

ROOT = Path(__file__).resolve().parents[1]


def main():
    summary = json.loads((ROOT / "verification/kisssoft-run-summary.json").read_text(encoding="utf-8"))
    core = [
        ("ISO/TR 6336-30:2022", "ISO-TR-6336-30-2022-supplemented-reading-copy.pdf", 70, "1-63", "补页阅读副本；原扫描缺正文第 2 页", "84147"),
        ("ISO 6336-1:2019", "ISO 6336-1-2019.pdf", 144, "1-134", "通用影响系数", "63819"),
        ("ISO 6336-2:2019", "ISO 6336-2-2019.pdf", 46, "1-37", "齿面接触强度", "63821"),
        ("ISO 6336-3:2019", "ISO 6336-3-2019.pdf", 64, "1-55", "含 2020-11 勘误；轮齿弯曲强度", "63822"),
        ("ISO 6336-5:2016", "ISO 6336-5-2016.pdf", 54, "1-47", "材料强度与质量", "55353"),
        ("ISO 6336-6:2019", "ISO 6336-6-2019.pdf", 44, "1-37", "变载荷寿命", "63823"),
    ]
    labels = {"K01-spur": "直齿基准", "K02-helical": "斜齿 / 调质钢", "K03-premachining": "预加工与磨齿", "K04-EV-stage1": "EV 第一级", "K05-EV-stage2": "EV 第二级"}
    rows = []
    for c in summary["cases"]:
        v = c["values"]
        rows.append({"case": c["id"], "description": labels[c["id"]], "pages": c["report_validation"]["pages"],
                     "z1": int(v["ZR[0].z"]), "z2": int(v["ZR[1].z"]), "mn_mm": v["ZS.Geo.mn"],
                     "beta_deg": math.degrees(v["ZS.Geo.beta"]), "speed_rpm": v["ZR[0].nnominal"],
                     "KV": v["ZP[0].KV.KV"], "KHbeta": v["ZP[0].KHb"],
                     "KHbeta_mode": "原模型输入" if v["Zst.KHbVariant"] == 1 else "自动计算",
                     "sigmaH_MPa": v["ZP[0].Flanke.sigH"], "sigmaF1_MPa": v["ZPP[0].Fuss.sigF"], "sigmaF2_MPa": v["ZPP[1].Fuss.sigF"],
                     "SH1": v["ZPP[0].Flanke.SH"], "SH2": v["ZPP[1].Flanke.SH"],
                     "SF1": v["ZPP[0].Fuss.SFnorm"], "SF2": v["ZPP[1].Fuss.SFnorm"],
                     "calculation_ok": c["calculate_return"], "reload_identical": not c["reload_differences"]})
    with (ROOT / "reports/report-summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    md = ["# M33 验收前置资料包", "", "整理日期：2026-10-28（用户时区 America/Los_Angeles）。", "",
          "**资料准备已完成：六份核心标准可供核对，五份 KISSsoft 完整报告共 68 页，附原生模型与机器可读结果。M33 的公式逐项对拍尚未执行。**", "",
          "## 必读：TR 6336-30 原扫描有缺页", "",
          "用户提供的 `ISO TR 6336-30-2022.pdf` 有 69 个 PDF 页面；正文页码从 1 直接跳到 3，缺第 2 页符号表。", "",
          "`standards/core/ISO-TR-6336-30-2022-supplemented-reading-copy.pdf` 是本次生成的 70 页补页阅读副本：在 PDF 第 8 页插入 iTeh 公开预览中的原始第 2 页。其余 69 页与原扫描逐页渲染一致。补入页保留全部预览水印，原下载文件另行保留。此文件是有来源记录的阅读副本，不是出版社重新签发的原件。", "",
          "补页来源：<https://cdn.standards.iteh.ai/samples/84147/9ae91150411a40e592ecb65e1429702b/ISO-TR-6336-30-2022.pdf>。来源、文件哈希和页码映射见 `verification/page-repair-provenance.json`。", "",
          "## 核心标准", "", "| 标准 | PDF 页数 | 正文页码 | 备注 |", "|---|---:|---|---|"]
    for name, filename, pages, numbering, note, _ in core:
        md.append(f"| [{name}](standards/core/{quote(filename)}) | {pages} | {numbering} | {note} |")
    md += ["", "核心标准封面版次、正文页码连续性和可渲染性已检查；OCR 误识别页号已通过图像复核。扫描件没有可搜索文字层，公式、上下标和表格数值应以原图为准。本次不声称逐字校对过标准。", "",
           "用户提供的 21 份 PDF 已按原字节保存并记录 SHA-256：`core/` 为六份核心原件及一份补页副本；`ISO-supplementary/` 为 -4/-20/-21/-22/-31；`GB-reference/` 为六份 GB/T、GB/Z；`historical/` 为四份 2006 旧版。补充和旧版资料仅编目，未逐页审查。GB/T 文件不自动视为相同年份 ISO 的等同替代。", "",
           "来源目录：`D:\\BaiduNetdiskDownload\\ISO 6336-1-2019全套 + GBT3480全套`。", "",
           "## KISSsoft 报告", "",
           f"本机 KISSsoft {summary['software']['runtime_version']}，文件版本 {summary['software']['file_version']}；COM 模块 `Z012` 许可检查通过。强度方法均为 `ISO 6336:2019`，方法 ID `10029`。每个案例均从安装目录的厂商示例重新计算。", "",
           "| 案例 | 覆盖 | 齿数 | mn / mm | β / ° | 页数 | 最小 SH | 最小 SF | KHβ |", "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        md.append(f"| [{r['case']}](reports/{r['case']}/{r['case']}.pdf) | {r['description']} | {r['z1']}/{r['z2']} | {r['mn_mm']:g} | {r['beta_deg']:.1f} | {r['pages']} | {min(r['SH1'],r['SH2']):.4f} | {min(r['SF1'],r['SF2']):.4f} | {r['KHbeta_mode']} |")
    md += ["", "每个案例目录包含：原厂源模型 `source-example.Z12`、本轮保存的 `.Z12`、KISSsoft 原生 `.rtf` 和 `.html` 报告、由原生 RTF 经 Word 导出的 `.pdf`、从 PDF 提取的 `.extracted.txt`、COM 全精度字段与计算记录 `.json`。", "",
           "五例 `CalculateRetVal=True`，计算消息均为空；保存后重新加载计算，161 个提取字段在相对 1e-9 / 绝对 1e-10 容差下保持一致（字符串精确一致）。未手工填入应力或安全系数。", "",
           "K02 原示例采用 DIN 3990，仅将强度方法从 `10070` 切换为 `10029`；这一改动已保存在案例 JSON 中。其它案例未改输入参数。各例几何方法沿用原模型，报告显示 ISO 21771:2007；材料、寿命、质量、公差、刀具和润滑分支均以原报告为准。", "",
           "### 对 M33 的使用边界", "",
           "- K01-K03 的 KV、KHα 和 KHβ 自动计算，可作为相应公式的对拍候选。K04-K05 的 KV、KHα 自动计算，KHβ 沿用原模型输入值；它们不能证明 KHβ 自动公式正确。", 
           "- K02 的最小 SH≈0.7121，K05 的最小 SH≈0.9946；保留这些真实结果，可用于不合格边界回归。计算成功不等于齿轮强度通过。", 
           "- 这五份是厂商示例的本机复算报告，不是 ISO/TR 6336-30 的八个标准算例。应把标准算例和商业工具报告分别纳入后续对拍。", 
           "- 后续必须先冻结同一几何、载荷、材料、寿命、自动标志和方法，再逐项比较因素与实际应力；本包未运行 gearmath 对拍，也不代表 M33 或产品放行通过。", "",
           "## 验证与复算", "",
           "文件检查结果见 `verification/final-validation.json`；标准页码复核见 `verification/standards-validation.json`；商用工具计算与重开结果见 `verification/kisssoft-run-summary.json`。报告已逐页生成缩略图并检查布局，图像存于 `verification/`。", "",
           "```powershell", "& 'D:\\anaconda3\\python.exe' -X utf8 '.\\scripts\\validate_evidence.py'", "```", "",
           "需重新从 KISSsoft 生成整套报告时：", "", "```powershell", "& 'D:\\anaconda3\\python.exe' -X utf8 '.\\scripts\\generate_kisssoft_reports.py'", "```", "",
           "重新生成会更新本包报告日期、模型与哈希，须重新建立清单。所需软件：KISSsoft 2026、Microsoft Word，以及 Python 的 pywin32/PyMuPDF；页码 OCR 另用本机 Tesseract。", "",
           "导出细节：本机 `ReportWithParameters` 的 RTF 类型 `0` 能完整展开报告模板；类型 `1/10/20` 在此模板下保留模板指令，因此不作为交付报告。", ""]
    # The exact field count is derived, rather than fixed in prose.
    md_text = "\n".join(md).replace("161 个提取字段", f"{len(summary['cases'][0]['values'])} 个提取字段")
    (ROOT / "README.zh-CN.md").write_text(md_text, encoding="utf-8")
    core_html = "".join(f'<tr><td><a href="standards/core/{quote(filename)}">{name}</a></td><td>{pages}</td><td>{numbering}</td><td>{note}</td></tr>' for name, filename, pages, numbering, note, _ in core)
    report_html = "".join(f'<tr><td><strong>{r["description"]}</strong><small>{r["case"]}</small></td><td>{r["z1"]}/{r["z2"]}</td><td>{r["mn_mm"]:g}</td><td>{r["beta_deg"]:.0f}°</td><td>{r["pages"]}</td><td>{r["KHbeta_mode"]}</td><td><a href="reports/{r["case"]}/{r["case"]}.pdf">PDF 报告</a> · <a href="reports/{r["case"]}/{r["case"]}.Z12">模型</a> · <a href="reports/{r["case"]}/{r["case"]}.json">数据</a></td></tr>' for r in rows)
    doc = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>M33 标准与 KISSsoft 报告</title>
<style>body{{font:16px/1.65 "Segoe UI","Microsoft YaHei",sans-serif;background:#f3f5f8;color:#183047;margin:0}}main{{max-width:1100px;margin:40px auto;padding:0 24px}}h1{{font-size:32px;margin:4px 0 12px}}h2{{font-size:22px;margin:30px 0 12px}}.eyebrow{{font-size:12px;letter-spacing:2px;color:#526f88}}.card{{background:white;padding:22px 26px;border:1px solid #dae2ea;border-radius:12px;margin:18px 0}}.notice{{border-left:5px solid #d69520}}a{{color:#0b66ab;text-decoration:none}}a:hover{{text-decoration:underline}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:12px 10px;border-bottom:1px solid #e3e9ee;text-align:left}}th{{color:#526f88;background:#f8fafc}}small{{display:block;color:#6d7d8b}}p{{margin:8px 0}}.scroll{{overflow:auto}}.status{{color:#16754b;font-weight:600}}footer{{font-size:13px;color:#607487;margin:22px 0 40px}}</style>
<main><div class="eyebrow">GEARBASE · M33 · 2026-10-28</div><h1>标准正文与 KISSsoft 报告</h1><p>6 份核心标准 · 5 份完整报告 · 68 页计算结果 · 原生模型与全精度数据</p>
<div class="card notice"><strong>TR 6336-30 缺页已补入阅读副本</strong><p>原扫描缺少正文第 2 页符号表。下方提供 70 页补页副本，补入页来自公开预览并保留水印；原件和来源记录均已保存。</p><a href="verification/page-repair-provenance.json">查看补页记录</a></div>
<section class="card"><h2>核心标准</h2><div class="scroll"><table><thead><tr><th>标准 / 点击打开</th><th>PDF 页数</th><th>正文页码</th><th>说明</th></tr></thead><tbody>{core_html}</tbody></table></div><p><small>扫描件无可搜索文字层。6336-3:2019 为 2020-11 勘误版；其他 ISO 分册、GB/T 与历史版本已按目录保存。</small></p></section>
<section class="card"><h2>KISSsoft 2026 计算报告</h2><p class="status">5/5 计算完成，无警告；原生文件重开复算一致</p><div class="scroll"><table><thead><tr><th>案例</th><th>齿数</th><th>mn / mm</th><th>β</th><th>页数</th><th>KHβ</th><th>文件</th></tr></thead><tbody>{report_html}</tbody></table></div></section>
<section class="card"><h2>验收使用说明</h2><p>报告统一采用 ISO 6336:2019 强度方法。两个 EV 案例保留原模型输入的 KHβ，可用于应力计算对拍；不能用于验证 KHβ 自动公式。</p><p>斜齿案例和 EV 第二级存在 SH 小于 1 的结果，均按真实结果保留。这些报告来自厂商示例复算，尚未与 gearmath 逐项对拍。</p><p><a href="README.zh-CN.md">完整说明与复算命令</a> · <a href="reports/report-summary.csv">结果汇总 CSV</a> · <a href="verification/final-validation.json">文件验证记录</a> · <a href="SHA256SUMS.json">哈希清单</a></p></section>
<footer>本页标记的是资料准备状态。M33 公式验收与产品强度放行须另行完成。</footer></main></html>'''
    (ROOT / "index.html").write_text(doc, encoding="utf-8")
    excluded = {"SHA256SUMS.json", "verification/final-validation.json"}
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob("*"))
                if p.is_file() and p.relative_to(ROOT).as_posix() not in excluded and "probes" not in p.parts and "__pycache__" not in p.parts}
    (ROOT / "SHA256SUMS.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest_files": len(manifest), "cases": len(rows), "report_pages": sum(r["pages"] for r in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
