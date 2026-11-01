# v0.16 OPT3 / M34 优化主线审查

审查对象：原始 stage4 `extracted/gearbase`；修复只在 `D:/my_Works/Gears/gearbase-v016-milestone-work`。本路未操作 COM、GUI，未更改历史档案，未扩搜索域。使用 optimizer-research-route-guard、objective-review；修复另按 root-cause-analysis、system-impact-analysis、systematic-debugging、TDD 执行。

## 结论与阻断

1. **三例外部计算不能关闭整个 M34。** 顶层验收门是唯一可编辑文档、梯度对照 1e-6、H2 一致且评估次数下降、Claude Desktop/Code 实连（`docs/顶层设计.html:496–503`）。`gearmath/tools/milestones.py:137–143` 的 H2 仍 partial、实连仍 open。外部商业软件闭环只是后来增加的一条产品证据。
2. **原包梯度 done 过度泛化。** `milestones.py:140` manual done；但 K02/K04 存档 `assurance.optimality[0].gradient_self_check` 为 inconsistent（3.27722439e-4 / 2.47258064e-4），其自身阈值甚至是 1e-4，已经宽于 1e-6 验收门。`docs/M34-优化器主线.md:120–124` 实际承认门只对 C001/K01 成立。
3. **本轮已最小修复导数语义，尚不等于重新优化。** 6 个 K02/K04 起点/连续 NLP 解点/制造回圆点全部目标和约束导数过 1e-6，所有前向值逐位保持；原始存档的 KKT/solver fingerprint 仍属于旧版本。本轮不把历史解重标为新求解器最优解。
4. **K02 原始预测外部闭环未过原门。** 实际 SH 差约 1.1%、SF 差约 1.7–2.9%，不是可用 1e-4 门解释的误差。held DIN 公差变化导致重算 KHβ/KFβ 变化，是高优先级差异；不得用外部实测值覆盖输入来声称原始事前预测通过。

## 输入契约与外部证据

完整高精度请求、预测、coefficient_status 已写 `preflight-opt3.json`。来源为三份原始 `output/m34/opt3/*.report.json`，无需从短文本反推精度。

| 例 | z1/z2 | mn | b1/b2 | x1/x2 | a | 齿顶/轴口径 |
|---|---|---|---|---|---|---|
| OPT3-1 K04 | 25/57 | 2.5 | 20.8/18.8 | .423/.1330438814 | 118.5306742 | kFaktorFlag=true，kXmn=0；其余原生输入保留 |
| OPT3-2 K01 | 23/68 | 6 | 28.6/28.6 | .453/−.2485 | 274.2071586 | kFaktorFlag=false；显式轴 88/8.8/44，lsdFlag=true |
| OPT3-3 K02 | 26/98 | 2 | 27/26 | .3/.07388831908 | 128.5292024 | kFaktorFlag=false；显式轴42/4.2/21，lsdFlag=true |

自动 kXmn 本库不圆整；KISSsoft 通常按 .001 mm 圆整。K01 原始 εα 差 2.4733e-5；K02 εα 差 1.56257e-4，均超几何原始 1e-6 门。可做额外明确归因层，不应覆盖 raw 证据或放宽门。

外部实际读取仅来自主路输出各 `OPT3-*/run.json`。K04/K01 四个安全系数接近预测，但 K04 **KHβ=1.2874948181504524 两侧完全相同，模型状态 held**。这是外部模型继续采用原持有值，不能证明本库已具有 KHβ 独立随几何重算能力。

## 系数边界

依据 `gearmath/gear/multi_factor_docs.py`、`factor_recompute.py:coefficient_status` 与每份 run.json：

