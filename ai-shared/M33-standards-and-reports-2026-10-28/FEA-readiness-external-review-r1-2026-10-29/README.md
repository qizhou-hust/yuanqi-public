# FEA readiness v0.1.0 外部独立审查包 r1

下载 [FEA-readiness-0.1.0-external-review-r1.zip](FEA-readiness-0.1.0-external-review-r1.zip)（39.13 MiB），解压后先读 `START-HERE.md` 和 `REVIEW-BRIEF.md`。

完整包包含固定版本源码与 wheel、23 项测试、M37 重放依赖和原生输入、历史真实 DAT/FRD/STA/LOG 等结果、3 案例/4 变异的重放入口、研究与资产来源记录，以及 Windows/Linux CPython 3.12 x86_64 离线依赖。无需原作者本机目录或网络即可进行包内审查重放；需已有 Python 3.12 解释器。

已在 Windows 独立环境从最终 ZIP 异地解压完成全部重放，详见 [FEA-readiness-0.1.0-external-review-r1.verification.json](FEA-readiness-0.1.0-external-review-r1.verification.json)。Linux wheel 已核对来源哈希，Linux 运行本轮未验证。

业务源码与提交 `492ef02a4f1038f9d6ba2f042eab0c27681ac2aa` 一致。当前是提交方制包验证完成，外部独立审查尚未进行；工程验收状态保持未通过。完整模式不会调用新的 FEA 求解器。

SHA256：`0f508efd1e8b8a3982f1a2cdb1da96054fdf280260ab8b9c99bda2d68ffdc0dc`
