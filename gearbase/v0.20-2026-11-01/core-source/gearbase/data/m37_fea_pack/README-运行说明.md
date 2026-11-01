# M37 FEA 题目包：运行说明

这个包是请您在自己的电脑上用 CalculiX 求解的 FEA 验证题目，覆盖 L0 补丁、L1 Hertz、L2 齿根 YF·YS 矩阵和 L3 直齿副刚度/接触应力四级。跑完后，把生成的一个 zip 文件发回即可。

> **如实说明：本包没有在我们的环境里求解过。** 我们的云环境不允许运行 ccx。我们已经做过的检查有：所有脚本的语法、用 gmsh 生成全部 82 个作业的网格并检查单元质量（雅可比）、生成全部 .inp 并做格式自检（关键字、集合与面名引用、节点存在、*STEP 配对）、齿形与 gearbase/ISO 参考值逐点对照（相对差 ≤ 2e-9），以及用合成 .dat 测试后处理链路。ccx 是否接受这些 .inp、能否收敛、结果是否达标，都要等您本地运行后才能知道。

## 1. 环境要求

| 项 | 要求 |
|---|---|
| Python | 3.10 或更高（Windows / Linux 均可）。脚本只用标准库加 gmsh，**不联网、不下载任何东西** |
| gmsh Python 包 | `pip install gmsh==4.15.2`，即本包验证所用的版本（4.11 至 4.15 应该都可以；网格会随版本略有差异，结果文件会记录版本号） |
| CalculiX | `ccx` 2.21、2.22 或 2.23（运行时用 `ccx -v` 检查，不在范围内会给出警告但不中断）。Windows：任何 2.21–2.23 的 `ccx*.exe` 都行，例如 PrePoMax 自带的 `Solver\ccx_dynamic.exe`、CalculiX Launcher 或 bConverged 发行版。Linux：Ubuntu 24.04 可用 `sudo apt install calculix-ccx`（2.21），也可以自己编译 |
| Linux 无图形界面时 | gmsh 的 wheel 需要几个 X/GL 库：`sudo apt install libglu1-mesa libxcursor1 libxft2 libxinerama1` |
| 磁盘 / 内存 | 约 2–4 GB 临时文件（.frd 占大头），内存 ≤ 4 GB |

## 2. 一键运行