| 模型 | 仍持有/证据保持 | 由公式/适配重新计算 |
|---|---|---|
| K04 | KHβ、C_R、Y_ST、小轮孔径25、f_ZCa；部分材料/工况作为输入 | KV、KFβ、KHα/KFα、ZL/ZV/ZR、寿命/齿根辅助因子、ISO1328公差、轮坯大轮孔径、几何 |
| K02 | ZNT/YNT、YδrelT/YRrelT/YX、ZW/ZX、DIN3961公差（含fHβ5）、f_ZCa、小轮孔径0、显式轴42/4.2/21、Y_ST | KV、KHβ方法C、KFβ、KHα/KFα、ZL/ZV/ZR、YB/YDT、轮坯大轮孔径、几何/自动齿顶缩短 |
| K01 | Y_ST、显式轴88/8.8/44；材料和工况输入 | 主要强度、寿命、齿根、ISO1328公差、KHβ、轮坯孔径与几何/齿顶缩短 |

`coefficient_status` 关注列表不包含全部 hold_evidence，例如 f_ZCa；不能只看报告的精简 hold 清单判定无其余证据输入。recomputed 表示存在公式路径，不表示其依赖均已独立校准，或公式标准证据等级已经提升。

### K02 未经代入对齐的差异

完整逐字段表：`optimizer-factor-diff.json`（全部三例）。相对差定义 `(本库−外部)/外部`。

| 量 | 本库预测 | 外部实际 | 相对差 |
|---|---|---|---|
| SH1 | 1.172888425 | 1.160373016 | +1.07857% |
| SH2 | .960843269 | .950197290 | +1.12040% |
| SF1 | 5.930546177 | 5.761281862 | +2.93796% |
| SF2 | 4.659496728 | 4.580931662 | +1.71505% |
| KHβ（重算） | 1.418552995 | 1.457616778 | −2.67998% |
| KFβ（重算） | 1.337515042 | 1.368086457 | −2.23461% |
| KHα/KFα（重算） | 1.149847846 | 1.143109672 | +.58946% |
| fHβ5（held，µm） | 6 | 6.5 | −7.69231% |
| ZNT2（held） | .889610384 | .889242392 | +.04138% |
| YNT2（held） | .891638051 | .891250788 | +.04345% |
| YδrelT1（held） | .991379672 | .988837187 | +.25712% |
| YδrelT2（held） | .996531142 | .996842568 | −.03124% |

已验证这些差值；“DIN公差→KHβ/KFβ→安全系数”为有源码依赖支持的主要归因方向，尚未做逐项反事实分解，不能声称已完全解释残差。外部 K02 SH2 仅高于 .95 下限 .00019729，应作为边界可行候选记录，而非强裕度。

## 根因与最小修复

症状：K02/K04 导数与中心差分不符。触发：选择 `root_theta_iteration=kisssoft_step_1e-5`。机制：`kisssoft_multi._formulas` 给 theta 公式 tol=1e-5；`graph.Model.evaluate` 调用 `dual.solve_fixed_point`；原实现先按容差得到截断 θ，再在该近似 θ 处用隐函数导数 `dθ=∂f/∂p/(1−∂f/∂θ)`。中心差分微分的却是“执行有限步并按数值停止”的实际值映射。

原报告称“对偶数只微分截断后的迭代”与源码不符，当前源码原本已用隐函数法。问题是值与导数语义不一致。固定点形式为 θ = 2G/zn·tanθ·rad − H。

选择方案：Formula 新增显式 `fixed_point_derivative` 策略，默认 implicit；仅 KISSsoft θ 截断适配选择 finite_iteration。保持同一个迭代起点、前向运算顺序、停止阈值与最新迭代返回值，对执行的每一步传播 Dual。非默认策略进入 model_sha256。默认隐式调用、高精度固定点、internal_gear、tooth_thickness 均不自动切换策略。

拒绝方案：全局按 tol 猜策略（误伤其它固定点）、全局收紧 tol（改变已对齐商业软件的前向值）、差分梯度作生产求解梯度（替换白盒内核）。

分段边界：停止步数切换处有限迭代映射可能有小跳跃，不能保证任意邻域光滑。修复保证当前执行分支的链式导数；仍需在优化实际候选处进行梯度自检。不声称整个域的所有点都已过门。

### 验证与兼容性

