# T-20261113-TRAE-THUMBNAIL-NAV handoff

- 工具：Trae CN
- 分支：`agent/trae/T-20261113-TRAE-THUMBNAIL-NAV`
- commit：`3b3205e`
- 改动：仅 `viewer.py`（+76/−4）

## 交付

- 左侧固定 `#thumbrail`，复用 `pages/page_N.jpg`，lazy/async；
- 点击缩略图 `scrollIntoView` 定位 `section#pN`；
- window + document capture scroll-spy，60ms 去抖，高亮当前页；
- `#thumbtoggle` 折叠/展开，localStorage 记忆；≤700px 默认折叠；
- 空/单页文档安全 return；
- 顺带修复 main 上 refs 导出 JS 的模板转义 bug（`\\`/`\r\n` 被 Python 普通字符串吞掉），改用 `String.fromCharCode` 常量。

## 验证

- 2025_1 17/17、40_10569 7/7、52_230725 7/7 缩略图；
- 点击定位、滚动高亮、折叠/展开、窄屏折叠均通过；
- 浏览器 console 0 error；截图 3 张；
- `test_pipeline.py` 12/12；compileall viewer.py OK；
- 正式 `out/` 未写入，哈希 `09a8820b…`。

## 备注

- 缩略图与既有顶部页码 nav 并存；未新增静态资源。
- 本回合未 merge/merge_check。
