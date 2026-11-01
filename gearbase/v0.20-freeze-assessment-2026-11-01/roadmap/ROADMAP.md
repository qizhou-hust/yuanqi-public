# gearbase v0.20：终局目标反向规划与冻结边界

审计日：2026-11-01。对象：`D:/my_Works/Gears/gearbase-v020-work`，Git `80117283778cf8732b5557fa15c2e41f626f92fc`。本分工只读产品，写此目录；没有新FE、KISSsoft或GUI操作，没有编辑核心、旧黄金、真实金标或原验收门。

**首要瓶颈是系统合同与全链依赖。** 当前已有副级数学真源、圆柱校核、固定家族Stage0和有限优化；还不能从输出要求、空间和轴线关系自动装配任意允许的简单组合，再将其完整校核、布置、建模和更新。建议将当前版本冻结为范围明确的可重放数学/证据工具底座，保留所有开放项；下一步先审查系统合同、端口/级序和失效机制的最小切片。

本路线是建议，**不授予M40解冻，也不改变既有门**。原M32–M40的门继续逐项约束其原声明；下面R1–R8是新增终局交付门，不作为原门替代分母。软件快照冻结、可计算用途、数值工具资格、结构/制造成熟度和生产冻结分别声明。

用户既有自主推进和本地FE授权继续有效。本轮只读选择不撤销这些授权；下述前置是实现/工程证据依赖，不增加逐项研发审批。M40原冻结/解冻决定和工程数据/方法拍板边界继续保留。

配套机器记录：[goal-map.json](D:/my_Works/Gears/v020-freeze-assessment-2026-11-01/roadmap/goal-map.json)、[freeze-contract.json](D:/my_Works/Gears/v020-freeze-assessment-2026-11-01/roadmap/freeze-contract.json)、[本轮边界探针](D:/my_Works/Gears/v020-freeze-assessment-2026-11-01/roadmap/boundary-probes.json)。源码文件的逐字节身份保存在探针的`source_files_sha256`。

## 已核边界与终局缺口

