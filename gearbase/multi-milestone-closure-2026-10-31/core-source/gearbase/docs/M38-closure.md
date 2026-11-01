# M38 原始验收门收口

绑定 `docs/顶层设计.html` 的四项门；当前机器状态见 `output/m38/closure.json`。
该状态与外部工程放行、M34 的真实 Claude 模型调用分别记录。

## 数字追溯与多模型

原40题要求允许未标注题参与数字追溯、结果分布和追问一致性。
规则721个、实际 Terra 681个、实际 Sol 684个数字的不可追溯数均为0；
人工金标尚无，因此语义准确率及标注追问精确率、召回率保持 null。
Sol 读取过 intent.py，两个模型结果属于首轮探索评测，不能称为盲评。
原始输出和收据字节保持不变；身份为运行记录，并非供应商签名证明。
完整口径及限制见 `M38-bench-closure.md`、`output/m38/MODEL-COMPARISON.md`。

## 三个原始旗舰

`data/flagships-stage0/` 固定 H2、W2W、P2 的原始参数与显式算法选项，
记录原测试来源 SHA256。没有用 C001/K01 代替这三个任务。

`scripts/ci_flagships.py` 启动真实 MCP stdio 服务器，逐项调用
`requirement_compile`，使用返回的工作流调用 `flagship_workflow`，执行有限域求解并复查首个候选。
收据记录原输入文件哈希、规范需求哈希、实际请求响应和范围。
这是确定性协议客户端，不冒称 Claude Code 的模型发起调用。

H2 与 P2 保持原 Stage0 几何问题；W2W 保持原几何、固定摩擦效率和散热筛查。
它们的 L2 有界枚举没有冒充通用公式图或族强度模型。
H2 复查重新求域成员，P2 几何复查不独立证明排名与重数；原始求解器作为另外的测试对照。
W2W 全15个候选嵌套结果与原求解器一致，原首选的 `thermal_ok=false`
继续输出 `candidate_requires_changes`。
三个流程均保持 `engineering_accepted=false`、`persisted=false`。

## 干净 Windows 环境

`scripts/ci_portable_fresh.py` 在私有托管 Windows VM 从官方二进制 ZIP
下载并校验 Python 3.12.10 嵌入版，构建完整私有便携包，使用独立 Python `-I`，
清除系统 Python 路径与用户环境影响，运行 doctor 及 MCP initialize/list/实际tools/call。
计时包含下载、校验、构建及调用，硬门小于600秒。
本机隔离验证已通过；托管 VM 结论以 `output/m38/portable-hosted-receipt.json`
和 `closure.json` 的 hosted_run_url 为准，缺少收据时此门保持 partial。
完整数据便携包为私有交付，默认轻量包不会被宣称为完整 doctor 通过。

M34 客户端门仍为 partial：真实 Claude Code 2.1.304 已连接 MCP，
但模型请求因账户 HTTP403 额度不足被拒，没有真实模型发起的 tools/call。
确定性协议测试与目录发现均不能替代这一门。
