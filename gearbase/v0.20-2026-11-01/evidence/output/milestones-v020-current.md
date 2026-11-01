# M32–M40 进度表（gearbase 0.20）

口径：docs/里程碑口径.md（验收门条目完成数；partial 不计入）。不是工程验收。

| 里程碑 | 验收门条目 | done | partial | open | 完成度（done/总） | 接力交接估计 |
|---|---|---|---|---|---|---|
| M32 | 5 | 5 | 0 | 0 | 100% | **关闭** |
| M33 | 4 | 3 | 1 | 0 | 75% | partial |
| M34 | 4 | 3 | 1 | 0 | 75% | partial |
| M35 | 2 | 1 | 0 | 1 | 50% | partial |
| M36 | 3 | 1 | 2 | 0 | 33% | open |
| M37 | 4 | 0 | 0 | 4 | 0% | open |
| M38 | 4 | 3 | 1 | 0 | 75% | partial |
| M39 | 3 | 2 | 1 | 0 | 67% | partial |
| M40 | 3 | 0 | 0 | 3 | 0% | — |

## 仓库状态

- 测试用例（发现数，未运行）：1379
- 编译错误：0
- 外部对拍文件：data/kisssoft 7、data/kisssoft_v014 13、data/kisssoft_v015 19
- 未决用户决定：接力交接最新'需要用户' 0 条；系统层输入 {'C001': 5, 'K01-spur': 2}
- bench 金标待标注：42

| 模块 | 公式数 | 证据等级分布 |
|---|---|---|
| gear.formulas（CYLINDRICAL_PAIR，等级取 data/registry） | 88 | E2: 4、E5: 83、none: 1 |
| gear.scuffing_integral | 36 | E5: 27、none: 9 |
| gear.scuffing_flash | 19 | E5: 11、none: 8 |
| gear.micropitting | 23 | E5: 20、none: 3 |
| system.thermal_14179 | 25 | none: 25 |
| system.din743 | 44 | E5: 20、none: 24 |
| system.din6892 | 8 | E4: 2、E5: 4、none: 2 |
| system.din6892_b | 15 | E4: 7、E5: 8 |
| system.din7190 | 13 | E4: 4、E5: 6、none: 3 |
| system.iso281 | 15 | E5: 2、none: 13 |
| system.shaft_line | 3 | none: 3 |
| system.shaft_beam | 4 | none: 4 |

## 条目明细

### M32
- [done] 原型 21 项测试全绿（manual：docs/M32-验收报告.md：双系统真实 CI 原型 21 项通过）
- [done] M31 旧测试经适配器回归（manual：docs/M32-验收报告.md：原 73 模块 678 项全过、零跳过；原 81 文件哈希与真实导入来源已验证）
- [done] 守门在 CI 生效（manual：docs/M32-验收报告.md：托管 CI 守门及真实破坏性反例通过，附源码提交与运行链接）
- [done] 全库可编译（probe：py_compile gearmath/**/*.py：0 个错误）
- [done] 通过量纲校核（manual：docs/M32-验收报告.md：双系统输入/内核/注册表与全量测试门通过）

### M33
- [done] 22 个证据系数中 ≥20 个改为公式（manual：docs/M33-closure-current.md；output/m33/closure.json 逐项映射20/22，KA为输入、YST为标准常数）
- [partial] ISO/TR 6336-30 全部示例逐系数复现（E4）（manual：docs/M33-验收报告.md：例1–4 数值验收、例5–8 全链；例7 HB→HV 待用户）
- [done] 主链误差 ≤1%（probe：v0.20 用户指认例7/8八条几何差异；历史2/6身份未复原，不替代完整E4或全部齿轮族；当前模型8/8相对误差≤1%且重放/来源哈希有效，最大0.00475106%；硬度、fsh0、原表输入身份仍属E4开放项）
- [done] C001 新链重算并逐项解释与 M31 差异（manual：docs/M33-closure-current.md；18项旧链收据对照，九次迭代重建与当前收敛结果差异已解释）

### M34
- [done] 一个设计只有一个可编辑文档（manual：docs/M34-closure.md；真源所有权/CAS/元数据token及导入、优化真源读取回归）
- [done] 梯度与中心差分一致到 1e-6（manual：output/m34/closure/closure.json：120个AD/FD比较，最差1.22e-8）
- [done] H2 旗舰结果一致且评估次数下降（manual：docs/M34-closure.md；原始Stage0同域同排序，378216→9948次，不另加未规定强度门）
- [partial] Claude Desktop / Code 实连可用（manual：真实Claude Code已连接MCP发现工具，模型HTTP403额度不足，尚无真实tools/call，不能关闭）

