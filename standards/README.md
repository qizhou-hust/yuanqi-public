# 齿轮与传动标准统一资料库

这里是本仓库标准资料的统一入口。已将原M33和后续M36/M39目录中的标准PDF实际归集到本目录，按用途与版本分类。旧目录保留以维持原链接和历史证据；后续查找标准优先从这里开始。

[全部文件目录](CATALOGUE.md) · [外部AI入口与提示词](AI_START_HERE.md) · [已知问题/待补清单](KNOWN_ISSUES.md) · [机器可读目录与下载地址](CATALOGUE.json)

本次编目 **39份不同字节的标准/预览/工程阅读本PDF**，另附修复报告、证据和OCR文本。该数字包括历史版和同版不同扫描，不是39项独立有效标准。相同SHA-256的来源归为一条，旧位置记在source_paths中。

## 分类目录

| 目录 | 内容 | 编目数 |
|---|---|---|
| [01-ISO-6336](01-ISO-6336/README.md) | ISO 6336 齿轮承载能力与算例 | 11份PDF |
| [02-GB-3480](02-GB-3480/README.md) | GB/T 3480、GB/Z 3480 中文参考 | 6份PDF |
| [03-M36-shafts-bearings-keys](03-M36-shafts-bearings-keys/README.md) | M36 轴、轴承、键与过盈连接 | 8份PDF |
| [04-M39-thermal-clearance](04-M39-thermal-clearance/README.md) | M39 热容量与侧隙 | 2份PDF |
| [05-engineering-readers](05-engineering-readers/README.md) | 工程修复与补页阅读本 | 4份PDF |
| [06-historical-editions](06-historical-editions/README.md) | 历史版次（2006） | 4份PDF |
| [07-previews](07-previews/README.md) | 公开预览（非完整标准） | 1份PDF |
| [08-alternate-copies](08-alternate-copies/README.md) | 同版不同扫描/OCR副本 | 3份PDF |
| [09-repair-evidence](09-repair-evidence/README.md) | 修复说明、表12、数值检查、哈希与来源记录；保留自包含阅读本副本 | 配套证据 |
| [10-OCR-navigation](10-OCR-navigation/README.md) | 六份核心ISO标准的既有OCR | 仅用于检索 |

## 按计算任务选资料

| 任务 | 起点 | 注意 |
|---|---|---|
| M33 齿轮承载能力/疲劳寿命 | 01的ISO 6336-1/-2/-3/-5/-6及05的TR30补页本 | 2019、2016等版次按所用方法匹配；2006历史版单独放置 |
| M36 轴、轴承、键、过盈连接 | 03的DIN743-1至4、ISO281、DIN6892、DIN7190-1；DIN6885结合05标注本 | DIN6885尺寸表和DIN6892强度计算用途不同 |
| M39 胶合、微点蚀、热容量与侧隙 | 01的ISO/TS6336-20/-21/-22、04的DIN3967、05的TR14179阅读本 | 先读09修复说明；未确认热流分项不能当作标准原式 |
| 中文术语与对照 | 02 | 先核对具体版次和采标关系 |

## 三条使用规则

1. 原始扫描、公开预览、工程修复稿分别标识；工程阅读本不是ISO/DIN官方修正版。TR14179-2表12在源PDF41，先前“缺表”判断已更正。
2. 先看KNOWN_ISSUES和文件备注。OCR只能检索，公式和表格核对PDF原图；同版不同文件用哈希区分。
3. 资料收录、算例复算和产品验收是不同结论。修复说明标有A直接恢复/官方更正、B工程重建、C替代模型、U未确认。

## 相关计算报告

- [原M33资料和KISSsoft案例说明](../ai-shared/M33-standards-and-reports-2026-10-28/AI_START_HERE.md)
- [TR30例7/例8复算资料](../ai-shared/M33-standards-and-reports-2026-10-28/TR30-7-8-2026-10-29/README.md)
- [M33原生计算补充资料](../ai-shared/M33-standards-and-reports-2026-10-28/M33-native-headless-2026-10-29/README.md)

报告属于计算证据，不计入标准PDF数；具体通过状态以相应报告限制为准。

## 下载与校验

打开PDF后点击Download raw file可下载单份；外部AI可直接用CATALOGUE.json中的raw_url。仓库Code菜单→Download ZIP会下载整个仓库。

只下载标准目录，可在已安装Git的电脑执行：

```powershell
git clone --filter=blob:none --sparse https://github.com/qizhou-hust/yuanqi-public.git yuanqi-standards
cd yuanqi-standards
git sparse-checkout set standards
```

CATALOGUE.json记录标准PDF的来源路径、页数、SHA-256和直读地址；FILE_MANIFEST.json记录本目录交付文件（不含清单自身）。旧修复manifest保持原义，路径说明见09目录SOURCE_CONTEXT.md。

整理日期：2026-10-29。第三方标准及既有水印保留原权利信息；归档不改变资料许可。
