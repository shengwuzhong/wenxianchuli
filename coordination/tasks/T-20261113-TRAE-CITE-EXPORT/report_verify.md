# T-20261113-TRAE-CITE-EXPORT 复核报告（重发任务）

结论：本任务已在 main 完成并审核通过，本轮**无代码改动**，只做验收复核。

- 实现提交 `3ce162e`「引文索引导出 CSV(8 列, 全量, 纯前端)」，合并 `6581e5f`，审核 `a990017`；本轮在 main `a990017` 复核，工作区干净。

## 行数 / 列数（临时副本 `out_llm_trial/wb_cspan_review2`）

| doc | cspan | CSV 数据行 | 列数 | CRLF | disabled |
|---|---|---|---|---|---|
| 2025_1 | 46 | 46 | 8 | 是 | 否 |
| 42_93 | 59 | 59 | 8 | 是 | 否 |
| 52_230725 | 8 | 8 | 8 | 是 | 否 |

空 cspan（`_cite_export_btn({'citation_spans': []})`）→ 输出 `disabled`，`onclick` 保留。

## 真实 JS 执行（非复刻）

Node v22 直接执行生成页面里的 `window.citeExport`（Blob/document/URL 打桩），2025_1 产出：

- `type=text/csv;charset=utf-8`，文件名 `2025_1_citation_spans.csv`；
- 47 行（1 表头 + 46 数据），全部 8 列，CRLF=True，无 BOM；
- 表头 `page,uid,confidence,citation_text,sentence,linked_nums,linked_titles,unlinked`；
- 首行 `1 / u0_13 / exact / 0`（unlinked=0 表示已回链）。

## 全量语义确认

`_cite_export_btn` 在渲染期直接遍历 `meta["citation_spans"]` 生成 `data-cite`，与「仅未回链」复选框（DOM 侧 `cionly` 过滤）无耦合，勾选状态不影响导出。

## 回归

- `py -m unittest test_pipeline.py`：Ran 12 tests，OK
- `py -m compileall viewer.py`：通过
- `out/` 1151 文件哈希：`09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`（不变）
- 生成页冒烟：`id="citecsv"` 唯一、无 `@@CITEEXP@@` 残留、`citeExport` 已注入

## 未覆盖项

- 浏览器 console / 截图：本机无 Playwright（未安装），改用 Node 执行同一段导出函数 + Python `csv.reader` 复核，字段与编码路径等价；如需像素级截图请在装有浏览器的机器补。
- 复核脚本在 `out_llm_trial/trae_cite_export/`（临时，不入库）。
