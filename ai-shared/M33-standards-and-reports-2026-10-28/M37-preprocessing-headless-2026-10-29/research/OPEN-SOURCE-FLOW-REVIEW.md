开源 FEA 前处理流程研究与 M37 有限范围独立审计

审阅日期：2026-10-29（America/Los_Angeles）。本轮结论是：可以把现有 M37 无头流程收窄为可核验的 CPE6、指定接触卡和两步加载流程；所查 MCP 项目适合借鉴工具桥接、命名区域、检查点和求解封装，但不能替代几何、约束、载荷和结果定义的独立验证。M33、M37 的验收状态不因此改变。

证据分为三层：仓库 README / 能力审计文件属于作者声明；固定 commit 的实现属于静态源码证据；本地独立负例、代数重构和既有结果读取属于本轮验证。没有安装或运行下载的第三方代码，没有配置 MCP，没有启动新求解。本报告不宣称独立审查了全部代码或已证明通用模型正确。

**来源冻结与实际阅读范围**

45 份文本来自以下 6 个固定版本；逐文件 URL、SHA256、大小和取得时间保存在 `source-manifest.json`。`sources/` 只作本地研究缓存，不进入公开交付。Gmsh 来源明确为 `live-clones/gmsh` 镜像。

| 项目 | 冻结 commit | 阅读重点 |
| --- | --- | --- |
| Cai-aa/CAE-Agent-Hub | `56705e07ce6e99f0d5a0d0c7b5e28b6b2c0bc973` | CalculiX parser / runner；Abaqus server / precheck；HyperWorks mesh quality / profile；PyAnsys 子树身份 |
| ISCPC/PrePoMax | `4badc8bde66b6fc660eb2f6e2dfe350f5a74815f` | 接触候选搜索、接触卡导出、CLOAD / DLOAD 和 surface writer |
| Dhondtguido/CalculiX | `9e4fc4a856259ebfae0d7a2659c2c4a8030fe542` | 官方手册的 CONTACT PRINT 及 `printoutcontact.f` 的实际积分定义 |
| live-clones/gmsh（镜像） | `ffb9e4d7aad674bbfa9cf076ed480fb23275885c` | physical groups、布尔后映射、周期对应、高阶 Jacobian API 的不同保证范围 |
| nschloe/meshio | `b2ee99842e119901349fdeee06b5bf61e01f450a` | Abaqus 网格读取 / 写出和单元类型映射 |
| ansys/pymapdl | `7330f4921f3b0f7642e5d4ada7cadb5cdde5404b` | 官方 Python / gRPC API 的身份和功能声明 |

**各项目能带来什么，不能据此声称什么**

