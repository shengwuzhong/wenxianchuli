# Handoff — T-20261113-TRAE-CITE-EXPORT

- 工具：trae
- 分支：agent/trae/T-20261113-TRAE-CITE-EXPORT（基于 main）
- 状态：review（handoff_to: deepseek）
- 范围：仅 `viewer.py`；未 merge、未 merge_check。

## 改了什么
1. `#citebar` 增加占位 `@@CITEEXP@@`；新增 `_cite_export_btn(meta)` 生成按钮（8 列载荷放 `data-cite`，空 cspan `disabled`）。
2. 新增 `window.citeExport(btn)`：全字段引号包裹、`"`→`""`、CRLF、UTF-8 Blob → `<doc>_citation_spans.csv`。
3. `#citebar button` 样式；`build_compare_viewer` 增加 `v.replace("@@CITEEXP@@", ...)`。

## 验证
- 2025_1 46 行 / 42_93 59 行 / 52_230725 8 行，均 8 列，Python `csv.reader` 复核通过。
- 浏览器点击捕获 `download=2025_1_citation_spans.csv`，无异常；三篇 console 0 error。
- 勾选「仅未回链」不影响导出（仍全量）。
- unittest 12/12；compileall OK；`out/` 1151 文件哈希 mismatch 0。

## 遗留 / 注意
- CSV 无 BOM（Excel 双击日文可能乱码）；如需 BOM 另开 task。
- sentence 列保留全句（不截断）；citation_text 为原文引文串。
- linked_nums/linked_titles 用 `;` 分隔，条目内若含 `;` 未转义（罕见）。

## 下一步
Integrator 评审 → merge_check → 合到 main；合并后建议在正式 out 上抽查一次 42_93（59 行）导出。
