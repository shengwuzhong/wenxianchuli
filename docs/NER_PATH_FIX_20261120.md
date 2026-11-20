# NER 产物落点修复（2026-11-20）

## 结论

`ner_lite.write_outputs` 统一落到：

```text
<区根>/out_llm_trial/fds_extract/ner_lite/<doc>/
```

`stages`、`pipeline`、GUI、QC、entview 使用同一判据。历史 204 篇错位产物已经迁移，迁移清单和回滚说明见
`coordination/migrations/T-20261120-WB-NERPATH.{json,md}`。

## 代码

- `ner_lite._leaf(base)`：`normpath` 后识别三种输入——
  - `…/out_llm_trial` → 补 `fds_extract/ner_lite`
  - `…/fds_extract` → 补 `ner_lite`
  - `…/fds_extract/ner_lite` → 保持不变
- `pipeline.ner_root_for_out(out)`：`out/<doc>` 的同级 `out_llm_trial`；A/B 区分别得到
  `<区根>/out_llm_trial`，不再写到 `<区根>/out/fds_extract/ner_lite`。
- `pipeline.main` 的 NER `write_outputs(..., dst=_ner_root)` 使用该根。
- `stages._st_ner` 继续使用 `zone.ner`/`ctx["ner_root"]`。

## 迁移

`tools/ner_migrate.py` 支持 `--plan/--apply/--snapshot/--verify/--rollback/--relocate-top/--self-test`。
本次清单为**事后快照 + 完整性校验**，不是 write-ahead 日志；逐篇 `src_verified:false`，回滚按全量对称搬迁。

已验证：

```text
--verify : 311 篇; 缺失 0 / 新增 0 / 变更 0
--plan   : 待迁 0 篇
--self-test: plan/apply/快照/校验/回滚/整体搬回 全通
```

## 回归

```text
py -3.11 -m unittest -q test_ner_paths.py \
  test_issue_header_year.py test_doc_types.py test_front_fallback.py \
  test_field_audit.py test_workbench_accounts.py test_workbench_state.py \
  test_ingest.py test_stages_optional.py test_webapp_rescue.py \
  test_workbench_runner.py test_pipeline.py
# 150 tests OK (skipped=30)
```

## 回滚

- 代码：`git revert` 本次 commit，恢复到旧 `write_outputs` 语义（不推荐，会重新出现“跑成功但显示未跑”）。
- 数据：`python tools/ner_migrate.py --relocate-top coordination/migrations/T-20261120-WB-NERPATH.json --apply -m <rollback.jsonl>`，
  再跑 `--verify` 复核。
- 迁移脚本和清单保留在 `coordination/migrations/`，不随日常构建删除。

## 注意

- 迁移清单是事后快照；不能逐篇证明当时从哪个源目录搬来，只能证明“现在 311 篇完整且 doc 字段一致”。
- `out_llm_trial` 下仍有 `check3/diag_*/trae_*` 等非产物目录，迁移脚本明确不碰。
