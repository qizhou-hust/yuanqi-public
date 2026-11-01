# v0.20 案例库与既有需求生成挑战

评估对象为 `D:/my_Works/Gears/gearbase-v020-work`，commit `80117283778cf8732b5557fa15c2e41f626f92fc`、VERSION `0.20`。本轮所有文件写在本目录；没有改核心、需求、标准数据、金标或验收限值，没有启动 CAD/GUI/FE。

当前入口能在**指定架构族**内枚举许多参数方案。对本轮三项原始 Stage0 需求实际返回的 60 个候选，全系统检查均为 blocked；W2W 的 15 个候选另有明确的热失败。不能由“返回候选”推导为工程可行，也不能将 H2/W2W/P2 三项不同需求拼成“同一需求的三种实现”。本轮对实际 `requirement_compile` 的不指定族请求得到 unsupported；携带原负载与轴关系的完整合同则被当前 Stage0 输入模式拒绝。

## 来源集合与去重

| 集合 | 本轮确认的单位数 | 类型及边界 |
|---|---:|---|
| `data/m31/cases/C001..C050` | 50 | 自编派生传动实例；50 个文件全部声明 `original_derived_benchmark_not_a_source_reproduction`。恰有 50 种作者预先写好的 stage-kind 顺序，未证明来自一个需求的自动生成。 |
| `data/flagships-stage0` | 3 | 历史自编 Stage0 回归需求，固定 H→H、W→W、P→P 家族。关联 `flagships-system` 是同题的系统源文件。 |
| K01..K05 | 5 | 商业工具固定齿轮副对拍身份。source/factors/COM/report/P3/P4/诊断文件不增加题数；K04/K05 是 EV 的两个级，不是两台完整变速器。 |
| TR30 例1..8 | 8 | 标准固定齿轮副算例。表、附录、CSV、商业工具跟进均按例号去重。本子任务只盘点其元数据，未重新宣称整例验收通过。 |
| 外部引用注册表 | 7 | 其中 2 项元数据描述有实物试验的来源（NREL GRC GB2、ROOZING/VOLBEDA 摆线执行器），4 项公开作者 CAD 项目、1 项 python-gearbox 齿轮副 worked example。属于外部来源候选，不是本轮已经完成的真实工程输入和金标。 |
| `v017-capability-probe` | 1 | 自编圆柱齿轮系统有限枚举能力探针；源代码明确说不是 C001 的真实工程数据。 |
| `data/bench/v1/requirements.json` | 40 | 语言需求评测条目，金标尚待工程师标注。只盘点，未写金标；与 50 个传动实例使用不同分母。 |

这些单位不能相加后宣称为“真实整机案例数”。案例库保存在 `case-catalog.json`，字段来源采用文件 SHA、JSON pointer 和既有叶子的 source/provenance/certificate。`inventory.json` 给出消费过的源文件及代码哈希。

**分发边界：本目录是 LOCAL_PRIVATE 审核材料。** 本地 catalog 的 TR30 `field_sources.input_contract` 和商业来源/证据细节可能含私有数字转录；没有附带PDF/native并不构成全面公开合规。公开包应将这些字段换成ID、类别、源哈希、引用指针与限制，商业项公开计算摘要/哈希，私有版留在本地。

一题多文件按稳定设计/算例 ID 去重；同 ID 的既有派生变体保留 lineage 和输入 SHA，不另外增加独立需求。C001 的 golden、math-source、factors、system 和 G1 结果仍属于 C001。旧 `gearbase-v0.8-work/gearbase` 的 50 题与 7 个外部引用，逐文件与当前仓比较 **57/57 字节相同**，没有再次入库。

## 本地额外资料的扫描边界

- `gear-compiler`：只列首层、读取 `stage0/SPEC.md` 及明确的 `reports/benchcad-local-plan.json`。SPEC 指向历史 H2/W2W/P2 旗舰同源；旧 plan JSON 在 line 119 column 7 解析失败，错误与 SHA 已记入 inventory，本轮未修复或从坏索引猜造新案例。
- `fea-case-library/CATALOG.json`：索引有 25 个 FE 问题身份，包含历史齿轮/数值试验与 5 个公共数值基准。索引中的 physical_case_count 是其自身口径；不能解读为 25 个独立真实传动需求。本轮未重跑 FE。
- `gears_doc`：首层有齿形脚本、文献 PDF、归档及演示。未解析正文，不能判断是否还有可提取的独立工程题。
- 工作区的 `POD需求确认.xlsx`、蜗杆/斜齿 DOCX、XLSX/XLSM 已列为待整理输入，仅绑定哈希，未猜测其中需求。

