# 找回的三份原CAD包核验

**用户记忆对应 `D:/my_Works/精翔爬梯` 的源码打包任务。FreeCAD源码已找到。** 三份原ZIP均按当前字节重新计算SHA256、对照原sidecar、检查外层CRC与关键内部文件；未执行任何安装/验证原脚本。

| 原包 | 字节 | 当前SHA256 | 核验 |
|---|---:|---|---|
| [开源CAD源码合集_20261027.zip](https://github.com/qizhou-hust/yuanqi-public/releases/download/open-source-cad-cae-2026-10-29/CAD-source-collection-20261027.zip) | 593,841,501 | `f0edde2f0fde907f7cd14ded99c86bc21a02e914e1bd3b51fa02e52ca28b1002` | PASS |
| [AI_CAD轻量包_build123d_20261027.zip](https://github.com/qizhou-hust/yuanqi-public/releases/download/open-source-cad-cae-2026-10-29/AI-CAD-light-build123d-20261027.zip) | 841,624 | `aedc23b579f2282361362ef390cf8c9eae439bf737bab65df001305c08e86f27` | PASS |
| [CAD内核_build123d_Linux_x64_Python312_20261027.zip](https://github.com/qizhou-hust/yuanqi-public/releases/download/open-source-cad-cae-2026-10-29/CAD-kernel-build123d-Linux-x64-Python312-20261027.zip) | 66,849,887 | `1f4c3c4b245dd150ed2d1c7d675f20e330e1dbc7dc68d68f2a5e9ba039ef614a` | PASS |

源码合集：12个主项目 + 25份固定提交子模块归档、25处放置映射。对37份内部ZIP重做CRC和manifest大小/SHA核对，原SHA256SUMS也逐项重验。FreeCAD主源码为提交 `1ec79da434be621d89c97287188b53b2ec2ce8a3`，同时保留OndselSolver、GSL、AddonManager、coin、pivy五个直接子模块，以及coin的cpack.d和doxygen-awesome-css两个递归子模块，共七处放置。它是源码快照，不是Windows安装版，也不是完整离线编译工具链。

| 项目 | 仓库 | 固定提交 | 源码归档字节 | 子模块位置数 |
|---|---|---|---:|---:|
| FreeCAD | FreeCAD/FreeCAD | `1ec79da434be621d89c97287188b53b2ec2ce8a3` | 91,297,226 | 7 |
| LibreCAD | LibreCAD/LibreCAD | `f37ef6b10f96434f505715841cd3712513c9365d` | 94,016,084 | 1 |
| QCAD | qcad/qcad | `f07c755ad56f63c27c6fc4fba604a33d0ed0b65a` | 96,274,003 | 0 |
| SolveSpace | solvespace/solvespace | `30e1c3ac0beb77fe3e098315b1bb662840ddc99a` | 3,991,461 | 10 |
| OpenSCAD | openscad/openscad | `e5721012999ba873f6dd74ffd89fa33f7dd11f63` | 27,668,900 | 6 |
| CadQuery | CadQuery/cadquery | `8178185a24a035c9af7f4679033be14267f6a6ef` | 8,042,239 | 0 |
| build123d | gumyr/build123d | `c49a0493ad0003ae2bf940be1d59b6d1f41d0788` | 23,877,031 | 0 |
| OpenCASCADE | Open-Cascade-SAS/OCCT | `53706f78a8640c4407bdcc6752df13a270b159f2` | 66,600,249 | 0 |
| Chili3D | xiangechen/chili3d | `03a6a542e841a7f1952f67aa729e0658a8096c08` | 11,444,458 | 0 |
| Dune3D | dune3d/dune3d | `d01faaf16f309e55834c3b93dddce5c852453cfe` | 2,086,040 | 0 |
| Truck | ricosjp/truck | `b0a38a17f44371a5bd74af05f12d119f57d82664` | 683,450 | 1 |
| replicad | sgenoud/replicad | `6ef8ae10f7cb708ec34c74b37f3be255c3c2dbc8` | 17,608,618 | 0 |

build123d轻量包：246份保留的上游源码/文字文档/示例逐文件哈希一致；不是完整仓库，也不含OCCT、NumPy、SciPy等运行依赖。原安装脚本需要联网，本次未运行。

CAD内核配套包：两份原始wheel（cadquery-ocp-novtk 8.0.1.1.0及同版proxy）SHA、大小、内部CRC均通过。仅适用于Linux x86_64、CPython 3.12、glibc ≥2.28，不含Python/pip、VTK/GUI或build123d全部依赖。原verification.json记录曾完成6000 mm³实体、STEP往返和隐藏线投影验证；这是历史记录，本次只校验文件身份，未重跑该内核验证。

三份原包应以原ZIP及sidecar直接复用，不重写原归档。CalculiX/Gmsh不是这份CAD源码合集的两个主项目，另由主路补独立运行组件。此前R25.20是另一个CADBench工程运行包，可作为次要材料；其主几何实现build123d + OCP/OCCT与“源码合集包含FreeCAD”并不冲突。

## Where This Review May Be Wrong

1. 本次未编译12个项目、安装依赖或运行原脚本；CRC/SHA通过不代表这些开发快照可在目标平台编译。
2. Git LFS指针检查保留原记录，未重新按源码语义扫描；固定ZIP哈希相同证明当前内容与原包一致。
3. 主许可证摘要不能替代第三方逐文件许可；保留原licenses、NOTICE及来源清单，未把所有子项目当作同一许可证。