### M35
- [done] 独立对标 ≥5 例（E5），误差 ≤1% 且可解释（probe：data/kisssoft 案例文件 5 个（K01-spur.json, K02-helical.json, K03-premachining.json, K04-EV-stage1.json, K05-EV-stage2.json）；误差 ≤1% 与可解释性见 docs/M33-对拍契约.md（人工））
- [open] 经外部工艺人员审阅的变位斜齿制造图（manual：docs/接力交接-2026-10-30.md 第2节 M35 缺口：外部工艺审阅）

### M36
- [partial] C001 全系统（齿轮、轴、轴承、键）由同一张图校核（probe：design_check(C001) 子检查状态 {'gear_rating': 'pass', 'shaft': 'blocked', 'bearing': 'blocked', 'key': 'blocked'}）
- [done] 系统优化结果与小规模全枚举一致（manual：docs/v017-system-optimization.md；output/m36/closure.json；显式齿轮/轴/轴承27组合独立全枚举对照，来源与代码哈希绑定）
- [partial] 三个旗舰与编辑用例回归一致（probe：gearmath/product/flagship_system.gate_probe：H2 系统级 blocked（{'shaft': 'blocked', 'bearing': 'blocked', 'key': 'blocked', 'gear_rating.stage1': 'blocked', 'gear_rating.stage2': 'blocked'}，模板缺项 93，unsupported 0）；W2W 系统级 blocked（{'shaft': 'blocked', 'bearing': 'blocked', 'key': 'blocked', 'gear_rating.stage1': 'blocked', 'gear_rating.stage2': 'blocked'}，模板缺项 62，unsupported 5）；P2 系统级 blocked（{'shaft': 'blocked', 'bearing': 'blocked', 'key': 'blocked', 'gear_rating.stage1': 'blocked', 'gear_rating.stage2': 'blocked'}，模板缺项 61，unsupported 5）；编辑用例 6/6 通过；Stage0 共同部分逐位一致 True；系统级缺项未补齐前保持 partial（不编造参数），见 docs/v017-system-regression.md）

### M37
- [open] 斜齿副峰值落在 Hertz 估算 ±15%（manual：docs/接力交接-2026-10-30.md：L2/L3 未完成（L1 仅二维 Hertz penalty 冒烟））
- [open] YFS FE/ISO ∈ [0.90, 1.10]（manual：模块 B 原包缺失）
- [open] σH0 ∈ [0.92, 1.08]（manual：L3 *CONTACT FILE 待用户）
- [open] 优化器内环 → 最终 FE 复核闭环，代理误差 <3%（manual：未开工）

### M38
- [partial] 凭空数字率为 0（金标评测）（manual：docs/M38-bench-closure.md；数字可追溯已达成（规则721/Terra681/Sol684 不可追溯 0），但验收门原文要求金标评测：bench v1 仍有 42 处 pending_engineer_label，工程师标注完成前保持 partial（v0.17 O 复核））
- [done] 三个旗舰需求端到端跑通（manual：docs/M38-closure.md；原H2/W2W/P2显式需求→真实MCP编译→求解→复查；保留Stage0范围及W2W热失败）
- [done] 新机 10 分钟内接通（manual：docs/M38-closure.md；私有GitHub托管全新Windows VM、嵌入Python、实际MCP工具调用，详见receipt）
- [done] 首轮多模型评测报告（manual：docs/M38-bench-closure.md；真实terra/sol输出与原始收据、完整限制，无人工金标）

### M39
- [partial] 高速齿轮可完成全失效模式校核（probe：design_check(K01-spur，代高速例) 子检查状态 {'gear_rating': 'blocked', 'scuffing': 'blocked', 'micropitting': 'blocked', 'thermal': 'blocked'}）
- [done] 体积—中心距—安全系数三目标前沿（manual：docs/M39-source-frontier-closure.md；同源12点有限域前沿，非全局最优）
- [done] 公差下可行率报告（manual：docs/M39-source-frontier-closure.md；每点3个显式公差情景，明确分母与blocked，不作概率外推）

### M40
- [open] 行星至少 1 题完整校核 + 1 例独立对标（probe：gearmath/gear 族模块：无）
- [open] 蜗杆至少 1 题完整校核 + 1 例独立对标（probe：gearmath/gear 族模块：无）
- [open] 锥齿轮单独立项评估（manual：未立项）

