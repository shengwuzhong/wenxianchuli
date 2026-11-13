# Review — T-20261113-WB-ENTITY-JA（approve）

- 代码：`07a0206`（直接提交在 main；任务分支未承载代码）
- 改动：仅 `metapy/entity.py`（+191/−65）
- 结论：**Approve**

## 指标

| 类型 | before | after |
| --- | ---: | ---: |
| funding | 1 | **2** |
| software | 3 | **5** |
| datasets | 2 | **2** |

新增样本：

- `52_230302` funding `JSPS JP18H05224`，evidence 为谢辞整句；
- `9_1` funding `GX 技術創出事業 JPMJGX23B3`；
- `52_230302` software `GSAS` / `Z-Rietveld`；
- `40_10569` software `4 Steps エクセル統計`；
- `9_1` software `LabSolutions`；
- `5_55` datasets `PDB` / `NCBI`。

## 验证

- `py -m metapy.entity`：10/10 PASS
- `py -m unittest test_pipeline.py`：12/12
- 正式 `out/` 哈希不变
- 旧 42_93/43_10814 的 `R` 假阳性被移除，方向正确

## 偏差

- handoff 汇总写 datasets `2→3`，实际 total 为 **2**（5_55 2→2）；数据本身无问题，是汇总行笔误。
- 代码未走 `agent/workbuddy/T-20261113-WB-ENTITY-JA` 分支，直接落在 main；因范围和测试均通过，保留不 revert，记录为流程例外。