新增回归先红：六个点均在 SF1/x1 失败，误差 1.382e-4–4.260e-4。修复后新回归 4 项通过（其中 6 个参数点遍历全部目标/约束），前向字典与修复前金标逐值 exact 相等。默认 implicit 的松容差正控仍返回隐式导数2；显式 finite_iteration 同值而导数1；不收敛仍抛错；策略改变模型身份。

只读先行诊断写回点：K04 最大误差 1.39109e-4 → 2.17071e-9；K02 3.47559e-4 → 1.09936e-8；K01原值约5.58e-9。证据：`optimizer-static-probe.json`、`optimizer_preflight_probe.py`。

相关测试：test_kisssoft_multi 29/29（含原商业齿根几何逐位回归），test_kernel_ext 17/17。最初使用 Windows cp1252 时1个CLI测试UTF8读取错误，设置PYTHONUTF8=1后消失。

最终相关回归共 **86项，OK（skipped=1）**，其中唯一跳过项为已有的私有KISSsoft v0.15证据重提取测试。未跑全库测试（遵循本路禁止广泛测试的范围）。独立进程测量 `theta-gradients-before.json` / `theta-gradients-after.json`：K02三个点修复后最大误差1.08e-8/1.21e-8/1.10e-8；K04三个点8.59e-9/1.82e-9/2.17e-9；六点全部 `forward_exact=true`。

内核指纹改变使旧存档正例的3个commit测试被正确拒绝，另1个确定性SHA测试不再相同。迁移采用新的真实K01小域求解写入独占 `output/m34/v016-derivative-fix`，历史 `output/m34/opt3` 不改。正例使用当前内核真实重放；新增负例要求历史内核不能冒充当前内核提交。未放松或绕过 fingerprint guard。最终相关结果见 `derivative-fix-related-tests.log`。

`derivative-fix-manifest.json` 记录源码/测试/当前生成投影/清单变动文件、3个新回放artifact和新solver指纹；`derivative-fix.patch` 包括相对原始包的这些差异。逐文件SHA核对已验证整个历史 `output/m34/opt3` 与原包不变，新K01回放内核指纹与当前源码一致。

### 包清单与 registry 边界

交付前用原工具 `python -m gearmath.tools.export_registry` 正规更新当前生成投影，再用 `python -m gearmath.tools.package_hashes` 刷新包清单。最终 MANIFEST 正规更新3个已登记registry文件的哈希，`package_hashes --check` 与 `export_registry --check` 均输出一致。沿用既有约定，新的tests/output文件由PACKAGE-CONTENTS完整覆盖，不提升证据接受等级。

前次静态检索“没有Formula/Model重建消费者”的结论已更正：`kernel/registry.py:replay_vector` 确实会重建单条Formula/Model用于标量向量回放。为保留执行语义，导出器现在仅在非默认时添加可选 `fixed_point_derivative` 字段；校验器认可并校验枚举；新增 `formula_from_entry` 用于恢复策略并由向量回放复用。旧记录缺该字段仍为implicit。新增真实AD roundtrip正控证明finite_iteration回环后值2/导数1，旧记录同值而隐式导数2，非法策略被拒绝。新增测试先红后绿；theta回归现5项通过。

当前registry是由代码生成的快照，区别于原生KISSsoft/TR30证据及历史signed优化档案，正确版本迁移需要重新生成。为分清AD与平台变化，本路从未修改的baseline代码在同一Windows环境仅render到独占 `registry-baseline-windows`，再与当前正规导出作两段对照（`registry-diff.json` / `registry-diff.md`）：

- 历史快照→baseline同Windows投影：formulas183处、cases122处，全部为数字末位差，最大规范化差1.46445e-14；assessments语义无差异。
- baseline同Windows投影→当前AD修订：cases仅12处，即K02/K04/K05共6条theta公式新增finite_iteration字段及更新note；无数值变更。formulas/assessments无AD差异。
- 所有evidence_level、source_check、rows_passed保持不变。assessments文件重写可能只表现为平台行尾字节变化；MANIFEST哈希据实更新。

