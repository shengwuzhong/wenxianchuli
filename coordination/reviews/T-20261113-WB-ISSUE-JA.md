# Review — T-20261113-WB-ISSUE-JA（approve）

- 代码：`4203e83`（cherry-pick 到 main；原 issue 分支已对齐 main）
- 改动：仅 `metapy/issue.py`（+82/−7）
- 结论：**Approve**

## 指标

- journal **11/11**；journal_en 11/11
- 2025_1：活断層研究 / 2025 / vol 63 / issue null / 1-17 / keywords 4
- 5_55：Proteome Letters / 2020 / vol 5 / issue 2 / 55-63
- 9_1：Proteome Letters / 2024 / vol 9 / issue 1 / 1-11
- 其余 8 篇 year/volume/issue/pages 不变
- keywords 仅 2025_1 4 条；英文 Key words 不反推
- 测试：issue 25/25；unittest 12/12；out hash 不变

## 备注

- 代码曾落在 issue 分支所在工作区（main 工作树），已 cherry-pick 到 main 并重置分支；流程例外已记录。
- `_DOI_JOURNAL` 仅 `10.14889`，后续新刊按表追加。
