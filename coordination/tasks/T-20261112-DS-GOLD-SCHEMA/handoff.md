# Handoff — T-20261112-DS-GOLD-SCHEMA

- 任务：日文金标准 GT 与比对骨架
- 工具：deepseek（Integrator）
- 基线：`main` @ `75a3da1`
- 状态：done

## 一、交付物

| 文件 | 内容 |
| --- | --- |
| `eval/ja_gold.json` | 11 篇文档字段/摘要 + 3 篇 61 条 refs；schema 1.0 |
| `eval/gold_eval.py` | 只读比对 `out/<doc>/metadata.json`；输出 Markdown + JSON |
| `eval/validate_gold.py` | GT 结构校验（必填字段、refs 字段、年份格式、重复 num） |
| `eval/reports/baseline_current.md` / `.json` | 当前代码基线（临时副本 `out_llm_trial/ja_status_1112`） |
| `docs/ja-gold.md` | GT 配置说明、计数、口径、基线、限制 |
| `docs/ja-improvement-plan.md` | 进度/规划更新（GT 60%、用户决策、优先级） |

## 二、GT 计数

- 语料：11 篇（`uploads/` 实际只有 11 个 PDF；用户口径“第 12 篇”未找到）。
- 文档字段：11/11。
- 日文摘要全文：8/11；`2025_1`/`52_230302`/`52_230725` 原文无日文要旨，GT `abstract=null`，`abstract_en` 作为补充。
- refs GT：
  - `2025_1`：35 条（34 唯一；#22 与 #6 原文重复，`duplicate_of=6`）；
  - `40_10569`：19 条；
  - `52_230725`：7 条。
- 其余 8 篇 refs：`pending`，不参与 recall 分母。

## 三、2025_1 验收口径（给 WorkBuddy）

- 条目级 recall = 1.0（34/34 唯一；或 35/35 含重复，按 `gt_refs_unique` 口径）。
- `title` 相似度 ≥0.90；`authors` token 命中 ≥0.60。
- `journal`/`volume`/`issue`/`pages`/`doi` 允许噪声，人工抽检。
- 命令：`py eval/gold_eval.py --pred <tmp> --doc 2025_1`。

## 四、基线（当前代码）

- `2025_1`：refs 0/34；journal/volume 空、issue=63（应为 volume=63, issue=null）；`abstract_en` 0.981（尾部日文行）。
- `40_10569`：refs 5/19，title 0/19。
- `52_230725`：refs 3/7，title 1/7。
- 文档 title/作者/年/页基本正确；摘要 8 篇 1.000。

## 五、已知限制

1. 第 12 篇文件缺失；GT 的 `corpus.expected_docs=12`、`present_docs=11`。
2. 8 篇 refs 未建 GT（pending）。
3. 2025_1 实际 35 条 < 用户估计的 ≥40；已逐页核对，未凑数。
4. 书籍/报告/网页的 `journal` 存出版社/机构，满足“journal/venue 必须包含”。
5. 重复条目默认按标题去重；若验收要求 35 条全中，需改 `gt_refs_unique`。

## 六、下一步

- `T-20261112-DS-GOLD-EXPAND`：补 8 篇 refs；第 12 篇到位后补入。
- WorkBuddy refs 合并前用 `eval/gold_eval.py` 复测 `2025_1`/`52_230725`。
- Trae layout 回归不受影响。
