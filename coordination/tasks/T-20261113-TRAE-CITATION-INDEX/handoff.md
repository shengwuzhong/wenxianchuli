# T-20261113-TRAE-CITATION-INDEX handoff

- 工具：Trae CN
- 分支：`agent/trae/T-20261113-TRAE-CITATION-INDEX` @ `5d4c5e8`
- 改动：仅 `viewer.py`（+95）

## 交付

- 右上 `#citetoggle` + 右侧 `#citepanel`；
- `#citedata` JSON 载荷由 `_cite_index_json(meta)` 生成；
- 每行：页码/引文串/confidence/句片段/回链题名/未回链标记；
- 点击滚动到 `section#p{page-1}` 并高亮 `[data-u=uid]`；
- “仅未回链”过滤，计数 `n/N`；无 cspan 安全显示。

## 验证

- 2025_1 46、52_230725 8、42_93 59；42_93 过滤 59→1；
- 点击定位/高亮、console 0 error；截图 2 张；
- `test_pipeline.py` 12/12；compileall OK；out hash 不变。

## 备注

- 已 rebase 到 main，包含缩略图导航/refs 导出修复；无冲突。
- 本回合未 merge/merge_check。