### Windows（PowerShell，在本目录下执行）

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip install gmsh==4.15.2
.\.venv\Scripts\python scripts\selfcheck.py                      # 10 秒：不需要 ccx
$env:M37_CCX = "C:\Program Files\PrePoMax\Solver\ccx_dynamic.exe"   # 改成您的 ccx 路径
.\.venv\Scripts\python scripts\run_m37.py --smoke --threads 4    # 1–3 分钟：工具链冒烟测试
.\.venv\Scripts\python scripts\run_m37.py --threads 4            # 全部题目
.\.venv\Scripts\python scripts\pack_results.py                   # 生成回传 zip
```

### Linux（bash）

```bash
python3 -m venv .venv
.venv/bin/pip install gmsh==4.15.2
.venv/bin/python scripts/selfcheck.py
export M37_CCX=$(command -v ccx)            # 或 ccx_2.23 等的完整路径
.venv/bin/python scripts/run_m37.py --smoke --threads 4
.venv/bin/python scripts/run_m37.py --threads 4
.venv/bin/python scripts/pack_results.py
```

常用参数：

- `--ccx <路径>`：指定 ccx，优先级高于环境变量 `M37_CCX`。
- `--cases L0,L1`：只跑某几题。
- `--l2-points P01,P03`：只跑 L2 的部分点。
- `--no-mortar`：跳过 MORTAR 实验变体。
- `--timeout 3600`：单个作业的超时秒数。
- `--dry-run`：只生成网格和 .inp，不求解。
- `--force`：忽略已有结果，全部重算。

运行可以随时中断（Ctrl+C）后续跑：已经求解过、.inp 没有变、并且已有当前版本严格读取与运行身份记录的作业，会自动跳过。

**建议顺序**：先跑 `--smoke`。如果冒烟测试报错，请先把 `results/run.log` 和 `results/runs/L0/*.log` 发给我们，不必跑完全部题目。

## 3. 预计耗时（单线程估算，`--threads 4` 时约为其一半到三分之一）

| 题 | 作业 | 估计 |
|---|---|---|
| L0 | 10 个小作业 | < 1 分钟 |
| L1 | 8 个（5k–19k 个二次单元，带接触） | 5–10 分钟 |
| L2 | 42 个（4k–8k 单元，线性） | 5–10 分钟（其中网格生成约 1 分钟） |
| L3 | 22 个（27k–40k 单元，带接触，两步加载） | 30–90 分钟（其中网格生成约 3 分钟） |
| 合计 | 82 个 | 约 0.7–2 小时 |

## 4. 回传什么

运行 `scripts/pack_results.py` 后会得到 **`results/M37-results-<日期>-<主机指纹>.zip`**，请把这一个文件发回。zip 里有：

- `results.json`：汇总结果，格式见 `results-schema.json`，样例见 `results-example.json`（样例中的数值是伪造的）。内容包括题号、网格级别、单元类型与数量、网格质量、每级结果、外推值、收敛阶、penalty/相位研究、求解器版本（`ccx -v` 原样输出）及 sha256、运行时间、机器信息、警告，以及本地即时判定。
- 每个作业的 `.dat`、`.sta`、`.cvg`、`.log`，以及很小的 `.meta.json` 和 `.record.json`。有了这些，我们可以在云端重新做后处理复核。
- 默认**不含** `.frd`（体积大）和 `.inp`（可以由脚本重建）。只有在我们明确要求时，才需要运行 `pack_results.py --with-frd`。

`results.json` 中的本地判定（local_assessment）只是给您看的即时提示。正式判定由 gearbase 侧的 `ingest_fea_results.py` 根据各级原始值重新计算。

## 5. 可能遇到的情况

- **ccx 不支持 `*EL PRINT … COORD`**：脚本会自动关闭这项请求，重跑该作业，并在结果里记一条警告。这时齿根应力会用积分点最大值，通常会偏低几个百分点。这一项本身也是我们想了解的结果。
- **MORTAR 变体报错或不收敛**：这一组是实验，失败只会记录下来，不影响 penalty 路线的判定。设计文档 F1 要求在 ccx 2.2x 上实测 MORTAR，失败本身也是一个有用的结论。
- **个别作业不收敛或超时**：结果会记为 `solver_failed`，其余作业照常运行。请连同对应的 `.log` 和 `.sta` 一起发回。
- **路径含中文时 ccx 找不到文件**：个别 Windows 版 ccx 处理非 ASCII 路径有问题。可以用 `--out C:\m37out` 把运行目录放到纯英文路径下，打包时对应用 `pack_results.py --results C:\m37out`。
- **网格生成报错**：请把 `run.log` 和 `python -c "import gmsh; print(gmsh.__version__)"` 的输出发给我们。

## 6. 发算门与严格字段读取（题目包 1.1 起）

外部审查 FEA-readiness-R1 的 R02/R03/R04 在本包内的对应处理。它们只拒绝不合格的输入或输出，不改变任何物理输入、网格、参考值或验收线。

| 门 | 何时 | 不通过时 |
|---|---|---|
| STEP 状态检查（`scripts/deck_state.py`） | 每个作业建模后、求解前；`--dry-run` 也执行 | 记为 `lint_failed`（`failure=step_check_failed`），**不启动 ccx**。拒绝：过程卡在 STEP 外、同一步重复过程卡、空步、STEP 未闭合、本步约束与集中力落在同一自由度（常见于上一步位移驱动被继承而没写 `OP=NEW`）、profile 外的关键字或参数，以及经符号链接或越出 .inp 所在目录的 `*INCLUDE` |
| 运行身份（`scripts/run_m37.py`） | 准备时、启动前、结束后各算一次 INP、`<job>.meta.json`、INP 中显式 `*INCLUDE` 文件和求解器可执行文件（解析符号链接后）的 sha256 | 启动前不一致（包括可执行文件被替换）：不启动。结束后不一致：记为 `solver_failed`（`failure=input_identity_drift_postrun`），全部输出保留，不做后处理 |
| 严格字段读取（`scripts/ccx_strict.py`） | 求解成功后 | 记为 `post_failed`（`failure=strict_field_read_rejected`）。终态取 .sta 最后一条已收敛记录，按 (step, increment) 选块；覆盖由 deck 中的输出请求预先声明。缺块、终态内重复块、时刻不符、缺行、重复节点、多余节点、非有限值、空覆盖，都会拒绝。deck 请求了 .frd 输出时，.frd 必须有与 .sta 终态一致的 1PSTEP |

积分点数和接触面号映射按 (ccx 版本, 单元类型) 登记在 `ccx_strict.py` 里，是实测登记，不是手册条文：
- ccx 2.21：CPE6 每单元 9 个积分点，CPE8 每单元 27 个；接触面 S1→3、S3→5。
- ccx 2.23：接触面 S3→5。

不在表内的版本、单元类型或边号一律拒绝读取。所以用 2.22 或 2.23 跑 `*EL PRINT`（L0 补丁、L2）会被拒，要先补实测登记。

.dat 只打印活跃的接触行，无法预先确定完整覆盖，所以记录里标 `coverage_unverifiable`。由这些行得到的量要与独立通道比对：p_max 对 .frd 终态的 CPRESS（deck 需请求 `*CONTACT FILE`），L0c 压力误差对接触统计的平均压力 |Fn|/area。比对写在 `contact_crosscheck` 里，gearbase 入库时按各自原有验收线判定。不一致或没有独立通道，该级最多记为 `contact_unverified`。现有 L3 deck 没有请求 `*CONTACT FILE`，所以 σH 目前不能授予通过。

旧读取函数 `ccx_io.last_block / nodal / contact_tables` 原样保留，提取量仍由它们计算，但计算前必须与严格读取的同一块逐值一致。每个作业记录（`<job>.record.json` 与 `results.json`）新增 `step_check`、`run_identity`、`strict_read`、`contact_crosscheck`，`results.json` 顶层新增 `field_read_protocol`。gearbase 入库时，没有 `field_read_protocol`（包括 1.0 旧包）或 solved 作业缺少通过记录的结果包，整包拒绝。

已知限制：
- 运行身份是前后哈希比较，求解器在运行中改写输入、读完再改回的情况查不出来（TOCTOU）。建议改为把输入复制到只读暂存目录再启动。
- `.frd` 场值仍按旧方法读取（L1 半宽）。
- 没有写数据行的 `*STATIC`，时间段按 CCX 缺省值 1.0 计。

## 7. 目录

```
README-运行说明.md     本文件
题目说明.md            L0–L3 每题的目的、几何、材料、网格、边界、载荷、接触、提取量、验收线
cases/*.json           每题参数（脚本只从这里读取）
expected/*.json        参考值：L0/L1 用解析解；L2/L3 由 gearbase 公式图实算，附公式链与标准条款
results-schema.json    回传格式
results-example.json   回传样例（伪造数据）
scripts/
  run_m37.py           一键运行（建模 → 求解 → 后处理 → 外推 → results.json）
  selfcheck.py         不需要 ccx 的自检（--mesh 时还会生成全部网格）
  pack_results.py      打包回传 zip
  gear_geom.py         展成齿形（渐开线 + 刀尖圆角包络），30° 切点实测
  mesh_gmsh.py         gmsh 二维二次网格与质量统计
  inp_writer.py        .inp 生成与格式自检
  cases.py             各题建模与单作业后处理
  study.py             作业清单、收敛 / 外推 / 相位汇总、本地判定
  post.py              主应力、积分点外推、Richardson、penalty 外推、Hertz
  ccx_io.py            调用 ccx，解析 .dat / .frd / .sta
  ccx_strict.py        严格字段读取（终态以 .sta 为准；预先声明覆盖；积分点/面号注册表；与 ccx_io 并列）
  deck_state.py        受限 STEP 状态机（过程卡、BC/CLOAD 继承与 OP=NEW、profile 外语法拒绝）
```