因此，本轮可描述当前仓的完整案例结构和上述有限本地索引；**不能声称整个本地工作区的真实工程题数量为 0**。未遍历 D 盘，没有复制或上传标准扫描件、商业原生文件及外部 CAD 原件。

## 实际运行的入口与计数

运行命令：

```powershell
python -B 'D:/my_Works/Gears/v020-freeze-assessment-2026-11-01/cases/run_challenges.py' --source 'D:/my_Works/Gears/gearbase-v020-work'
```

脚本 SHA256：`0aff757eb3545a239264ab471d0f252a902ddec9c7d4475e5fcb115b36e116ff`。实际命令参数向量 SHA256：`4668fc03f366e8e4726200ad986140884c8154eb74aac25af4e7b94932d27452`。命令、环境、基线、源 SHA 和运行时间位于 `challenge-results.json.provenance`；源 git status 前后均为空。脚本只向自身目录写结果，下一次也拒绝 commit/VERSION 漂移。

已检查的路径：

- `gearmath.tools.intent.requirement_compile` → `gearmath.tools.flagship_workflow.run` → 原 H2/W2W/P2 求解器。
- 对每个实际返回候选，调用 `gearmath.product.flagship_system.solve`，仅在内存中选择该现有候选的 rank，保留原始需求。
- 对两个既有固定解，调用 `gearmath.product.design_check.check(..., 'all')`。
- 50 题通过明确披露的 `archive/m31/src/gears/benchmark/math_adapter.verify` 桥，算术路由到当前 `gearmath.compat.m31.calculator`/kernel。此项是新算出的理想无损运动学重放，非新的多族工程规划入口。

| 原需求 | 原始成对域 | Stage0 带内接受行 | 实际返回 | 返回中参数变体 | 架构族数 | 运动学复核 | Stage0 几何复核 | 全系统 pass / blocked | 热 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| H2 | 378216 | 9948 | 40 | 40 | 1 | 40/40 | 40/40 | 0 / 40 | 未实现 |
| W2W | 980 | 15 | 15 | 15 | 1 | 15/15 | 15/15 | 0 / 15 | 0 pass、15 fail |
| P2 | 117855 | 2311 | 5 | 5 | 1 | 5/5 | 5/5 | 0 / 5 | 未实现 |

表中“Stage0 接受”是原求解器自己的几何/速比谓词，**不含全部工程约束**。运动学/几何复核分母仅为实际返回行，全系统 pass=0 也只针对检查过的返回行；没有据此断言其余 9948/2311 行都不可行。空间、齿面接触、完整运动周期与带壳体干涉均未验证，不能把表中的“几何”写成空间布置通过。

H2 的两个去重 stage 域为 459 和 824，利用速比剪枝只计算 9948 个配对，40 是原始 `max_candidates` 输出上限；并非只有 40 个带内解。P2 的 4386 是 stage 检查次数，485 是去重 stage identity，117855 是无序 stage 配对；2311 个带内配对压缩成 5 个 Pareto 代表。P2 每级 `m_options=[2,2.5,3]` 是未实例化的模数选项，不再乘成新拓扑/新方案。模块的原始 scope/search 字段完整保留。

| 需求源文件 | 文件 SHA256 |
|---|---|
| H2.json | `86883650922342a117c90bae2f2a930a7cd09e7ed084f6de911220cf834fc355` |
| W2W.json | `f1e1b6e70dc9dad4d3f3b1b198bf28b470e1b3dddc39a20b6e6bd365721c0a78` |
| P2.json | `47e7011e0984e306a9ab8183fc242bd34b23d30e754697d8162d27063dacbc15` |

`H2/W2W/P2-workflow-raw.json` 是本轮实时求解返回；`*-candidates-checked.json` 是逐候选实时复核，`*-system-first.json` 保留首选完整缺项。所有文件的摘要在最终文件清单中绑定。

## 各族的可行性与不足

