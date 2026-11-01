# A11 求解器来源核验（2026-11-01）

按用户 v0.18 A11 的明确授权规则，从 [CalculiX 作者站点](https://www.dhondt.de/) 的 Linux 可执行版本链接直接下载 [ccx_2.23.tar.bz2](https://www.dhondt.de/ccx_2.23.tar.bz2)，全程以二进制保存。未经过文本中转，核验过程中未执行求解器。

| 对象 | SHA256 |
|---|---|
| 官方归档 | `35d426fed5eb164fbbaaafa20819d13d22e30bc2b9bc9c6c4ed957e9468355dd` |
| 归档内 `./CalculiX/ccx_2.23/src/ccx_2.23` | `31be21fc2f0902bd9a05acc2651dbac6dc2a2573dabbf235e39a38cb6f458862` |
| 本地 vendor 对应文件 | `31be21fc2f0902bd9a05acc2651dbac6dc2a2573dabbf235e39a38cb6f458862` |

三者与交接记录中的完整哈希一致。A11 关闭；允许的范围是这一确定字节的 Linux x86_64 求解器，用于显式输入的本地验证。该文件不是 Windows 原生程序，本次未启动平台兼容层，也未自动执行 FE 作业。

登记：`data/solver/ccx-2.23-allowance.json`。官方下载时间、响应头、最终 URL、成员名和核对结果：`data/solver/ccx-2.23-origin-proof.json`。每次检查会验证登记、证明文件和当前二进制；可选择重新检查官方归档及其唯一普通文件成员。未知、缺失或改变的二进制会拒绝。

```powershell
python -m gearmath.tools.solver_allowance --solver vendor/fea/vendor/CalculiX/ccx_2.23/src/ccx_2.23 --archive PATH/ccx_2.23.tar.bz2
```

这项登记不授予 M37 数值验收，不改变接触输出策略和读取注册，不替代三级网格收敛、真实齿轮接触结果或模块 B 原包。此前 v0.17 探针执行早于本次来源许可，历史次序保留，不追改为“事先已许可”。