| 终局要求 | 当前证据与判断 | 需要补的系统能力 |
|---|---|---|
| 输出性能、空间、同轴/交错轴驱动候选生成 | 普通意图只支持单级直齿；四类输出/空间/轴线字段在本轮探针中均unknown_argument。旗舰入口明确只接受手选H2/W2W/P2及stage0。[intent.py:36](D:/my_Works/Gears/gearbase-v020-work/gearmath/tools/intent.py:36)、[intent.py:153](D:/my_Works/Gears/gearbase-v020-work/gearmath/tools/intent.py:153)、[flagship_workflow.py:4](D:/my_Works/Gears/gearbase-v020-work/gearmath/tools/flagship_workflow.py:4) | 类型化端口、有序级、轴/固定构件、自由度、允许组合语法、同一输出合同和拒绝原因。总比相同的不同级序保留不同身份。 |
| 全组合物理校核 | 蜗杆/行星的强度与轴向载荷编译明确unsupported；Stage0不做完整评级。[flagship_system.py:246](D:/my_Works/Gears/gearbase-v020-work/gearmath/product/flagship_system.py:246)、[flagship_system.py:272](D:/my_Works/Gears/gearbase-v020-work/gearmath/product/flagship_system.py:272)、[flagship_system.py:401](D:/my_Works/Gears/gearbase-v020-work/gearmath/product/flagship_system.py:401) | 逐族模型资格、独立对标和混合链传播；未解锁族只输出筛选层候选。 |
| 谱、功率流、可逆与保持 | W2W为常摩擦正向效率筛选；P2没有效率/热模型。DIN743已有谱计算原语，但轴系谱衔接仍TODO。[flagship_w2w.py:15](D:/my_Works/Gears/gearbase-v020-work/gearmath/gear/flagship_w2w.py:15)、[flagship_p2.py:3](D:/my_Works/Gears/gearbase-v020-work/gearmath/gear/flagship_p2.py:3)、[din743.py:735](D:/my_Works/Gears/gearbase-v020-work/gearmath/system/din743.py:735)、[shaft_line.py:321](D:/my_Works/Gears/gearbase-v020-work/gearmath/system/shaft_line.py:321) | 工况有符号n/T/P、双向损失、载荷路径、循环计数、峰值持续时间和回驱域；功率反算与转矩传播独立对账。 |
| 系统多目标和鲁棒裕量 | 联合搜索是作者给出的有限圆柱域，目标仅齿坯+轴体积；前沿是单副有限域，安全坐标为原始min(SF,SH)，情景比例无概率含义。[system_optimize.py:129](D:/my_Works/Gears/gearbase-v020-work/gearmath/product/system_optimize.py:129)、[system_optimize.py:144](D:/my_Works/Gears/gearbase-v020-work/gearmath/product/system_optimize.py:144)、[source_frontier.py:141](D:/my_Works/Gears/gearbase-v020-work/gearmath/gear/source_frontier.py:141) | 整机可计算目标、逐限值归一化裕量、目录离散化后重验、显式不确定域、稳健备选和不同成熟度候选的可比性。 |
| 布置、支承、箱体和真实空间 | C001源记录支承/KHβ几何冲突、扭矩作用位置和真实材料缺口；梁接口没有完整的齿轮体/轴承/箱体柔度及评级反馈。[C001.system-input.json:5](D:/my_Works/Gears/gearbase-v020-work/data/system/C001.system-input.json:5)、[C001.system-input.json:24](D:/my_Works/Gears/gearbase-v020-work/data/system/C001.system-input.json:24)、[beam_face_scope.md:5](D:/my_Works/Gears/gearbase-v020-work/docs/beam_face_scope.md:5) | 3D坐标/轴线/支承、所有传扭与止转接口、箱体至安装座载荷路径、完整组件manifest及全运动空间验证。 |
| 制造与成本 | 当前K02准备包是尺寸和圆包络；明确没有完整工作齿面/产形齿根、制造图或工艺放行。现有联合目标排除成本。[v020-M35-review-preparation.md:3](D:/my_Works/Gears/gearbase-v020-work/docs/v020-M35-review-preparation.md:3)、[同文件:9](D:/my_Works/Gears/gearbase-v020-work/docs/v020-M35-review-preparation.md:9)、[system_optimize.py:146](D:/my_Works/Gears/gearbase-v020-work/gearmath/product/system_optimize.py:146) | 可加工离散集合、刀具/变位/精度/热处理、孔毂连接与配合、装配工艺、真实BOM和带批量/日期/币种来源的成本模型。 |
| 唯一真源与自动更新 | 副级source拒绝派生落源，支持回执/参数表投影和所有权/CAS。现有schema不接受topology；系统输入另存，旗舰投影输出全部显式叶子、model_family=None。[math_source.py:63](D:/my_Works/Gears/gearbase-v020-work/gearmath/gear/math_source.py:63)、[design_store.py:79](D:/my_Works/Gears/gearbase-v020-work/gearmath/tools/design_store.py:79)、[系统层输入-schema.md:3](D:/my_Works/Gears/gearbase-v020-work/docs/系统层输入-schema.md:3)、[flagship_system.py:343](D:/my_Works/Gears/gearbase-v020-work/gearmath/product/flagship_system.py:343) | 系统修订拥有需求、拓扑、组件和证据引用；既有副级与系统文档成为受控子文档/投影。计算、优化、CAD、网格、FE、报告使用可核查依赖签名。 |
| CAD拓扑ID | 归档存在命名历史及回转体重绑定；其文档明确STEP不转移命名，拆分没有稳定子ID。当前活跃制造投影没有证明全系统ID贯通。[command_naming.py:22](D:/my_Works/Gears/gearbase-v020-work/archive/m31/src/cadbench/command_naming.py:22)、[design_rebinding.py:148](D:/my_Works/Gears/gearbase-v020-work/archive/m31/src/cadbench/design_rebinding.py:148) | 稳定组件/特征/语义面身份，split/merge/delete/suppress事件映射；歧义必须阻断，不能按面号默默重绑FE载荷。 |
| 自然语言与代理权限 | 已有结构化意图、预览/CAS和提交。本轮同一25 N·m输入仅改调用方来源：agent_proposed为pending，user为pass。优化环境开关只控制列举，直接call仍分派。[ai_tools.py:54](D:/my_Works/Gears/gearbase-v020-work/gearmath/tools/ai_tools.py:54)、[ai_tools.py:232](D:/my_Works/Gears/gearbase-v020-work/gearmath/tools/ai_tools.py:232)、[ai_tools.py:536](D:/my_Works/Gears/gearbase-v020-work/gearmath/tools/ai_tools.py:536)、[optimize_commit.py:10](D:/my_Works/Gears/gearbase-v020-work/gearmath/tools/optimize_commit.py:10) | 数值来源约定与身份/授权分开；自然语言只能提出带原文定位的草案。内容token与CAS不构成独立工程师签署。 |
| 真实casegold和工程release | 实际40题均pending。C001被标为派生基准和项目筛选假设，部分材料/连接是synthetic；目录名golden不构成真实工程答案。当前报告保留FE失败和M40冻结。[requirements.json:4](D:/my_Works/Gears/gearbase-v020-work/data/bench/v1/requirements.json:4)、[C001.json:19](D:/my_Works/Gears/gearbase-v020-work/data/m31/cases/C001.json:19)、[C001.json:115](D:/my_Works/Gears/gearbase-v020-work/data/m31/cases/C001.json:115)、[derived-candidate.json:256](D:/my_Works/Gears/gearbase-v020-work/data/m31/golden/C001/derived-candidate.json:256)、[v020-progress.md:19](D:/my_Works/Gears/gearbase-v020-work/docs/v020-progress.md:19) | 真实原件/独立参考/边界/签署/失败账本，软件一致性与工程放行分开；不由AI填写自己的真金标。 |

