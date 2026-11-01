# CHANGELOG

## v0.20（2026-11-01，M33 指认几何项收口与真实 FE 矩阵）

- **M33 数值门推进至3/4**：按用户对例7/8八条历史几何差异的本轮指认，当前模型8/8相对误差≤1%（最大0.004751%）。门3明确限定这一几何数值范围；不声称恢复旧2/6、不声称全齿轮族或完整E4通过。原严格1e-6门、原表输入身份、硬度、fsh0与例8应力条件保持。原生最终齿条诊断64条映射为56个唯一量（50公式、2数值方法、4输入），不虚增独立检验计数。当前重算、源/参考/生产者哈希和反例检查参与统计。
- **M37 实际执行**：精确获准ccx2.23完成预先固定14点×3网格42个L2作业，原始字段与提取量通过严格重贴复核并recorded；原验收线下仅9/14点通过，L2及M37不记通过。额外P02加密、P03/P08保力保矩控制、直齿L3三个网格的只改输出派生试算均保留独立源和原始数据；后者尚缺罚刚度/相位研究及下级资格，不充当斜齿或完整L3验收。
- **严格入库修复**：显式测量配置支持确定哈希的2.23/CPE6；默认规范读取器不放宽。额外输出文本篡改、STA/INP/元数据身份、版本与算例错配、缺失力平衡字段均拒绝。修复负观测阶被取绝对值及不等比网格Richardson公式错误，采用有记录的假定阶回退；原题目包脚本保持，旧错误算法凭据保留为历史文件。
- **M35 准备材料**：生成K02来源参数表、尺寸包络SVG、空白审阅表和确定性完整性验证；修复SVG仅CSS导致部分渲染器黑填充/文字重叠，已在PyMuPDF检查。明确没有生成变位齿廓/产形齿根，缺制造输入与真实工艺签署，原门保持开放。
- **M38 评测修复**：金标文档的compiled类别与工具pass_pending_human_confirmation在评分时明确对应，真实待人工确认状态不变。新增空白40题表单与完整来源/逐题签名日期/独立声明导入，拒绝删题、改文、改来源、非有限数和未实现自定义评分。真实题库不填答案、不改金标；工程师金标门仍开放。
- **交付纪律**：VERSION实际升0.20、CHANGELOG同步；原81文件、18个既有内核Python与真实金标保持字节不变。Claude实连继续暂缓，M40不解冻，C001/H2真实参数及油品/热边界不补默认。

## v0.19（2026-11-01，外部软件待办与求解器来源收口）

- **版本与交付**：由已校验的 v0.18 base64 二进制恢复包派生，版本实际升至 0.19；本条记录与新增代码同轮交付。原 81 项源文件、18 个既有 kernel Python 文件和工程师金标保持字节不变。
- **A11 关闭**：直接下载 dhondt.de 官方 ccx 2.23 归档，归档 SHA256 `35d426fe…355dd`、可执行文件与 vendor SHA256 `31be21fc…58862` 一致。登记精确字节许可和可复核证明；本轮未执行求解器，不提升 M37 数值门，也不追改此前执行顺序。
- **渗氮与 DIN 3967**：新增显式 NT/NV 长寿命、齿根缺口敏感性/粗糙度/尺寸分支；逐轮显式 DIN 代号按当前直径查表并传入现有 A_sn_i→xE 路线。适配器在直径台阶附近阻断不可微域，局部导数不代表跨台阶全局最优。旧默认契约与历史存档保留。原图页码、完整文件哈希和适用域见源核查记录。
- **K02 新商业取证**：KISSsoft 2026 静默运行原优化 Z12，不改输入；计算、保存、重载计算均成功，读回无差异。回传 TXT、原生文件及 run.json。组合诊断四安全系数相对差均 <0.014%；齿根表面完整性仍为显式假设，不作整族外部验收。
- **M36 收据**：只绑定受控重放的静态传递模块、相关 schema/注册表、探针及证书身份。相关改变失效、无关 Python 改动不失效；新增依赖会纳入。反射/新增运行时文件读需要重新审查。M39 原身份策略不改。
- **最近可行编辑**：新增只读 MCP nearest_feasible_edit；显式有限组合、目标、四项 pass 约束与精确十进制权重，按改变记录 ID 的加权代价排序、保留全部精确并列，逐次重新校核，不自动应用、不授予写入 token。独立全枚举和真实 stdio tools/call 对拍。
- **架构与独立性修复**：把继承的旗舰产品层公式移入 L2，修复独立校核复用生产力公式的反例；禁止物理输入叶子空白来源通过有限优化/编辑检查。原有静定/梁输出保持。
- **梁接口**：增加 Euler–Bernoulli 中心斜率乘齿宽的有符号分量与外部明确给出的扭转位移接口；这仍不是完整 f_sh、Method B 或 KHβ，缺分布扭矩和其他柔度模型，不默认反馈评级。
- **里程碑**：A11 作为外部子任务关闭；不将这些实现伪写成整项里程碑关闭。Claude 实连继续依用户决定暂缓，M38 独立工程师金标、真实 C001/H2 参数、M39 油品/边界及 M37 数值门仍保留。

## v0.18（2026-11-01，外部系统层推进 + O 复核与第 6 波）

本版 = 外部"v0.17 系统层推进"完整包（托管 CI 41279541808，功能提交 f1eda618；外部包 VERSION 仍为 0.17、未写 CHANGELOG，此处补记）+ O 复核 + 两路新增。全量 1307 项通过（1266 + SYSREG 31 + K02GAP 10；skipped=6）。M33、M37 仍未验收。

