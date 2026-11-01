# 最终增量独立审查

对象：`D:/my_Works/Gears/gearbase-v016-milestone-work`（下文路径相对此目录），与原始v0.16源码直接git diff --no-index比较。只读审查registry/export、UTF8边界和新增测试；没有阅读实现者自评，没有再调用Claude模型，没有COM或代码修改。

## Findings

1. **P2（已修复并独立验证）：案例注册表的相同性判定遗漏新增AD策略。** `gearmath/kernel/registry.py:250-252`比较case记录与library记录时列出expr/output/unit/domain/kind/start/tol/clause/note，未纳入fixed_point_derivative。因此只改变导数策略的合法case记录被误拒为库级相同。独立最小复现：建立Formula('fp','y','1','y/2+p','test',kind='fixed_point',tol=3)，implicit版entry作为library，dataclasses.replace(...,fixed_point_derivative='finite_iteration')版entry作为case（其他字段全部相同），validate_cases实际返回`C：fp 与库级记录相同，应记在库级`。修复方向是比较规范化后的策略e.get('fixed_point_derivative','implicit')，并验证缺省与显式implicit仍相同。这是新增执行语义字段应跟随的比较遗漏。现有K02/K04同时有不同tol/note，不会触发本复现，所以它不等于当前包运行失败。

## Verified

- `registry.py:59-65`新formula_from_entry恢复非默认fixed_point_derivative；旧快照缺字段默认implicit。新增字段在OPTIONAL_FIELDS内，不改变旧必填字段集合；非法策略验证拒绝。
- `export_registry.py:85-100`仅非默认策略写入新字段，默认implicit输出结构不增加字段。新roundtrip测试实证非默认AD=1、缺字段旧implicit AD=2，既有hash策略仍有效；未看到指纹守门被绕过。
- `ai_tools.py:562-576`将默认stdin/stdout从导入时捕获改为调用时取得，并仅对未显式传入的系统流重配UTF8。显式StringIO流不重配、不关闭，调用方所有权保留。bench/doctor只在__main__边界重配stdout，导入它们不改调用者流。
- 实跑`tests.test_theta_iteration_derivative` 5条与`tests.test_windows_utf8_stdio` 4条：**9 tests / OK / 1.384s**。覆盖原有六点前向逐位保持、六点梯度1e-6、非默认hash、registry roundtrip、默认CP1252系统流读写UTF8、中文JSON-RPC id往返、显式流不重配/不关闭、bench与doctor CLI中文输出、doctor实际子进程MCP握手。
- `python -X utf8 -I gearmath/tools/package_hashes.py --check`当前输出 **一致**，前次报告的PACKAGE-CONTENTS不一致已在此快照消除。
- 独立递归比较原始与当前data/registry的全部evidence_level/source_check字段：formulas-v1.json 850字段、assessments-v1.json 2804字段、cases-v1.json 1974字段均未改变。没有证据等级被本次增量升级。

## 结论

registry单条导出/恢复和UTF8默认MCP流修复在所测范围内成立；P2案例相同性遗漏现已修复并独立验证，当前审查范围没有未关闭发现。此前有限迭代停止步数边界非光滑限制仍有效；此增量没有更改前向数值或搜索域。完整M34原门与真实客户端调用仍应单独列状态，特别是本轮Code模型403后没有tool_use/tool_result，UTF8修复不会自动关闭该门。

## Where This Review May Be Wrong

- 案例相同性问题通过合成合法记录复现，未证明当前真实K02/K04记录触发；它针对通用schema契约，而非声称现有产物已失败。
- 本次只执行9条最小回归及只读清单检查，完整1110测试最终结果由主路运行提供；不能用这里的通过代替全量结果。
- 默认系统流reconfigure假设serve在首次读取stdin前启动；如宿主已读取部分隐式stdin再调用serve，Python可能拒绝重配置。显式传入的宿主流已按所有权规则保持原样。

## P2 收口复核（最终状态）

已只读核对`gearmath/kernel/registry.py:250-253`新增双方`get("fixed_point_derivative", "implicit")`比较。新增两例验证：（1）仅finite_iteration与库级implicit不同的合法case被接受；（2）显式implicit与旧缺省implicit仍被判为相同，不能制造虚假case差异。两者精准覆盖原复现及向后兼容保护。

独立实跑7条theta回归与4条UTF8 stdio回归：**11 tests / OK / 1.376s**。本次仅复核上述P2，没有扩大范围。P2状态改为**修复已验证**；此前Findings保留为原始审查证据，不再表示当前缺陷。完整最终全量由主路负责，不把此11条替代全量。