| 来源 | 可核实的实现 | 对 M37 的使用方式与界限 |
| --- | --- | --- |
| CAE-Agent-Hub / CalculiX | `FastMCP` 注册 parse / edit / run / results 工具；`extract_loads` 读取 CLOAD / DLOAD 目标、DOF 或类型及数值。[C1][C2] | 可借鉴命令桥接、原卡片局部编辑和显式 unsupported 清单。当前 parser 的结构化摘要没有完整接触、法向、间隙、合力 / 合矩验证，`_KNOWN_CARDS` 未列 CONTACT PAIR。 |
| 其 CalculiX runner | `solver.py` 检查 `*ERROR`、超时及 `.sta` 数据行或非空 `.dat`。[C3] | 代码中 `.dat` 的后备判据没有按 FREQUENCY 限定，也未证明到达目标 step/time 或排除旧输出。不能原样作为 M37 成功门。新运行应隔离目录、绑定输入与程序 hash、验证最终增量与目标时间。 |
| CAE-Agent-Hub / Abaqus | server 使用 FastMCP 桥接 Abaqus Python；2020 版 precheck 检查材料、section / assignment、实例、step、BC、load、mesh、job 等存在性。[A1][A2] | 可借鉴“生成 → 检查 → 提交”的阶段分离以及 named sets/surfaces。`至少一个 BC` 并不证明刚体自由度约束正确；现有 precheck 不是接触语义证明。 |
| CAE-Agent-Hub / HyperWorks | quality handler 读取 volume / Jacobian / aspect / skew，并保留 unavailable 元素；profile 中接触静力例子是 CGAP / PGAP 小位移夹具。[H1][H2] | 可借鉴检查点、有限实体选择和缺失质量统计；不得把 unavailable 当合格，也不能将该夹具的成功推广为齿轮曲面接触能力。ADVANCED_CAPABILITY_AUDIT 中的运行结果仅是作者声明，本轮没有运行 HyperWorks。 |
| PrePoMax | ContactSearch 先做包围盒筛选，再核三角形最近距离、相反法向、连接向量方向及允许穿透分支。[P1] ContactPair writer 明确接触方法、Small sliding、ADJUST 及 slave/master 顺序。[P2] | 接触候选必须以几何、方向和区域身份共同约束。保存是否启用 ADJUST，避免隐式移动初始面。CLOAD 写出器不代替节点力合计及作用矩校核。 |
| Gmsh | physical groups 影响默认元素导出；布尔操作返回实体映射；周期 API 要求显式仿射对应。[G1][G2][G3] | 导出前后核体和边界区域覆盖、元素数、实体 ID 映射。M37 的跨周期齿号应保留圆周对应，不采用普通整数均值选面。 |
| Gmsh 高阶质量 | `minDetJac/maxDetJac` 文档为 adaptively computed；`minSJ/minSICN/minSIGE` 为 sampled；`getJacobians` 在指定局部坐标计算。[G4] | 所有质量数字应附算法与覆盖范围。正角点面积不代表 TRI6 全域 Jacobian 正；正 Jacobian 也不代表接触压力收敛。 |
| meshio | Abaqus reader 主要解析 NODE、ELEMENT、NSET、ELSET、INCLUDE；未知 keyword 分支直接跳过。多个物理单元名映射到相同拓扑后，反向字典不能保留原身份。[M1] | 适合网格交换和可视化；不将完整 INP 经 meshio 往返作为 BC/contact/material 语义保真的方式，也不以拓扑同名宣称物理单元相同。 |

PyMAPDL 与 MCP 需要分清：官方 PyMAPDL README 描述 Pythonic MAPDL / gRPC API。[N1] CAE-Agent-Hub 的 PyAnsys 子树另外收录了 MCP 项目快照，其中 `pymechanical-mcp` 的 server 实现确有 MCP 基类、工具注册与 stdio / HTTP 运行入口。[N2] 前者不是仅凭库名就成为 MCP，后者的存在也不代表本机已安装或连通。本轮只确认源码身份，没有验证 Ansys 运行能力。

**对本地前处理门的独立检查**

已阅读 `preprocessing-work/m37-preflight/semantic_preflight.py`、`preprocessing-work/extended_preflight.py` 及 `preprocessing-work/check_before_solve.py`，并检查相关 JSON 中与审计有关的字段。基础门修复前 / 后源码 hash 和结果分别保存在 `INDEPENDENT-PREFLIGHT-CHECKS-BEFORE.json` / `INDEPENDENT-PREFLIGHT-CHECKS.json`；wrapper 的单独证据是 `INDEPENDENT-PROFILE-CHECKS.json`。这些是有限范围审阅，不能代表未列出的功能或后续代码版本。

`independent_preflight_checks.py` 只通过 AST 提取被审函数，避免执行其模块级入口和写文件行为。运行只写本研究目录；不 import 下载的第三方源码，不改原 deck、不启动求解。