**外部系统层推进（补记）：**M36 第 2 条门（齿轮—轴—轴承 27 组合联合优化与独立全枚举一致，8 可行，排序/并列/最优一致）；产品轴系经 drivetrain 统一后端；ISO/TR 14179-1 显式热平衡路线接入 design_check；ISO/TS 6336-22 斜齿 XY（11.4–11.9，K02 七点 ≤1e-12）；FEA 准备（8 个 L2/L3/ph10 作业声明；以 vendor ccx 2.23 对合成 CPE6 片验证积分点 1–9，独立 opt-in 读取配置）；既有 KISSsoft 证据 176 个哈希核验，K04/K01 预测 1e-4 内，K02 SH2 偏差 −1,108 %（部分归因）。

**O 复核：**
- 版本号：外部包内容变化但仍为 0.17 → 升 0.18。
- FE 探针所用求解器为 `vendor/fea/.../ccx_2.23`（sha256 31be21fc…），即此前交接规则"不执行外来预编译 ccx"所指的那一个。其来源记录指向 dhondt.de 官方归档并给出归档哈希，但本环境无法访问该站核验。登记为外部待办：由用户下载官方归档核对哈希后，正式把该二进制列为允许的求解器（或改用 Ubuntu calculix-ccx 重做探针）。
- M36 第 2 条门收据绑定全部 gearmath 源码哈希，本轮代码改动使其失效；已按当前代码重跑 system_closure，27 组合、8 可行、最优 original/economy/original（206968,124 mm³）与原收据一致，刷新 implementation_sha256。（注意：此收据设计使任何代码改动都需重跑，后续可改为只绑定相关模块。）

**SYSREG（M36 门 3 + 梁后端）：**
- 新增 `gearmath/product/flagship_system.py`：H2/W2W/P2 编译为系统问题模板（齿轮副 + 轴 + 轴承 + 键），参数只来自原 Stage0 候选、原始需求与显式声明，缺项留空。门 3 改为探针判定（不再手写）：编辑用例 6/6 通过且 Stage0 共同部分逐位一致，但三旗舰系统级均 blocked（H2 缺 93 项工程参数；W2W/P2 另受 M40 冻结的蜗杆/行星强度模型限制）→ 门 3 保持 partial。
- 梁后端产品化：系统层输入新增显式 `shaft_model = statically_determinate | beam`（无默认，旧输入逐位不变）；beam 路线需显式 E、G 或 ν、剪切模型；三支承超静定、挠度/转角、KHβ 接口桩数据（只报告不回馈）。
**K02GAP（K02 外部复核偏差归因）：**
- 根因：f_Hβ5（ISO 6336-1 式(55) 的 5 级公差）被错误保持为 6,0 µm（理由误写为 DIN 3961），KISSsoft 按几何取 6,5 µm → K_Hβ 偏低 2,68 %。用已核 ISO 1328-1:2013 式(10) 计算与 KISSsoft 逐位一致。替换实验四项安全系数对数分解残差 ≤1e-15。
- 修复：新增显式适配选择器 `adapter.f_Hbeta5 = iso1328_grade5`（无默认），K02 启用；修复后 S_H1 差 +4,7e-5、K_Hβ 差 +4,6e-5；S_H2 余差 +4,6e-4 归因于保持的渗氮钢 Z_NT_2；S_F1 余差 +1,2 % 归因于未实现的 DIN 3967 齿厚公差。K02 重跑最优点不变，新预测 S_H2 0,95064（≥0,95）。
- 既有快照更新：`tests/theta_iteration_forward_baseline.json` 中 K02 三行前向值随修复变化（本库自身快照，非参考值）。
- `VERSION` → 0.18。

## v0.17（2026-11-01，外部多里程碑收口 + O 复核）

本版 = 外部"多里程碑收口"私有完整包（gearbase-v0.16-multi-milestone-closure，托管 CI 运行 41266599287，源码提交 ffd95397）+ O 复核修复。全量 1234 项通过（skipped=6，本环境无 SciPy/pymoo）。

**外部收口内容（原包未写 CHANGELOG，此处补记）：**M32 门全部达成（M31 旧测试 73 模块经兼容层回归 678/678，Ubuntu/Windows 托管 CI）；M33 原型 22 项中 20 项为公式、C001 新旧链 18 项差异解释；M34 真源所有权、120 项 AD/FD、H2 旗舰同域同排序且评估次数降 97,37 %；M38 原 40 题数字追溯（规则 721/Terra 681/Sol 684 个数字不可追溯 0）、三旗舰真实 MCP 流程、全新 Windows VM 3 秒接通、首轮多模型报告；M39 同源三目标有限前沿（12 点 9 可行）与公差情景报告。内核新增不动点导数策略（implicit/finite_iteration）、units 增 mm/min、兼容层 gearmath/compat/m31。

**O 复核修复：**
- **版本号冲突：**外部包与 O 的 v0.16 阶段包同为 0.16 但内容不同 → 升为 0.17。
- **M38 第 1 条门口径：**外部把门名改为"原40题数字追溯口径"并判 done；顶层设计原文为"凭空数字率为 0（金标评测）"。已恢复原文门名；数字追溯已达成，但 bench v1 仍有 42 处 pending_engineer_label，金标完成前判 partial。M38 由 4/4 改为 3/4 + 1 partial（milestones.py）。外部证据文件与 output/m38/closure.json 不改（其 number_traceability 为真是事实）。
- **存档确定性：**优化写回文档的来源串不再内嵌包版本号（求解器身份由内核源码指纹确定，包版本仍记在运行报告），以后升版不再使写回文档 sha256 失配。按新口径只重生成当前内核存档 `output/m34/m32-kernel-replay/K01-spur-recompute-local`（最优点与状态不变）；`output/m34/opt3/` 是外部有意保留的历史内核存档（测试要求其被拒绝提交），原样保留。
- 新增 `docs/外部任务清单-v0.17.md`：需外部完成的事项、交付物与验收标准。
- `VERSION` → 0.17。

