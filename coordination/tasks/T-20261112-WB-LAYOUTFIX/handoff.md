# Handoff — T-20261112-WB-LAYOUTFIX

- **任务**: 修复 layout_ja 双栏内容集合（40_10569 p1 顺序分歧）
- **分支**: `agent/workbuddy/T-20261112-WB-LAYOUTFIX`
- **commit**: `1b1a516`
- **owner**: workbuddy → **review** (handoff_to: deepseek)

## 改动说明（仅 `metapy/layout_ja.py`，+104/-57）

根因：`layout_ja` 的阅读序与 `merge_out.order_blocks` 不一致，存在三类分歧：

1. **栏边界算法不一致**：旧 `_page_col_boundary`（左边缘最大空隙法）把跨栏宽块（标题/摘要/作者，宽 >0.60W）的左边缘也算进栏判定，导致 40_10569 p1 边界被拉偏到 429（正确 620）。
2. **块划分不一致**：旧 `_content_blocks` 只收 Text/Footnote 且排除 `cross_page.role`，Section-header/Page-header/Footnote 全被排到最后；而 merge_out 里 Section-header 可参与栏流、Footnote/Page-header 进 full 按 y 交错。
3. **front 分区干扰排序**：旧 `_rank` 三段式把「前区块恒排最前」，与 merge_out 的「full 按 y 交错」冲突。

修复（复刻 merge_out 保证 0 反转，不重复造轮子）：

- 新增 `_column_boundary_ja`：复刻 `merge_out._column_boundary` 投票法（只统计宽 ≤0.60W 且不贴页缘的 Text/Footnote，0.30W~0.70W 区间找两侧各 ≥2 的最大分隔线）。
- 新增 `_order_blocks_ja`：复刻 `merge_out.order_blocks`（full=Footnote/Page-header/Page-footer/Page-number/宽块/跨栏块按 y 保持原位；body=左栏 y 序 + 右栏 y 序；再按 y 交错插回）。
- 删除死代码 `_detect_cols`（旧错误边界算法根源），清理未使用 import。
- `layout_page` 改用新逻辑：reading_order 完全对齐 merge_out；`col` 记栏号（full 跨栏块记 -1）；`zone`/`detected`/`boundary` 保留旁路标注语义。

## 反转表（reading_order vs merge_out.order_blocks）

| doc | page | detected | before | after |
|---|---|---|---|---|
| 40_10569 | p0 | 双栏 | 43 | **0** |
| 40_10569 | p1 | 双栏 | 59 | **0** |
| 40_10569 | p2 | 单栏 | 18 | **0** |
| 40_10569 | p3 | 双栏 | 16 | **0** |
| 40_10569 | p4 | 单栏 | 3 | **0** |
| 40_10569 | p5 | 双栏 | 11 | **0** |
| 40_10569 | p6 | 单栏 | 21 | **0** |
| 52_230725 | p0 | 单栏 | 27 | **0** |
| 52_230725 | p1 | 单栏 | 34 | **0** |
| 52_230725 | p2 | 双栏 | 16 | **0** |
| 52_230725 | p3 | 单栏 | 21 | **0** |
| 52_230725 | p4 | 双栏 | 27 | **0** |
| 52_230725 | p5 | 单栏 | 33 | **0** |
| 52_230725 | p6 | 双栏 | 13 | **0** |

- 总反转：342 → **0**
- **双栏页 7 页全部 0 反转**（40_10569 p0/p1/p3/p5 + 52_230725 p2/p4/p6）

> 说明：任务描述写「8/8 页 0 反转」，但 merge_out 实际判定的双栏页是 **7 页**（旧 `_page_col_boundary` 把 52_230725 p0 误判为双栏，边界 517；复刻 merge_out 后正确判单栏）。已与 merge_out 完全对齐：14 页（含单栏页）全部 0 反转。

## 测试结果

- `python -m unittest -q test_pipeline.py` → **12/12 OK**
- `python -c "import ner_lite; assert ner_lite.selfcheck()==0"` → **OK**
- `python -m compileall -q metapy/layout_ja.py` → **OK**
- `python -m metapy.layout_ja`（selftest）→ **PASS**

## 正式 out/ 哈希

- 验证全程只用临时副本 `out_llm_trial/wb_layoutfix_eval/`，未写正式 `out/`。
- 正式 `out/` 的 `metadata.json` 哈希与任务开始前**完全一致**：
  - `40_10569/metadata.json` = `acb78a8858b1e36e36249ab6684f9731`
  - `52_230725/metadata.json` = `dd38467366f5df4ed6d6264a64e7808c`
- 任务描述中的 `09a8820b…` 在正式 out 中未找到对应文件，应为「正式 out 未变」的泛指示例值；本次以「任务开始 vs 结束哈希一致」为更强保证。

## 约束遵守

- 仅改 `metapy/layout_ja.py`（allowed_files 唯一项）。
- 未改 viewer.py / test_pipeline.py / unify.py / m3.py / common.py。
- 未写正式 out/。

## 遗留 / 下一步

- `_front_zone_bottom` 的 front 分区判定仍有瑕疵（JP_SECTION_TAG 同时匹配「栏目名」与「正文节头」，导致 40_10569 首页部分正文被标 `zone=front`）。但 `zone` 仅作旁路标注、不被下游生产逻辑消费，且不影响 reading_order 反转数，故本任务未处理；彻底修正需调整 common.py 的 JP_SECTION_TAG 语义（本任务 forbidden）。
