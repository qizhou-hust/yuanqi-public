# 官方方法参考与主张边界

核查日期：2026-11-01。对象是拟议的 gearbase 数学化传动单元插件与最多四级预建组合库。只核查公开一手资料，未运行商业工具、gearbase 求解器或 API，未验证现有实现。本文件中“已核实”仅指已在官方原文找到相应说明；不等于独立复现厂商的精度、速度或覆盖率。

## 应先纠正的表述

1. **不能把商业工具概括为仅手工建模或缺少系统自动化。** KISSsoft 明确提供 SKRIPT/COM 参数研究；系统模块也有脚本事件机制。Romax 明确提供全系统参数化、优化和流程自动化，且长期有命令行/第三方程序驱动的 Batch Running。[KISSsoft 参数研究](https://www.kisssoft.com/en/news-and-events/newsroom/streamlined-parametric-study-using-skript)、[系统脚本](https://www.kisssoft.com/en/products/products/kisssoft-system-module/results/results)、[Romax 产品简介](https://www.cadence.com/en_US/home/resources/product-briefs/romax-software-suite-product-brief.html)、[Romax 批量运行](https://nexus.hexagon.com/community/public/romax/b/technical-blog/posts/evaluate-bearing-performance-according-to-supplier-data-with-skf-calculations-embedded-in-romax-products)
2. **KISSsys 应作历史名称处理。** Gleason 的 2024-04-01 新闻说新 KISSdesign 系统模块替代此前 KISSsys。当前所读官网栏目称 KISSsoft System Module。这里不能进一步推断二者仅改名、内部完全相同或接口兼容。[官方发布](https://www.gleason.com/en/facts-and-news/news-room/new-kisssoft-release-new-kissdesign-available-in-april)
3. **“首次自动化/首次将学习用于传动探索”没有证据。** 除前述能力，Romax 2026.2 官方公告已经说明 ODYSSEE 与参数研究集成。本文不对全球首创性作结论。[2026.2 公告](https://community.cadence.com/cadence_blogs_8/b/pss/posts/romax-2026-2-a-first-look-at-the-next-chapter-in-drivetrain-simulation)
4. **Modelica 的 `flow` 字段不要与速度变量混淆。** 旋转端口以角度为非 flow 变量、转矩为 flow 变量；平移端口相应为位移和力。角速度/线速度是位置导数。[旋转端口](https://build.openmodelica.org/Documentation/Modelica.Mechanics.Rotational.UsersGuide.FlangeConnectors.html)、[平移端口源代码](https://raw.githubusercontent.com/modelica/ModelicaStandardLibrary/v4.1.0/Modelica/Mechanics/Translational/Interfaces/Flange.mo)
5. **地端可以承受反力矩。** 固定边界约束角度，不附加“转矩为零”。地端角速度为零，故理想固定支座可以有反力矩而不传递机械功率。这是源代码约束与功率定义的直接推论。[Fixed 源代码](https://raw.githubusercontent.com/modelica/ModelicaStandardLibrary/v4.1.0/Modelica/Mechanics/Rotational/Components/Fixed.mo)
6. **“四级、几百种、工业界都能找到应用”应拆成三个待验事项。** 四级是本库范围；几百种须由冻结的字母表、连接规则与去重策略计数；逐组合工业应用须逐项取证。SEW P 族明确存在五级产品，足以否定“四级是工业通用上限”。[P 族产品表](https://www.sew-eurodrive.de/products/industrial-gear-units/planetary-gear-units/p/p.html)

## 方法比较：所读资料实际支持什么

| 维度 | KISSsoft / KISSdesign / 当前 System Module | Romax | 对拟议 gearbase 架构的可用结论 |
|---|---|---|---|
| 单元与系统建模 | 齿轮、轴、轴承、连接等置于系统拓扑；部件强度/寿命计算相互关联。[建模](https://www.kisssoft.com/en/products/products/kisssoft-system-module/modeling/modeling)、[计算](https://www.kisssoft.com/en/products/products/kisssoft-system-module/calculation/calculation) | 系统参数化与部件评级并存；不同产品覆盖概念、结构耐久、轴承、效率和 NVH。[产品页](https://www.cadence.com/en_US/home/tools/msc-software/romax.html) | “单元组合成系统”本身已有成熟先例。需要证明的是本项目契约与组合规则的具体价值。 |
| 复用与变体 | 有预定义装配、建模助手、同运动学下的变体表；涉及行星、分流与 CVT。[建模](https://www.kisssoft.com/en/products/products/kisssoft-system-module/modeling/modeling) | 可编辑的参数化系统模型和设计探索是产品能力。[产品简介](https://www.cadence.com/en_US/home/resources/product-briefs/romax-software-suite-product-brief.html) | 不能用“别人没有库/变体”作差异点；可以设计显式、版本化、可枚举的本地契约。 |
| 参数控制与自动化 | SKRIPT 与 COM 已核实；具体轴模型字段可通过文中函数修改。[参数研究](https://www.kisssoft.com/en/news-and-events/newsroom/streamlined-parametric-study-using-skript) | Batch Running、研究 targets/results、自动报告和导出已核实。[2026.1](https://community.cadence.com/cadence_blogs_8/b/pss/posts/romax-2026-1-a-new-foundation-for-drivetrain-simulation) | 应比较所需操作是否可表达、失败是否可追踪、结果是否可复现。本文没有做操作覆盖或效率基准。 |
| API 边界 | 公开文章证明 COM/脚本能力，未验证完整接口、拓扑创建覆盖与授权。 | 官方 API 服务落地页确实存在，但未取得调用契约；不能把它直接当完整桌面模型 API。[API 落地页](https://api.romaxtech.com/) | 外部工具适配层须通过正式文档和实际安装验证，不以页面标题推断 API 覆盖率。 |
| 数学与工程保真度 | 系统强度、寿命、损失、热平衡及部分振动分析已有官方说明。[计算](https://www.kisssoft.com/en/products/products/kisssoft-system-module/calculation/calculation) | 官方套件描述包含多种分析层级；并非每一项都属于同一产品或许可。[产品页](https://www.cadence.com/en_US/home/tools/msc-software/romax.html) | 本项目一期若只做准静态运动/载荷/功率方程，需明确与详细接触、柔性体及动态分析的界面。 |

这些资料没有给出可与本库直接比较的穷尽拓扑数、公开单元插件 ABI 或全局最优保证。其缺席于所读页面不能当成软件绝对不具备这些能力的证明。

## 可借鉴的 1D 物理端口语义

下面先区分官方定义，再给架构推论。

| 端口 | 非 flow 位势变量 | Modelica `flow` 字段 | 功率所需运动量 |
|---|---|---|---|
| 旋转 | 角度 `phi` | 切面转矩 `tau` | `omega = d(phi)/dt`，`P = tau * omega` |
| 平移 | 位移 `s` | 沿约定轴的切面力 `f` | `v = d(s)/dt`，`P = f * v` |

连接集合生成同位势约束与带方向符号的 flow 零和方程；符号由层级内外侧的连接约定决定。若应用统一规定所有端口 effort 正向指入元件，同一节点可写为运动变量相容与 effort 代数和为零。不能忽略层级展开、端口朝向与单位检查。[Modelica 3.6 第 9 章](https://specification.modelica.org/maint/3.6/connectors-and-connections.html)

若本项目的报告采用 `effort=(tau,f)`、`motion=(omega,v)` 的工作命名，应另行说明它与 Modelica `flow` 语法的区别。准静态转速网络可以直接用 `omega/v` 建代数相容方程；这属于本项目的模型选择，不是照搬完整 Modelica 位置/状态语义。

官方两轴端加支座的基础模型把支座转矩写成两轴端转矩之和的相反数，并允许支座显式连接或隐式固定。[支座基础模型源代码](https://raw.githubusercontent.com/modelica/ModelicaStandardLibrary/v4.1.0/Modelica/Mechanics/Rotational/Interfaces/PartialElementaryTwoFlangesAndSupport2.mo) 因此可以借鉴三点：

- `ground` 是运动约束和反力未知量的边界，不是删去反力的标志。
- 固定构件仍可承受载荷；行星固定齿圈与丝杆导向等约束应进入平衡和验收。
- 1D 标量端口提供扭转/平动与功率层的关系。对于蜗杆、交错轴和伞齿轮，真实三维壳体反力矩、齿轮径向/轴向力与轴承反力还需要局部坐标、力系恢复和结构模型；不能把所有不同轴向转矩直接当同一轴标量相加。

最后一点是适用范围判断，不是声称该 1D 标准提供了三维载荷恢复算法。

## “数学编译”的准确说法

以下是由连接方程语义导出的**拟议实现路线**，不代表 gearbase 已实现或通过验证：

1. 从类型化端口、连接图、元件参数和运行模式生成实例；检查单位、局部方向、约束成员与端口兼容性。
2. 展开元件的运动学、本构、损失及约束方程，再生成连接相容与节点平衡方程。元件之间的传动关系来自元件方程，不能把齿轮的两端误作刚性同轴连接。
3. 加入驱动、负载和固定边界，识别已知量/未知量，检查自由度、结构秩、冗余或冲突边界与无约束支路。
4. 对一期约定的代数/准静态问题求解；按方向或工作区间处理效率、回驱、自锁等模式，不能默认一个常数传动比包含了这些性质。
5. 输出节点状态、端口 effort、支座反力、损失和残差；把恢复后的工程载荷交给独立评级器或外部详细工具。

“图展开成方程再求解”可以描述为受限模型的数学编译。若没有惯性/柔性状态、时间积分、初始化与事件处理的实现及验证，不能把这一路线称为已经具备动态仿真。功率守恒检查、静力平衡通过，也不证明瞬态、NVH 或详细接触行为正确。Modelica 的连接语义只为该路线提供权威参照，不能替代本项目验收。

## 工业先例的可用粒度

机器可读登记见 [industrial-precedents.json](industrial-precedents.json)。本次仅收五个产品族，覆盖混合螺旋齿/蜗杆、带前级的行星、平行轴多级、重复行星等类别；各条保留来源、级数限制和未知项。它们均未作为有完整工况及参考解的命名 OEM 案例登记。

需要特别保留三个差别：

- 厂商列出的应用领域 ≠ 已识别的真实客户安装；匿名安装描述也不足以复现工况。
- 某产品族支持三级/四级 ≠ 已知每一级的固定成员、轴系和顺序；必须依据选定型号细化。
- 某族有工业产品 ≠ 该族所有排列、功率方向、空间布局和参数范围都工业可行。

预建组合库首先应冻结 `stage_count_policy`：按单一功率路径还是总元件数计级；一个行星组如何计级；丝杆或其他运动转换是否计入；复合部件如何展开。随后才可报告去重后的数量。级数与汽车的可选择档位数没有等价关系。这些均为架构计数与证据纪律，不是行业统计。

## 可直接采用的定位措辞

> 本项目拟将传动单元写成带类型端口、方向约定、本构关系、适用域与验收条件的数学契约，并在明确的最多四级范围内建立可追溯的预建组合库。商业传动工具已经具有系统参数化、部件评级、优化与自动化能力；本项目的具体价值须以契约复用、组合可表达性、验证覆盖和工程迭代证据评价。现阶段讨论限定于准静态架构，不作动态仿真已完成、全行业覆盖或全球首创的主张。

这是本研究给出的建议表述，尚不是产品交付事实。

## Where This Review May Be Wrong

- 所读公开页面可能没有展示某个版本、许可或内部接口的完整能力。要评估商业工具能否完全替代拟议工作流，需查相应版本正式手册并在授权安装中验证；不能由公开页的遗漏推出能力缺失。
- 这是官方文档事实核查，没有检查 gearbase 当前代码或实算结果。任何“已有”“已验证”的实现措辞仍须由仓库证据和本会话验收补齐。
- 产品族网页可能更新，且旧 S-series 技术注记不能覆盖当前所有变体。需要把正式导入库的具体型号、图纸/手册版本与级数证据绑定，再形成工况和数值参考解。

## 检索与复核记录

完整来源、访问状态与不支持的推论见 [sources.json](sources.json)。只将直接打开的官方正文或源代码作为事实依据；部分 SimCompanion 页面返回加载/CSS 错误，另一个 Enduro 产品页超时，已登记排除，未把搜索摘要冒充其全文。没有 GUI 操作、外部发消息、API 调用试验或求解器运行。
