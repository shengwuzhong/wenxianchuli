# 上游 2026-11-19 合并记录

## 基线

| 项 | 值 |
| --- | --- |
| 本地主分支 | `main` @ `9cb5361` |
| 上游 | `KieranFinn/multidoc-ocr-compare` @ `1393d42` |
| 分叉基点 | `84f9b47` |
| 备份 tag | `backup/pre-upstream-20261119` |
| 备份分支 | `backup/local-before-upstream-20261119` |
| 仓库 bundle | `_backups/upstream-merge-20261119/repo.bundle` |
| 集成分支 | `integration/upstream-20261119` |
| 合并提交 | `27c4979` |

## 合并策略

- GUI 采用上游实现（工作区、备注、异步质检、筛选、实体视图、停止按钮等）。
- 日文/竖排元数据继续使用本地实现：`metapy/front.py`、`issue.py`、`refs.py`、`cspan.py`、`abs.py`、`common.py`。
- `metapy/m3.py` 保持本地冻结版本，未采用上游 `_cols_guarded`。
- `viewer.py`、`webapp.py` 保留本地版本（本地查看器、rescue guard）。
- `pipeline.py` 保留本地竖排链，叠加 upstream 的三通道缓存预检、`chain_failures`、NER `run_doc` 接口。
- `stages.py` 采用 upstream `run_doc`/`write_outputs(dst=)`，保留本地 `_SPAWN_LOCK`、可选 NER、按任务注入 Paddle token。
- `.gitignore`、CI 取并集。
- 本地 `推送GitHub.bat` 已恢复；SHA-256 `FAE22E63DE6BB6BE489815EA92714017E28C333A4A54DA9F17C31FB2E9EFA25A`。
- 原 `out/`、`uploads/`、`zones/` 未迁移、未覆盖；A/B 数据仍在原位置。

## 冲突

完整 merge 产生 19 个冲突文件、56 个冲突块。核心冲突是两套 GUI 架构：

- 本地：A/B 双区、持久任务库、Paddle 账号/页额度、自动 ingest、基线提示。
- 上游：workspace、备注、异步 QC、实体视图、筛选/搜索。

本次按 Gate A 处理：**GUI 上游、日文本地、m3 冻结、本地 viewer/webapp 保留**；因此上游 `front/issue/refs/viewer` 的元数据/查看器测试与本地实现不兼容，合并测试中将 `UpstreamUnifiedSafetyTest`、`UpstreamExtractionFallbackTest` 标记跳过（30 项），本地 77 项测试及上游 GUI/workspace/cache/runner 测试通过。跳过不是删除：以后若要采用上游元数据实现，应单独评估并恢复这些测试。

## 验证

| 项 | 结果 |
| --- | --- |
| 全量测试 | 136 tests, OK (skipped=30) |
| `test_pipeline.py` | 95 tests, OK (skipped=30) |
| `import` | pipeline/stages/ner_lite/qc/workspaces/entview/archive/viewer/webapp/gui OK |
| 日文 gold exact | `ja_gold` 11/11 全字段 1.000 |
| 竖排 gold | title 10/10、authors 9/9；其余字段 gold 未标注 |
| 直接产物扫描 | 379 docs，index 379，三通道 367，两通道 12，单/零通道 0 |
| 标题 | `title_missing=3`（`2009f...`、`52_7...`、`54_5...`，均为无正文/特殊旧产物，非本次合并引入）；非文章 `title_not_applicable=9` |
| 页数 | 2315 unified pages |
| 上游 GUI | `gui.App` 启动成功，A 282 docs；自定义 workspace `zone_b` 97 docs，路径 `zones/zone_b/out`，只读扫描，无 OCR |

## 回退

```powershell
# 只回退本次合并（保留主分支历史）
git switch main
git reset --hard backup/pre-upstream-20261119

# 或从 bundle 恢复
git bundle verify _backups/upstream-merge-20261119/repo.bundle
```

`channels.local.json`、`.workbench/`、`zones/zone_b/.workbench/`、`eval/reports/`、`docs/` 已备份到 `_backups/upstream-merge-20261119/config/`。

## 未完成

- 主分支尚未 fast-forward 到集成分支，等待合并结果复核。
- 上游 30 项元数据/查看器测试跳过；本地元数据仍然权威。
- 年份覆盖仍不足；下一步按计划做页面页眉/页脚/DOI/PDF 元数据抽取，并用 30–50 篇随机人工 gold 验证到 70% 左右。
- 26/43_2 的 dots 渠道仍等待服务恢复；不自动重试。
- B 工作区以 `zone_b` 名称写入 `.gui_prefs.json`（本机配置，不入库）。