## v0.16（2026-10-31，阶段包 4）

KISSsoft v0.15 回传入库；第 5 波四路合入。测试 1100 项全部通过（991 + EXTM36 29 + EXTP5 20 + OPT3 35 + SYS 25；skipped=6）。M33、M37 仍未验收。摘要：`docs/分路报告/v0.16/`；运行请求：`docs/KISSsoft运行请求-v0.16.md`。

- **M34 优化器外部闭环通过（P5）**：写回文档预测与 KISSsoft 相差 ≤1,45e-5。design_store 父哈希链、MCP 受控写工具 optimize_and_commit（默认不列出）、齿顶缩短显式选择器、K02/K04 优化、ε-约束两目标前沿（K01）、统一优化报告。
- **统一核算主线（SYS）**：gearmath/product/design_check（9 个子检查）、结果与输入 schema、中文报告、MCP design_check、里程碑自动统计工具。
- **M36**：DIN 743 全系数与 KISSsoft 逐字段一致，差异归因到 KISSsoft 力残差；ISO 281、DIN 6892、DIN 7190 新增 E5 共 35 条；drivetrain_check 轴系统一入口。
- **M39**：-20 μm 链升 E5（跑合 0,6·Ra 证实）；K04 XCa 差异归因到 Ca/Ceq 口径（OPEN）。
- **既有测试改动**：test_m36_kisssoft_v014 两处、test_m39_kisssoft_v014 E5 集合（均为证据升级的必然结果）；合并修正 test_m36_kisssoft_v015 目录清单。
- 打包时发现：优化写回文档内嵌包版本号，版本号改为 0.16 后 OPT3 存档运行的候选 sha256 失配（确定性测试失败）。已在 0.16 下重跑全部 OPT3 存档（K01×2、K02、K04、Pareto、齿顶缩短回归、store 演示），最优点与状态与 0.15 存档完全相同，仅 sha256 随版本变化。TODO：存档确定性比较应排除版本字段，避免每次升版重跑。
- `VERSION` → 0.16。

## v0.15（2026-10-31，阶段包 3）

KISSsoft Release 2026 本地运行证据（P1–P4）入库并对拍；第 4 波四路合入。测试 991 项全部通过（892 + OPT2 19 + EXTB 34 + EXTC 40 + M33D2 6；skipped=6）。M33、M37 仍未验收。报告：`docs/分路报告/v0.15/`；新运行请求：`docs/KISSsoft运行请求-v0.15.md`。

- **外部证据：**`data/kisssoft_v014/`（14 个最小 JSON，私有，带来源 sha256）。用户提供的证据中标为诊断/失败/OPEN 的未作参照。
- **M34 优化器：**P2 外部复核发现 v0.14 优化解在 KISSsoft 中 SH1 = 0,99497（不可行）。对账：主因为证据区系数保持原设计值、d_inner 未更新、齿顶缩短；输入对齐后本库与 KISSsoft 安全系数一致到 1,5e-5。修复为系数随设计变量重算（factor_recompute），hold 项须逐项给理由。新 K01 最优 b 28,6、x1 0,449（SH1 1,00147）。新增 MCP 只读工具 optimize_declared。
- **M39：**-21 积分温度法 K01–K05 全中间量与 KISSsoft 逐位一致；-22 K01/K02 逐点一致；-22 方法 B pdyn,Y 与直齿 XY 新增；-20 θfl 有 −6,2 % 未闭合差异。55 个公式证据升 E5（模块元数据）。
- **M36：**DIN 7190-1 A2/A4 与 KISSsoft 逐位一致，与附录差异全部归因；轴系力定义一致；新增 DIN 6892 方法 B、刚度法超静定梁（挠度/转角）、ISO 281 推力轴承。
- **M33：**D2 外部证据——fsh、KHβ 与 KISSsoft 一致，但不能判别 fsh0 符号口径，仍为有条件。
- **模块 A（FEA-readiness）：**0.2.0 重建（wheel、MANIFEST、PACKAGE-ORIGIN 锚定 extractor 哈希），23 + 47 项测试与 audit verify/core 通过；单独交付。
- **既有测试改动：**`test_m39_tribology.test_refs_checked_and_evidence_null` 允许白名单 E5（证据升级的必然结果）。合并修正：`test_m36_kisssoft_v014` 目录清单只看 P4-*。
- **交付注意：**用户反馈 v0.13/v0.14 ZIP 在其传输链中被按文本转换（出现 EF BF BD）而损坏；本地原件完好（v0.13 sha256 1815f5ad…）。本版起每个 ZIP 附 .sha256。
- `VERSION` → 0.15。

## v0.14（2026-10-30，阶段包 2）

第 3 波四路合入。测试 892 项全部通过（800 + M33 13 + OPT 16 + M36 38 + M39 25；skipped=6）。M33、M37 仍未验收。报告：`docs/分路报告/v0.14/`；外部对拍需求汇总：`docs/KISSsoft运行请求-v0.14.md`。

