# Review — T-20261113-TRAE-META-EXPORT（approve）

- 分支：`agent/trae/T-20261113-TRAE-META-EXPORT` @ `74ce3b4`（已 rebase main）
- 改动：仅 `viewer.py`（+50/−3）
- 结论：**Approve**

## 验收

| doc | 导出键 | refs | cspan | 解析 |
| --- | ---: | ---: | ---: | --- |
| 2025_1 | 3（partial） | 35 | 46 | OK |
| 40_10569 | 17 | 19 | 44 | OK |
| 52_230725 | 17 | 7 | 8 | OK |

- 17 字段：doc/title/title_en/authors/affiliations/abstract/abstract_en/journal/journal_en/year/volume/issue/pages/keywords/body/references/citation_spans；
- 空字段/partial metadata 安全导出；按钮 disabled 规则；
- 纯前端 Blob，UTF-8 pretty JSON；截图 1 张；console 0 error；
- `test_pipeline.py` 12/12；out hash 不变。
