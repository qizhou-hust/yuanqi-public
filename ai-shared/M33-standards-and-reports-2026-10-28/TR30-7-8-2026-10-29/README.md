# TR30 例7、例8：KISSsoft 复算与逐行对拍

**M33 未验收；本包是复算候选证据，不是严格输入验收通过证明。** 用户给出的表内数值均保留；但 KISSsoft 原生修缘表示需要原表未给的长度，仍有一个明确列出的附属假设。不能将计算成功、保存重开一致、或显示精度内一致替代验收。

## 文件入口

| 案例 | 完整报告 | 高精度附录 | 原生模型 | 输入核对 | 三方逐行对拍 |
|---|---|---|---|---|---|
| 例7，双斜齿 | [PDF，14页](TR30-example-7/TR30-example-7.pdf) · [RTF](TR30-example-7/TR30-example-7.rtf) | [PDF](TR30-example-7/high-precision-appendix.pdf) · [全部变量CSV](TR30-example-7/high-precision-values.csv) | [.Z12](TR30-example-7/TR30-example-7.Z12) | [CSV](TR30-example-7/input-audit.csv) | [CSV](TR30-example-7/comparison.csv) · [JSON](TR30-example-7/comparison.json) |
| 例8，残余凸台 | [PDF，16页](TR30-example-8/TR30-example-8.pdf) · [RTF](TR30-example-8/TR30-example-8.rtf) | [PDF](TR30-example-8/high-precision-appendix.pdf) · [全部变量CSV](TR30-example-8/high-precision-values.csv) | [.Z12](TR30-example-8/TR30-example-8.Z12) | [CSV](TR30-example-8/input-audit.csv) | [CSV](TR30-example-8/comparison.csv) · [JSON](TR30-example-8/comparison.json) |

每例还包含 `run.json`（逐字段写入记录、计算状态、622 个读回变量、保存重开结果）、`validation.json`、`report.txt` 和 `relief-length-sensitivity.json`。CSV 保留 17 位有效数字；附录中的主要结果保留 12 位有效数字。厂商完整报告的显示精度未被修改。

## 主要发现

**例7硬度设置。** 材料选择 Own Input；材料类型 Through hardened steel，处理 alloyed/through hardened，质量 ML。COM：`mat.DBID=19999`、`mat.typ=2`、`mat.behandlung=2`、`mat.isoclass=1`、`mat.haerteDim=0`（界面 HBW）。齿轮1输入342，齿轮2输入300。实际齿轮模块读回：

| 输入 | KISSsoft HardnessHV |
|---|---:|
| 342 HBW | 359.810625986323 |
| 300 HBW | 315.623356128354 |

这两个点数值上等于 `HB/0.9505`，只能说明观测关系，不能据此宣称已证明厂商内部算法。安装帮助 `help/e/7674.htm` 对材料窗口转换说明引用 ISO 18265:2014 表A.1；相邻点线性插值给出 300 HB→315.555555555556 HV，与齿轮模块读回不同。本包将两条路径分别记录，未将 HB 改填为 HV。相关安装文件的哈希见 `software-reference-hashes.json`。

材料许用极限的独立性边界：例7的 `σHlim=1.313HV+188`、`σFlim=0.423HV+104` 由构建脚本按 ISO 6336-5 的 V 合金钢 ML 公式显式填入；例8按 Eh/MQ 填入1500/500 MPa。**这些极限不是本轮通过 KISSsoft 材料换算按钮独立取得的。** KISSsoft 独立计算其余几何、系数及应力；不能把本包说成材料全链独立商业验证。

**例8齿根与刀具。**

| 中间量 | 齿轮1 | 齿轮2 |
|---|---:|---:|
| YF | 1.25190846608401 | 1.27933008797541 |
| YS | 1.97878024314191 | 2.03527824455082 |
| σF0 / MPa | 291.736747613565 | 316.860306892293 |
| 刀具预加工 hfP* | 1.516 | 1.516 |
| 刀具圆角系数 | 0.4 | 0.4 |
| 凸台量 pr / mm | 0.267 | 0.267 |
| 磨削余量 q / mm | 0.220 | 0.220 |
| 残余凸台 pr−q / mm | 0.047 | 0.047 |
| 凸台角 | 10° | 10° |
| 齿面 Rz / μm | **2.3** | **2.3** |
| 齿根 Rz / μm | 18 | 18 |

齿面 Rz 保留原表2.3，未改为6Ra=2.28。刀具采用 Reference profile、`Tool.finishing=false`，齿根保持预加工状态。KISSsoft 的凸台高度坐标 `hprP=0.6325729779074764` 是依据工具几何 COM 计算将原表 `pr=0.267` 换算而来，未用任何应力输出拟合。

