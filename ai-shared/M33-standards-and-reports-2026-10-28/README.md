# M33 标准与 KISSsoft 报告资料包

[计算问题案例库独立审查包：25例、公开基准与完整原始证据（2026-10-29）](FEA-case-library-review-r1-2026-10-29/README.md)

[TR30 例7/例8复算候选（2026-10-29，M33仍未验收）](TR30-7-8-2026-10-29/README.md)

[外部 AI 从这里开始](AI_START_HERE.md) · [本地上传 GitHub 教程](GITHUB_UPLOAD_GUIDE.zh-CN.md) · [完整 ZIP 下载](https://github.com/qizhou-hust/yuanqi-public/releases/tag/m33-evidence-2026-10-28)

- 用户提供的标准原始目录：`standards-source/`，共 21 份 PDF。
- 本轮交付成果：`evidence/`，含标准分类、TR30 补页阅读副本、5 份 KISSsoft 报告共 68 页、原生模型、JSON、脚本和验证记录。
- 外部 AI 辅助材料：`ai/`，6 份核心标准共 422 页 OCR、文件直读地址和索引。OCR 未逐字校对，公式和数值必须核查 PDF 图像。
- 文件清单：`PUBLICATION_MANIFEST.json`，包含字节数、SHA-256。

## 外部 AI 可直接读取

入口（固定发布版本）：

https://raw.githubusercontent.com/qizhou-hust/yuanqi-public/m33-evidence-2026-10-28/ai-shared/M33-standards-and-reports-2026-10-28/AI_START_HERE.md

文件目录和全部直读链接：

https://raw.githubusercontent.com/qizhou-hust/yuanqi-public/m33-evidence-2026-10-28/ai-shared/M33-standards-and-reports-2026-10-28/ai/file-catalogue.json

KISSsoft 全精度结果和计算状态：

https://raw.githubusercontent.com/qizhou-hust/yuanqi-public/m33-evidence-2026-10-28/ai-shared/M33-standards-and-reports-2026-10-28/evidence/verification/kisssoft-run-summary.json

## 已知边界

TR30 原扫描缺正文第 2 页；补页阅读副本用公开预览补入此页，原件与水印保留。ISO 6336-3:2019 含 2020-11 勘误。
五例 KISSsoft 重开复算一致，但尚未做 gearmath 公式对拍；两个 EV 案例的 KHβ 是原模型输入。K02 和 K05 存在 SH 小于 1 的结果，不能把计算成功视为强度通过。

标准与厂商材料保留各自版权，本仓库未将第三方文件重新许可为开源材料。完整来源与使用边界见 AI_START_HERE.md 和 evidence/README.zh-CN.md。

## 下载整个目录

```powershell
gh release download m33-evidence-2026-10-28 --repo qizhou-hust/yuanqi-public --pattern '*.zip' --dir .
```

Release ZIP 为固定版本；以后向 main 推送修改不会改变本次 ZIP。
