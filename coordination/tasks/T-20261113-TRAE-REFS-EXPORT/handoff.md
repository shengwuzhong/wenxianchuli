# T-20261113-TRAE-REFS-EXPORT handoff

- 工具：Trae CN
- 分支：`agent/trae/T-20261113-TRAE-REFS-EXPORT`
- commit：`7e33c1b`
- 改动：仅 `viewer.py`（+69/−1）

## 交付

- `_meta_cell` 文献组新增“导出 CSV / 导出 BibTeX”按钮；
- 纯前端 Blob 下载，无后端接口；
- CSV：`num,authors,title,year,journal,volume,issue,pages,doi`，UTF-8，字段引号转义；
- BibTeX：`@article/@book`，key=`doc_num`，`\{}%&_#$` 转义；
- 空 refs 按钮 disabled。

## 验证

| doc | refs | CSV 行 | 列 |
| --- | ---: | ---: | --- |
| 2025_1 | 35 | 35 | 9 |
| 40_10569 | 19 | 19 | 9 |
| 52_230725 | 7 | 7 | 9 |

- CSV 经 Python `csv.reader` 复核，全部 9 列；
- BibTeX 浏览器内实际输出，样例见 `out_llm_trial/trae_refs_export/report.md`；
- console 0 error；空 refs disabled；
- `test_pipeline.py` 12/12；`compileall viewer.py` OK；
- 正式 `out/` 未写入，哈希 `09a8820b…`。

## 备注

- 导出载荷按页重复嵌入（2025_1 约 3 处）；当前可接受，后续可改单例 JSON 节点。
- 本回合未 merge/merge_check。