- **M34 优化器主线（OPT）：**声明式问题（kernel/declared.py，与齿轮无关）+ 区间剪枝格搜索（kernel/gridprune.py）+ 精确梯度 NLP/KKT + 写回真源 v2 + 统一校核复核，C001、K01 端到端闭环（C001 剪枝 703/760，与全域穷举逐位一致）；H2 旗舰几何层最小回归。新增 4 条 `opt.s_an*` 齿顶法向齿厚公式（not_in_evidence，evidence null），注册表已重导。声明中的搜索域与下限为代理提议，待用户确认；evidence 区系数为"保持"，待 KISSsoft 复核（P2）。
- **M36 系统层：**轴系两支承静定模型 → DIN 743 → ISO 281；DIN 6892 方法 C + DIN 6885-1 表1；DIN 7190-1 纯弹性。DIN 7190-1 附录 A、DIN 6892 附录 D 算例逐步复现。DIN 6885-1 表2 整表阻断。
- **M39 失效模式/热：**ISO/TS 6336-21 积分温度法闭环；-20 闪温法、-22 微点蚀、ISO/TR 14179-1 热平衡、DIN 3967 侧隙为骨架。14179-2 工程阅读本一律阻断。证据等级 null。
- **M33：**落实用户 2026-10-30 决定 D1–D8（见验收报告第 8 节）。例7 决定后 95/3，例8 98/2/0。凸台 dFf 以显式选择器接入主图（不选时逐位不变）。**M33 仍未验收**；剩余：HB→HV 口径（用户未表态）、fsh0 待 KISSsoft 确认、扩展严格几何门 2/6 明细等。
- **V2 二次复核：**F1、M34 可合入（已在 v0.13）；模块 A（F3）可合入，前提为锚定 extractor 哈希（A 包 MANIFEST/wheel 待重建）。建议 T_1 守门接入 model_from_doc。
- 注册表：`formulas-v1.json`、`assessments-v1.json` 新增 opt.s_an* 条目；MANIFEST 登记 `data/optimize/` 三个声明。
- 无既有锁定值或既有测试改动。
- `VERSION` → 0.14。

## v0.13（2026-10-30，阶段包 1）

多路编排第 1、2 波合入。测试 800 项全部通过（665 + F1 76 + M34 11 + M38 11 + S36 37；本环境无 SciPy/pymoo，6 项可选跳过）。M33、M37 仍未验收。**F1、M34 返工后尚未经 V 二次复核**，F3（模块 A）不在本包内，单独交付。各路报告：`docs/分路报告/v0.13/`。

**F1（FEA 资格门，审查 R02/R03/R04 + 入库门）：**
- 新增 `data/m37_fea_pack/scripts/ccx_strict.py`（READER 1.1）：字段块绑定 run/输入/step/inc/time/field/region/location/components，终态以 .sta（及 .frd PSTEP）为准，预声明覆盖；缺块/重复/冲突末态/时刻不符/非有限一律拒绝；积分点数按 (ccx 版本, 单元类型) 预注册（仅 ccx 2.21 CPE6=9、CPE8=27，F2 实测）；接触面号显式映射表（实测，非手册条文）；接触行覆盖标 coverage_unverifiable，p_max 等须与 .frd CPRESS/接触统计交叉核对。旧 `ccx_io.py` 保留不改。
- 新增 `scripts/deck_state.py`：受限 STEP 状态机（STEP 外过程卡、重复过程、空步、未闭合、跨步继承冲突、profile 外语法、符号链接/越界 include 均拒绝）。
- `run_m37.py`：准备/启动前/结束后三次身份（INP、meta、include、求解器可执行文件），漂移记失败并保留输出；发算前状态机、发算后严格读取。题目包 PACK_VERSION 1.1。
- `fea_ingest.py`：新增 verdict `rejected_field_read`。**无严格读取协议的结果包一律拒绝（含 pack 1.0）**；`tests/test_fea_ingest.py` 仅将夹具路径改为新建的 1.1 合成夹具，18 项断言一字未改；原 1.0 夹具保留并作为负例。现有门限、ACCEPT、accepted 逻辑未改。

**F2（云端 ccx 2.21 L0/L1 重放，诊断）：**Ubuntu calculix-ccx 2.21-1（sha256 6adaabf5…a1b）。L0+L1 共 18 作业：13 solved、5 MORTAR 全部 `catsmpcslavno` 失败（只记录现象）。严格读取 13/13 接受，三次身份 18/18 一致（R04 最小真实 job）。d8 峰值 849.1894 与冒烟逐位一致；与 R1 读数差 1e-6–5e-6 相对，来源无法确认。入库 verdict=recorded，L0/L1 passed，标注"L1 诊断，未验收"。结果包不在核心包内（见阶段输出 F2 目录）。

**M34：**K01–K05 转为 `gears.math-source/2`（`data/source/K0*.math-source.json`、`gear/math_source_kisssoft.py`），全部输入与 >50 个输出与 K 链逐位相等。T_1（P/(2πn₁) 派生量）置于 evidence 区并带 tool_calculation 证书，守门测试从证书文件重算并逐位比较，只改 n₁ 不改 T₁ 即失败。残余：守门只在测试中调用，未接入加载流程。

**M38：**`packaging/windows/` 便携包脚本（嵌入式 Python 版本与 sha256 须用户核对传入，不含二进制）；`doctor.py` 新增 ccx、ccx_strict 检查（WARN 级）；`docs/ClaudeDesktop实连检查单.md`。**锁定断言变更 1 处：**`tests/test_m38_ai_native.py` 检查项集合 5→7（新增 ccx、ccx_strict）。

**S36：**新增 `gearmath/system/din743.py`（DIN 743-1/-2/-3/-4，44 个公式 id + 疲劳核算主流程），逐式核 PDF 原图；缺 Beiblatt 算例，证据等级全部 null；读图类与歧义项阻断。不进 data/registry。

