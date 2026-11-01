# v0.16 不动点导数补丁独立审查

对象：原始 `received-stage-packages-2026-10-31/v016/gearbase-v0.16-stage4/extracted/gearbase`；工作副本 `D:/my_Works/Gears/gearbase-v016-milestone-work`。先读 raw diff `D:/my_Works/Gears/kisssoft-v016-run/derivative-fix.patch`，再查实际源码/测试/清单；未阅读实现者 review-optimizer 自评。以下行号相对工作副本。未运行COM、GUI或全测试，未修改产品代码。

## 结论与阻断

**没有发现阻断这项最小AD修复的实现错误；当前工作副本仍不能作为已冻结发行包。** 数学修改正确针对“执行了有限步并以相邻差停止的数值映射”，默认隐函数路径保持兼容。测试正例是当前求解器实际重算产物，旧fingerprint仍被拒绝。

**P1 冻结阻断：PACKAGE-CONTENTS 尚未更新。** 独立运行 `python -X utf8 -I gearmath/tools/package_hashes.py --check` 输出“不一致： PACKAGE-CONTENTS”；MANIFEST 已登记行没有报告stale。新测试与重放fixture在当前PACKAGE-CONTENTS中没有登记。需最终打包时重建并复验清单，不能现在声明包哈希一致。

这只支持导数子门的有限案例通过；**不构成 M34 整体关闭**，H2、实连、完整适用范围仍需独立证据。

## 已验证

| 要求 | 原始证据与实际验证 | 判定 |
|---|---|---|
| 默认固定点语义不变 | `kernel/dual.py:128-158`默认derivative=implicit，原迭代与隐函数公式保留；`tests/test_theta_iteration_derivative.py:36-41`粗容差一轮默认仍返回值2、导数2 | 已验证代码与针对性测试 |
| KISSsoft截断迭代AD对应前向算法 | `dual.py:133-143`沿相同迭代步骤传播Dual，判断仅用v并返回最后nx；`gear/kisssoft_multi.py:139-143`只在明确theta_tol适配分支选择finite_iteration | 已验证固定步数分支内语义 |
| 前向物理数值不变 | 在独立Python进程导入未改的原始源码，重算新fixture中的K02/K04 start/solution/written六点；6/6 values与fixture逐位相同；新实现同六点前向逐位相同测试通过 | 已验证六点，不外推全域 |
| AD与中心差分≤1e-6 | 新测试对六点全部连续变量、全部请求量逐项差分，4个新测试整体通过；不是只检查活跃约束 | 已验证测试范围 |
| 非默认策略进入模型身份 | `kernel/graph.py:67-71,282-287,338-340`验证策略、非默认策略入hash并传入求解器；策略不同hash不同测试通过 | 已验证 |
| 默认hash兼容 | graph.py仅在非默认策略附加tuple，默认payload保持原构造；新字段在dataclass末尾，既有位置参数不移动 | 静态已核，未穷尽全库历史hash |
| 非收敛/非法策略拒绝 | 原有和新增测试对有限步不收敛抛ArithmeticError；额外探针max_iter=0/1对implicit与finite_iteration均抛ArithmeticError；非法策略抛ValueError | 已验证 |
| 当前提交正例fixture真实 | 独立调用SO.optimize_source(K01-spur.factors, K01-spur-recompute-local)重新优化；solver完整指纹、optimum、new_sha256、verification与output/m34/v016-derivative-fix运行文件逐项相等 | 已验证真实重算，非仅改指纹标签 |
| 旧证据身份守门保留 | `tests/test_m34_opt3.py:282-284`专门拒绝历史运行；`tools/design_store.py:291-296`当前指纹比较未改；12个DesignStoreChain测试含旧指纹、伪造父/声明/solver、落盘篡改、失败不变通过 | 已验证 |

实跑命令：在工作副本用隔离Python和显式sys.path，unittest加载 `tests.test_theta_iteration_derivative` 与 `tests.test_m34_opt3.TestDesignStoreChain`，**16 tests / OK / 0.519s**。此外独立原始源码前向比对与K01当前fixture重优化通过。

审查中两个审查命令曾因Windows cp1252默认编码失败（read_text未显式UTF8、清单工具中文输出）；前者修正read_text(encoding='utf-8')重跑通过，后者加`-X utf8`得到上面的真实清单不一致结论。未把编码异常当产品数值失败。

## 非阻断限制与后续核对

1. **P2：有限迭代映射存在停止步数切换边界，不具有全域平滑导数。** `dual.py:139`用严格 `<tol`，AD对当前执行分支正确；跨步数切换点的中心差分可以跳变。额外合成探针 fn(x)=0.5*x+p、start=0、tol=1 得到 p=1.999999 时 value=2.9999985、AD=1.5；p=2时 value=3.5、AD=1.75。这个跳变前向算法原本就存在，此补丁没有制造它；不能为追求差分门平滑前向值。建议把“固定停止步数邻域内AD正确”写入说明，并在优化报告保留这种非光滑局限；六点测试未证明所有搜索点远离切换面。当前测试覆盖非收敛，但没有永久保存停止边界回归。
2. **P2：注册表导出未完整携带新AD策略。** `tools/export_registry.py:85-95`只导出kind/start/tol，`kernel/registry.py:25-26,61-63`按旧字段重建Formula，将回到默认implicit。运行时源码模型hash正确，但导出的注册表不能被称为完整AD语义可重放模型。注册表目前主要运行值测试，此限制不直接推翻本次运行时修复；如果下游依赖注册表恢复梯度，必须先扩schema/加载器/回归。
3. **求解身份的范围有限。** `kernel/gridprune.py:39`_FILES包含本次变化的dual.py，因此本次旧运行必然被识别；不包含graph.py与gear装配器是既有身份范围限制。本补丁未绕过该守门，也没有证明未来只改装配器时身份仍会变化。

## 一项重要里程碑的最短可信关闭路径

M32仍优于M34作为首个完整关闭目标：冻结M32所替换两引擎对应旧契约全集→新适配器执行旧断言并显示真实模块路径→原型、编译、量纲、架构守门负例与旧回归一起运行→取同源码身份的CI实际运行日志。缺CI运行证据就保持partial，不改变“CI生效”的原门。

若主路决定集中M34，本补丁只关闭“已覆盖案例梯度”子门：仍须H2同口径结果一致且评估次数下降，以及Claude Desktop/Code真实实连可用；不能用本次K01/K02/K04或P5数值复核代替。外部K02存在1–3%预测差异及小裕度的主路结果须如实保留，这与AD修复是否正确是两个维度。

## Where This Review May Be Wrong

- 我验证的是六个冻结点及一次K01重优化，未扫描K02/K04完整域的停止步数切换面；要扩大导数门声明，应统计搜索轨迹/停止步数并分开处理非光滑点。
- 清单不一致是审查时工作副本快照；主路可能随后完成更新。最终以刷新后只读check和实际交付归档哈希为准。
- 注册表AD重放问题按实际加载器字段判断；若注册表的明确契约仅是值测试，P2只需文档范围澄清。若有另一路未查看的加载器保留策略，应提供该调用路径再修正此结论。
