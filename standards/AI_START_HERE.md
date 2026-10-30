# 外部AI统一读取入口

主入口：https://github.com/qizhou-hust/yuanqi-public/tree/main/standards

直读入口：https://raw.githubusercontent.com/qizhou-hust/yuanqi-public/main/standards/AI_START_HERE.md

## 读取顺序

1. 读取 [README.md](README.md) 与 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)，确认任务范围和已知问题。
2. 读取 [CATALOGUE.json](CATALOGUE.json)，使用path/raw_url下载所需文件，记录standard、status、sha256、pdf_pages。source_paths是历史来源位置。
3. 对工程阅读本先读 [工程修复说明](09-repair-evidence/工程修复说明.md)；A/B/C/U等级分别表示直接恢复、工程重建、替代模型和未确认。
4. OCR只用来定位，公式必须核查PDF图像；仅说明实际成功读取的页和文件。网络/解析失败须明确报告。
5. 输出可支持的计算、适用版本、未确认项目和下一步所需证据。资料存在不等于验收通过。

本库包含历史版、预览及不同扫描副本，不要遍历后把所有文件都视作同一套适用标准。TR14179-2表12在源PDF41，非缺表；它的公式仍有部分未确认。DIN6885工程本不是2021-11官方版；TR14179-1来源合编本不使用PROOF正文。

## 可直接复制的提示词

请读取 https://raw.githubusercontent.com/qizhou-hust/yuanqi-public/main/standards/AI_START_HERE.md ，按入口说明读取README、KNOWN_ISSUES和CATALOGUE.json，并根据我的具体计算任务选择标准PDF。先列出实际读取的文件、版次、哈希及页码，再给出计算依据。区分原始扫描、公开预览、工程修复、替代模型和未确认项；OCR只用于定位，公式和表格核对原图。不要混用历史版，不要把工程修复稿当官方标准，不要凭30项算例检查宣称项目验收通过。发现缺少资料或无法读取时明确指出，不编造公式、系数或结论。