这些是逐项缺口，不是对全部既有公式的否定。原顶层设计已把拓扑、载荷谱列为源输入，把CAD/STEP/FE等列为只读投影；当前终局差距在于这些规则尚未覆盖完整系统。[顶层设计.html:273](D:/my_Works/Gears/gearbase-v020-work/docs/顶层设计.html:273)、[顶层设计.html:281](D:/my_Works/Gears/gearbase-v020-work/docs/顶层设计.html:281)

## 按价值排序的8个可交付切片

依赖表示准入条件，不表示工期。每个切片先交付可独立验收的软件机制，工程外部项保持明确open。原门及固定参考保持原身份；子域没有全部关闭时，仍可冻结已证明的更小用途。

### R1：统一系统合同、依赖和真实挑战入口

- **输入：** 固定v020源、用户输出/空间/轴线/寿命/工况要求，现有pair/system/flagship源，已有工程原件。
- **输出：** 加版本的`SystemDesign`；rotary/linear/frame端口、组件/轴/固定构件ID、`ordered_stages`与连接边；依赖/失效图；旧格式无损导入；真实挑战manifest。
- **验收：** 旧黄金和旧回执按原门重放；拒绝未知连接、单位错误、无连通、自由度未约束、重复驱动和未支持分流；级序变化改变身份并使所有相关投影stale/重算。C001/H2如实保留其synthetic/open字段，真实外部案例另给身份，不把缺参考算金标。
- **前置：** 后续独立实现切片需写明合同试验边界；本轮未进入产品。保留当前内核和领域分层，采用增量导入/适配，避免另造公式路径。
- **软件可独立：** schema、语义负例、导入/规范哈希/来源、依赖失效和回放器。**需外部：** 原始需求解释、实际载荷/布局、案例身份及独立答案。

