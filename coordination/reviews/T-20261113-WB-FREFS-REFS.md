# Review — T-20261113-WB-FREFS-REFS（approve，修订验收口径）

- 代码：`5d3f83c`（cherry-pick 到 main）
- 改动：仅 `metapy/refs.py`（仓库无 `metapy/frefs.py`，`frefs_doc` 在 refs.py）
- 结论：**Approve**

## frefs

- 42_93 的 3 条 frefs 实为页脚页码/刊名 running footer，不是脚注文献；
- 修复后 42_93 frefs **3 → 0**，并新增 `footnote_ref_validation.applicability`；
- 其余 10 篇给出“无编号脚注”适用性结论；
- 原任务 `frefs=3` 的验收前提是假阳性，按“删假阳性”通过。

## refs

- 40_10569 **19/19**；42_185 **18/18**；
- 133 条英文编号条目题名修正，suspicious=0；
- 条目数全语料不变：35/19/20/19/18/49/8/43/7/33/22；
- 测试：refs 51/51；unittest 12/12；out hash 不变。

## 备注

- 代码再次落在主工作树的 WB 分支，已 cherry-pick 到 main 并重置分支；流程例外。
- 5_55 少量题名在 OCR 断行处截断，未强改。
