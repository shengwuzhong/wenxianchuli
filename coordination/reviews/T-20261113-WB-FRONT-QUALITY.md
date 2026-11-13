# Review — T-20261113-WB-FRONT-QUALITY（approve）

- 代码：`0caec2d`（cherry-pick 到 main）
- 改动：仅 `metapy/front.py`、`metapy/abs.py`
- 结论：**Approve**

## 作者

- 2025_1：5 → 5 人；`・木村治夫`→`木村治夫`，`川嶋渉造*1\dagger`→`川嶋渉造*1`；
- 11 篇作者总数 51 → 51，无减少；
- 外来名中缀 `ジョン・スミス` 保留。

## abstract_en

- 2025_1 假名数 11 → 0；长度 1446 → 1396；
- 其余 10 篇与 `out_base` 逐字段一致；
- 正常英文摘要不截断。

## 测试

- front 10/10；abs 6/6；unittest 12/12；
- out hash 不变。

## 残余

- 2025_1 affiliations 仍空：脚注 `1)` 与 marker `*1` 语义不匹配，基线已存在，非本次引入。
