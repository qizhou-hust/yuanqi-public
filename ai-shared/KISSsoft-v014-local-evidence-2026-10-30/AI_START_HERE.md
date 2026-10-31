# KISSsoft v0.14 本地复算公开证据入口

日期：2026-10-30。软件：KISSsoft Release 2026，程序文件版本 26.0.0.0。

这是本地商业软件计算证据的阶段交付，包含成功运行、失败诊断与未验证项目。不要将文件上传、计算成功或数值相近视为验收通过。

## 建议读取顺序

1. [RESULTS.txt](RESULTS.txt)：整体状态、主要数值和未完成项。
2. [review.txt](review.txt)：P2/P3 逐字段覆盖与缺口。
3. [verification.json](verification.json)：已执行的验证；明确只覆盖列出的检查。
4. 按下面案例入口读取原始报告和运行 JSON；原生文件用于商业软件重放。

## 案例入口

| 项目 | 当前状态 | 证据 |
|---|---|---|
| P1 TR30 例7 | 复算与原生重载成功；fsh0 独立符号口径 OPEN | [P1 分析](P1-preflight.md)、[PDF](P1-TR30-example7-unchanged/P1-TR30-example7-unchanged.pdf)、[TXT](P1-TR30-example7-unchanged/P1-TR30-example7-unchanged.txt)、[运行 JSON](P1-TR30-example7-unchanged/run.json)、[Z12](P1-TR30-example7-unchanged/P1-TR30-example7-unchanged.Z12) |
| P2 K01 优化设计 | 补充由齿数/变位推导的中心距后成功；SH1=0.9949703、SF2=1.3945282；差异未关闭 | [对比 JSON](P2-comparison.json)、[PDF](P2-K01-geometry-mapped/P2-K01-geometry-mapped.pdf)、[TXT](P2-K01-geometry-mapped/P2-K01-geometry-mapped.txt)、[运行 JSON](P2-K01-geometry-mapped/run.json)、[Z12](P2-K01-geometry-mapped/P2-K01-geometry-mapped.Z12) |
| P3 K01–K05 胶合 | 五例已计算；采用各原生模型的油品/工况，不是 P2 优化几何 | 各 P3-* 目录的 PDF/TXT、run.json、p3-detail.json、Z12 |
| P3 微点蚀 | K01/K02 七点有效；K03–K05 缺油品试验数据，不能使用其零结果 | [K01 七点 TXT](P3-K01-spur/micropitting-seven-points.txt)、[K02 七点 TXT](P3-K02-helical/micropitting-seven-points.txt)、[补充标量](P3-supplemental-scalars.json) |
| P4 过盈 A1–A4 | 以 *-mapped-v2 为当前映射；四例计算/重载成功；附录逐字段等价仍有缺口 | P4-fit-A1-mapped-v2 至 P4-fit-A4-mapped-v2 目录中的 PDF/TXT、result.json、M10 |
| P4 平键 | 官方例方法 B 成功；仅切换方法 C 即失败，根因 OPEN | [最小探针记录](key-causal-probe.json)、[探针脚本](key_causal_probe.py)、key-debug.txt / key-baseline-debug.txt |
| P4 轴系/轴承 | 轴静力候选已修正；DIN743 截面与 ISO281 寿命未验证 | [轴候选读回](p4shaft/corrected-static-result.json)、[W10](p4shaft/P4-shaft-corrected-static.W10) |

## 使用边界

- 本次提供的 v0.13/v0.14 阶段 ZIP 已损坏；复算使用明确请求和已有哈希原生基准。见 input-preflight.md。
- P2-K01-requested-edits、初版 P4-fit-*、P4-key-*、轴静力早期候选是诊断记录，不是合格结果。
- P3 -20 的 XJ/XGamma 分布，以及 -21 的 theta_flaE/theta_MT/theta_flaintT 独立字段未取得；不能标为全字段闭合。
- 未包含标准原文/标准页截图或软件手册摘录。计算模型、报告及包含的运行记录按原始字节保留，校验值见 MANIFEST.json。
- JSON 里的绝对路径指原运行机器；在其他机器重放时需要重新指定本机安装与输入路径。脚本仅供显式调用，阅读入口不要求执行任何代码。

完整公开副本：[KISSsoft-v014-public-evidence.zip](KISSsoft-v014-public-evidence.zip)；[SHA256](KISSsoft-v014-public-evidence.zip.sha256)。
