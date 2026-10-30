# 计算问题案例库 v0.1.0 独立审查包 r1

下载单文件完整包：[FEA-case-library-0.1.0-review-r1.tar.xz](FEA-case-library-0.1.0-review-r1.tar.xz)（90.48 MiB），[SHA256](FEA-case-library-0.1.0-review-r1.tar.xz.sha256)。1079个成员、25个物理案例；与本地完整ZIP的每个解压文件逐字节相同。ZIP为128.29 MiB，超过GitHub普通仓库单文件上限，所以此目录提供相同内容的tar.xz。

在新空目录下载后解压，仅需Python标准库，也可用7-Zip/支持xz的tar：

```text
python -m tarfile -e FEA-case-library-0.1.0-review-r1.tar.xz .
cd FEA-case-library-0.1.0-review-r1
python -B tools/replay.py --output ../case-library-audit
```

先读 [START-HERE.md](START-HERE.md)。这是证据重放，不启动新FEA；再次计算需另备对应求解器。已在Windows干净venv与中文空格解压目录完成重放，12项代码测试、10个新真实作业复核、全部旧证据身份/覆盖检查通过。公开tar.xz的每个成员已对比经过重放的ZIP内容。见[制包验证](FEA-case-library-0.1.0-review-r1.verification.json)。外部独立审查尚未进行。

## 内容与实际完成度

- 已有20个物理案例：M33两例及M37十八例，124条历史作业记录、769份去重原始工件。包括全部14个L2参数点各三级网格、原始及修正16相位、失败与未启动记录。历史作业本轮未重新求解。
- 新增5个公开来源：COMET体力梁、COMET外压空心球、Code_Aster Hertz球、CalculiX Cook US3与beam8f模态梁。
- 梁和空心球已无头运行10次：原厚度梁保留2.26%偏差失败；薄层移植三级最细偏差0.00783%；空心球内位移最细偏差0.00510%。Hertz仅解析核对，另两例适配待完成。
- 已修复4项会漏放错误的入口：自平衡错误载荷、错误BC时序、重复末态字段、实际求解器路径未绑定哈希。负例可执行。

M33、M37 L2/L3保持未验收；新例的RF物理平衡和应力资格仍未闭环。不能把包重放通过解释成所有模型工程验收通过。

## 审阅入口

[25例目录](CATALOG.json) · [问题台账](ISSUES.md) · [复用架构](ARCHITECTURE.md) · [审查收口](REVIEW-CLOSEOUT.md) · [分发边界](DISTRIBUTION.md) · [文件清单](MANIFEST.json)

公开包不含付费标准全文、私有公式核心或商业求解器。旧题用规范化数值事实与精确原生模型审查；未提供私有几何生成器。源码、公开参考、原生输入、完整可用raw结果及标准库复核工具都在包中。源路径仅用于溯源，不依赖原机器目录。

公开tar.xz SHA256：`2679aab2120259e5c32c35017d4458c29b744edfc676bfacbecca1360f528860`。

本地ZIP SHA256：`f6f54fc9dc4f2cfc34e374a1b42e375e99038f3cec3efcf8c69c2cc877a6c682`。
