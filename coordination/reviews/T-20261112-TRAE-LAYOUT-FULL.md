# Review — T-20261112-TRAE-LAYOUT-FULL（approve）

- 分支：`agent/trae/main` @ `7daf70f`
- 基线：`main` @ `5398e18`
- 结论：**Approve**（验证 + viewer 修复）

## 验收

| 项 | 结果 |
| --- | --- |
| 语料页数 | **99 页 / 11 篇**（任务书写的 110 与仓库不符） |
| CSV 覆盖 | 99/99，无跳页 |
| 双栏页 | 39 |
| 双栏反转 | **0 / 39** |
| 单栏差异页 | 12，逐页判定为“实为双栏但 `layout_ja` 欠检” |
| 截图 | 12 张（6 页整页 + 6 页放大），存在且可读 |
| 测试 | `test_pipeline.py` 12/12；`compileall viewer.py` OK |
| 正式 `out/` | 未写；哈希仍 `09a8820b…` |

## viewer.py 改动

1. `8570767`：**恢复丢失的 layout 叠加**。合并记录/tag 存在，但 `main` 的 `viewer.py` 实际没有 overlay 代码（`layout-band`/双栏线/序号）；这不是新功能，是补回丢失实现。
2. `7daf70f`：修正 layout 序号配色选择器；跨栏块不再按左栏画序号。修的是展示层的实际缺陷。

## 遗留（不阻塞本任务）

- 12 个单栏差异页是 `layout_ja` 真实欠检：`_column_boundary_ja` 的“两侧各 ≥2 块”门槛在每栏仅 1 块时判不出双栏。需要 WorkBuddy 开 follow-up 修 `layout_ja.py`，并复跑本报告的 99 页回归。
- 本任务只验证，不修 `layout_ja`；不要因此把 `P0-4` 标成 100% 已完成；`layout_ja` 双栏检测应记为约 85%。

## 合并建议

- 先合 Trae viewer.py（与 WorkBuddy refs 无文件冲突）。
- 再合 WorkBuddy refs follow-up；两边都改 `viewer.py` 的概率低，但 refs 任务不改 viewer。