### R2：现有圆柱多级线的功率、载荷和支承闭环

- **输入：** R1合同；电机真实工作点或显式驱动边界；名义、短峰、反转、堵转/冲击/止挡等谱；真实支承/材料/轴承/连接/油品与热边界。
- **输出：** 逐工况逐级n/T/P/损失/三向力/循环计数；多级圆柱+轴/轴承/连接的同源校核；可逆/回驱适用域及缺项表；真实C001/H2至少一条线的计算结果，合格或不合格均可如实输出。
- **验收：** 同工况功率反算和转矩传播在预声明数值容差内一致；惰轮增加损失/支承，级序交换改变中间量；峰值持续时间不被当整动作。真实支承冲突先解决；谱原语到齿轮/轴/轴承计数逐项验证。小有限域整链独立全枚举与分层搜索的全部可行点/排序一致。无法评级的模式blocked。
- **前置：** R1及真实输入，保持M40物理族冻结。**软件可独立：** 工况调度、传播、已有L2装配、对账和缓存。**需外部：** 电机热/低压工作曲线、实际布局/材料/供应商应用因子和载荷谱。

### R3：受限拓扑枚举和逐族资格解锁

- **输入：** R1/R2端口传播接口，显式族/级数/标准件离散域，空间、制造和保持要求；逐族批准的公式模型与独立参考。
- **输出：** 多级平行、双蜗杆、蜗杆→斜齿、行星→蜗杆等允许语法的候选；级序、啮合数、零件清单和拒绝理由；每个候选分别显示`stage_A_screened`、`component_rated`、`packaged`及外部证据状态。
- **验收：** 小语法域独立穷举、对称去重/截断和级序身份核验；所有方案使用同一输出合同。未解锁族只给筛选候选，不能进入“全系统可行最优”。蜗杆与行星完整算例+独立对标仍遵守原M40门；交错轴另设点/椭圆接触、滑动/磨损/胶合/热及力方向模型域，不能移用平行轴ISO6336接触放行。
- **前置：** R1、R2；**每个M40族单独受控解冻决定**，不是本审计批准。**软件可独立：** 枚举、身份、比较、拒绝/分层状态。**需外部：** 标准与方法选择、真实摩擦/材料/磨损及独立对标。[原M40门](D:/my_Works/Gears/gearbase-v020-work/docs/顶层设计.html:566)

### R4：丝杆螺母接口和首个受限线性分支

- **输入：** R1/R2合同，推力—位置—速度—时间谱和行程，指定供应商丝杆/螺母、安装/材料/润滑证据。
- **输出：** rotary→linear统一端口；首个“旋转丝杆+止转螺母、导向承受横载、准静态同轴滑动梯形”的运动/静力筛选；分项完整状态表，寿命资料不足继续blocked。
- **验收：** 头数/螺距/导程与旋向符号正确；Fv和Tω/损失对账；全行程自由长度/支承进入屈曲与转速检查。越出首个模型域明确拒绝或未评价；效率、摩擦、许用和边界系数均有来源。正式滑动或滚珠模型各有独立参考后才可升级component_rated。
- **前置：** R1/R2、明确首个线性域和真实输入；不借此关闭M40。**软件可独立：** 接口、运动、单位/符号、分派、失效和缺项阻断。**需外部：** 几何/产品额定值、摩擦/磨损/热和寿命数据、保持与耐久验证。详细接口见后文。

### R5：可制造布局、CAD身份和支承箱体全装配

