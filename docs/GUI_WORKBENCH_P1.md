# GUI 工作台 P1：字段 / 实体审计

## 目的

P0 解决“任务能不能安全地跑”，P1 解决“结果里哪些字段能信、缺的字段是真缺还是没查”。
本阶段不自动补值，不把空值当成缺失。

## 入口

- 主表选中文献后，点操作条「字段审计…」
- 或右键文献 →「字段 / 实体审计…」
- 双击仍打开对照查看器；审计是独立窗口，不改变原操作习惯

## 字段（16 项）

| 组 | 字段 |
| --- | --- |
| 核心 | 标题、作者、期刊、出版年、正文 |
| 条件 | 卷、期、页码、参考文献 |
| 可选 | 关键词、摘要、机构、引文句/脚注 |
| 实体 | 数据集、基金、软件 |

## 状态

| 状态 | 含义 |
| --- | --- |
| `present` 有 | 字段有非空值 |
| `absent_confirmed` 确认无 | 有审计证据证明不存在；目前只用于实体三类 |
| `not_applicable` 不适用 | 原文结构上不存在，例如 `issue.confidence.source=volume_only` |
| `extraction_failed` 抽取失败 | 产物缺失/解析失败，不能当作“无” |
| `not_checked` 未查 | 没有值，也没有逐页/逐渠道负证据；这是缺省状态 |
| `uncertain` 待确认 | 有候选/不完整结果，例如只有 `reference_candidates` |

核心原则：**空列表不是缺失证据**。元数据缺值默认 `not_checked`，不会自动标“确认无”。

## 负证据

`absent_confirmed` 的实体记录带五项证据：

- 检查页
- 查询内容
- 方法/模型
- 结果
- 置信度

元数据字段目前不产生 `absent_confirmed`；如后续要提升，需要先补逐页页码覆盖、检索式和判定记录，不能只凭 `metadata` 为空。

## 证据文件

- `out/<doc>/metadata.json`
- `out/<doc>/metadata_audit.json`（抽取依据，如“未定位摘要头”）
- `out_llm_trial/fds_extract/ner_lite/<doc>/ner_lite.json`
- 同目录 `ner_lite_audit.json`

窗口底部按钮可直接打开这些文件。

## 已知边界

- 正文状态沿用 `qc.body_ok` 的 ≥500 字符口径，不是逐页完整性审计
- 参考文献只区分“有 / 候选 / 未查”，未做条目级核对
- 机构字段合并了 `metadata.affiliations`、`authors[].affiliation` 和 NER 的 org 实体
- 实体审计依赖 `ner_lite_audit.json` 的零错误计数；没有审计文件时只能显示“未查”

## 验证

```bat
py -3.11 -m unittest -q test_field_audit.py test_workbench_state.py test_pipeline.py
```

GUI 冒烟：打开窗口后应有 13 个字段行、3 个实体行，标题栏显示“核心 x/5 齐 · 待核 n”。
