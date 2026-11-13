# 日文金标准比对

- gold: `eval/ja_gold.json`
- pred: `out_llm_trial/wb_refs_review2`
- docs: 3

| doc | title | authors | journal | year | vol | issue | pages | abstract ratio | abstract_en ratio | refs recall | refs title | refs author |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025_1 | X | 0.0/0 | X | X | X | OK | X | - | 0.000 | 1.000 | 0.912 | 0.941 |
| 40_10569 | OK | 1.0/12 | OK | OK | OK | OK | OK | 1.000 | 0.000 | 0.947 | 0.789 | 0.947 |
| 52_230725 | OK | 0.0/0 | OK | OK | OK | OK | OK | - | 0.050 | 1.000 | 0.857 | 1.000 |

## 参考文献缺口（2025_1 / 40_10569 / 52_230725）

- **2025_1**: recall 1.000, pred 35 / gold 34, missing 0
- **40_10569**: recall 0.947, pred 19 / gold 19, missing 1
  - #16 The influence of stroke type, gender, and age on FIM improve — Tokunaga M, Watanabe S, Nakanishi R, et 
- **52_230725**: recall 1.000, pred 7 / gold 7, missing 0
