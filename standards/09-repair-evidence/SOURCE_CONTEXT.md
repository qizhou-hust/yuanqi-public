# 修复证据的路径解释

本目录完整保留此前 engineering-repair-R1 文件及其 manifest.json。其3份标准工程阅读本也按原字节收录在 ../05-engineering-readers/，这里保留同名文件，方便原清单就地校验。报告PDF为说明文档，不是标准正文。

TR30-page-repair-provenance.json 是旧 M33 资料包的原始补页记录，里面的 standards/core、standards/previews 是旧 evidence 目录的相对路径。用 ../CATALOGUE.json 的 source_paths 和 SHA-256 查找本库对应文件；不要把记录里的旧路径解释为本目录路径。

manifest.json 的 sources 可能仅列文件名和外部下载地址，不表示所有来源全文都在本目录。来源文件与输出文件应按字段分别理解。
