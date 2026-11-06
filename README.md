# yuanqi-public

资料集中管理仓库。当前 GitHub 可见性为公开（public），任何人可无须授权读取 raw 链接；计算资料的复核边界见各入口文档。

## 齿轮标准与计算资料

**[标准统一资料库：所有分类、修复说明和待补清单](standards/README.md)**

- [统一外部AI读取入口](standards/AI_START_HERE.md)
- [标准完整目录](standards/CATALOGUE.md)

以下为历史资料包和计算报告：

- [M33 标准与 KISSsoft 报告](ai-shared/M33-standards-and-reports-2026-10-28/README.md)
- [外部 AI 读取入口](ai-shared/M33-standards-and-reports-2026-10-28/AI_START_HERE.md)
- [完整资料包下载](https://github.com/qizhou-hust/yuanqi-public/releases/tag/m33-evidence-2026-10-28)
- [本地文件上传 GitHub 教程](ai-shared/M33-standards-and-reports-2026-10-28/GITHUB_UPLOAD_GUIDE.zh-CN.md)

## 自研机构计算平台：外部独立审查资料包（2026-11-05）

**[外部 AI 读取入口](ai-shared/cad-cae-external-review-2026-11-05/AI_START_HERE.md)** · [审查需求](ai-shared/cad-cae-external-review-2026-11-05/审查需求.md) · [SHA256SUMS](ai-shared/cad-cae-external-review-2026-11-05/SHA256SUMS.txt)

通用平面机构计算、逆向综合与优化平台的外部独立审查包：22 个 ZIP（合计约 253.8 MiB，单包均小于 19,000,000 字节）加 7 个辅助文件，还原后为 7,698 个逻辑文件。ZIP 直接入库（单文件均在 GitHub 限制内），可被外部 AI 通过 raw 链接逐文件取用，无需授权；完整性校验用 `SHA256SUMS.txt`，还原用 `解包并校验.py`。完整性与工程能力是两件事，边界见入口文档。

## 开源 CAD / CAE 工具链

**[开源 CAD / CAE 集中索引](ai-shared/open-source-cad-cae-toolchain-2026-10-29/README.md)** · [下载全部归档](https://github.com/qizhou-hust/yuanqi-public/releases/tag/open-source-cad-cae-2026-10-29)

包含 FreeCAD 等 12 个开源 CAD 项目的源码合集、build123d 轻量源码及 OCP 内核包，以及 CalculiX/Gmsh 无头运行包。大文件通过 Release 资产分发，索引、SHA256 和验证边界保留在仓库内。
