# 开源 CAD / CAE 工具链集中包（2026-10-29）

本目录是开源 CAD/CAE 资料的集中索引。原始大包保留原文件与 SHA256，不改写归档内容；普通 Git 目录只保存目录、来源、核验和运行说明。可下载的完整归档统一放在 GitHub Release：

**[下载全部归档：open-source-cad-cae-2026-10-29](https://github.com/qizhou-hust/yuanqi-public/releases/tag/open-source-cad-cae-2026-10-29)**

## 包清单

| 包 | 内容 | 大小 | SHA256 | 说明 |
|---|---|---:|---|---|
| [开源CAD源码合集_20261027.zip](https://github.com/qizhou-hust/yuanqi-public/releases/download/open-source-cad-cae-2026-10-29/CAD-source-collection-20261027.zip) | FreeCAD、LibreCAD、QCAD、SolveSpace、OpenSCAD、CadQuery、build123d、OpenCASCADE/OCCT、Chili3D、Dune3D、Truck、replicad 及固定提交子模块 | 593,841,501 B | `f0edde2f0fde907f7cd14ded99c86bc21a02e914e1bd3b51fa02e52ca28b1002` | FreeCAD 是源码快照，不是 Windows 安装程序 |
| [AI_CAD轻量包_build123d_20261027.zip](https://github.com/qizhou-hust/yuanqi-public/releases/download/open-source-cad-cae-2026-10-29/AI-CAD-light-build123d-20261027.zip) | build123d 保留源码、文档和示例 | 841,624 B | `aedc23b579f2282361362ef390cf8c9eae439bf737bab65df001305c08e86f27` | 不含完整运行依赖 |
| [CAD内核_build123d_Linux_x64_Python312_20261027.zip](https://github.com/qizhou-hust/yuanqi-public/releases/download/open-source-cad-cae-2026-10-29/CAD-kernel-build123d-Linux-x64-Python312-20261027.zip) | build123d 使用的 OCP/OCCT Linux wheels | 66,849,887 B | `1f4c3c4b245dd150ed2d1c7d675f20e330e1dbc7dc68d68f2a5e9ba039ef614a` | Linux x86_64、CPython 3.12、glibc ≥ 2.28 |
| [FEA-CalculiX-Gmsh-runtime-2026-10-29.tar.xz](https://github.com/qizhou-hust/yuanqi-public/releases/download/open-source-cad-cae-2026-10-29/FEA-CalculiX-Gmsh-runtime-2026-10-29.tar.xz) | CalculiX 2.23、Gmsh 4.15.2、Linux Python 3.12 runtime、依赖库、脚本和 smoke 证据 | 147,207,152 B | `89a57df5b0e334d306e66dd5853c2930fe0faf528cf2c6ee2deb1368c34becd4` | 无头工具链 smoke 包，不代表齿轮模型工程验收 |

Release 使用英文附件名，中文原名保留在表格和 `CATALOG.json` 中；文件内容保持一致。下载后按 [SHA256SUMS.txt](SHA256SUMS.txt) 核验。每个归档的 sidecar 位于本目录；完整组件清单见 [CATALOG.json](CATALOG.json)、[RECOVERED-CAD-PACKAGES.md](RECOVERED-CAD-PACKAGES.md) 和 [FEA-CalculiX-Gmsh-runtime-MANIFEST.json](FEA-CalculiX-Gmsh-runtime-MANIFEST.json)。

## 下载与校验

浏览器可从上面的 Release 页面下载。命令行示例：

```powershell
gh release download open-source-cad-cae-2026-10-29 --repo qizhou-hust/yuanqi-public --pattern '*'
python verify_downloads.py .
Get-FileHash '.\CAD-source-collection-20261027.zip' -Algorithm SHA256
```

校验脚本需要 Python 3.11+，一次检查全部四包的存在性、大小和 SHA256。也可将 `Get-FileHash` 结果与 `SHA256SUMS.txt` 或 `CATALOG.json` 对比。不要把 ZIP 内容重新压缩后再比较哈希。

## 验证边界

- CAD 源码合集完成归档身份、外层/内部 ZIP CRC、内部 manifest 和路径安全核验；没有在本轮编译 12 个项目或运行 GUI。
- CalculiX/Gmsh 运行包已做 Windows Gmsh smoke 和 WSL2 Ubuntu CalculiX/Gmsh smoke；验证的是工具链调用、基本网格和线性拉伸例，不是齿轮模型的工程结论。
- 包含不同项目的许可证与来源，不能把整个合集视为单一许可证；请先阅读各项目随包的 LICENSE/NOTICE。
- FreeCAD 在源码合集内，未提供 FreeCAD 安装器或完整离线桌面运行环境。

## 来源资料

- 原始 CAD 包核验：[RECOVERED-CAD-PACKAGES.md](RECOVERED-CAD-PACKAGES.md)
- 运行包组件与哈希：[FEA-CalculiX-Gmsh-runtime-COMPONENTS.json](FEA-CalculiX-Gmsh-runtime-COMPONENTS.json)
- Linux 验证：[FEA-CalculiX-Gmsh-runtime-verification-linux.json](FEA-CalculiX-Gmsh-runtime-verification-linux.json)
- Windows 验证：[FEA-CalculiX-Gmsh-runtime-verification-windows.json](FEA-CalculiX-Gmsh-runtime-verification-windows.json)

本目录和 Release 资产用于集中管理与复核，不能替代各上游项目的许可证、构建说明或商业软件授权。

## 本次发布修复

发布前发现新运行包内的 Gmsh 源码下载在 16 MiB 处截断，已从官方地址补齐至 18,496,049 字节。重新检查 gzip 结束标记/CRC、全部 tar 成员和两个 wheel CRC，并重建运行包和 manifest；详见 [归档核验](FEA-CalculiX-Gmsh-runtime-verification-archives.json)。运行二进制、脚本和原有双平台 smoke 证据没有更改；本次没有重跑齿轮计算。
