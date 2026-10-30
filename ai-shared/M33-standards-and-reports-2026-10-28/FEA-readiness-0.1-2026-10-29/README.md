# FEA readiness（无头前处理与理论预计算）

这是一个独立的、证据驱动的 FEA 准备层。它把输入意图、解析理论、原生输入语义、求解启动和结果审查分开；没有通过准备门的案例不会被启动。当前 `0.1.0` 只把 M37 的 CPE6、两步、小变形、无摩擦 penalty 已验证 profile 接通，通用 3D、斜齿、任意求解器适配器仍是后续工作。

核心顺序是：

1. 用 Hertz 线接触、名义直齿啮合几何和矩形悬臂梁形成可重算的数量级预期；每个公式都带单位、适用域和限制。
2. 由原生适配器检查材料归属、接触面/边界身份、载荷合矩、二次单元 Jacobian、初始重叠筛查和输入哈希。缺少支持类型或证据时返回 `UNKNOWN`/`FAIL`。
3. 在新目录中无头运行；启动前再次准备并核对输入、适配器和求解器 SHA256。零退出码单独不足以说明结果完成。
4. 读取原始结果后分别检查自由体力/矩、实际接触边、同物理量网格序列和理论适用性。没有同定义证据时保持 `UNKNOWN`；额外齿端接触也不会被自动归类为穿透。

## 快速使用

```powershell
D:\anaconda3\python.exe -B -X utf8 -m unittest discover -s tests -v
D:\anaconda3\python.exe -B -X utf8 -m fea_readiness precalculate examples/hertz.json --output hertz.out.json
D:\anaconda3\python.exe -B -X utf8 tools/replay_m37.py `
  --asset-root D:\my_Works\Gears\parallel-v09-2026-10-29 `
  --output artifacts\m37
```

`tools/replay_m37.py` 只重放已经存在的 M37 输入和结果，不启动求解器。它验证原始错误输入被拒绝、修复后的 ph00/ph10 通过准备门，并对 ph10 的实际接触网格触发诊断；结果仍标记 `engineering_accepted=false`。

通用计算/审查使用 Python 标准库；M37 适配需要 `numpy`、`shapely` 和 `m37-assets.json` 中列出的原项目文件。源码包不复制旧齿形内核或标准全文。换机器时将 `asset_root` 指向完整的既有 M37 目录，哈希不符会阻断。`run` 当前接收本机原生 CalculiX 可执行程序；本机既有 WSL 运行方式的适配列为 P1，本轮未宣称已通过新入口执行真实 FEA。

安装 wheel 后同样可使用 `fea-readiness precalculate/prepare/review/run`。`prepare`/`review` 的退出码 2 表示存在失败或缺证，不能据此删除异常数据；详见生成的 JSON。`run` 必须提供 `--prepared`、`--solver`、`--solver-sha256` 和新的 `--run-dir`。

## 目录

- `fea_readiness/theory.py`：透明理论模型。
- `fea_readiness/pipeline.py`、`adapters/m37.py`：准备和只读原生适配。
- `fea_readiness/runner.py`：隔离目录、二次哈希检查和无头启动。
- `fea_readiness/review.py`：平衡、网格、接触和理论比较诊断。
- `docs/ARCHITECTURE.md`、`docs/THEORY-AND-DIAGNOSTIC-REVIEW.md`：架构、适用域和异常判别。
- `docs/ROADMAP.md`：P0–P4 的复用决策、下一步和退出门。
- `research/LITERATURE-AND-OPEN-SOURCE.md`、`research/sources.json`：国际资料和开源实现的固定来源记录。
- `asset-audit/ASSET-REUSE.md`：旧 CAD/CAE 资产的复用边界。

旧 M33、M37 和 gear-compiler 核心没有在本目录修改。该包是诊断准备层，不是商业求解器或齿轮强度认证器。
