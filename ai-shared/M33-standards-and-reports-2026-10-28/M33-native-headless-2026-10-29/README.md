# TR30 例7、例8 KISSsoft 复算回传（2026-10-29）

**M33 未验收。** 本目录接续同级 `TR30-7-8-2026-10-29/` 的旧候选，保留全部差异，不覆盖旧证据。完整输入身份尚未关闭；下列文件是候选复算和独立诊断，不能用于宣称原表已经严格验收。

## 先看这些文件

- [独立审计摘要](PUBLIC-AUDIT-SUMMARY.md)：例7硬度换算、例8高精度齿根/凸台/粗糙度量、逐行比较结论及未闭合项。
- [例7完整报告](ex7-base-native/ex7-base-native.pdf) / [原生Z12](ex7-base-native/ex7-base-native.Z12) / [17位CSV](ex7-base-native/high-precision-values.csv)。
- [例8完整报告](ex8-Rz2.3/ex8-Rz2.3.pdf) / [原生Z12](ex8-Rz2.3/ex8-Rz2.3.Z12) / [17位CSV](ex8-Rz2.3/high-precision-values.csv)。
- [300 HB→HV设置截图](screenshots/ex7-HB300-to-HV-DIN18265.png)。材料窗口显示315.5556；模块字段315.6233561283535，两条原生路径分别保留。
- [完整运行说明](LOCAL-RUN-NOTES.md)、[完整性检查](evidence-integrity.json)、[审计检查](audit-validation.json)。

共13个有效变体、13份完整RTF/PDF（184页），每版1196个字段，并保留材料窗口生成的额外种子 `ex7-native-material.Z12`。`ex7-diag-lim` 把印刷极限当输入，十份 `ex7-life-*` 只用于寿命曲线诊断，均不能替代基线。报告显示精度由原厂模板决定，CSV保留17位读回。

例8的Ra=.38自动换算尝试不满足请求：RZFlag=0把Ra改为.6，Rz改为4.8。失败记录仅在 `research/FAILED-ex8-Ra0.38/`，不纳入13个有效变体。其它缺项及默认设置见审计摘要；没有用手工6Ra计算冒充原生换算。

## 无头复查

用户要求不占鼠标后，使用 `GetModule('Z012', False)` / silent COM，未请求显示界面；未操作鼠标或键盘。保留的截图取自切换无头之前，剩余截图要求未冒充完成。

在装有KISSsoft 2026许可证及pywin32的Windows上，可只读重开单个模型：

```powershell
python scripts/recheck_native.py ex8-Rz2.3 --output recheck.json
```

脚本不保存原生文件；`calculate_return=true`且`differences={}`只证明重放一致。保存文件的独立检查需要PyMuPDF：

```powershell
python scripts/verify_m33_evidence.py . --output verify.json
```

`run_variants.py`和`life_curve.py`保留原运行脚本及来源路径，需要旧候选、相应安装资源及本地目录布局；它们不是跨机器免配置入口。`recheck_native.py`可直接检查本目录保存的模型。

## 交付范围

公开包包含本次原生模型、厂商计算报告、实际输出、截图、自写脚本和审计摘要。完整逐行TR30转录/对拍CSV、核心源码及标准全文留在本地工作目录；此处未复制安装模板或材料UI源码。`LOCAL-RUN-NOTES.md`提到的其他探索目录只保留在本地。

`MANIFEST.json`列出内容哈希，`SHA256SUMS`包含manifest哈希。两者均不把文件完整性通过等同于工程验收。
