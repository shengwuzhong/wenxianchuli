# Review — T-20261113-TRAE-REFS-EXPORT（approve）

- 分支：`agent/trae/T-20261113-TRAE-REFS-EXPORT` @ `7e33c1b`
- 改动：仅 `viewer.py`（+69/−1）
- 结论：**Approve**

## 验收

| doc | refs | CSV 行 | 9 列 |
| --- | ---: | ---: | --- |
| 2025_1 | 35 | 35 | ✓ |
| 40_10569 | 19 | 19 | ✓ |
| 52_230725 | 7 | 7 | ✓ |

- CSV UTF-8、字段引号包裹、内部 `"` 转义；
- BibTeX `@article/@book`、key=`doc_num`、`\{}%&_#$` 转义；
- 空 refs 按钮 disabled；
- 浏览器 console 0 error；
- `test_pipeline.py` 12/12；`viewer.py` compile OK；out hash 不变。

## 备注

- 导出载荷按页重复嵌入（2025_1 约 3 处），当前可接受；后续可改为单例 JSON 节点瘦身。