- **输入：** R1身份/依赖，R2或R4已计算候选，真实刀具/齿面与标准件、传扭/止转/支承/箱体接口；混合族还需R3对应资格。
- **输出：** 零件/组件/自由度manifest、参数化全装配、语义特征/面组、STEP及重导入；全运动干涉和制造缺口表。
- **验收：** 变位工作齿面与产形齿根通过独立几何对拍；孔毂、轴承、键/花键/过盈等传扭连接显式。split/merge/delete/suppress及齿数变化产生可核查映射或ambiguous阻断。STEP核验名字、逻辑组件/实体数量和关键尺寸；按端点、中间、最近接近及连续扫掠做全组件精确布尔，含支承、箱体、紧固件、密封、线口和公差/热预算；显示相位检查与全齿轮转动分析分开。
- **前置：** 所需后端/独立几何域通过。归档命名/CAD可以逐模块再资格复用，不直接导入为生产路径。**软件可独立：** 参数映射、命名、重导入、运动与自动失效。**需外部：** 供应商、配合/预紧/润滑、工艺与装配审阅。
- **成熟度：** G0计算→G1几何→G2名义包络→G3载荷路径→G4带箱体全运动概念逐门声明。G4也不自动等于生产冻结。

### R6：系统多目标、制造/成本与稳健离散短名单

- **输入：** 已资格物理域；相同输出合同和必要检查；离散目录/加工分辨率、真实BOM与成本来源、明确不确定范围/相关性。
- **输出：** 全部硬约束及归一化裕量、可计算目标的Pareto集合、离散后最差角点/情景复核、稳健备选及未评价项。
- **验收：** 小域独立全枚举oracle核全部可行集合/前沿；按每个检查自己的限值算裕量，原始min(SF,SH)只作原始指标。每点都要全链复核；blocked不能算全系统可行。连续建议离散回可购/可加工件后重算。没有分布证据只报情景/区间覆盖；没有报价/成本域保留open，不由体积猜成本。至少保留一个有已声明余量的备选，若不存在则明示。
- **前置：** R1/R2；混合族/线性/空间目标分别依赖R3/R4/R5。**软件可独立：** 现有数学优化器、问题编译、oracle、非支配/约束与稳健验证。**需外部：** 不确定性和生产公差来源、材料/摩擦/电机温度域、工艺/报价。缺物理模型时先补模型，复杂求解器不能提供缺失的工程证据。

### R7：自然语言系统草案和可审查修订权限

- **输入：** R1源/依赖、已资格工具、原文需求、当前head及调用身份/角色策略。
- **输出：** 带原文定位的结构化需求、追问和补丁草案；候选/参数diff与下游失效预览；绑定源head、补丁、候选、方法和证据的草稿修订；独立来源确认/工程签署记录。
- **验收：** 读/提案/运行/草稿提交/来源确认/release权限分开；禁用写权限时工具不列出且直接call也拒绝。模型不能以user/evidence自标、confirm布尔或自算token取得来源升级/签署权限。旧token与并发head变更拒绝；级序/需求/目录件编辑使所有相关计算/CAD/FE/优化/报告失效；未应用需求不丢弃。真实工程师题库先签署，再检验全系统创建/修改、拒绝与越权负例；AI不代填真实答案。
- **前置：** R1和相应用途后端；身份策略及真实标签。**软件可独立：** 协议/权限拒绝/CAS/状态/来源传染/数值溯源。**需外部：** 工程师身份独立性、需求歧义、来源确认与正式签署。此切片不以模型权限取代工程责任。

### R8：按用途资格的FE证据和工程release包

- **输入：** 所申报用途对应R1–R7、原FE阶梯/失败账本、独立对标/供应商/工艺/样机资料。
- **输出：** concept、prototype、production分别声明的release dossier；源/公式/环境/求解器/原始场/资格域绑定；独立工程审阅、holdout重放、未关闭项和重验触发器。
- **验收：** 原M33/M35/M36/M37/M38/M39开放门不换名关闭。FE收录、数值收敛、物理验证、准予用途分开；固定失败矩阵不删点、不按结果改oracle。代理只在已合格域使用，越域按合同阻断或回到已授权基础模型；最终候选按指定用途独立复核。生产冻结前须闭合实际供应商件、制造/公差/支承、效率/热/保持/耐久及NVH等所需外部证据。
- **前置：** 相应用途各门，保留用户既有自主推进/本地FE授权和工程输入边界；本轮选择只读、无新FE/商业运行。**软件可独立：** 身份/入库/资格隔离、release完整性和重放。**需外部：** 物理模型资格、工艺/供应商审阅和生产条件试验。软件交付与production release分别签署。

