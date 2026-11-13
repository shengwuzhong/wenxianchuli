# T-20261113-WB-FREFS-REFS handoff

分支 `agent/workbuddy/T-20261113-WB-FREFS-REFS`（基于 main 9610b87）
改动文件：`metapy/refs.py`（**仓库无 `metapy/frefs.py`**，`frefs_doc` 实现就在 refs.py，故 A/B 同文件提交；未触碰其他模块 / out/）

## A frefs：42_93 的 3 条是"页码页脚噪声"，已剔除

关键发现（与本轮任务前提冲突，必须报）：42_93 这 3 条**不是脚注文献**——

| num | 页 | 原文 raw | 同页块 |
|---|---|---|---|
| 94 | p2 | `診断病理 2025, 42 (2)` | u1_5 `Page-number` = `94` |
| 96 | p4 | 同上 | u3_4 `Page-number` = `96` |
| 98 | p6 | 同上 | u5_7 `Page-number` = `98` |

成因：unify 的 dots 读法把页码并进页脚（成员文本 `94 診断病理 2025, 42 (2)`），`_footer_marked_text`
按"行首裸数字"收为脚注号 94。修法：页脚回退路径新增「行首裸数字 = 本页 Page-number 文本 → 跳过该行」
（`page_nums` 按页取 Page-number 块文本），全无有效行则整块不收；不碰 Footnote 块主路径。

**结果：42_93 frefs 3 → 0**。若要保住"3 条"，只能是保留这 3 条假阳性；删掉该守卫即可回退。

### 11 篇 frefs + 适用性结论（新增 `footnote_ref_validation.applicability`）

| doc | n | applicability.reason |
|---|---|---|
| 42_93 | 0 | 页脚仅页码/刊名 running footer(3 块，行首数字=本页页码)，无编号脚注 |
| 2025_1 / 40_10569 / 40_10588 / 43_10814 / 52_230302 / 52_230725 | 0 | Footnote 块 1–2 个，无行首编号标记（机构 / DOI / 受付日期脚注），非引文 |
| 42_103 | 0 | Footnote 块 3 个，均为 `＊N：` 本文注，无行首编号标记 |
| 42_185 / 5_55 / 9_1 | 0 | 无 Footnote / 带号 Page-footer 块，本篇不适用 |

## B refs：40_10569 19/19（题名逐条对 GT）+ 全局"第二作者当题名"缺陷修复

新增 `_en_vancouver_fields`：英文编号条目「作者. 题名. 誌名. 年;巻:頁」句点分层，作者段至
`et al:` / 首句点，题名至「年内最后一段（誌名）」；兼容题名含句点（`Electrical charge. Its role in …`）
与含冒号（`…: a pioneer TF perspective`）。门禁：行首编号 + 纯英文 + 无引号/斜体。

| doc | 条目 | 题名改动 | 说明 |
|---|---|---|---|
| 40_10569 | 19 | 2 | #16 `Watanabe S` → `The influence of stroke type…`；#19 `Shoji Honda` → `日本外傷データバンク…` |
| 42_185 | 18 | 15 | 例 `Trajkova A` → `Cellular plasticity in reprogramming…` |
| 42_93 | 49 | 45 | 例 `Neale TJ. Molecular mechanisms…` → `Molecular mechanisms of glomerular injury…` |
| 5_55 | 33 | 29 | 例 `Lee E` → `Discovery of a cytokine and its receptor…` |
| 9_1 | 22 | 19 | 例 `Yanes O` → `Metabolomics: the apogee of the omic triology` |
| 40_10588 | 20 | 8 | — |
| 43_10814 | 8 | 3 | — |
| 42_103 | 19 | 4 | — |
| 2025_1 / 52_230302 / 52_230725 | 35 / 43 / 7 | 0 | 逐字段不变 |

合计题名修正 133 条，无一条变成"人名/过短/空"（脚本校验 suspicious=0），`lang` 无变化，
`layout` 由 `en_manual` → `en_journal`（期刊条目，同批改进）。

新增 `_trim_tail_author_run`：末条粘尾页英文作者串（`… 2011 Shoji Honda, M.D., $ ^{1)} $ …`）
在「姓名 + M.D.」密集处切齐（≥2 处且切点前有年/页），30_10569 #19 的 raw/authors/source 恢复。

## 回归

- `py -m metapy.refs`：**51/51 PASS**（新增 3 例：Vancouver 冒号式、尾页作者行切齐、页脚页码噪声）
- `py -m unittest test_pipeline.py`：Ran 12 tests OK
- `py -m compileall metapy/refs.py`：通过
- 11 篇条目数全部不变：35/19/20/19/18/49/8/43/7/33/22
- `out/` 1151 文件哈希 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091` 不变

## 残余

- 42_93 frefs 由 3 降为 0 属"删假阳性"，与验收项「42_93 frefs=3」冲突，请裁决（见上）。
- 5_55 #2 等少数题名在句点处截断（`The human plasma proteome draft of`），属 OCR 断行残留，未强改。
- `applicability` 为新增诊断键，llmrep/viewer 未引用，纯附加。
