"""产品层（v0.15 SYS）：统一核算管线与证据报告。

不新增物理公式：每个子检查只调用 gearmath.gear / gearmath.system 已有模块；本包只做输入装配（带来源的系统层输入
gears.system-input/1）、阻断收集、结果汇总（gears.design-check-result/1）与中文报告。
不放进 gearmath/kernel/（内核不出现齿轮概念）。

  design_check.check(design_doc, system_input, scope)  统一入口
  report.render_markdown(result)                       中文 Markdown 报告
  system_input.load / validate                         系统层输入
"""
