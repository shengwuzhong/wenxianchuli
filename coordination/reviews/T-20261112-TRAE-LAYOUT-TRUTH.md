# Review — T-20261112-TRAE-LAYOUT-TRUTH（approve）

- 报告：`out_llm_trial/trae_layout_truth/report.md`
- 真值表：`out_llm_trial/trae_layout_truth/truth.csv`
- 截图：`out_llm_trial/trae_layout_truth/shots/`（30 张）
- 结论：**Approve**（独立真值，只读，无代码改动）

## 计数

任务书写 12+17=29 页，但 WorkBuddy handoff 实际列了 18 个“误判页”，因此本轮判读 **30 页**：

- 12 目标页：11 double + 1 ambiguous（`42_103 p13`）
- 18 旧“误判页”：17 double + 1 single（`43_10814 p3`）
- 合计：**28 double / 1 single / 1 ambiguous**

## 关键结论

1. **旧 51/48 验收线错误**：18 个旧“单栏”里 17 页实际是双栏；只有 `43_10814 p3` 是单栏（两张并排 ROC 图，无正文栏）。
2. **42_185 p1 是双栏**：分界 619，gap 25px，y 重叠 381px；失败原因是前区 3 个窄跨栏块阻断“候选线划分全部块”，不是缺 gap。
3. **42_103 p13**：稀疏尾页，左文献尾 + 右责任作者信息，判 ambiguous；后续允许 double 或 single。
4. **几何兜底方向正确**：18 个旧误判页里 17 页判 double 是对的；不应因旧标签放弃兜底。

## 建议

- 采用“正文带 + 每侧≥1 个 Text 块 + 允许前区/图表跨线块为 full”的规则；
- 不再要求“候选线划分全部块”；
- 新目标：30 页 audited 28/1/1；39 个已知双栏不变；其余 30 个旧单栏页复核后再定全量目标（暂定 67/31/1）。
