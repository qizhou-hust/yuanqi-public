# gearbase v0.20 系统全貌与初步冻结评估

2026-11-01（America/Los_Angeles）。从 [index.html](index.html) 阅读；HTML内嵌图、数据、样式和交互，无网络依赖。报告版本1，数学核心仍为 v0.20，Git `80117283778cf8732b5557fa15c2e41f626f92fc`。

结论：可作为明确适用范围内、工程师主导的计算与有限优化工作台试用；尚未形成从输出需求/轴关系/空间到成熟整机的自动设计器。初步冻结是保存已重放底座及边界，不能读作生产设计放行。原M32–M40门未改变。

## 本轮实际工作

- 当前会话重新运行146模块架构检查、数据包校验、里程碑探针和62项定向测试。
- 运行实际MCP/需求/三旗舰/系统入口；需求40→400N·m反例保留，模板优化与真实评级之间的适用域差异有原始响应。
- H2/W2W/P2返回40/15/5候选；60条全部接入系统模板，均blocked；W2W另有15/15热初筛失败。
- 50题是自编派生基准；本轮理想无损运动学50/50，使用明确披露的类型化kernel和归档数学桥，不代表50个完整真实工程方案。
- 同需求跨族探针被当前接口拒绝；固定C001/K01副校核不算架构生成。C001本轮是b=30mm的派生G1，不是原基准b=10mm的双级整系统。
- 只读核查POD需求表：19项要求单元格为空；没有创建工程金标。
- 给出26项能力矩阵、8个高价值切片、丝杆/螺母路线、系统真源与变更传播设计建议。
- 未改核心，未新增FE/KISSsoft求解、真实模型客户端请求、生产模型或工程决定。

## 本地完整附件与公开派生

本地完整包中 `cases/case-catalog.json` 等包含标准/商业来源的私有数字转录或详细元数据，仅用于本地审计。**没有PDF不等于允许公开数字库。**

公开附件另生成 `cases/public-case-catalog.json`、`public-challenge-results.json`、`public-inventory.json`：只保留允许分发的目录/来源身份、当前计算摘要与明确适用域，不包含标准完整输入转录、商业原件或求解器二进制。公开HTML链接相应派生文件；`PUBLIC-DERIVATION.json`记录原始与派生哈希及删减规则。公开附件不能独立复现依赖私有核心数据和归档环境的全部回归。

## 附件索引

- `baseline/`：本轮命令、stdout/stderr与基线收据。
- `architecture/`：26项能力、8个发现、原始运行响应、代码行/哈希证据和可复制当前入口。
- `cases/`：按来源类别去重的案例目录与6项挑战、全部60个候选检查、50题运动学、同需求失败与原始响应。
- `roadmap/`：终局需求映射、8个切片、冻结合同、实际边界探针、4个官方丝杆方法来源。
- `intake-metadata.json`：空白需求模板的公开结构摘要；单元格提取仅在本地私有附件。
- `historical/`：前轮固定提交的CI/FE/对拍交付凭据；本轮未重新执行这些全部求解。
- `report-data.json`：HTML展示数据；`freeze-manifest.json`：原核心身份、允许范围及开放项；`browser-qa/receipt.json`：无头桌面/手机交互检查。
- `review/`：发布前复核。`DELIVERY-MANIFEST.json` 在压缩包内绑定成员哈希。

## 只读复跑

需要原v0.20完整本地核心的指定提交Git检出及各脚本指明的历史资料；普通ZIP解压没有Git提交身份，不足以直接运行这些审计脚本。脚本默认根目录/提交身份已固定，可用其现有参数指定source（案例脚本支持），修改其他路径后应视为新一次独立运行，保留新哈希。

```powershell
python -X utf8 -B run_baseline.py
python -X utf8 -B architecture/run_smokes.py
python -X utf8 -B cases/run_challenges.py --source D:/my_Works/Gears/gearbase-v020-work
python -X utf8 -B roadmap/probe_boundaries.py
```

上述命令将更新自身附件目录，不能用于保持原冻结附件字节。要审阅原证据，直接打开JSON；要复跑，先在另一个目录复制附件并记录新运行身份。报告与HTML不是新的产品求解器，也不会自动关闭原工程缺口。


## This is the public derivative

Use `index.html` to read offline. `cases/public-*.json` replace the three private audit files. Private original hashes are preserved as provenance, not assertions that excluded originals are present here. See PUBLIC-DERIVATION.json. Original-source review receipts remain original-bound; public transformation has separate hash and browser checks. The report data are preserved summaries, not new solver outputs.
