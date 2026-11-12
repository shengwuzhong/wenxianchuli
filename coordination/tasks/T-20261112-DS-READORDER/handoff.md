# T-20261112-DS-READORDER — handoff

## 任务
`merge_out.py` 的双栏阅读序：从“按 18px 行带 + x”改为“栏内 y 序”，修复日文双栏文献中右栏文字插到左栏中间、页眉页脚混入正文的问题。

## 分支 / commit
- worktree：`.worktrees/deepseek`
- 分支：`agent/deepseek/T-20261112-DS-READORDER`
- commit：`24d1877`
- base：`main`（`3157a5a`）

## 改动
### `merge_out.py`
- 新增 `_box()`、`_column_boundary()`、`order_blocks()`。
- `_column_boundary()`：在页面 30%–70% 宽度内，找“左侧结束 / 右侧开始”的正文块最多的竖线；两侧各至少 2 块才判双栏。
- `order_blocks()`：
  - 双栏：正文按“左栏自上而下 → 右栏自上而下”；
  - 标题/摘要/关键词等 full-width 块按 y 插入；
  - `Page-header` / `Page-footer` / `Page-number` / `Footnote` 不参与栏流，按 y 放回原位；
  - 单栏：仍按 `(y, x)`。
- 替换原来的 `blocks.sort(key=(round(y/18), x))`。

### `test_pipeline.py`
新增 `MergeReadingOrderTest` 两个用例：
- 双栏：`H, title, L1, L2, R1, R2, F`；
- 单栏：`A, B`。

## 验证
```bash
python -m unittest -v test_pipeline.py
# Ran 12 tests ... OK

python -c "import ner_lite; assert ner_lite.selfcheck() == 0"
# selfcheck OK

python -m compileall -q merge_out.py test_pipeline.py
# exit 0
```

### 52_230725 首页（mineru）
**旧**：
`Keywords → ケースが（右栏）→ I. はじめに → 左栏正文`
**新**：
`Keywords → I. はじめに → 左栏正文 → ケースが（右栏）→ 尚 → II. 電子プローブ径の最小化 → 脚注`

### 40_10569 首页（mineru）
**旧**：
`原著 → 标题 → 作者 → 要旨 → Keywords → 左栏正文 → 40:343 / 页眉`
**新**：
`40:343 → 原著 → 页眉 → 标题 → 作者 → 要旨 → Keywords → 背景および目的 → 左栏正文 → 右栏（日～2017年…）`

## 临时评测（未写正式 out/）
- `out_llm_trial/readorder_eval/52_230725`、`40_10569`：用新代码重跑 `merge_out.merge_doc`；
- `out_llm_trial/readorder_baseline/`：用现有 merged 直接跑当前 `unify` 作对照；
- 两组的 unify 指标一致（52_230725 `coverage=0.9571`、`one_to_one=0.6456`、`orphan=0.1519`；40_10569 `0.9853/0.7123/0.0548`），说明本次只改阅读序，没有改变归并结果。
- `out/` 正式产物未改，仍为 1,151 文件 / 185,248,343 字节。

## 已知限制
- 页面中部横向跨双栏的块（少见）仍按 y 插入，可能截断左栏；后续可用 `layout_ja` 的 `reading_order` 进一步细化。
- `unify.intra_group` 自己还会按 `(y/18,x)` 重排，所以本次只影响 `merged/` 与 `merged.md` 的阅读序，不影响 `unified/` 的几何/文本；这是有意为之（不改冻结文件）。
- 没有改 `unify.py` / `metapy/m3.py`。

## 下一步
- 请 WorkBuddy/Trae 或人工 review `merge_out.py` 的 `_column_boundary` 阈值（0.60W、0.65W、两侧≥2）。
- review 通过后由 Integrator 运行：
  ```bash
  python coordination/merge_check.py T-20261112-DS-READORDER --base main
  ```
  再合并。
