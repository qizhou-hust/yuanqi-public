# 外部独立审查包 · 外部 AI 读取入口（2026-11-05）

主入口：https://github.com/qizhou-hust/yuanqi-public/tree/main/ai-shared/cad-cae-external-review-2026-11-05

直接入口（raw，单文件直取）：https://raw.githubusercontent.com/qizhou-hust/yuanqi-public/main/ai-shared/cad-cae-external-review-2026-11-05/AI_START_HERE.md

本目录是“通用平面机构计算、逆向综合与优化平台”的**外部独立审查资料包**，不是新产品发布，也不是已冻结产品的验收声明。

## 这个包是什么

- 22 个 ZIP 承载：原始需求、精选原始模型、代码、固定回放脚本、历史日志、作者说明。
- 7 个辅助文件承载：需求文档、运输哈希、包清单、新鲜验证结果、一键解包脚本、目录页。
- ZIP 之间按内容哈希去重，必须整组使用；单独解压某个数据包不能运行工程。

## 这个包不是什么

- 完整性 PASS 不等于工程能力 PASS。
- 包内 `FINAL` / `FROZEN` 命名、作者说明、既有测试数量、作者报告，都不是正确性证明。
- 不含 Python / Node 运行时、`node_modules`、JAX 环境、浏览器二进制；缺环境不等于算法失败。
- 损坏的 Fusion 原件按原始字节保留，是待审证据，不是可用程序。
- 3,751 条历史索引记录未全部包含；收录的是 36 份精选原始资料。

## 三步取用

### 1. 下载全部 29 个文件

Bash / Linux / macOS，在空目录中执行：

```bash
base="https://raw.githubusercontent.com/qizhou-hust/yuanqi-public/main/ai-shared/cad-cae-external-review-2026-11-05"
mkdir -p review-package && cd review-package
# 辅助文件（中文名需 URL 编码，用 python3 编码后再取）
for f in "解包并校验.py" "SHA256SUMS.txt" "PACKAGES.json" "PACKAGE_VERIFICATION.json" "README_先读.txt" "审查需求.md" "审查包目录.html"; do
  enc=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$f")
  curl -fsSL --retry 3 -o "$f" "$base/$enc"
done
# 22 个 ZIP（真名均为 ASCII，直接按 SHA256SUMS.txt 第二列取）
awk '{print $2}' SHA256SUMS.txt | while read -r z; do curl -fsSL --retry 3 -O "$base/$z"; done
```

Windows PowerShell，在空目录中执行：

```powershell
$base="https://raw.githubusercontent.com/qizhou-hust/yuanqi-public/main/ai-shared/cad-cae-external-review-2026-11-05"
$pkg=(Invoke-RestMethod "$base/PACKAGES.json" -UseBasicParsing)
$names=@($pkg.archives.name) + @("解包并校验.py","SHA256SUMS.txt","PACKAGES.json","PACKAGE_VERIFICATION.json","README_先读.txt","审查需求.md","审查包目录.html")
foreach($n in $names){ Invoke-WebRequest "$base/$([uri]::EscapeDataString($n))" -OutFile $n -UseBasicParsing }
```

说明：raw 直取单文件上限 100 MB，本包最大单包 18,795,467 字节，全部可用 raw 直取；中文文件名需 URL 编码。完整克隆仓库亦可，但仓库体积远大于本包。

### 2. 校验

```bash
sha256sum -c SHA256SUMS.txt     # Linux / macOS
```

```powershell
# Windows：按 SHA256SUMS.txt 逐条比对
Get-Content SHA256SUMS.txt | ForEach-Object { $h,$n = $_ -split '\s+',2; $a=(Get-FileHash -LiteralPath $n.Trim() -Algorithm SHA256).Hash.ToLower(); if($a -ne $h){"FAIL $n"} }
```

### 3. 解包还原

```bash
python 解包并校验.py --output REVIEW_UNPACKED
```

只用 Python 标准库，无需 7-Zip，无需手工合并分卷。推荐 Python 3.12，最低 3.11。脚本会核对每包 SHA256、片段与原文件 SHA256，并按相对路径还原全部 7,698 个逻辑文件（4,087 个唯一对象，3,611 条去重路径）。必须使用空输出目录。

## 还原后按此顺序读

1. `REVIEW_UNPACKED/review/USER_REQUEST.md` —— 原始需求与用户追加确认。
2. `REVIEW_UNPACKED/materials/optimizer/` —— 用户最初三份 Markdown、案例原始模型和其他精选原件。
3. `REVIEW_UNPACKED/cases/spoiler_ab_ideal_100N/` —— 源模型、问题表、显式驱动覆盖。
4. 代码、固定回放脚本、原始日志。
5. 最后再读 `三页讲清楚.html`、`整合蓝图.html` 和三份 `*_audit.md`，与独立判断交叉核对。

