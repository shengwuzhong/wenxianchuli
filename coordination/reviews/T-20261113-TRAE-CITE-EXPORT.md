# Review — T-20261113-TRAE-CITE-EXPORT（approve）

- 分支：`agent/trae/T-20261113-TRAE-CITE-EXPORT` @ `3ce162e`（已 rebase main）
- 改动：仅 `viewer.py`（+47/−1）
- 结论：**Approve**

## 验收

| doc | CSV 行 | 列 |
| --- | ---: | --- |
| 2025_1 | 46 | 8 |
| 42_93 | 59 | 8 |
| 52_230725 | 8 | 8 |

- 列：page,uid,confidence,citation_text,sentence,linked_nums,linked_titles,unlinked；
- 全量导出，不受“仅未回链”过滤影响；
- CSV UTF-8、引号转义、CRLF；`csv.reader` 全部 8 列；
- 空 cspan 按钮 disabled；console 0 error；截图 1 张；
- `test_pipeline.py` 12/12；out hash 不变。

## 备注

- 无 BOM；Excel 双击可能乱码，需要时另开任务加 BOM。