**数值变化：**无既有锁定值变化。（模块 A 中 ph10 轮力残差 6.912479340685832e-08→6.91247934773211e-08，fsum 求和差约 7e-17，见 F3 报告。）

**V 复核：**第一轮三路均"返工"，返工已完成（F1：V 反例 N1–N8 除 N6a TOCTOU 外均拒或封顶；F3：N2/N5 修复、N1/N3 缓解；M34：T_1 改证书）。二次复核待做。

- `VERSION` → 0.13。

## v0.12（2026-10-30）

合入分路 C。测试 665 项全部通过（原 653 项 + 新增 12 项；本环境无 SciPy/pymoo，6 项可选适配器测试跳过）。M33 仍未验收，M37 仍未验收。

**分路 C（M35）合入：**
- `gear/iso1328.py`：ISO 1328-1:2013 式(5)–(12)、附录 D（Fpz/8T，式 D.2）、E（FrT）、F（单面啮合 fisT,max/min、FisT、式 F.4 角度换算）、G（fuT）；4.4.5 测量直径 dM、4.4.6 滤波截止 λα/λβ；5.2.2 等级系数、5.2.3 分档取整。附录 D/E/F/G 正文未写取整，本库按 5.2.3 取整并在 note 注明为本库口径。
- `gear/tooth_thickness.py`：内/外齿几何、齿厚偏差、公法线 Wk（含推荐跨齿数）、量球距 MdK、法向弦齿厚/弦齿高。
- `gear/parameter_sheet.py`：制造参数表，只读投影（JSON + Markdown）；栏目、齿顶圆口径必须显式选择，缺输入阻断不出数。修正：Markdown"依据"列原来对两轮都显示 1 号轮公式 id（如 `iso1328.fpT.1`），改为 `iso1328.fpT.i`。

**让测试通过所做的事（补丁本身未带测试，原 2 失败 2 报错均为登记类）：**
- 运行 `assess_registry.py`、`export_registry.py`、`package_hashes.py`，为新增 68 条 `iso1328.*` 公式生成评定与注册表行。
- **锁定计数变更 1 处：**`tests/test_registry.py::test_source_check_rule` 中 pdf_image_checked 由 71 改为 139。增加的 68 条全部是分路 C 的 `iso1328.*`（两轮各 34 条），其 ref 文本写明"原图已核"并给出 PDF 页/印刷页；评定规则只按文本给状态。**本轮没有 ISO 1328-1 原图，未重核**，该状态的依据是分路 C 作者的声明。
- 新增 `tests/test_m35_iso1328_sheet.py`（12 项），三类参照分开：
  - KISSsoft 2026 同输入报告值：K01/K03/K04 的 fpT、ffαT、fHβT 共 18 个，全部相等（K02 为 DIN 3961、K05 为 ISO 1328:1995，不同标准，未纳入）；
  - 测试内独立重写的 11 个公差式与 5.2.3 取整，对 K01/K03/K04 两轮全部相等；
  - 测试内独立实现的外齿 Wk、MdK（二分法反解 inv）、直齿弦齿厚经典式，对 K01（直齿）、K04（斜齿）相等至 1e-7 mm。
- **未独立对拍：**内齿 MdK、内齿弦齿相关量、附录 F 单面啮合（无参照值），只测了阻断与适用性；ISO 21771 原文不在证据包，几何/测量公式 source_check 维持 not_in_evidence。
- `VERSION` → 0.12。

**新增外部资料：**
- `docs/外部审查/FEA-readiness-R1/`：用户提供的 FEA 资格基础设施独立审查 R1（R01–R07、失败账本、八项任务 T0–T7）。原样收入，只读。
- `docs/Cowork编排提示词-v0.12.md`：多路并行编排（各路模型、思考强度、文件边界、合并顺序）。

**已知情况：**`qizhou-hust/yuanqi-public` 在 2026-10-30 从外部访问返回 404。M37 前处理更新（提交 c9cf959）与 FEA 模块 A/B 原包本轮无法读取，接力时须由用户直接上传。审查 R03 所指的 `ccx_io.py` 字段读取缺陷同样存在于本包 `data/m37_fea_pack/scripts/ccx_io.py`（`last_block` 取最后匹配块，不校验时间/覆盖/唯一性），尚未修复。

## v0.11（2026-10-30，接力版）

用户周额度即将用完，本版收拢后交接。653 项测试通过（9 项可选跳过）。

**本版合入：**
- **M34：**
  - 新增唯一可编辑真源格式 gears.math-source/2，C001 已转为真源文档；
  - design_store 改为以真源文档为提交单元；
  - 新增区间算术 v0（`kernel/interval.py`）。
- **M38：**
  - 意图工具（需求编译、不可行解释）；
  - MCP Resources/Prompts；
  - 评测集 bench v1 骨架（40 条需求，金标待工程师标注），附规则基线评测器；
  - 自检命令 doctor，`mcp_server.py`，接入指南。

**未完成，附在 `docs/接力-未完成分路/`：**
- A：云端 FEA（ccx 2.21 冒烟测试通过，全量未跑）；
- C：ISO 1328 全部公差、齿厚、参数表（测试未过）。

**其他：**删除误留的 `surface_factors.py.orig`。

交接内容（状态、里程碑、缺口、后续任务、接力提示词）见 `docs/接力交接-2026-10-30.md`。

## v0.10（2026-10-29）

纳入用户在本地用 KISSsoft 2026 复算 TR30 例7、例8 的证据。测试 578 项：原 540 项未改，新增 38 项。M33 仍未验收。