`test_registry.py` 31项全部通过（`registry-current-tests.log`）。本轮没有修改 `data/kisssoft*` / TR30任何原始数值，也没有将平台末位漂移伪装成AD数值改进。

后续独立审查P2已补：`validate_cases` 的案例/库级相同判断原本遗漏导数策略，导致仅策略不同的合法case被误拒。最小修复在原相同性条件中加入双方 `get('fixed_point_derivative','implicit')` 比较。新增回归先红（finite_iteration case被误判相同）后绿，并验证缺省implicit与显式implicit仍判同、不能伪造无意义case。最终theta相关7项、registry31项全部通过；证据等级和schema版本不变。修复后再次用原package_hashes刷新并通过--check，patch/manifest同步更新。

## baseline、预算和优化声明

本轮 lane 为**产品交付 / meter calibration**，不是算法能力对比。低成本原始点复评依据 `optimizer-static-probe.json`：

| 例 | 原始点同一当前适配meter的V | 写回V | 相对变化 | 原始点身份 |
|---|---|---|---|---|
| K04 | 605177.464 | 467357左右 | 体积−22.7735% | 在声明约束内可行；KHβ仍held |
| K01 | 7963296.492 | 4166953左右 | 体积−47.6730% | 原始K01点重用本轮自动齿顶/孔径适配；不是与OPT2同预算A/B |
| K02 | 433399.190 | 891883.436 | 体积+105.788% | 原点SH1=.869311、SH2=.712149低于.95；属于可行化，不能称减体积 |

原始点基准是父文档的设计变量，采用本轮新meter复评，**不是历史优化器 incumbent**，也不是同预算算法基线。未跑多seed，不具有默认策略推广证据。

存档预算：K04点求值44177/区间15322、300格剪233解67、252.9s；K01点3839/区间1987、21格剪11解10、28.5s；K02点64610/区间7408、90格剪51解39、353.7s。计数含适配器调用，不能与不同语义的外部solve次数混用。原声明未建立固定多seed或同预算比较，本轮不能声称性能优于旧算法。

覆盖为 `interval_pruned_lattice_with_local_nlp`，claim_scope=local：离散格处理不等于每个连续叶子已全局求最小。KKT是一阶必要条件；NNLS复核使用相同导数，不提供导数独立性。`gradient_self_check` 在 `optimize.py:705` 的 start 点计算，并非报告所称的“最优点”。历史KKT不能因SF1不活跃就整体忽略导数缺口，尤其K04 bending.wheel仍活跃。

K02/K04 mn在声明上界（2/2.5）只是**搜索域边界诊断**。声明域本身为agent_proposed；扩大mn会改变问题，不能作为本轮算法提升证据。下一步先解决K02公差/held因子计量契约，再单独决定域扩展；不把两项混成一次性能结论。

## 最小剩余工作

- 对本轮当前修复可声明“关闭 K02/K04 已复现参数点的值/导数语义缺口”，保留有限步数切换边界说明。
- 对外部闭环：将K04/K01与K02分别结论；K02先做公差与held因子的契约追踪、逐项差异分解，保留原始预测失败记录。
- 对M34整个里程碑：H2强度层/实际评估次数可比基准、真实Claude实连仍须各自取证；TR30唯一文档覆盖也不能由目录文件数证明。
- 对当前优化身份：新代码下未重跑K02/K04优化，旧存档不得改写为当前solver身份；本轮没有全局最优声明。

## Where This Review May Be Wrong

- K04两侧KHβ相等可能是外部原生模型本就显式输入，其物理合理性需要原项目轴/支撑与方法来源；本路只证明其held身份，未证明该值错误。
- K02差异主因以依赖图与系数差为依据，未做全链逐项反事实分解；精确贡献需另做保留raw的诊断层，不能据此声称全部残差闭合。
- 梯度回归只覆盖6个明确点与邻域步长，停止步数边界可能不可微；不能把当前过门推成全域光滑性证明。
