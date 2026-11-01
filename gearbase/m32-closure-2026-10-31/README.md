# M32 单一数学内核与适配器验收

2026-10-31；gearbase v0.16。M32 的原始 5 项验收门全部通过，状态关闭。

验收源码：`3e8e4469d149e7f54c0d66d2ccfb58860ecde6c6`。真实托管 CI：[完整运行](https://github.com/qizhou-hust/yuanqi-private/actions/runs/41262897242)。
该源码的三项作业 core (ubuntu-latest)、core (windows-latest)、legacy 全部 success；原始日志和 JSON 随交付包保存。

| 原始验收门 | 证据 |
|---|---|
| 原型 21 项测试 | 两系统实际运行，通过 |
| M31 旧测试经新适配器 | 原 73 模块、678 项全部通过，0 skip、0 failure、0 error；81 原测试及 fixture 文件哈希未变 |
| 守门在 CI 生效 | 实际执行 AST/import 守门与独立破坏性反例；几何、强度、优化器越界均非零退出，通用数学正例通过 |
| 全库可编译 | 两系统全源码编译门通过 |
| 量纲校核 | 输入、内核、注册表及全量单元门通过 |

旧 calculator、optimizer、graph 入口为薄适配器；父进程和独立子进程的实际导入路径指向新 compat/kernel。没有以旧计算器结果冒充新内核回归。

数值兼容采用明确的 `binary64-ordered-fma-v1` profile：支持的一维 float64 向量范数按索引做融合乘加、最后 sqrt，实际实现与后端路径逐进程审计。通用内核经系统 FMA 1032 例独立复核，NumPy API 兼容检查为必跑步骤。旧门在原先产生末位差异的 Haswell BLAS 背景复验；不依赖随机获得某种 CPU。该 profile 是新内核的显式兼容语义，不冒称原 vendor BLAS 实现未改变，也不修改原金标准或逐位断言。

独立完整精度金标准包含 2050 条向量，绑定公式身份与 14 个案例的原始来源；直接参考与原容差不变。CI 不刷新金标准，实时数据在覆盖前检查结构、有限性和数值一致性。实际回放与反向破坏测试均通过。

原归档 README 曾声明 10 项可选 CAD 跳过。本验收配置实际运行 OCP8/build123d 父环境与原冻结 OCP7/CadQuery 原生工作环境，并要求旧 73 模块零跳过；元数据桥和 Face_s 同义 API 只用于该隔离回归，保留真实版本来源。

关闭范围为 M32 架构、兼容性和回归出口；工程公式的证据等级及 M33–M40 的验收状态保持各自证据口径。旧 73 模块在 Linux/POSIX 验收，新核心在 Linux 和 Windows 验收。全量核心测试已有的可选证据跳过逐项保留在原始日志中。

## 交付与状态收尾

功能验收提交为 `3e8e4469d149e7f54c0d66d2ccfb58860ecde6c6`；交付提交为 `7b26819c559a332977e095c716d86b4ec006d6a7`。后者仅更新验收文档、里程碑状态和包哈希三个文件；`delivery-delta.json` 证明其他全部源码、适配器、测试与 fixture 字节不变。收尾编译、10 项包完整性测试及 M32 状态 5/5 定向检查通过，未为文档重复 CAD 全回归。

核心全量运行：两系统各 1183 项；Linux 保留 17 项、Windows 保留 29 项既有可选证据跳过，未把这些计作旧门通过。旧 73 模块单独为 678/678、零跳过。

完整本地交付包含全部源码、旧回归材料和证据；公开包为验收证据与核心代码增量，不包含完整旧私有语料或标准数值金标准。公开入口：[GitHub 报告](https://github.com/qizhou-hust/yuanqi-public/blob/main/gearbase/m32-closure-2026-10-31/README.md)，[二进制证据包与 SHA256](https://github.com/qizhou-hust/yuanqi-public/releases/tag/gearbase-m32-closure-2026-10-31)。

下一步优先 M34：H2 双级强度接线与独立复核、真源写入契约、Claude Code 的真实只读工具调用。H2 载荷、材料和强度基准必须有可追溯来源；现有几何样例不能充作强度验收。具体可执行项见 `NEXT-M34.md`。
