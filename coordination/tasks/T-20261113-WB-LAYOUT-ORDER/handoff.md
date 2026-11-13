# T-20261113-WB-LAYOUT-ORDER — 13 页新增双栏阅读序修复

## 结论
**PASS**。13 页块级反转 **36 → 0**；39 个已知双栏**无一页反转增加**；
检测未改：`layout_eval` 仍 **85/85 double、0 false positive**。

## 改动（仅 `metapy/layout_ja.py`，检测/边界主判据未动）
1. 排序单元换成 mineru 子块（`_merge_sort_units`）：只取与块框 IoU≥0.5 的子块，再取 IoU 最大者，
   否则退回块自身 → 合并块的排序位置与 merge 阶段一致。
2. 阅读序的栏边界改为「用 mineru 子块复算 merge 投票」（`_merge_boundary_ja`）；
   复算为单栏时阅读序退回 y 序（merge 也如此），不再硬套左栏全先。
3. full 块按 y 切带，**带内先左后右**（原单队列会被左栏靠下小块堵住，把右栏上段挤到跨栏图之后）。
4. `_selftest` 增加用例：跨栏图切上下两带，断言 `l1<r1<f<l2<r2`。
`_column_boundary_ja`（检测）与 `merge_out`/`unify`/`viewer` 均未改。

## 13 页 before/after（反转对数，IoU≥0.5 匹配口径）
| doc | page | before | after |
| --- | --- | ---: | ---: |
| 2025_1 | 3 | 6 | 0 |
| 42_103 | 5 | 1 | 0 |
| 42_103 | 10 | 2 | 0 |
| 42_185 | 4 | 1 | 0 |
| 42_93 | 3 | 2 | 0 |
| 42_93 | 6 | 4 | 0 |
| 52_230302 | 4 | 3 | 0 |
| 52_230725 | 2 | 5 | 0 |
| 52_230725 | 6 | 2 | 0 |
| 5_55 | 1 | 2 | 0 |
| 9_1 | 1 | 4 | 0 |
| 9_1 | 5 | 3 | 0 |
| 9_1 | 7 | 1 | 0 |
| 合计 | | **36** | **0** |

## 39 个已知双栏
- 仍 0 反转：34 页；其中 `2025_1 p16` 由 1→0、`42_103 p6` 由 3→0（变好）。
- 与基线持平（未增加）：`2025_1 p8` 1、`2025_1 p14` 1、`9_1 p3` 1。

## 检测回归（未改检测，仅确认未受影响）
- `py eval/layout_eval.py --pred out_llm_trial/wb_layout_order_eval --min-recall 1.0 --max-fp 0`
  → recall 1.0000（85/85）、false positive 0、precision 1.0000、未判 0 页。
- `42_185 p1` double、`43_10814 p3` single、`42_103 p13` double（ambiguous，允许）。
- 全量 99 页阅读序反转：**43 → 5**。

## 测试与哈希
- `py -m metapy.layout_ja` → PASS（含新增带序用例）
- `py -m unittest -v test_pipeline.py` → 12/12 OK
- `py -m compileall -q metapy/layout_ja.py` → OK；`ner_lite.selfcheck()` → 0
- 正式 `out/`：1151 文件，哈希仍 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`
- commit：`76f7e92`（Base `2abfc10`）

## 残余
- 非门禁页各余 1 条反转：`2025_1 p13`（0→1）、`42_103 p8`（0→1）。两者都不在 13 页与 39 页清单内；
  成因是 unify 丢/并了 1 个 mineru 子块，导致 merge 投票复算为单栏而 merge 实际判双栏。
- `2025_1 p8`/`p14`、`9_1 p3` 与基线相同的 1 条反转，属块集合差异，本轮未动。
- 本回合未 merge、未 merge_check。
