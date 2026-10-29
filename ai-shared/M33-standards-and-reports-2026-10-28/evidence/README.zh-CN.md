# M33 验收前置资料包

整理日期：2026-10-28（用户时区 America/Los_Angeles）。

**资料准备已完成：六份核心标准可供核对，五份 KISSsoft 完整报告共 68 页，附原生模型与机器可读结果。M33 的公式逐项对拍尚未执行。**

## 必读：TR 6336-30 原扫描有缺页

用户提供的 `ISO TR 6336-30-2022.pdf` 有 69 个 PDF 页面；正文页码从 1 直接跳到 3，缺第 2 页符号表。

`standards/core/ISO-TR-6336-30-2022-supplemented-reading-copy.pdf` 是本次生成的 70 页补页阅读副本：在 PDF 第 8 页插入 iTeh 公开预览中的原始第 2 页。其余 69 页与原扫描逐页渲染一致。补入页保留全部预览水印，原下载文件另行保留。此文件是有来源记录的阅读副本，不是出版社重新签发的原件。

补页来源：<https://cdn.standards.iteh.ai/samples/84147/9ae91150411a40e592ecb65e1429702b/ISO-TR-6336-30-2022.pdf>。来源、文件哈希和页码映射见 `verification/page-repair-provenance.json`。

## 核心标准

| 标准 | PDF 页数 | 正文页码 | 备注 |
|---|---:|---|---|
| [ISO/TR 6336-30:2022](standards/core/ISO-TR-6336-30-2022-supplemented-reading-copy.pdf) | 70 | 1-63 | 补页阅读副本；原扫描缺正文第 2 页 |
| [ISO 6336-1:2019](standards/core/ISO%206336-1-2019.pdf) | 144 | 1-134 | 通用影响系数 |
| [ISO 6336-2:2019](standards/core/ISO%206336-2-2019.pdf) | 46 | 1-37 | 齿面接触强度 |
| [ISO 6336-3:2019](standards/core/ISO%206336-3-2019.pdf) | 64 | 1-55 | 含 2020-11 勘误；轮齿弯曲强度 |
| [ISO 6336-5:2016](standards/core/ISO%206336-5-2016.pdf) | 54 | 1-47 | 材料强度与质量 |
| [ISO 6336-6:2019](standards/core/ISO%206336-6-2019.pdf) | 44 | 1-37 | 变载荷寿命 |

核心标准封面版次、正文页码连续性和可渲染性已检查；OCR 误识别页号已通过图像复核。扫描件没有可搜索文字层，公式、上下标和表格数值应以原图为准。本次不声称逐字校对过标准。

用户提供的 21 份 PDF 已按原字节保存并记录 SHA-256：`core/` 为六份核心原件及一份补页副本；`ISO-supplementary/` 为 -4/-20/-21/-22/-31；`GB-reference/` 为六份 GB/T、GB/Z；`historical/` 为四份 2006 旧版。补充和旧版资料仅编目，未逐页审查。GB/T 文件不自动视为相同年份 ISO 的等同替代。

来源目录：`D:\BaiduNetdiskDownload\ISO 6336-1-2019全套 + GBT3480全套`。

## KISSsoft 报告

本机 KISSsoft 2026，文件版本 26.0.0.0；COM 模块 `Z012` 许可检查通过。强度方法均为 `ISO 6336:2019`，方法 ID `10029`。每个案例均从安装目录的厂商示例重新计算。

| 案例 | 覆盖 | 齿数 | mn / mm | β / ° | 页数 | 最小 SH | 最小 SF | KHβ |
|---|---|---|---:|---:|---:|---:|---:|---|
| [K01-spur](reports/K01-spur/K01-spur.pdf) | 直齿基准 | 25/76 | 6 | 0.0 | 14 | 1.3328 | 2.4298 | 自动计算 |
| [K02-helical](reports/K02-helical/K02-helical.pdf) | 斜齿 / 调质钢 | 27/104 | 1.5 | 14.0 | 14 | 0.7121 | 2.4727 | 自动计算 |
| [K03-premachining](reports/K03-premachining/K03-premachining.pdf) | 预加工与磨齿 | 12/45 | 2.5 | 0.0 | 14 | 1.0005 | 3.8121 | 自动计算 |
| [K04-EV-stage1](reports/K04-EV-stage1/K04-EV-stage1.pdf) | EV 第一级 | 26/61 | 2.15 | 29.0 | 13 | 1.1153 | 1.6574 | 原模型输入 |
| [K05-EV-stage2](reports/K05-EV-stage2/K05-EV-stage2.pdf) | EV 第二级 | 24/88 | 2.5 | 19.0 | 13 | 0.9946 | 1.4263 | 原模型输入 |

每个案例目录包含：原厂源模型 `source-example.Z12`、本轮保存的 `.Z12`、KISSsoft 原生 `.rtf` 和 `.html` 报告、由原生 RTF 经 Word 导出的 `.pdf`、从 PDF 提取的 `.extracted.txt`、COM 全精度字段与计算记录 `.json`。

五例 `CalculateRetVal=True`，计算消息均为空；保存后重新加载计算，132 个提取字段在相对 1e-9 / 绝对 1e-10 容差下保持一致（字符串精确一致）。未手工填入应力或安全系数。

K02 原示例采用 DIN 3990，仅将强度方法从 `10070` 切换为 `10029`；这一改动已保存在案例 JSON 中。其它案例未改输入参数。各例几何方法沿用原模型，报告显示 ISO 21771:2007；材料、寿命、质量、公差、刀具和润滑分支均以原报告为准。

### 对 M33 的使用边界

- K01-K03 的 KV、KHα 和 KHβ 自动计算，可作为相应公式的对拍候选。K04-K05 的 KV、KHα 自动计算，KHβ 沿用原模型输入值；它们不能证明 KHβ 自动公式正确。
- K02 的最小 SH≈0.7121，K05 的最小 SH≈0.9946；保留这些真实结果，可用于不合格边界回归。计算成功不等于齿轮强度通过。
- 这五份是厂商示例的本机复算报告，不是 ISO/TR 6336-30 的八个标准算例。应把标准算例和商业工具报告分别纳入后续对拍。
- 后续必须先冻结同一几何、载荷、材料、寿命、自动标志和方法，再逐项比较因素与实际应力；本包未运行 gearmath 对拍，也不代表 M33 或产品放行通过。

## 验证与复算

文件检查结果见 `verification/final-validation.json`；标准页码复核见 `verification/standards-validation.json`；商用工具计算与重开结果见 `verification/kisssoft-run-summary.json`。报告已逐页生成缩略图并检查布局，图像存于 `verification/`。

```powershell
& 'D:\anaconda3\python.exe' -X utf8 '.\scripts\validate_evidence.py'
```

需重新从 KISSsoft 生成整套报告时：

```powershell
& 'D:\anaconda3\python.exe' -X utf8 '.\scripts\generate_kisssoft_reports.py'
```

重新生成会更新本包报告日期、模型与哈希，须重新建立清单。所需软件：KISSsoft 2026、Microsoft Word，以及 Python 的 pywin32/PyMuPDF；页码 OCR 另用本机 Tesseract。

导出细节：本机 `ReportWithParameters` 的 RTF 类型 `0` 能完整展开报告模板；类型 `1/10/20` 在此模板下保留模板指令，因此不作为交付报告。
