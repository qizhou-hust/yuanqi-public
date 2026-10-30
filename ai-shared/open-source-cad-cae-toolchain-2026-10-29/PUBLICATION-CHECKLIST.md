# 发布核验记录

范围：四个现有 CAD/CAE 归档及其集中索引。原 CAD 三包保持字节不变；新运行包修复 Gmsh 源码截断，不改求解器或工程验收状态。

| 检查 | 证据/验收方式 | 状态 |
|---|---|---|
| C1 原 CAD 包身份 | 原 sidecar SHA256 与当前字节一致 | PASS |
| C2 新运行包完整性 | 外层 27 成员逐文件比对；6 个内部压缩归档 CRC/结束标记与成员检查 | PASS |
| C3 下载验证工具 | 四包全量通过；错误 SHA256 负例被拒绝 | PASS |
| C4 GitHub 发布内容 | 发布后 PUBLICATION-VERIFICATION.json 中每个资产的字节数、服务端 SHA256 和 uploaded 状态均与本地一致 | PASS |

本次没有重跑 CAD 编译或齿轮 FEA；保留已有 smoke 证据与验收边界。
