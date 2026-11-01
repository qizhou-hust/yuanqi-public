# v0.17 系统层回归范围

`tests/test_v017_drivetrain_backend.py` 验证产品轴与轴承真实调用统一
drivetrain 后端、同一次检查共享求解、跨次修改重新求解，以及旧静定结果逐项保持。
`tests/test_mcp_p0.py`、`test_mcp_p1.py` 和真源编辑测试继续覆盖受控写入。

`scripts/ci_flagships.py` 与原 H2/W2W/P2 对照测试继续验证三条原始
Stage0 需求和求解结果回归。它们不提供 H2/W2W/P2 的完整轴系耦合或
行星/蜗杆族强度评级。M36 第3条门因此保持 partial；M40 继续冻结。

联合优化的有限域验收单列为 M36 第2条门。它使用明确标注的能力演示边界，
既不替换真实 C001 所缺的跨距、材料、扭矩位置，也不替代 C001 同图全系统门。
