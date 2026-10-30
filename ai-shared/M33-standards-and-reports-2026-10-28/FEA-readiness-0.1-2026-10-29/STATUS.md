# 实施状态（2026-10-30 UTC）

| 项目 | 状态 | 当前证据 |
|---|---|---|
| 理论预计算（Hertz、名义直齿、梁筛查） | closed | `tests/test_theory.py`，冻结 M37 pitch 参考值 |
| 规则契约和 UNKNOWN/空检查 fail-closed | closed | `tests/test_review.py`、`contracts.eligible` |
| M37 原生前处理适配 | closed（限定 profile） | 三例重放；原 ph00 拒绝，修复 ph00/ph10 通过 |
| 完整孔边节点/边界实际值、预载和逐齿对相位绑定 | closed | `artifacts/m37-final/mutation-check.json`：4 项变异全部阻断 |
| 无头受检启动 | closed（合成 runner 门） | `tests/test_runner_execution.py` 7/7；未用鼠标 |
| 真实 M37 结果重放审查 | closed（历史结果） | `artifacts/m37-final/ph10.review.json` |
| ph10 实际接触网格 | diagnostic fail | 活动边长度/目标接触尺度比 40.3429，需局部网格研究 |
| ph10 理论峰值比较 | UNKNOWN | 多齿/延伸接触和定义尚未闭合 |
| 网格收敛 | UNKNOWN | 需同物理量、同区域、同提取规则的至少三级序列 |
| 本机 WSL 新入口真实发算 | deferred | 本轮重放历史 raw；`docs/ROADMAP.md` P1 |
| 通用 3D/CAD/斜齿/多求解器 | deferred | 见 `docs/ARCHITECTURE.md`、`docs/ROADMAP.md` |

所有 `closed` 项都在本会话重新运行过门；`diagnostic fail` 和 `UNKNOWN` 不会被合并成工程通过。`runner` 的单元测试使用 synthetic solver，只证明启动和完成状态机，不代表真实 FEA 结果。
