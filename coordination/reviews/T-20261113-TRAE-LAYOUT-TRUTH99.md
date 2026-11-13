# Review — T-20261113-TRAE-LAYOUT-TRUTH99（approve）

- 产物：`out_llm_trial/trae_layout_truth99/truth99.csv`、`report.md`、`shots/`
- 结论：**Approve**（只读真值，无代码改动）

## 计数

- 99/99 页：**double 85 / single 13 / ambiguous 1**
- 30 页旧真值 + 30 页本轮 + 39 个已知双栏 = 99，计数闭合。
- 10 个已知双栏抽检 **10/10** 一致。
- 本轮新判 double **18 页**；single 12 页；ambiguous 0（沿用 42_103 p13 的 1 页）。
- 18 张新 double 截图。

## 关键结论

1. 旧检测器只有 39 double，truth 为 85，**漏检 46 页**，旧 51/48 验收彻底作废。
2. 新 double 集中在“整栏被 OCR 并成 1 块”和“一侧是图/表”两类；这正是 V2 的 13 个漏判来源。
3. `42_103 p13` 仍 ambiguous；`43_10814 p3` 是唯一 single；`42_185 p1` double。

## 使用方式

- 已固化为 `eval/layout_gold_99.csv`（99 行）；
- 用 `eval/layout_eval.py --pred <tmp>` 做 V2 复测；
- 这是后续 WorkBuddy V2 补漏与 Trae 最终验收的唯一基线。
