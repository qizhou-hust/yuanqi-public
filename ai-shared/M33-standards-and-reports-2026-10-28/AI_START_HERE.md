# 外部 AI 读取入口：M33 标准与 KISSsoft 报告

本目录提供标准资料、5 个 KISSsoft 2026 圆柱齿轮副计算案例及复算记录。资料准备完成，不等于 M33 公式实现验收通过。

## 推荐读取顺序

1. 读本文件和 `evidence/README.zh-CN.md`，明确版本、缺页修复、自动标志和验收边界。
2. 读 `evidence/reports/report-summary.csv`，了解 5 个案例的输入范围、应力和安全系数。
3. 读 `evidence/verification/kisssoft-run-summary.json`，取得每例 132 个 COM 字段、计算返回值、警告与保存重开复算结果。
4. 读 `evidence/reports/<case>/<case>.extracted.txt` 和同名 `.json`；PDF 保留完整报告版式。
5. 用 `ai/standards-ocr/*.md` 检索标准条款，再核对对应 PDF 原图。`ai/ocr-manifest.json` 提供来源、页数和哈希。
6. 读 `PUBLICATION_MANIFEST.json`，检查文件大小和 SHA-256。下载完整 ZIP 时先校验 Release 附件中的 SHA256 文件。

所有可直接读取的 GitHub Raw 地址见 `ai/file-catalogue.json`。支持命令行的 AI 可以直接克隆本仓库，或下载 Release 的完整 ZIP。

## 标准与页码

- ISO/TR 6336-30:2022：使用 `evidence/standards/core/ISO-TR-6336-30-2022-supplemented-reading-copy.pdf`。用户原扫描 69 页，缺正文第 2 页；阅读副本插入 iTeh 公开预览该页后为 70 页，原件及所有水印保留。PDF 页 7 对应正文页 1，PDF 页 8 对应补入正文页 2。详情见 `evidence/verification/page-repair-provenance.json`。
- ISO 6336-1/-2/-3:2019，-3 为 2020-11 corrected version。
- ISO 6336-5:2016 与 ISO 6336-6:2019。
- 其它 ISO、GB/T、GB/Z 和 2006 旧版仅作为补充资料；不要混用不同版次。
- 扫描 PDF 是核查依据；OCR 未逐字校对，公式、上下标、负号、小数点及表格列可能识别错误。OCR 页标题同时给出 PDF 页码与正文页码。

## KISSsoft 案例与约束

| 案例 | 内容 | KHβ 模式 |
|---|---|---|
| K01-spur | 25/76 齿，mn=6 mm，直齿 | 自动计算 |
| K02-helical | 27/104 齿，mn=1.5 mm，β=14° | 自动计算 |
| K03-premachining | 12/45 齿，预加工/磨齿 | 自动计算 |
| K04-EV-stage1 | 26/61 齿，β≈29° | 原模型输入 |
| K05-EV-stage2 | 24/88 齿，β≈19° | 原模型输入 |

五例强度方法均为 ISO 6336:2019，方法 ID 10029；几何方法沿用厂商示例的 ISO 21771:2007。
K02 从 DIN 3990 方法改为 ISO 6336:2019，其余输入未人为调参。五例计算及原生文件重开复算成功，计算消息为空。
K02、K05 有接触安全系数小于 1 的结果，不可因计算成功而判定强度合格。
两个 EV 案例不能用于证明 KHβ 自动公式正确。
这五例来自厂商示例复算，并非 ISO/TR 6336-30 的八个标准算例。

字段单位：长度 mm，COM 角度 rad，报告角度 deg，转矩 Nm，转速 rpm，应力 N/mm²，寿命 h。
应先对齐输入、材料/热处理、刀具、修形、公差、寿命及自动标志，再按几何→力→K 系数→Z/Y 系数→实际应力→许用应力→安全系数的顺序比较。不要通过调输入追平最终安全系数。

## 可复制给外部 AI 的任务

请从本文件开始读取 M33 资料，建立输入、标准版次、方法、单位与自动计算标志的对拍契约。使用 KISSsoft 原生报告和 JSON 作为商业工具证据，使用标准 PDF 原图核对公式；OCR 仅用于定位。先给出可验证字段、覆盖范围与缺失输入，再做逐项数值比较。明确区分“资料可读”“商业工具复算一致”“公式对拍通过”“产品强度合格”，不要把其中任何一项替代另一项。指出 TR30 的补页来源以及 K04/K05 的 KHβ 输入限制。

## 权利及来源

标准和厂商资料保留各自版权及既有水印；仓库公开不代表这些文件转为开源或获得新的转授权。本包不为第三方材料附加开源许可。原始来源、校验和及补页记录随包提供。
