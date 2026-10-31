# KISSsoft v0.14 输入预检

核验日期：2026-10-30。范围仅为阶段包静态核验、输入可读性与映射检查；未运行附带代码、COM 或 UI，未修改库。

## 结论

两个指定 ZIP 均无法作为有效 ZIP 读取，故未解压到 package-v013/package-v014，亦未创建这些目录。当前无法从其内容可靠取得 K01 与 C001 优化候选参数，不能声称完成本次 v0.14 输入完整性检查或本地复算。没有修改或尝试修复原包。

## 已核验证据

|包|字节数|SHA256|ZIP 读取|
|---|---:|---|---|
|gearbase-v0.13-阶段包1-2026-10-30.zip|44924672|239210f8dfb2974837e93ad0f1d6456507fdc2b505d3596aa73ead3627106ccb|BadZipFile: Bad magic number for central directory|
|gearbase-v0.14-阶段包2-2026-10-30.zip|25308044|ffdbc2e8dba1c1a678ebf886399bbd1a6c09a641386960efbec25c00c7188a60|BadZipFile: Bad offset for central directory|

两个文件的二进制头/尾均出现 EF BF BD 字节序列，且 ZIP 尾部目录偏移/注释长度与文件实际长度矛盾。v0.13 尾记录宣称目录偏移 1572716527；v0.14 为 3220111360，均超过文件长度。该现象与二进制曾经过有损文本转换相符，转换来源未核实。SHA256 仅为本地现状指纹，无发布方校验值可供比对。

对 v0.14 请求文档的原始压缩字节做无修改解压尝试，zlib 报 invalid code lengths set。没有产生可用请求正文。

## 输入映射线索（仅文件名，内容未验证）

原始字节内可辨认以下文件名；它们不是可信 ZIP 目录，不表示文件正文完整：

|对象|基线|优化声明|优化运行输出|优化候选 math-source|
|---|---|---|---|---|
|K01|data/source/K01-spur.math-source.json；data/kisssoft/K01-spur.json|data/optimize/K01-spur-min-volume.decl.json|output/m34/K01-spur-min-volume.run.json|output/m34/K01-spur.opt-04f1d167.math-source.json|
|C001|data/source/C001.math-source.json；data/m31/cases/C001.json|data/optimize/C001-G1-min-volume.decl.json|output/m34/C001-G1-min-volume.run.json|output/m34/C001.opt-afcc042f.math-source.json|

还可辨认 docs/KISSsoft运行请求-v0.14.md、docs/M34-优化器主线.md、顶层 00-KISSsoft运行请求.md。

由于这些正文不可读，齿数、法向模数、螺旋角、压力角、变位、齿宽、中心距、材料、载荷/转速/寿命、精度、润滑、ISO 方法、系数口径及候选身份均未核实，不能从文件名猜测。

## 本地替代源搜索

对 D:/my_Works/Gears 与 C:/Users/AAA/Downloads 的文件名搜索未找到当前 v0.14 请求文档的已解压副本或同名有效 ZIP。可见旧 M33/TR30 材料、旧工作树及其他版本包；这些不是本次 v0.14 优化候选的可信替代来源，未擅自替换。

机器可读详情见 package-validation.json；raw-filename-hints-v013.txt 与 raw-filename-hints-v014.txt 只保留损坏包中的可辨认字符串，禁止当作完整目录清单使用。

## Where This Review May Be Wrong

- 未扫描整台机器的所有路径，其他目录可能存在有效副本；可提供其位置再核验。
- EF BF BD 与结构错误支持有损转换的推断，但没有传输链证据，不能确定损坏发生在哪一步。
- 文件名关联可能与实际优化对象不同；必须读取有效请求、声明和候选 JSON 后才能确认映射。