- **证据入库：**`data/kisssoft/tr30-7-8/`，与上传原件逐字节相同，加载时按 sha256 校验；私有数据，不得再分发。
- **三方对拍：**新增 `gear/tr30_kisssoft78.py`，结果如下：
  - 例7 正式口径（ISO 18265 表A.1）：gearbase 与 KISSsoft 在严格双门下 91/99 通过，失败的 8 行全是材料极限，原因是 HB→HV 换算。
  - 例7 改用 KISSsoft 读回的 HV 作外部输入（`HV_external_readback`，非默认）：99/99 通过。
  - 例8：101/101 通过。
  - 例8 的 σF0₁、σF₂：两个实现相差 <0.003 MPa，但都超出 TR30 印刷值的显示量子。性质记为"原表印刷（候选）"，偏差登记仍为"未知"。
- **例8 凸台 dFf：**用独立数值方法算得 65.874865 / 284.033308 mm，与 KISSsoft 相差 ≤3.4e-7 mm，与印刷值一致。未接入主公式图；dFf 定义所在的 ISO 21771 不在资料包里。
- **修缘长度 LCa：**取 0.5mn 或 1mn，输出全部不变；`strict_input_closure=false` 保留。
- **FEA 入库：**`gearmath/tools/fea_ingest.py`，附 18 项测试；题目包放在 `data/m37_fea_pack/`。
- **文档与门判定：**`docs/M33-验收报告.md` 新增第7节；门判定只新增字段与阻断条件，没有放宽。

## v0.9（2026-10-29）

四路并行。测试共 540 项：系统 Python 下 9 项可选适配器测试跳过；在 SciPy 1.18.1 + pymoo 0.6.2 环境下跳过 1 项（"缺依赖报错"检查，装了依赖即不适用）。锁定计数的改动逐条见 `docs/M33-分路报告/v0.9-*`。

**M33 收尾**
- 例6 dFf2（内齿插齿）由 TR30 A.6 与 ISO 6336-3 式(33)–(44) 组合得出：−1212.794，原表 −1212.79，通过。仅适用于直齿，须用户认可。
- 例8 凸台刀具的 dFf：资料包中没有凸台几何，标为"无法确认"。
- 例1–4 的"根切不缩短啮合线"假设，在例1–3、5–7 改为图内判定。其余 4 项假设（矿物油、VI95、两轮齿根表面完好）原文无法消除。
- 例7 新增显式选择器 `fsh0_basis`（总宽 / 半齿宽），原文未定义该口径。
- 新增 `docs/M33-验收报告.md`，`m33_acceptance` 新增 `acceptance_gate`（严格门目前全部为 false）。
- 用户选择严格验收，待 KISSsoft 复算例7、例8。

**M34 注册表**
- 新增 `data/registry/assessments-v1.json`，逐条评定证据等级：E5 195 条、E4 71 条、E2 7 条、未评 19 条。
- 从已通过的对拍行自动生成测试向量，覆盖 273 条公式。
- 新增案例级注册表 `cases-v1.json`（14 个案例）。
- 注册表数据含标准数值，不得再分发。

**M35 优化器**
- 齿数作为整数变量，用分支定界求解，结果与全枚举一致（z1=28、m=1.5）。
- 新增二阶条件检查，单独作为 `second_order_check` 报告。
- 新增 pymoo 多目标适配器。
- 与 SciPy SLSQP / trust-constr 逐题对照，x 与乘子一致到 1e-8。

**AI 接入（MCP）**
- 设计状态持久化：文件存储，记录不可变，带父版本链和乐观锁。
- 新工具：`registry_lookup`、`list_nlp_templates`、`optimize_nlp`（只接受模板白名单与数值参数）。

## v0.8（2026-10-29）

新到标准：ISO 1328-1:2013、ISO 18265:2013（用户购买，扫描件，已核原图）。三路并行：M33 收口、M34、M35。456 项测试通过（1 项为 SciPy 真后端对照，未装 SciPy 时跳过）。原有测试未删、未跳过、未放宽；锁定计数的变化均为实算结果变化，逐条见分路报告。

**M33 收口**
- fHβ5：
  - 公式核对：ISO 1328-1:2013 式(10)（PDF33）、5.2.3 舍入（PDF32）、第1章适用范围（PDF7）原图已核，原来凭记忆写的公式正确。
  - 实现：新建 `gear/iso1328.py`，在公式图内计算；kernel 新增 `round_to(x, q)`，导数为 0、标记为非光滑；越出适用范围时阻断。
  - 结果：例1–8 全部与原表一致。
- 例7 HB→HV：
  - 新增选择 `ISO18265_A1_linear`，按 ISO 18265 表A.1 相邻行线性插值；数据在 `data/iso18265/table-a1.json`（私有标准数据）。表A.1 是资料性附录，数值为估计值。
  - 正式口径改用它后，例7 有 3 行偏差 ≤0.7 MPa（TR30 原表更接近 HB/0.95）。没有调输入去追平；HB/0.95 只留作对比。
- fsh0：
  - 依据 ISO 6336-1 附录F 表F.1（PDF137）的定义与式(59) 的线性关系，取 fsh/(Fm/b)。没有编号公式，需复核。
  - 例7（双斜齿）的 Fm/b 取总宽还是半齿宽，原文未定义，标为"无法确认"。
- dFf/dNf：按 TR30 附录A A.6（PDF50–51）。例1–4 与例5–8 共用 `gear/tr30_shared.py`；只在无根切、无凸台的前提下计算。
- 例8：
  - Rz 新增显式选择器 `rz_source`（ra_times_6 / printed_rz），不设默认值。
  - σF0 偏高约 0.1% 的根因无法确认：已排除 Ft 舍入、齿宽、刀具口径、fε、Yβ 等。复现入口 `ex8_root_stress_analysis()`。