**H2**：原需求锁定 a1=80 mm、a2=100 mm、i=10±3%、mn∈{2,2.5,3}、β8–30°，是零变位 sampled 域。40 个返回行均满足本轮所测的速比与中心距谓词；每行仍缺齿宽、材料、刀具、寿命/方法与系数等评级输入、效率边界、支承布置/轴段/截面、轴承、键。首选模板含 86 个缺失叶子和 7 个结构缺项，系统阻断。已有系统源明确的输出为 600 N·m@150 rpm；没有由此擅自补入输入转矩或效率。

**W2W**：原需求是 a1/a2=100/125 mm、1440 rpm、i=144±2%、Tout=800 N·m、ρv=5°、K=12 W/(m²K)、A=0.5 m²、环境30°C/油温上限90°C。首选 i=16×9、ηtot=0.5408407223、Pin=1548.99 W、Qloss=711.23 W、Areq=0.987825 m²、油温148.539°C。按原简化热模型，15/15 返回候选热失败；提高散热面积/冷却的建议属于后续需求变更，不在本轮改数。强度、磨损/胶合、三向啮合力及轴承/轴/键系统仍 blocked。

**P2**：原需求 i=40±2%、1440 rpm、固定齿圈/太阳入/架出，只有整数几何域。5 个代表满足测过的同心、相位整除、邻接、顶隙与速比谓词。源码明确警告：全零变位同心下两个啮合同时理论零侧隙，需要变位设计；Stage0 pass 不等于可制造装配。原需求没有扭矩/功率、效率、热、行星载荷分配和 ISO 强度系统闭合。首选模板 54 个缺失叶子和 7 个结构缺项；全系统 blocked。

三者的效率边界、负载和轴关系并不相同。`equivalence_group_id` 分别为 `H2-original-demand`、`W2W-original-demand`、`P2-original-demand`，没有将三者归入同一需求组。

## 同一需求的跨族生成探针

`SAME-H2-DEMAND` 与 H2 共用 `equivalence_group_id=H2-original-demand`：保留原中心距、速比、模数域、角度域与输出预算，合同同时保留源文档已有的 600 N·m@150 rpm 与 H2 原来的平行轴含义。没有给 W/P 猜效率、输入转矩、轴姿态或新增工程限值。

实际调用有两项：

1. 原 Stage0 需求只去掉 family，经 `requirement_compile` 和 `flagship_workflow.run` 均返回 `blocked_unsupported_scope: Unsupported original flagship`。
2. 将原 system 源的 `operating` 叶子和原平行轴语义保留在请求中，实际 compiler 返回 `blocked_invalid_inputs: Only explicit Stage0 requirement fields are accepted`。

因此，当前这个注册路径无法在不指定族的同时承载完整公共工程合同并跨族出解。计数记为 **null**，表示未建立搜索对象，而不是已经搜索并找到 0 个可行跨族方案。最小请求并未把负载交给 Stage0；第二个请求正是对该输入模式限制的实测，不能隐去这一点。

W2W 不可直接拿来替代此 H2：其 i=144、中心距100/125、输入1440rpm/Tout800 与原 H2 不同；蜗杆轴关系也不同，原合同未许可轴变换。P2 的 i=40、同轴 NGW、缺输出载荷及效率，同样不可比较。具体 `not_comparable` 列表和需要追问的公共边界保存在结果 JSON。

## 固定解检查与字段缺口

| 固定检查 | 输入身份 | 本轮结果 | 解释 |
|---|---|---|---|
| C001 G1 | 既有 derived-candidate 的20/36、mn=2、b=30mm、900rpm/25Nm | gear_rating pass，全系统 blocked | SH1/2=1.190815/1.273158；SF1/2=4.506427/4.878201。依赖材料/工况/系数假设。只验原双级系统的G1派生变体。 |
| K01 spur | 厂商例25/76、mn=6、b=44mm的既有输入/证据 | gear_rating blocked、manufacturing pass，全系统 blocked | SH1/2=1.332842/1.388188；SF1/2=2.521161/2.429805 数值超过给定限值，但 εα,min 缺来源，评级整体仍 blocked。 |

