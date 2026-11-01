# M35：K02 变位斜齿工艺审阅准备包

本轮输出可逐数核查的参数表和带尺寸的宏观几何审阅 SVG，**没有完成原门“经外部工艺人员审阅的变位斜齿制造图”**。本包不具备制造放行资格，原 M35 门不得据此关闭。

`gearmath/tools/m35_packet.py` 从 `data/kisssoft/K02-helical.json` 读取 K02：法向模数 1.5 mm，法向压力角 20°，螺旋角绝对值 14°，齿数 27/104，法向变位系数 0.3255/0.07388831907841498，齿宽 21/20 mm。参数表记录各字段原始定位、单位、源哈希、模型哈希、公式编号及证据限制。图中的齿顶圆直接取源数据（含齿顶缩短），分度圆、基圆及名义齿根圆来自现有公式图；没有用未包含缩短的基本齿条齿顶式覆盖源值。法向齿厚上、下偏差与四项报告公差直接取原报告，不另选制造参数。

图纸为 A3、1:1 的两个独立零件外形包络视图和轴向宽度视图；圆线分别表示齿顶、分度、基圆和名义齿根直径，**不是齿面边界**，图中没有齿廓、滚刀包络或根部过渡。横向坐标 +X 向右、+Y 向上，轴向 +Z 向右；源未明确旋向，图上保留 hand TBD。没有把绝对螺旋角解释为右旋。由字节确定性重建和 XML 数值测试核对图纸标注与圆半径。所有文本显式声明字体及字号，图元显式声明填充和线型，不依赖嵌入 CSS 样式表；PyMuPDF 渲染预览已检查，圆包络透明、文本无重叠。

限制的直接证据是归档 `archive/m31/src/cadbench/tooth_authority.py`：`_zero_shift` 拒绝非零变位，`_flank_data` 检查零变位齿顶和齿厚关系。当前接口不能生成经核查的 K02 变位斜齿完整工作齿面和齿根。为关闭这个缺口，下一步需建立受限的变位斜齿齿面/产形齿根接口，并与同输入独立几何或刀具包络核对。当前仅圆包络的 SVG 不能冒充完整制造图。

另外仍缺孔/轮毂/键槽、基准、公差与配合、完整材质热处理和表面要求、旋向、跨齿数及量球直径的制造决定。K02 原报告精度为 DIN 3961:1978 6 级，未转换成 ISO 1328；如要求 ISO 1328，需要真实授权的精度要求。`external-review-unsigned.json` 的审阅人、独立性、日期、结论、签字及七项缺口处置全部留空。本生成器与验证器只核验未签署准备包；真实签署记录应另行保存并核验身份和问题关闭证据，不以任意填入签名字符串充当外部审阅。

准备包文件：`source.json`、`parameters.json`、`parameters.md`、`manufacturing-review.svg`、`external-review-unsigned.json`、`manifest.json`。清单包含全部工件和生成程序/几何程序/受限权威源文件的 SHA256。验证器从仓库源重新投影，阻断源身份更换、尺寸/单位变动、工件篡改、重新填哈希伪造、清单工件乱序或缺失、额外工件和虚假放行状态。该检查是确定性和来源完整性检查，不认证原报告的法律效力或外部审阅独立性。

在仓库根运行（隔离环境、禁用 site，仅标准库）：

```powershell
python -I -S -c "import sys,runpy; from pathlib import Path; sys.path.insert(0,str(Path.cwd())); sys.argv=['m35_packet','--out','output/m35/review-packet']; runpy.run_module('gearmath.tools.m35_packet',run_name='__main__')"
python -I -S -c "import sys,runpy; from pathlib import Path; sys.path.insert(0,str(Path.cwd())); sys.argv=['m35_packet','--out','output/m35/review-packet','--verify']; runpy.run_module('gearmath.tools.m35_packet',run_name='__main__')"
python -I -S -c "import sys,unittest; from pathlib import Path; sys.path.insert(0,str(Path.cwd())); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests',pattern='test_v020_m35_packet.py')); sys.exit(not r.wasSuccessful())"
```

七项新增测试覆盖同源实际尺寸及 SVG 半径、无需样式表的内联显示属性、输入身份/单位/标准及零变位拒绝、确定性往返、工件及重填清单伪造、工件顺序及伪造放行、缺失与额外文件。连同已有参数表/公差测试，共 19 项在 `python -I -S` 下通过。核验成功必须同时返回 `manufacturing_release=false` 和 `external_review_completed=false`。
