# Review — T-20261113-TRAE-THUMBNAIL-NAV（approve）

- 分支：`agent/trae/T-20261113-TRAE-THUMBNAIL-NAV` @ `3b3205e`
- 改动：仅 `viewer.py`（+76/−4）
- 结论：**Approve**

## 验收

| doc | 页数 | 缩略图 | 点击 | 高亮 |
| --- | ---: | ---: | --- | --- |
| 2025_1 | 17 | 17 | data-p=9 定位成功 | scrollY→5，底部→16，顶部→0 |
| 40_10569 | 7 | 7 | — | — |
| 52_230725 | 7 | 7 | — | — |

- 左侧固定缩略图栏、lazy load；折叠/展开/localStorage；≤700px 默认折叠；
- 截图 3 张；浏览器 console 0 error；
- `test_pipeline.py` 12/12；`compileall viewer.py` OK；out hash 不变。

## 额外修复

- 同时修复 main 上 refs 导出 JS 的模板转义 bug（`\\`/`\r\n` 被 Python 普通字符串吞掉）；
  用 `String.fromCharCode` 常量替代，保证之前合并的 CSV/BibTeX 导出真正可用。
- 属于 viewer.py 内必要修复，不扩大范围。

## 备注

- 缩略图与既有顶部页码 nav 并存；未新增静态资源。