审查问题清单与报告格式见 `审查需求.md`（与 `00_START_HERE.zip` 内需求同源）。

## 完整性重放（可选，先只跑确定性模式）

```bash
python REVIEW_UNPACKED/review/REPLAY_REVIEW.py --mode fast     # 便携入口
python REVIEW_UNPACKED/review/REPLAY_REVIEW.py --mode core     # 固定数学
python REVIEW_UNPACKED/review/REPLAY_REVIEW.py --mode torque   # 扭矩
python REVIEW_UNPACKED/review/REPLAY_REVIEW.py --mode web      # 产品重放
```

依赖见 `REVIEW_UNPACKED/requirements-audit.txt`；`core` / `torque` 另需 JAX。不要直接使用作者的 `runtime_environment.local.json`（其中含作者机器绝对路径）；便携入口可用 `--python 你的解释器` 指定。

## 文件清单

ZIP 共 22 个，合计 266,087,921 字节（约 253.8 MiB）；全目录 29 个文件合计 266,117,194 字节。

| 文件 | 字节 | 说明 |
|---|---:|---|
| `00_START_HERE.zip` | 1,155,366 | 00 入口：清单、需求、工具、验证日志 |
| `01_DOCS_EVIDENCE_01.zip` | 3,859,375 | 01 文档与证据 |
| `02_ORIGINALS_01.zip` | 13,128,693 | 02 精选原始资料（必须整组保留） |
| `02_ORIGINALS_02.zip` | 15,462,142 | 同上 |
| `02_ORIGINALS_03.zip` | 16,634,491 | 同上 |
| `02_ORIGINALS_04.zip` | 6,857,799 | 同上 |
| `02_ORIGINALS_05.zip` | 16,949,528 | 同上 |
| `02_ORIGINALS_06.zip` | 17,005,428 | 同上 |
| `02_ORIGINALS_07.zip` | 17,005,411 | 同上 |
| `02_ORIGINALS_08.zip` | 16,629,885 | 同上 |
| `02_ORIGINALS_09.zip` | 16,906,326 | 同上 |
| `02_ORIGINALS_10.zip` | 16,949,528 | 同上 |
| `02_ORIGINALS_11.zip` | 17,005,428 | 同上 |
| `02_ORIGINALS_12.zip` | 17,005,411 | 同上 |
| `02_ORIGINALS_13.zip` | 4,315,760 | 同上 |
| `02_ORIGINALS_14.zip` | 16,636,936 | 同上 |
| `02_ORIGINALS_15.zip` | 7,072,968 | 同上 |
| `03_WEB_B8_01.zip` | 11,835,775 | 03 产品 B8 证据 |
| `04_WEB_BASELINES_01.zip` | 7,823,445 | 04 基线对比 |
| `05_CORE_OPT_GUI_01.zip` | 3,884,173 | 05 核心优化与 GUI |
| `06_SYNTHESIS_CAM_01.zip` | 18,795,467 | 06 逆向综合与凸轮（最大单包） |
| `06_SYNTHESIS_CAM_02.zip` | 3,168,586 | 同上 |
| `审查需求.md` | 5,145 | 审查问题清单与报告格式 |
| `README_先读.txt` | 1,524 | 最短上手说明 |
| `SHA256SUMS.txt` | 1,928 | 22 个 ZIP 的运输哈希 |
| `PACKAGES.json` | 3,913 | 包清单、字节数、哈希、去重统计 |
| `PACKAGE_VERIFICATION.json` | 8,622 | 发布时的新鲜解包与重放结果、限制声明 |
| `解包并校验.py` | 3,848 | 一键还原脚本（标准库） |
| `审查包目录.html` | 4,293 | 带相对链接的目录页 |

## 读取时必须保持的边界

- 每包严格小于 19,000,000 字节；01 至 06 是数据对象包，必须整组保留，不要按需只解一个。
- 去重采用内容哈希，因此不能仅解压某个数据包就运行工程，应使用一键还原脚本。
- 已有报告、已知失败和损坏原件均保留；完整性 PASS 不等于工程能力 PASS。
- 不把缺环境（JAX / Node / 浏览器）误判成算法失败，也不要隐去安装失败。
- 不在原始 archive 或 materials 上修改；工程计算会写输出，请保存初始 manifest 与日志。