- 门判定：全表覆盖按输出表计算，域外行算作未覆盖；新增 e4_gate / e4_blockers，判定只比原来更严，不更松。

**M34 注册表 schema v1**
- 新增文件：
  - `docs/注册表-schema-v1.md`
  - `kernel/registry.py`（校验器）
  - `tools/export_registry.py` → `data/registry/formulas-v1.json`（防漂移测试）
- 证据等级沿依赖链传播：新增 `kernel/evidence.py` 与 `Result.evidence`，取依赖链上最弱一环；MCP explain 输出带上该字段。
- 现有公式还没有逐条评定证据等级，所以目前全部显示为 unassessed。

**M35 自研 NLP**
- `kernel/nlp.py`：增广拉格朗日 + 带界拟牛顿，梯度用对偶数精确计算；约束号向 g≤0，λ≥0；KKT 四项残差分别报告；search_claim 只允许 local。
- 分支定界：整数变量与有序离散集合（SOS 二分）。
- HS071/035/021/043/006 与 Rosenbrock 均达到已知最优；不可行问题如实报告"局部不可行"。
- 可选 SciPy 适配器 `kernel/adapters/scipy_nlp.py`，号向转换已测。
- 齿轮问题：56 个离散组合全枚举得 111130.22，旧网格法为 112221.22。

## v0.7（2026-10-29）

v0.6 由外部接力完成。v0.7 先做两路审计，再四路并行修复与推进。合并后 380 项测试全过，原测试未删、未跳过、未放宽。

- **审计：**
  - YF·fε、16 个系数公式、ISO 6336-5 表1、TR30 转录 60 余值抽查均正确。
  - CZL 原图印 437,5 属印刷错误，文档已改。
  - TR30 判据原先把程序间未舍入偏差门用在舍入表值上，已纠正。
- **TR30 分档判据（4.2.14/4.2.15）：**
  - A 档（未舍入参考）：双门判据。
  - B 档（舍入表值）：|Δ| ≤ q/2 + min(0.01, 0.5%|r|)。
  - 例1–4 数值验收 4/4，0 行失败；例1 附录A 172 项全过。
- **ZV 口径：**新增 `method.Z_V_velocity ∈ {v_w, v_ref}`，无默认。TR30 与 KISSsoft 均为 v_ref（证据见文档）。
- **主库：**
  - YX 分轮。
  - `method.Z_BD` 让 fZCa 显式化。
  - fε 在 εαn=2 处记录原文矛盾，并加近折点告警。
  - dFf/dNf（附录A A.6）。
- **TR30 例5–8 全强度链：**新模块 material_branches、internal_gear、double_helical、protuberance、tr30_full58。结果 91/91、91/91、91/92、90/94，全部 0 例验收，假设单列。
- **KISSsoft：**K02 95/95、K04 98/98、K05 98/98、K03 60/64；ZV 判定为参考圆速度。
- **卫生：**
  - 去掉 load_distribution 默认选择器和 dynamic 的 helix 默认值。
  - 文档措辞修正。
  - output/ 清理。
  - 新增 `gearmath/tools/package_hashes.py`。
  - data/tr30 标注为私有标准数值数据，不得再分发。

## v0.6（2026-10-29）

- 原始 M33 资料已补齐；90 个清单文件 SHA256 全部一致，登记原扫描与70页补页阅读副本的独立身份。
- K01：所选剩余系数已按 ISO 原图核验，新增中性 ZW/ZX 和 YB/YDT 显式分支；113 行在原容差内，原回填系数清零。应用假设仍单列，未宣称产品合格。
- 修正主库 YF 漏乘 fε（ISO6336-3:2019 式9–14），斜齿影响显著；C001 原数值回归保留。修正 CZL 发布舍入式和工作节线速度，未用连续性假设替换原文。
- TR30 八例原表转录、逐页出处与显示精度已落地。例1–4同一公式图算通 K/Z/Y、独立材料极限、σH/σF/SH/SF；例5–8几何/载荷实算。严格abs0.01且rel0.5%与原表舍入兼容分开，未放宽容差；0例授予验收。
- ISO6336-5 表1明确公式实现 Eh/MQ 与 V合金钢/MQ 材料极限，未把TR输出回填为材料输入。
- K02–K05具名适配器：分轮齿宽/刀具、精确刚度当量齿数和显式fZCa条件。K02 85/85；K03接触53/57、齿根不支持；K04 76/77；K05 75/77。保留所有超差，不用末位误差解释替代证据。
- 测试：旧占位断言随真实资料到位更新。**v0.5 的 CZL「分段连续（<1e-9）」断言已被「按标准发布舍入式 σHlim/4375+0.6357 的跳变 1.43e-5（delta=1e-10）」断言替换**，即移除了连续性约束；另 v0.5 的「ISO 原图待核」状态断言替换为含 SHA 与条款引用的「原图已核」断言。除此之外未删除、跳过或放宽数值对拍容差。**M33仍未验收。**
- v0.6 后续加固：`pair_model_ld` 不再内置 K_V/K_Hβ/K_Hα 默认选择器（须显式给出，缺则阻断）；`dynamic.set_dynamic_inputs` 非直齿级缺 `helix_angle_deg` 即报错（直齿 kind=spur 才为 0）；表面系数 `.endpoint` 变体由基础公式派生并有测试钉住表达式同源；`output/` 过期产物 tests-v0.5.txt 移出发布包；`data/tr30` 增加私有数据不可公开再分发声明。


## v0.5（2026-10-29）