## 丝杆螺母独立接口与首个适用范围

丝杆应是末级能量/载荷转换组件，和齿轮、电机、轴承通过相同端口与工况ID连接。当前活跃`design_check`九scope没有丝杆；`rundnut`命中是轴的环槽名称。[design_check.py:45](D:/my_Works/Gears/gearbase-v020-work/gearmath/product/design_check.py:45)、[din743.py:556](D:/my_Works/Gears/gearbase-v020-work/gearmath/system/din743.py:556)

| 合同组 | 必须保存的作者输入/引用 | 只读输出与失效消费者 |
|---|---|---|
| 身份/结构 | component_id；模型种类；旋转丝杆或旋转螺母；左右旋与坐标正向；旋转/直线端口及抗转/轴向支承接口 | 运动符号、机械自由度、传扭/推力/止转载荷路径；不得只给total_ratio |
| 几何/制造 | 螺纹形式/版次；公称/中径/根径；螺距、头数、导程的独立输入与相容约束；有效啮合长、工作长度、端部台阶、加工/表面/精度/背隙；型号/图纸引用 | 导程角、螺纹/芯部截面、接触面积和制造尺寸；CAD/STEP/网格/参数表 |
| 安装/支承 | 每个支承位置/约束类型与刚度或其简化声明；全行程受压/转动自由跨度；预拉伸/装配偏心；导向横载/弯矩、螺母固定与保持结构 | 轴向反力、弯曲/挠度、实际边界下屈曲及转速检查；不能用同一通用边界系数 |
| 工况谱 | F、速度、位置、方向、持续时间/距离、重复次数、加减速、停留/保持、温度与润滑状态；堵转/冲击/止挡路径 | 每行的rpm、扭矩、功率、损失、能量、应力、计数和裕量；线性输出要求与电机工作点 |
| 摩擦/损失 | 指定材料对、润滑/表面、温度和老化状态的摩擦模型/范围，或同域供应商扭矩映射；轴承、止推面、密封与预紧损失分开 | 提升/下降/回驱扭矩、效率及发热；不得固定η替代模型，也不得把止推损失重复计入摩擦 |
| 额定/寿命证据 | 每型号静/动额定值与定义；滑动螺纹p/PV、磨损/蠕变/温升资料或滚珠评级模型；寿命目标、可靠度/使用因子与来源；检验/试验引用 | 分项pass/fail/blocked/out_of_domain，磨损/疲劳/热/保持限制和证据域；没有数据不输出寿命承诺 |

所有重要量带单位、来源、工况、标准/方法/版次和证据状态。导程与螺距/头数的关系只计算一次；多头不把螺距误当每转位移。结构从旋转丝杆改成旋转螺母时重新分派支承和动力学模型，不能仅将某个rpm设零保留旧转速结论。

**首个最小可用范围建议：** 只选一项有真实图纸/目录和材料/润滑参数的滑动梯形丝杆，旋转丝杆、螺母止转并作直线运动，已声明固定—支承配置，导向承受全部横载，准静态同轴载荷，温度/速度/行程在该供应商或验证模型的明确范围。支持明确的正反运动/推拉工况；冲击、横载、不同安装、旋转螺母、长期蠕变及未验证高速域先阻断。这里“准静态/范围”必须具体化为输入和验证域，不能硬编码为全产品通用数值。

第一个交付称`kinematic_and_static_screen`。每一项都返回状态；如寿命数据缺失，寿命保持blocked，用户要求完整寿命时整机不能升为工程可行。最少检查：