| 检查 | 本轮独立证据 | 判断 |
| --- | --- | --- |
| TRI6 Jacobian 候选算法 | 根据六个参考节点插值坐标二次多项式并独立求导，分别验证标准正向 `+1`、反向 `−1`、退化 `0`、中点折叠 `−3`；100 组固定种子随机中点扰动，每组 13,041 个三角域网格点对照 | 104 个单元样本符合预期；算法最小值未高于任何独立采样最小值，最大采样差 `0.0002725806353143234`。这是浮点实现的有限验证，不是区间算术证明。 |
| TRI6 拓扑 | 两相邻正向单元的共享中点改为坐标相同、ID 不同；随后恢复相同 ID；再加造成三重共边的单元 | 中点不一致和非流形负例都被拒绝，正例通过。 |
| 载荷方向 | 在 periodic ph00 的复制件中反向所有 CLOAD | 修复前基础 `audit()` 总 pass，`abs(abs(M)-target)` 丢弃方向；主路改为有符号顺时针扭矩后，本路复测总 fail。wrapper 亦拒绝。 |
| 材料引用闭合 | 复制件增加 `E=1 MPa, ν=0.1` 的材料，并让 WHEEL section 真正引用它；另构造悬空材料引用 | 修复前错误第二材料总 pass；主路新增材料归属和逐 section 引用校核后，本路复测两负例均 fail，原 ph00 正例仍 pass。wrapper 亦拒绝。 |
| 关键字参数语义 | 仅在 step1 的预闭合 `*BOUNDARY` 加 `,FIXED` | 初版基础 parser 和 wrapper 均忽略该参数，负例 ready=true。官方 FIXED 定义冻结前步变形，首步取零，实际改变预闭合位移。[D3] 主路补充逐关键字属性白名单后，用同一负例复测，wrapper拒绝 `FIXED`；原正例仍通过。前版证据保留 `INDEPENDENT-PROFILE-CHECKS-BEFORE.json`。基础parser仍须通过profile wrapper限制使用。 |
| CLOAD 的 step 语义 | 静态阅读基础 parser | 它记录 step，但 audit 累加全部 CLOAD，未按各 step / OP 重建当前载荷。本轮未构造执行该项负例。应限于已核实的单一指定加载模板，未知扩展直接拒绝。 |
| 局部最近边 | `nearest()` 按三个节点距离选前 12 条二次边，再求驻点 | 没有保守的全域最近距离下界。能证明已找到的局部近点，不能据此证明任意曲边场景的全域最近或全域无穿透。当前 JSON 对该限制已有明确 scope。 |
| 刚体约束 | 六个平面刚体模态上的 MPC/SPC 矩阵，分 step 检查 rank 和 pinion 转动自由度 | 这是 2D 刚体模态与边界意图检查，不能称为完整刚度矩阵无奇异，也不能推广到 3D 稳定性。 |

语义负例是对检查程序拒绝能力的变异验证，并不表示现有未修改 deck 已含这些错误。旧失败证据被保留；前两项已由当前源码复测闭合。本报告不因发现门的局限而断言当前模型全部失效，也不因样本通过而宣称门已普遍正确。

本地 extended 记录中 ph09 / ph10 / ph11 的 TRI6 最小 Jacobian 均为正，且未报告共享中点冲突或非流形边。本轮独立验证了其 Jacobian 函数，没有重新求解这三个工况。ph10 的全轮初态 polygon 检查用每条二次边 4 / 8 / 32 子段，最大弧弦偏差分别约 `0.00709594 / 0.00177398 / 0.000110874 mm`，交叠面积约 `1.26e-9 / 1.32e-9 / 1.34e-9 mm²`。保留精确共享端点是必要的拓扑处理，但这个面积筛查仍不是曲边全域无穿透证明。齿端 41 点局部 signed gap 最小 `+0.0014202947 mm` 也只能描述这些采样点的初始局部关系。

**CalculiX 量的定义及守恒检查**

官方手册 CONTACT PRINT 说明 CF / CFN / CFS 是所选 face-to-face penalty 接触对从面的总力、法向力向量和切向力向量，并报告相对全局原点及接触区重心的矩。[D1] `printoutcontact.f` 给出更具体的实现：[D2]

- 从面积分点的坐标取 `co + vold`，力矩应注明当前构形及参考原点。
- 累加 `F = Σ df`、`M0 = Σ (x × df)`，随后 `M_CG = M0 − CG × F`。
- 输出 mean normal 是面积平均的法向；平均后不再单位化。最后一行 scalar normal force 是 `F · mean_normal`，不是自动等于 `Σ p dA`、`|CFN|` 或理想齿轮 `T/rb`。

