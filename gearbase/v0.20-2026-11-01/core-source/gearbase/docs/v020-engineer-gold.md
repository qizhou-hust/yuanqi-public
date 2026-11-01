# M38 工程师金标接收与评分

原始40题保持未标注。程序只生成空白表单，不填写期望答案，不用模型输出充当金标。

```powershell
python -m gearmath.tools.bench_gold --template output/m38/engineer-gold-blank.json
python -m gearmath.tools.bench_gold --labels PATH/engineer-signed-gold.json --out output/m38/engineer-gold
```

由真实齿轮工程师填写：实现者名单、独立性声明、逐题标注人和日期、期望结果类别、结构化需求、追问字段及要点。每题均须明确填写并设为 labeled；不能删题、改原文、重复题号或把实现者当作独立标注人。程序验证结构与提交的声明，不能独立证实自然人身份、资质或声明真实性；正式验收仍需核实这些外部证据。当前未收到签署金标，M38不关闭。

导入要求绑定当前完整题库的规范化 SHA256、原40题身份及顺序。缺题、来源过期、签名/日期缺失、非有限JSON数字、重复追问字段或自定义评分规则会拒绝。当前只实现原有默认逐字段精确匹配与追问集合评分，自定义规则不会被静默忽略。

结果单独写入 annotated-benchmark.json、import-receipt.json、result.json；源 requirements.json 与提交的签署文件保持不变。真实金标完成后，需要复核并正式收入受控题库，随后按原验收门重跑；单独生成一份评分文件不会自动改变里程碑状态。

修复了一处此前会使完整金标误判的问题：题库规定成功编译类别为 compiled，而工具真实状态是 pass_pending_human_confirmation。评分时只将这两个明确对应的类别匹配；原始工具状态、待人工确认要求及写入权限均不改变。未标注的基线指标与输出保持原样。

测试只使用明确标注的合成题目和合成签名，不写入真实金标；用例检查完整接收、过期/缺项拒绝和 compiled 类别映射。
