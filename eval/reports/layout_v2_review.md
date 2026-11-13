# Layout 真值比对

- gold: `eval/layout_gold_99.csv` (99 页: double 85 / single 13 / ambiguous 1)
- pred: `out_llm_trial/wb_layout_v2_review` (double 73 / single 26)
- recall(double): **0.8471** (72/85)
- false positive(single→double): **0**
- precision(double): 1.0000
- 未判: 0 页

## 漏判 double（13）
- `2025_1` p6：pred=single
- `2025_1` p17：pred=single
- `40_10569` p3：pred=single
- `42_103` p12：pred=single
- `42_185` p7：pred=single
- `42_93` p1：pred=single
- `42_93` p4：pred=single
- `42_93` p6：pred=single
- `42_93` p9：pred=single
- `52_230302` p1：pred=single
- `52_230302` p6：pred=single
- `52_230725` p1：pred=single
- `5_55` p4：pred=single

## 误判 single→double（0）

## ambiguous（1）
- `42_103` p13：pred=double（允许 double/single）