因此真实自由体平衡与理想齿轮参考比较应保留为两组结果：前者比较作用于同一体、同一原点与构形的 F/M；后者比较现有理论契约，不互相替代。源代码 commit 的定义证据不等于对本机求解器二进制的版本证明，二进制版本 / hash 仍应独立记录。

`MODEL-DEFINITION-AUDIT.json` 由并行的模型定义审计提供，本报告读取并引用其结果，没有重跑或改写它：P02 原始网格的合力正确，但作用矩相对名义点的比值随网格摆动约 ±2.2%；精确截断 patch 的 d8/d12/d18 比值分别为 `1.0000000233845765`、`0.9999999703272225`、`1.0000000314910669`。这个修正只证明载荷作用矩漂移已被消除，不能解释或关闭剩余 FE/ISO 偏差。

同样，ph10 接触力矩换到 O2 后与轮孔 RF 矩的残差约 `1.5709e-5`，接触矩对输入扭矩残差约 `3.604e-5`，说明原“守恒”失败需要按量定义拆读；原理想参考误差 `0.0030085081711857054 > 0.001` 仍应原样保留失败。这里不批准改变阈值、加入低载修正或宣布 θ 假说成立。初始穿透、BC 错误尚未被证明为根因。

**建议落实的无头流程契约**

| 顺序 | 持久化内容 | 求解前 / 后的拒绝条件 |
| --- | --- | --- |
| 1. 冻结输入 | case、生成器、deck、meta、solver 版本与 SHA256；原始量及单位；CPE6 plane strain、1 mm 厚与每毫米载荷约定 | 输入漂移、未支持 keyword / 属性、单位或材料引用不闭合 |
| 2. 构造命名区域 | body / tooth / phase / face / physical group → element-side 和 node IDs；周期映射与几何依据 | 空区域、错体、重复/内部面误选、非法 side ID、覆盖缺失；不能只核名称 |
| 3. 初态与接触 | 主从顺序、法向、gap、ADJUST、接触方法和刚度；局部与全域证据分别标 scope | 局部方向错误、已证交叠、未经声明的初态调整；采样筛查不得升级为严格证明 |
| 4. 材料 / 单元 / 约束 | 实际 section→material→element 关系；TRI6 全域候选 Jacobian、共享中点；step 级 MPC/SPC 当前状态和意图 | 非正 Jacobian、失配中点、未知 body、非有限值、依赖 DOF 冲突或错误的自由刚体模态 |
| 5. 一致载荷 | 保留目标 patch 的解析区间；沿二次边截断和形函数积分；逐 step 的有符号 F/M | 合力正确但矩错误、扭矩方向错误、旧 step 载荷重复累加 |
| 6. 导出再读回 | 从最终 deck 重新得到的区域、材料、F/M、step 和接触卡摘要；与生成前意图对拍 | 生成器内存状态正确而导出卡片丢失/错序；meshio 整 deck 往返不作为替代 |
| 7. 运行和结果 | 新 run 目录、目标增量和时间、错误行、输出 hash；RF、CF 与 M 的作用体、原点、构形 | 仅有 exit code / 非空 dat / 任一 sta 行；结果来自旧运行；结果量定义未闭合 |
| 8. 比较与交付 | 真实平衡、旧理论参考门、网格/接触压力收敛、当前开放问题分别输出 | 不通过调整材料、penalty、阈值或参考量掩盖失败；3D 挤出查看只能称诊断可视化 |

扭矩方向与逐 section 材料核查已落实并通过本轮独立负例；before-solve CLI 也已实现。尚需闭合其未知关键字属性（已复现 BOUNDARY FIXED）及 step 模板语义，再核主路 32 个原始/修正相位矩阵。当前不需要为此换用未知 MCP 或重建完整通用前处理器。

公开交付限本报告、manifest 以及自写独立检查脚本/结果；第三方缓存、完整官方手册与本地临时 fixture 不自动上传。所有通过结论仅对应所列 hash 和范围。未来解析器、生成器、接触定义或阈值变更，需要重跑受影响的正负例。

