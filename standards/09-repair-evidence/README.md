# 修复包入口

先读 ENGINEERING_REPAIR_REPORT.pdf 或 工程修复说明.md，再使用对应工程阅读本。

- ISO-TR-14179-2_ENGINEERING_READER.pdf：前置工程说明、原45页及表12位置修复。仍错乱的原页公式按前置说明使用；并非全部公式都已恢复。
- ISO-TR-14179-1_WITH_SOURCED_PAGE_ii.pdf：原正式版扫描 + 同版预览版权页ii，不使用校样内容。
- DIN-6885-1_2021-06_ENGINEERING_CORRECTIONS.pdf：依据官方公告修正两个质量数值，框出未闭合质量栏，保留2021-06身份。
- Table12_recovered.csv：原表转录，不是新算例。
- verify_repairs.py / verification_results.json：可复算的算术、热平衡示例、有限体积交叉验证。运行需要 Python 与 NumPy，命令 `python verify_repairs.py`。
- manifest.json：原始来源文件的 SHA-256、下载网址、输出清单和未确认项。

外部AI提示词：请先读工程修复说明和manifest，将A（直接恢复/官方更正）、B（工程重建）、C（替代模型）、U（未确认）分开。不要把工程修复稿称为ISO/DIN官方原版，不要把算例通过称为产品验收通过。表12在源PDF第41页，之前“内容缺失”的判断已纠正。对未确认公式不要补造系数或填默认值；明确本轮实际复算了哪些项目。
