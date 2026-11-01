# gearbase Windows 便携包构建

目标：得到一个解压即用的目录（内含 python.org 嵌入式 Python + gearbase 核心包 + 三个启动 bat），用户机器无需安装 Python。

## 重要声明

- 本目录**不含任何二进制**，构建过程可下载或使用本地嵌入式 Python。Python 和 PowerShell 构建路径已在 Windows 的隔离目录实测。
- Python 版本号与 sha256 **没有内置**，必须由你到 python.org 对应版本发布页核对后传入；传入占位符或哈希不匹配都会失败。我们不编造哈希。
- 拷入范围：`gearmath/ data/ docs/ tests/ bank/ vendor/` 与根目录入口文件。总包 `00-包索引.md` 不在本包内，核心包范围以其为准，必要时改脚本顶部的 `$dirs`/`DIRS`。
- 私有资料 `data/tr30、iso18265、kisssoft、registry` 默认**不拷**（加 `-IncludePrivate` / `--include-private` 才拷）；缺少它们时依赖这些数据的测试会失败，属预期，不是故障。
- 默认精简包目前无法通过 doctor 的完整 MANIFEST 自检：它有意省略了清单要求的私有数据和 legacy 文件。需要完整自检时使用 `--include-private` 或 `-IncludePrivate`；完整包包含私有数据，仅适合有权使用这些资料的环境。构建时校验原 MANIFEST 的全部 data/legacy 哈希，按实际包内容生成独立 PACKAGE-CONTENTS；不会改动源清单。

## 用法

PowerShell：

```
powershell -ExecutionPolicy Bypass -File packaging\windows\build_portable.ps1 -PythonVersion <版本> -PythonSha256 <核对过的哈希>
```

Python 版（任意平台，仅标准库）：

```
python3 -I packaging/windows/build_portable.py --python-version <版本> --sha256 <核对过的哈希>
```

离线：先自行下载 `python-<版本>-embed-amd64.zip`，加 `-EmbedZip <路径>` / `--embed-zip <路径>`（仍校验哈希）。输出默认在 `dist\gearbase-portable\`。

## 产物

- `doctor.bat`：自检（`--full` 等参数透传）。
- `run_tests.bat`：全量测试。
- `mcp_server.bat`：MCP stdio 服务器，状态目录 `state\`；Claude Desktop 配置里 `command` 指向 `python\python.exe`、`args` 为 `["-I", "<目录>\\gearbase\\mcp_server.py"]`，见 `docs/ClaudeDesktop实连检查单.md`。

嵌入式 Python 默认带 `._pth` 文件，已隔离环境；bat 仍加 `-I`。若 doctor 提示 ccx 未找到属 WARN，FEA 为可选能力。
