# CalculiX + Gmsh 无头运行组件包

这是可复用的计算工具链附件，不是完整 CAD 应用，也不包含 FreeCAD 安装器。它包含 CalculiX 2.23 及 Linux/WSL 运行库、Gmsh 4.15.2 的 Linux/Windows wheel、Gmsh 官方源码、便携 Linux CPython 3.12 和许可/来源信息。

## 已验证的使用边界

- Linux x86_64 / WSL2：实际无头执行 Gmsh 4.15.2 和 CalculiX 2.23 单元拉伸 smoke，通过几何布尔体积、网格生成、位移和支反力检查。
- Windows AMD64 / CPython 3.12：实际无头执行 Gmsh 4.15.2 smoke，通过布尔体积和三维网格检查；CalculiX 按当前流程在 WSL2 中运行。
- Smoke 只是工具链身份/基本调用检查，不是齿轮模型验证，也不代表所有宿主 Linux 发行版兼容。

## 使用

在包根目录运行完整性检查：

```text
python -B prepare.py --verify-only
```

Linux/WSL2 需要从包外新目录准备，不修改宿主系统：

```text
python3 -B prepare.py --output ../calculix-gmsh-runtime
```

Windows 只准备 Gmsh Python wheel：

```powershell
py -3.12 -B prepare.py --output ..\calculix-gmsh-runtime
```

`smoke.py` 会在新目录建立简单几何、生成三维网格，并在 Linux/WSL2 调用 CalculiX。每次输出目录必须是新的。

## 与原 CAD 包的关系

之前的全面源码包仍是独立附件：`开源CAD源码合集_20261027.zip`，包含 12 个固定提交项目和 25 个子模块，含 FreeCAD **源码**，不是安装版。此前的 `AI_CAD轻量包_build123d_20261027.zip` 和 `CAD内核_build123d_Linux_x64_Python312_20261027.zip` 也保持原始字节，不在这里重打。

原始附件身份：

- 开源 CAD 源码合集：593,841,501 bytes，SHA256 `f0edde2f0fde907f7cd14ded99c86bc21a02e914e1bd3b51fa02e52ca28b1002`
- build123d 轻量包：841,624 bytes，SHA256 `aedc23b579f2282361362ef390cf8c9eae439bf737bab65df001305c08e86f27`
- build123d Linux CAD 内核：66,849,887 bytes，SHA256 `1f4c3c4b245dd150ed2d1c7d675f20e330e1dbc7dc68d68f2a5e9ba039ef614a`

这些原始 ZIP 已按原 sidecar、外层 CRC 和内部 manifest 重新核验；详见 `toolchain-packaging/inventory/RECOVERED-CAD-PACKAGES.md`。

## 边界

没有复制 FreeCAD 二进制、Windows 安装器、Qt 编译环境或全部 build123d 依赖。CalculiX 的 ABI 运行库和 Python/Gmsh wheel来自既有冻结资产；许可与来源见 `COMPONENTS.json`、`calculix/ GPL-2.0.txt`、wheel 内许可证和 `licenses/`。
