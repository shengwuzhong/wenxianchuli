# Layout 真值比对

- gold: `eval/layout_gold_99.csv` (99 页: double 85 / single 13 / ambiguous 1)
- pred: `out_llm_trial/wb_layout_order_review` (double 86 / single 13)
- recall(double): **1.0000** (85/85)
- false positive(single→double): **0**
- precision(double): 1.0000
- 未判: 0 页

## 漏判 double（0）

## 误判 single→double（0）

## ambiguous（1）
- `42_103` p13：pred=double（允许 double/single）