- M33 四路并行推进：TR30 来源与对拍契约、表面系数、寿命/齿根系数、ISO 21771 几何换算核验。
- 新增 ZL/ZV/ZR、ZNT/YNT、YδrelT/YRrelT/YX 的显式原型分支，经 `factor_selectors` 接入同一 `rating.pair_model`。K01 109 行均在原容差内；仅 ZW/ZX/YB/YDT 仍回填。ISO 6336-2/-3 原式页图未附，标准核验状态保持 pending。
- NL 由转速、持续时间、齿数比和显式每转载荷次数计算；缺输入/选择器阻断。原始参考系数字段可删除而不影响公式计算。单位尺度常量禁止调值。C001 收据路径保留。
- TR30 八例仅建立未映射槽位及可执行导入/对拍框架：逐源哈希、逐字段页码、方法/版次、单位、容差、45 项最低公式覆盖和首分歧。当前 8/8 缺原页阻断，0 项验收，不授予 E4。
- 附件 ISO 21771-1:2024 支持 q=0 精加工 xE 换算；fpbT 的直接口径由公开 TR30 PROOF 支持，正式版仍待核；几何版次继续为 2007。
- 原 166 项测试全部保留，新增 62 项；共 228 项全过。新增可复现入口 `python3 -m gearmath.gear.m33_acceptance --output output/m33-acceptance.json`。


## v0.4（2026-10-29）

- **M33 第二轮：KISSsoft K01 全链改为公式路径（全部一致，第一分歧点：无）：**
  - KV 方法B：fpb = max(fpb1, fpb2)（6.5.4，不再以 ffα 代替）；式(17) 补 Cf 项；新增 `method.m_red ∈ {eq30, exact}`、`method.f_pb ∈ {fpt, fpbT}`。K01 KV 6.3e-8，公式层 K01–K05 ≤1.2e-5。
  - KFβ 指数：式(72) b/h 取 min(b1/h1, b2/h2)、<3 取 3；K01–K05 KFβ ≤1e-12。
  - 齿根：`method.root_shift ∈ {nominal, generating}`，generating 用 xE,min（ISO 6336-3 6.1），新增输入 `A_sn_i_1/2`。
  - `method.K_Hbeta ∈ {C, external}`、`method.K_Halpha ∈ {B, external}` 接入 `rating.pair_model`；`kisssoft_case` 按报告行号写契约选择器，证据路径仍可选。
  - C001：M31 对拍契约（eq30、fpt、external、nominal）仍逐位复现收据；KISSsoft 口径下 K_V −8.09e-4。
  - `data/kisssoft/*` 登记 MANIFEST；`K01-spur.known-divergences.json` 改为 schema/2（当前分歧 + v0.3 分歧修正记录）。新增 `tests/test_m33_fixes.py`（13 项），测试共 166 项。
- **G 路：KV 两条路径合一（接续文档第 7 节第 1 项）：**
  - `rating.pair_model(editions, selectors=…)`：选择器 `method.K_V ∈ {B, external}` 经 `kernel/select.py` 特化；B = 方法 B 公式，external = K_V 必须是 evidence 输入。
  - 无隐式默认：不选择则 `blocked_missing_selectors`，列出可选项。`m31_case.stage_model(selectors=…)` 不传时由案例 `dynamic_factor_method` 决定并记来源。
  - 选择器取值写入 `model_sha256`，校核输出新增 `selectors`、`selector_sources`；方法 B 输入并入 `gear/inputs.py` 的声明表（`full_input_table`）。
  - `kernel/select.py`：`specialize(prune=True)`、`build/method_diff` 增加 `prune`、`editions` 参数。
  - `pair_model_kvb` / `stage_model_kvb` 保留为薄包装。新增测试 `tests/test_kv_unified.py`（12 项）。
- **G 路：MCP P0（接续文档第 7 节第 6 项）：**
  - `ai_tools`：id 为规范 JSON 的 sha256；所有模型类工具回显全部参数；新增 `gear_get_design`、`gear_preview_edit`、`gear_commit`（比较并交换，过期 token 拒绝）；状态只在进程内存。
  - 新增测试 `tests/test_mcp_p0.py`（17 项，含 stdio 往返）。

## v0.3（2026-10-29）

四路并行，合并后 95 项测试全过。

- **探针修复：**
  - 输入声明表 `gear/inputs.py`：量纲不符、未声明名字、NaN、越域值、未使用输入，都返回阻断状态，不再给出 pass。
  - 缺安全系数限值返回 `blocked_missing_inputs`，不再抛异常。
  - 新增测试 `tests/test_inputs_editions.py`，共 23 项。
- **标准版次按分册配置：**
  - 同一分册禁止混用版次，跨分册可用不同年份。
  - 缺版次时阻断；版次写入 model_sha256。
- **内核：**
  - `where` 分段函数与近折点报告。
  - 方法选择器 `kernel/select.py`：specialize、external、method_diff。
  - 温度量纲 Θ，degC 只在边界换算。
  - 新增测试 `tests/test_kernel_ext.py`，共 17 项。
- **KV 方法 B 公式化：**
  - `gear/dynamic.py`：C001 G1 的 K_V 与收据逐位一致。
  - 新增测试 `tests/test_kv_method_b.py`，共 13 项。
- **三类性质分开报告：**
  - Problem IR v1；`assurance` 拆为搜索覆盖、KKT 一阶残差、数值收敛、证据等级四项，没有合并标签。
  - 新增测试 `tests/test_certificates.py`，共 13 项。
- **文档：**收窄"已实现""可证明"的表述；新增三类性质说明；版次改为按分册配置。

## v0.2（2026-10-29）

- 新架构独立包：核心 + data/m31 + legacy/m31（76 个迁移参照）+ 分包。
