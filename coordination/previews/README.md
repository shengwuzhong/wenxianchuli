# 预览冻结：out/ 2026-11-12T1413

## 是什么

WorkBuddy 在 `T-20261112-WB-ABS` 任务期间，把日文摘要修复的结果写进了正式 `out/`（10 个文件，5 篇文档 × `metadata.json` + `metadata_audit.json`）。用户决定**保留这份预览，不回滚**。

本目录记录这份预览的哈希与快照位置，防止后续误覆盖。

## 快照位置（Git 忽略）

```
out_llm_trial/previews/2026-11-12T1413/
├── out/5_55/metadata.json
├── out/5_55/metadata_audit.json
├── out/43_10814/...
├── out/42_93/...
├── out/40_10569/...
├── out/52_230725/...
└── manifest.json
```

## 已记录

- 10 个文件的逐文件 sha256 / bytes；
- `files_sha256`：这 10 个文件的聚合哈希；
- `out_manifest_sha256`：当前全部 1,151 个 `out/` 文件的聚合哈希；
- 生成时间、来源任务、文档列表。

见 `T-20261112-WB-ABS-preview.json`。

哈希口径：sha256 小写；全量 `out/` 清单按 posix 相对路径排序，完整清单在
`out_llm_trial/previews/2026-11-12T1413/out_manifest.tsv`。校验时请用同一排序口径，
不要用 PowerShell `Sort-Object` 与 Python `sorted` 互相比较。

## 冻结规则

1. **不得**再对正式 `out/` 运行 `metadata.py`、`pipeline.py`、`webapp.py` 的写操作，直到明确解冻。
2. 所有验证/测试必须用临时副本（`out_llm_trial/...`）或 `--out` 指向临时目录。
3. 如果发现 `out/` 被意外改写：
   - 先比对 `out_manifest_sha256`；
   - 只恢复被改的文件，不要整目录覆盖；
   - 恢复来源：`out_llm_trial/previews/2026-11-12T1413/out/...`；
   - 恢复后重新计算 `out_manifest_sha256`，应与记录一致。
4. 合并 WorkBuddy 的 `T-20261112-WB-ABS` 代码后，**也不自动重跑**正式 `out/`；预览保持原样。等用户明确要求再生成新预览。
5. `out/` 与 `out_llm_trial/` 都在 `.gitignore`；本目录的 JSON/README 才入库。

## 恢复单文件示例

```powershell
$main = 'D:\处理工具\2\multidoc-ocr-compare-main'
$snap = Join-Path $main 'out_llm_trial\previews\2026-11-12T1413'
Copy-Item "$snap\out\40_10569\metadata.json" `
          "$main\out\40_10569\metadata.json" -Force
```

## 注意

- 这份预览是用**尚未合并**的 WorkBuddy 代码生成的；`main` 上的代码与 `out/` 暂时不完全一致。
- 这是有意的：先保留预览，代码 review/merge 后再决定是否重新生成。
- 不要 `git clean -fdx`、不要删 `out_llm_trial/previews/`。