[C1]: https://github.com/Cai-aa/CAE-Agent-Hub/blob/56705e07ce6e99f0d5a0d0c7b5e28b6b2c0bc973/MCP/CalculiX/mcp_server.py#L23
[C2]: https://github.com/Cai-aa/CAE-Agent-Hub/blob/56705e07ce6e99f0d5a0d0c7b5e28b6b2c0bc973/MCP/CalculiX/tools/inp_parser.py#L321
[C3]: https://github.com/Cai-aa/CAE-Agent-Hub/blob/56705e07ce6e99f0d5a0d0c7b5e28b6b2c0bc973/MCP/CalculiX/tools/solver.py#L145
[A1]: https://github.com/Cai-aa/CAE-Agent-Hub/blob/56705e07ce6e99f0d5a0d0c7b5e28b6b2c0bc973/MCP/Abaqus/mcp_server.py
[A2]: https://github.com/Cai-aa/CAE-Agent-Hub/blob/56705e07ce6e99f0d5a0d0c7b5e28b6b2c0bc973/MCP/Abaqus%EF%BC%882020%EF%BC%89/abaqus_precheck.py#L146
[H1]: https://github.com/Cai-aa/CAE-Agent-Hub/blob/56705e07ce6e99f0d5a0d0c7b5e28b6b2c0bc973/MCP/HyperWorks/hyperworks_extension/hyperworks_mcp_extension/handlers.py#L2083
[H2]: https://github.com/Cai-aa/CAE-Agent-Hub/blob/56705e07ce6e99f0d5a0d0c7b5e28b6b2c0bc973/MCP/HyperWorks/src/hyperworks_mcp/analysis_profiles.py#L862
[P1]: https://github.com/ISCPC/PrePoMax/blob/4badc8bde66b6fc660eb2f6e2dfe350f5a74815f/CaeMesh/ContactSearch/ContactSearch.cs#L356
[P2]: https://github.com/ISCPC/PrePoMax/blob/4badc8bde66b6fc660eb2f6e2dfe350f5a74815f/CaeModel/FileInOut/Output/Calculix/Keywords/ModelDefinition/CalContactPair.cs#L28
[G1]: https://github.com/live-clones/gmsh/blob/ffb9e4d7aad674bbfa9cf076ed480fb23275885c/tutorials/python/t1.py#L113
[G2]: https://github.com/live-clones/gmsh/blob/ffb9e4d7aad674bbfa9cf076ed480fb23275885c/tutorials/python/t16.py
[G3]: https://github.com/live-clones/gmsh/blob/ffb9e4d7aad674bbfa9cf076ed480fb23275885c/tutorials/python/t18.py#L36
[G4]: https://github.com/live-clones/gmsh/blob/ffb9e4d7aad674bbfa9cf076ed480fb23275885c/api/gmsh.py#L3475
[M1]: https://github.com/nschloe/meshio/blob/b2ee99842e119901349fdeee06b5bf61e01f450a/src/meshio/abaqus/_abaqus.py#L101
[N1]: https://github.com/ansys/pymapdl/blob/7330f4921f3b0f7642e5d4ada7cadb5cdde5404b/README.md#L22
[N2]: https://github.com/Cai-aa/CAE-Agent-Hub/blob/56705e07ce6e99f0d5a0d0c7b5e28b6b2c0bc973/MCP/Ansys/PyAnsys/pymechanical-mcp/src/ansys/mechanical/mcp/server.py#L102
[D1]: https://github.com/Dhondtguido/CalculiX/blob/9e4fc4a856259ebfae0d7a2659c2c4a8030fe542/doc/CalculiX.tex#L20795
[D2]: https://github.com/Dhondtguido/CalculiX/blob/9e4fc4a856259ebfae0d7a2659c2c4a8030fe542/src/printoutcontact.f#L100
[D3]: https://github.com/Dhondtguido/CalculiX/blob/9e4fc4a856259ebfae0d7a2659c2c4a8030fe542/doc/CalculiX.tex#L19361
