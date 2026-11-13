# Review — T-20261113-WB-CSPAN-JA（approve）

- 分支：`agent/workbuddy/T-20261113-WB-CSPAN-JA` @ `de54511`（代码 `718a7f9`）
- 改动：仅 `metapy/cspan.py`（+186/−30 量级）
- 独立复测：`out_llm_trial/wb_cspan_review2`（refs 已填充）

## 指标

| doc | spans | exact | partial | unlinked |
| --- | ---: | ---: | ---: | ---: |
| 2025_1 | 46 | 46 | 0 | 0 |
| 52_230725 | 8 | 8 | 0 | 0 |
| 全语料 | **384** | **374** | 5 | 5 |

- exact 率 **97.40%**（≥95%）
- 旧 332 → 384；仅移除 9 条伪 span，无 exact 回归
- 测试：cspan 18/18；unittest 12/12；out hash 不变

## 残余（非阻塞）

- 52_230302 的 `服部ら(2016)`、`Yagi and Hishinuma, 1995` 为 partial，因本篇 refs 无对应条目；不改 cspan。
