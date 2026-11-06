# 从这里开始
这是外部独立审查资料包，不是新产品发布。

1. 把全部ZIP和“解包并校验.py”放同一目录。
2. 运行：python 解包并校验.py --output REVIEW_UNPACKED
   只用Python标准库，无需7-Zip，也不需要手工合并分卷。
3. 该脚本核对每包SHA256、片段/原文件SHA256并还原全部逻辑路径。
4. 打开 REVIEW_UNPACKED/review/REVIEW_REQUEST.md，按建议顺序审查。
5. 如需先看设计者意图，阅读三页讲清楚.html；详细技术依据为整合蓝图.html。先独立判断再对照作者报告。
6. 完整性：python REVIEW_UNPACKED/review/REPLAY_REVIEW.py --mode fast
7. 固定数学/扭矩/产品重放分别用 --mode core / torque / web。依赖见requirements-audit.txt；core/torque另需JAX。
不要直接使用作者的runtime_environment.local.json。可给便携入口加 --python 你的解释器。
每包严格小于19,000,000字节，19MB按十进制保守控制。01至06是数据对象包，必须整组保留；00包含清单/需求/工具。
去重采用内容哈希，不能仅解压某个数据包就运行工程；应使用一键还原脚本。
已有报告、已知失败和损坏原件均保留，完整性PASS不等于工程能力PASS。

解包推荐Python 3.12，最低Python 3.11。review/USER_REQUEST.md是用户需求的整理记录，并非逐字聊天导出；用户原始三份技术文件按原始字节保留。根目录审查需求.md与00包内需求相同，便于直接阅读。