两个固定检查各只有 **1 个调用方给定解、0 个自动生成解**；其 `unique_topology_count` 和 raw/stage_A 计数为 null。C001 原始50题 G1 的 b=10mm，而本次既有 math-source 对应派生 b=30mm，不能隐去变体差异或把该单级通过推广为原始双级完成。`manufacturing pass` 仅为所给模型的公差/尺寸计算，并非实际制造或整机空间合格。

重要缺口直接来自既有源：

- C001 支承合同冲突：KHβ 输入使用 bearing_span60/offset15，而 system_boundary 给 supports -5/45、齿轮位置20（跨距50且居中）。输入联轴器作用位置未给；轴/毂/键材料及许用值为 synthetic test；油品、Ra/Rz口径、胶合/微点蚀/热的最小限值未闭合。
- K01 εα,min、胶合与微点蚀最小安全限值未确认；轴、轴承、键、过盈、热参数不存在。没有为过门填写 1.2 等建议限值。
- NREL 外部元数据仍有试验HSS偏置方向/应用、材料牌号、轴承预载/刚度、测量通道到零件载荷路径、齿根桥到MPa标定、同载荷独立应力真值及相位覆盖等空缺。ROOZING/VOLBEDA 的实际打印PLA弹性/许用值、轴承刚度、原始时间测量等仍缺。本轮只确认本仓元数据内容，没有重新鉴定实物真值。
- Utkarsh 旧来源元数据的 README 级齿数为20/80与18/108，而登记的STEP产品名为23T/69T与34T/69T；应先统一来源版本/参数，不能直接合成金标。

## 50题支持度：实时计算与历史报告分开

| 能力 | 本轮证据 | 可作何种结论 |
|---|---|---|
| typed ideal kinematics | 本轮50/50重算，通过与 archive 独立理想链对照；见 `benchmark50-kinematic-replay.json` | 理想无损转速/齿条线速度及已实现名义力，不含效率和承载资格。 |
| 完整强度输入 | 仅C001有engineering，且声明project assumptions | 不是50个真实承载工程题；49题没有这一组输入。 |
| 全部级都是spur/helical | 6题：C001/C002/C003/C004/C006/C008 | 仅为类型/数据静态分类；不是6题强度系统通过。 |
| 全系统与空间 | 本轮没有新的整机/空间验证；C001既有G1系统检查blocked | 已验证整机数0，不能用缺验证推断全部物理设计不可行。 |
| 历史M23 matrix | 原始family math_kernel 25 pass/25 unsupported；exact_velocity50 pass、typed_math50 pass、stage STEP4 pass/46未跑、strict projection6 accept/44reject、full_machine50未跑 | 全部为hash绑定的**报告派生**计数，未升级成当前几何复算。 |

后续持续回归应至少保留以下结构：一个需求有固定 demand_id、revision/source_sha、公共输入/输出轴位姿、n/T/功率效率边界、包络、寿命/负载谱、材料/热约束；其下再记录 family 与参数 variant。由目标资格等级分别统计 returned、Stage0、强度、支承系统、空间 pass/blocked/fail，输出预算和Pareto压缩另列，不用一个 feasible 数混合。

优先从已有的真实输入资料整理一个可冻结的公共需求；遇到缺失轴关系/效率/载荷边界时保留待确认。随后对获准的不同族运行各自评级，不把未实现的蜗杆/行星强度用圆柱齿轮评级代替。保留一个需求多实现的证据分组和本轮失败项，下一轮在同一输入 SHA 下看新增通过哪些门。标准/商业对拍继续作为公式证据；工程师未标的语言题不制造新金标。

## Where This Review May Be Wrong

- 扫描边界只覆盖当前仓和四个明确兄弟目录的有限索引；未解析的工作表、DOCX、PDF或归档可能含未迁入的真实工程题。应解析这些明确来源并逐字段核对后补库，不能把本次盘点当全磁盘普查。
- 不指定族探针覆盖现有注册 requirement_compile/flagship_workflow、固定族模块和有明确范围的圆柱系统枚举；可能存在未审阅的实验性入口。若提出另一入口，应在相同 H2 合同下给出实际调用与源哈希，而不是用不同族的默认示例替代。
- Stage0复核、50题算术桥和系统模板都复用本仓部分公式，不能构成独立工程真值；外部引用的实物资格也只读了本地元数据。应以统一输入的独立工具/原始测量、完整轴系与空间证据复核后提升资格。