1. 行程/速度/动作时间，头数—螺距—导程相容和旋向；以独立扭矩路径与功率/损失账核Fv、Tω和动作能量。
2. 推力传到螺纹、轴向支承、肩部/紧固件、导向和箱体的完整路径；峰值/堵转/止挡分别计，不隐去保持或反驱工况。
3. 丝杆芯部拉压+弯曲+扭转，螺纹根部、螺母弯曲/剪切/剥离与实际有效承压面积；不把全部啮合圈视作均匀分担而不声明模型。
4. 全行程的受压自由长度/偏心/安装边界下屈曲，适用时弯曲与挠度；刚度/端部条件及许用裕量明确。屈曲不适用必须由载荷符号和结构证明。
5. 旋转丝杆的临界转速及供应商最高允许速度；旋转螺母是另一个结构域，需检查其自身转动件与支承限制。
6. 实际材料/润滑/温度/占空比下的p、滑动速度、PV、热、磨损/蠕变、背隙和导向接触。公开供应商资料的PV限制与材料、热和工况有关，只能在其产品域使用。[igus官方FAQ](https://www.igus.co.uk/threaded-rod/wiki)（2026-11-01检索）
7. 静态与动态摩擦、振动/磨损/润滑变化下的保持和回驱策略分别检查；自锁筛选不替代保持试验或实际制动/机械锁证据。

**何时升级正式梯形线程模型：** 需要长期寿命、温升、频繁往复、预紧/消隙、多头、高温或聚合物螺母时，必须接入指定材料/润滑/温度/压力/滑速/行程/占空比的磨损、热和蠕变模型或供应商实测映射，并按实际载荷—滑动距离谱积分/验证。线程几何标准决定尺寸术语；不能仅凭几何名称推出PV或寿命。资料缺失时先补台架证据，保留open。

**何时升级滚珠丝杆模型：** 在相同输出要求和保持/成本约束下选择滚珠方案，且需要该件的额定载荷、疲劳寿命、预紧刚度与高速循环限制时，单独接入滚珠插件和指定型号目录。ISO 3408-5官方摘要的范围是滚珠丝杆静/动轴向额定载荷和运行寿命；不作为滑动梯形螺母磨损寿命依据。[ISO官方摘要](https://www.iso.org/standard/34618.html)（2026-11-01检索）

滚珠插件需来源明确的Ca/C0a与定义、预紧/内载分布、载荷谱/反向工况、安装误差、润滑污染/温度、支承和实际损失/回驱扭矩；仍保留芯部应力、屈曲和临界转速。THK说明安装方式/跨距影响允许载荷与临界速度，允许速度还需与具体型号DN/循环件限制比较；本路线不抽取全型号通用转速或边界系数。[THK安装](https://www.thk.com/us/en/products/ball_screw/selection/0005/)、[THK允许转速](https://www.thk.com/us/en/products/ball_screw/selection/0007/)（2026-11-01检索）

## 真实挑战库的最小合同

原50例、C001旧收据、商业参考和40题原题/空标签全部保留原身份。新增真实案例在独立版本中记录：

- 原始需求故事、文件/原件hash、项目和来源/权限；输出/工况谱/环境/空间/固定接口；当前参考结构与已知失败。
- 独立参考的作者、方法/软件/版本、输入定义、单位、输出范围、逐量容差和证据等级；不能由实现输出生成oracle。可接受多个方案，不强迫只有一个数值最优点。
- 真实、项目假设、合成能力题、故障负例分明；缺材料/布局或参考时保留open，不把synthetic重命名为真实。
- 创建/修改脚本：改输出、交换级序、反转、改变峰值持续时间、替换目录件、改支承/箱体；预期失效范围和拒绝条件。
- 开发集与holdout身份、工程师逐项签署和来源/独立性核实；每个切片都追加相应真实挑战，不等到最终release才开始。

当前真实工程师标签接收器只能核提交的声明结构，不能独立认证自然人资质；40题仍是空标签。[v020-engineer-gold.md:3](D:/my_Works/Gears/gearbase-v020-work/docs/v020-engineer-gold.md:3)、[bench_gold.py:64](D:/my_Works/Gears/gearbase-v020-work/gearmath/tools/bench_gold.py:64)

## 冻结与重验的使用方式

`freeze-contract.json`分别列出可冻结、实验、禁止用作工程放行、需签署和重验触发器。它是审查建议，当前产品没有因此新增权限策略。

可冻结的范围包括固定数学接口、副级source/CAS、适用域内分项校核、Stage0/有限搜索、证据收录、MCP草案及未签制造准备包。必须保留每项的范围/缺项和失败。原FE报告的“recorded”仅为收录；本轮未新跑或重新资格。尤其不能据当前L2失败矩阵、初步L3结果升级完整FE用途或优化代理。[v020-m37-verified-profile.md:15](D:/my_Works/Gears/gearbase-v020-work/docs/v020-m37-verified-profile.md:15)、[v020-progress.md:27](D:/my_Works/Gears/gearbase-v020-work/docs/v020-progress.md:27)

级序、需求/谱、几何/刀具/旋向、支承/箱体、丝杆架构、供应商/材料/润滑、标准/方法、实现/环境、成本/不确定性、权限/来源或oracle身份变化时，按依赖标stale并在再次使用前重验。能证明未受影响的工件可复用；边界不清时保守失效。源文件字节hash、规范参数hash、公式/模型hash与运行环境身份分别保存。冻结不是禁止实验：新实验保持独立身份、用途、准入和退出门，已有冻结结果不可被静默覆盖。

原门依据包括[系统层门](D:/my_Works/Gears/gearbase-v020-work/docs/顶层设计.html:524)、[FE门](D:/my_Works/Gears/gearbase-v020-work/docs/顶层设计.html:535)、[AI门](D:/my_Works/Gears/gearbase-v020-work/docs/顶层设计.html:546)、[多目标/失效门](D:/my_Works/Gears/gearbase-v020-work/docs/顶层设计.html:556)和[族扩展门](D:/my_Works/Gears/gearbase-v020-work/docs/顶层设计.html:566)。本路线不以新名字降低这些标准。

## 本分工的验证记录

直接运行了只读[probe_boundaries.py](D:/my_Works/Gears/v020-freeze-assessment-2026-11-01/roadmap/probe_boundaries.py)：`python -X utf8 -B -I -S .../probe_boundaries.py`。源schema基线合法、拓扑顶层键拒绝；终局输出字段、多级与混合族正确暴露当前范围；实际40题/0 labeled；来源标签状态对比完成；产品`git status --porcelain`为空。首次未开UTF-8时终端cp1252导致stdout编码失败，随后显式UTF-8重跑退出码0；没有修改被审计代码。

本分工没有重复全库回归、CAD重建、真实FE或商业软件资格。`output/m36`、`output/m38`、`output/m39`的统计是读取到的既有回执，未凭它们宣称本轮全部重验。可冻结建议还应合取父审计的当前会话结果。

## Where This Review May Be Wrong

1. **归档复用范围可能高于本审计覆盖。** 我按活跃gearmath入口判断终局能力；归档已有命名、回转体重绑定、CAD/装配等算法，未全部再资格。本结论不表示从未实现过这些模块。用R5的活跃导入、同源投影、编辑/STEP/面组回放逐项核实复用边界。
2. **真实资料可能在快照之外。** 当前C001/40题确有假设与空缺，但用户可能在其他位置已有真实布局、材料、载荷和签署答案。将原件独立核实入新挑战manifest即可缩小缺口；不能据本地未找到判定外部不存在。
3. **目标用途与工程资格仍需逐项界定。** 本路线面向用户提出的通用组合与全链自动设计；固定家族概念筛选可在更小范围冻结。本轮未新做FE、KISSsoft或完整CAD验证，具体物理错误/回归和资料身份应以父审计及后续独立工程证据进一步收紧结论。