例8 gearmath v0.8 的 σF0₁=291.734263902652 MPa，与 KISSsoft 只差0.002483710913 MPa；两者都高于原表印刷值291 MPa。本次商业复算未消除该偏差，也不能据此断言原表错误。下一步应追溯未舍入参考值及源例的方法细节，而不是调整输入追平。

## 输入映射与尚未闭合的条件

- 原表来源是 ISO/TR 6336-30:2022 表15、表17；使用已核图的 v0.8 转录，并核对本地原表页图。例7质量等级为5/5。源阅读副本 SHA-256：`12834eabe980fd66da9a6e41881339ba0ddda0ff8222af6eec3bfc3401e7b2db`。
- 四个跨齿距全部精确读回：例7为60.068/289.367 mm，例8为35.706/118.358 mm。KISSsoft 的 Own Input 齿厚公差使用 `As=(W原表−W无侧隙)/cosαn`，上下限相同；不是以应力结果反求输入。
- 例7 KISSsoft 齿宽包括空槽：215.9 mm总宽−50.8 mm空槽=165.1 mm有效总宽；每侧82.55 mm。轴距、支承位置、齿坯内径、左右旋向、有限点蚀和质量公差均经计算后读回。
- 原表括号中的 x₂ 是派生值。例8预加工 hfP*=1.516 与 q=0.220 mm 在 KISSsoft 中生成精加工 hfP*=1.373058451548，按原表精度显示为1.373。未调这两个主输入；精加工值列为“派生值按显示精度一致”，不伪称逐位相等。
- **修缘长度仍是未闭合项：** 原表给 Ca=13 μm，未给修缘长度或曲线类型。直接设置结果字段 Ca 会被软件重算。为使原生文件保留13 μm，候选文件采用对称线性修缘、LCa=0.5mn；挠度补偿选项仍为 No。LCa=1mn 的单独复算中，例7的99项、例8的101项可映射对拍输出全部不变。此敏感性结果不能把附属假设变成原表事实，`strict_input_closure=false` 保留。
- 润滑油选择 Own Input，ν40分别为25、220 mm²/s。原表未指定的ν100、温度、胶合与微点蚀参数沿用种子文件默认，仅作附属报告内容，不能作为TR30的验证结论。
- fsh0 未从本轮商业输出中提取，保持空缺；例7半宽/总宽定义问题未关闭。

## 验证与对拍口径

两例最终计算与释放模块后的重新载入计算均返回成功，622项提取字段重开后无变化。例8首次建模计算曾返回 false、消息为空；未改输入重复计算后成功。失败尝试保存在 `run.json`，没有作为结果采信。

完整报告已检查页数、2019版次、齿根/接触应力章节与报告结束标记，并逐页检查渲染排版。COM 消息为空不等于没有界面提示：例7打开时有 fZCa建议、高线速度润滑、胶合适用域及齿轮2跨齿测量可行性提示。原表输入保留，提示不隐藏。

逐行对拍同时保留三列：TR30印刷值、KISSsoft高精度值、原公式未改的gearmath v0.8值。例8模型使用显式 `printed_rz`。严格双门 `|Δ|≤0.01 且 |Δ|≤0.5%·|参考|` 单列保留；原有显示量子规则 `q/2+min(0.01,0.005|r|)` 仅作诊断。**没有放宽判据或将 accepted 改成 true。**

按显示量子诊断，例7仍有 σFP₁/₂、σHlim₁/₂、σHP₁ 五行差异；例8仍有 σF0₁、σF₂ 两行差异。严格双门通过数为例7的75/99、例8的79/101个已提取行，其余逐行见CSV；fsh0不计入已提取分母。

## 复现

需要 Windows、已许可的 KISSsoft 2026（Z012/COM）、Microsoft Word、Python及pywin32、PyMuPDF、ReportLab。先在 `scripts/build_cases.py` 中设置安装路径，再执行：

```powershell
python -X utf8 scripts/build_cases.py
python -X utf8 scripts/finalize_reports.py --gearbase <本地gearbase核心目录>
python -X utf8 scripts/check_relief_representation.py
```

`finalize_reports.py` 使用用户私有 v0.8核心中的原表转录及公式图。本发布不另发标准扫描页、原始转录JSON或gearbase源码包。`SHA256SUMS` 为本包文件校验清单。

## 旧案例与其余工作

旧案例是 K01—K05 厂商示例，并非TR30例7/8；仍位于原目录的 `evidence/reports/`，固定版本为 tag `m33-evidence-2026-10-28`。

附件5个分包已经在本机组装。本轮另外完成 Windows cp1252 下 MCP JSON响应与KISSsoft CLI摘要输出的编码修复；本机完整回归456项通过、1项可选SciPy真实后端测试因依赖未安装而跳过，源码与私有数据保留在本地0.8.1核心包。M34证据注册、M35后续优化、FEA和MCP持久化的原待办继续保留，未宣称这些里程碑已完成，也未把M33未验收状态作为其他工作的前置阻断。
