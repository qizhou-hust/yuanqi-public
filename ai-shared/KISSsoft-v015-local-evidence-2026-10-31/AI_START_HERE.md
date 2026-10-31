# KISSsoft v0.15 本地计算公开证据

软件：KISSsoft Release 2026，程序文件版本26.0.0.0。阶段结果：P5通过用户指定SH/SF数值阈值，其余项目有明确开放项。后续运行均为无头COM，不占鼠标/键盘。

先读 [RESULTS.txt](RESULTS.txt)、[summary.json](summary.json)、[case-index.json](case-index.json)。不要把计算成功、相近结果或文件上传当作全项验证通过；未修改gearbase接受状态。

| 项目 | 当前证据 |
|---|---|
| P5 A | [运行记录](cases/P5-A-tip-coefficient-input/run.json)、[PDF](cases/P5-A-tip-coefficient-input/P5-A-tip-coefficient-input.pdf)、[Z12](cases/P5-A-tip-coefficient-input/P5-A-tip-coefficient-input.Z12)；SH1=1.0014633877146772，SF2=1.4044681760904472 |
| P5 B | [运行记录](cases/P5-B-auto/run.json)、[PDF](cases/P5-B-auto/P5-B-auto.pdf)、[Z12](cases/P5-B-auto/P5-B-auto.Z12)；SH1=1.0005261124965774，SF2=1.4028557338294552 |
| M39 | [逐项分析与缺口](evidence/M39-return-summary.txt)；K01 RunIn0摩擦系数、K02/K05 XCa吻合；K04 XCa仍与预测不同 |
| M36 R1 | 六组截面已真实计算并全新实例重开；Rz6.3依赖[用户粗糙度记录](replay/user-database/record.json)。原生PPRPT含完整强度章节 |
| M36 R2/R3 | [反力审计](cases/R3-reaction-diagnostic/reaction-audit.json)、[基本寿命](cases/R2-6206-RZ/run.json)；0.385102329N力残差仍OPEN |
| M36 R4 | [原始方法C错误](evidence/R4-GUI-error.txt)；取消反向转矩后方法C成功；B与D.1 D2=270均有报告 |
| M36 R5 | A1-A4已输入500Nm，提供Sr与避免微滑Tlimit；完整标准等价范围有限 |

仍缺：独立FIT温度字段、FZG LS14的714.2Nm原始来源、K01/K03的-20连续曲线表、K03-K05专用油品微点蚀试验数据、M33 fsh0原生定义。可选P6未运行。

R1/R2 PDF/TXT是未改动原生PPRPT的文本可读渲染，图形保留在PPRPT；不是供应商原生PDF版式。Z012 PDF/TXT仅在渲染副本去除了泄漏的HTML表头标签，原始RTF/原生模型未改动；操作与哈希有记录。

本轮提供的stage ZIP未通过SHA256与ZIP目录校验，未解包/使用。本次使用明确请求与已有可追溯原生基准。未上传损坏ZIP、私人标准扫描或软件手册全文。

下载完整结果：[二进制ZIP](KISSsoft-v015-local-evidence-2026-10-31.zip)、[同名SHA256](KISSsoft-v015-local-evidence-2026-10-31.zip.sha256)。直接按二进制下载并核对，避免任何文本中转。ZIP内MANIFEST.sha256逐文件校验。
