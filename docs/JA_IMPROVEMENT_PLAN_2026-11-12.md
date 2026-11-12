# 日文文献处理：进度与规划说明

- 版本：2026-11-12
- 基线：`main` @ `c61a3fc`（GT/评审/布局回归已提交；此前 `75a3da1` 为 7 个抽取任务 done）
- 适用范围：`out/` 下 11 篇日文文献（10 篇已有正式元数据，`2025_1` 只有 merged/unified/viewer，没有 `metadata.json`）。用户口径为“12 篇、2025_1 为第 12 篇”，但 `uploads/` 与 `out/` 实际只有 11 个 PDF，第 12 篇未找到；见 §6。
- 当前策略：**A 方案冻结**。正式 `out/` 保持 2026-11-12T1413 预览，不重跑；所有验证在临时副本进行。新预览按用户决定放 `out_preview/`。
- 完成度口径：**工程完成度**（已通过验收的子项 / 当前定义的子项），不是字段准确率。金标准已建 11 篇文档字段/摘要 + 3 篇 refs，refs 准确率仍以 `eval/ja_gold.json` 为准。
- 金标准说明：`docs/JA_GOLD_2026-11-12.md`；基线 `eval/reports/baseline_current.md`。

---

## 0. 结论摘要

| 判断 | 内容 |
| --- | --- |
| 已完成 | 日文摘要（要旨/内联/无头）、作者与机构（核心案例）、英文摘要/标题（残余 1 篇）、`layout_ja` 实现、查看器日文面板与警告 |
| 最大缺口 | 参考文献（refs）日文化：`2025_1` 抽出 0 条，`52_230725` 7 行只切出 3 条，日文条目字段普遍错位，`lang` 仍把日文标成 `ko` |
| 第二缺口 | 引文句（cspan）依赖 refs：全角括号/日文作者-年份形态未支持，`2025_1` 为 0，`52_230725` 6 条 unlinked |
| 验证缺口 | Trae 已回归 11 篇 99 页：39 个双栏页反转 0；但 12 个单栏页实际是双栏但 `layout_ja` 欠检 |
| 评测缺口 | GT 已建：11 篇文档字段/摘要、3 篇 61 条 refs；其余 8 篇 refs 仍 pending；基线见 `eval/reports/baseline_current.md` |
| 交付缺口 | 正式 `out/` 是旧预览：摘要 4/10 有值，而当前代码 8/11；52/40/42_103 的英文摘要修复只在代码里，不在 `out/` |
| 等权工程完成度 | 15 项等权约 **54%**（100+80+90+85+100+70+45+60+15+100+0+60+0+0+0）/15 = 53.7% |

---

## 1. 改进项清单

### 1.1 总表

| 编号 | 改进项 | 优先级 | 状态 | 完成度 | 实现位置 / 依据 |
| --- | --- | --- | --- | --- | --- |
| P0-1 | 日文摘要抽取（`要旨：` 内联 + 无头首段） | P0 | 已完成 | 100% | `metapy/abs.py:122` `_collect_jp_inline`；`:151` `_collect_jp_headingless`；`:223` `abstract_doc`；merge `2db9c43` |
| P0-2 | 日文作者切分 / 机构关联 | P0 | 已完成（核心） | 80% | `metapy/front.py:7` `_BARE_SUP`；`:64` `_parse_author_line`；`:180` `front_doc`；`metapy/common.py:425` `EN_AFFIL_STRONG`；merge `8d1ecd6` |
| P0-3 | 英文摘要 / 英文标题残余修复 | P0 | 已完成（残余 1 篇） | 90% | `metapy/abs.py:12` `_AUTHOR_ROW`；`:17` `_is_en_abstract_start`；`:41` `_collect_abstract`；merge `45a4b0e` |
| P0-4 | `layout_ja` 栏检测 / 前区 / 阅读序实现 | P0 | 已完成（12 页欠检） | 85% | `metapy/layout_ja.py:75` `_column_boundary_ja`；`:99` `_order_blocks_ja`；`:145` `layout_page`；对齐 `merge_out.py:62` `order_blocks`；merge `71c1d05` |
| P0-5 | 查看器日文标签、字段警告、版面叠加 | P0 | 已完成 | 100% | `viewer.py:782` `_META_LABELS`；`:806` `_meta_is_ja`；`:825` `_meta_warnings`；`:1097` `_meta_overview`；merge `31e8098`；验证 tag `verify-T-20261112-TRAE-LAYOUT` |
| P1-1 | 参考文献（refs）日文化：文献区识别、条目切分、字段解析、`lang=ja` | P1 | 进行中（review changes requested） | 70% | `metapy/refs.py:7` `_split_entries_block`；`:456` `_extract_fields`；`:657` `lang` 二分类；`:1341` `refs_doc`；`regress.py:14` `REF_HEAD`；WorkBuddy `810de5a`；review `coordination/reviews/T-20261112-WB-REFS-JA.md` |
| P1-2 | 引文句（cspan）日文化：全角括号、日文作者-年份、回链 | P1 | 进行中 | 45% | `metapy/cspan.py:35` `NARR`（仅 ASCII 括号）；`:274` `_ref_pages`；`:288` `cspan_doc` |
| P1-3 | 本篇来源（`issue`）日文刊名 / 关键词 | P1 | 进行中 | 60% | `metapy/issue.py:133` `_jname_from_line`；`:201` `extract`；`:385` `issue_doc` |
| P1-4 | 脚注文献（frefs）日文适用性 | P1 | 未开始 | 15% | `metapy/refs.py:1706` `frefs_doc` |
| P1-5 | `layout_ja` 全量回归（11 篇 99 页） | P1 | 已完成 | 100% | Trae `T-20261112-TRAE-LAYOUT-FULL`：99 页逐页表、39 双栏页 0 反转、12 单栏差异判定；`coordination/reviews/T-20261112-TRAE-LAYOUT-FULL.md` |
| P1-6 | `layout_ja` 双栏欠检修复（12 页） | P1 | 未开始 | 0% | Trae 回归发现 `2025_1` p7/p13、`40_10588` p4、`42_103` p5/p13、`42_185` p1/p6、`42_93` p8/p10、`52_230302` p7、`5_55` p8、`9_1` p9 实为双栏但 `detected=single` |
| P2-1 | 日文金标准与字段准确率评测 | P2 | 进行中 | 60% | `eval/ja_gold.json`（11 篇字段/摘要，3 篇 61 条 refs）；`eval/gold_eval.py`；`eval/validate_gold.py`；基线 `eval/reports/baseline_current.md` |
| P2-2 | 文本规范化 / 术语统一 | P2 | 未开始 | 0% | 无实现；`metapy/common.py:80` 只有兼容字 NFKC 折叠，不是全文规范化 |
| P2-3 | 翻译（日→中） | P2 | 未开始 | 0% | 无实现、无规格 |
| P2-4 | 正式 `out/` 重生成 / `2025_1` 元数据补跑 | P2 | 未开始（按决定冻结） | 0% | `coordination/previews/T-20261112-WB-ABS-preview.json`；`out_manifest.tsv`；正式 `out/` 1151 文件 |

> 说明：P0-2、P0-3 标注“已完成（核心/残余）”表示任务已合并、主验收项通过，但仍有明确残余（见 §2）。完成度按子项计，残余比例不隐藏。

### 1.2 分项说明与依据

#### P0-1 日文摘要抽取 — 100%

- 三级查找：独立头 `要旨` → 内联 `要旨：` → 无头首段。
- 修复前 5 篇预览文档中只有 4 篇有日文摘要；修复后当前代码在 11 篇中 **8 篇有日文摘要**，其余 3 篇经核对属于原文无日文摘要（`2025_1`、`52_230302`、`52_230725` 均以英文摘要为主）。
- 负例处理：`52_230725` 返回 `None` + `empty`，未强行造摘要。
- 残余（非阻塞）：`_collect_jp_inline` 遇任意 `<` 即止，摘要内 `<sup>` 引文可能被截断；无头启发式缺少“确实无摘要”的负例固定测试。

#### P0-2 日文作者 / 机构 — 80%

- `52_230725`：作者 `[]` → `[小暮 敏博]`。
- `42_93`：1 条连写“本田 一穂 康 徳東 川西 邦夫” → 3 人。
- `43_10814`：作者切分并完成 `^{1)}`/`^{2)}` 机构关联（实际 7 人，任务书原写 5 人系误记）。
- `42_103` / `42_185`：各 1 人，经首页核对是正确的单作者综述，不是漏抽。
- 残余：`2025_1` 作者列表里“・木村治夫”“・谷口 薫”保留了前导“・”，上标 `*1\dagger` 也未清洗；语料没有作者人数金标准，无法量化全量准确率。

#### P0-3 英文摘要 / 英文标题 — 90%

| 文档 | 修复前 | 修复后 |
| --- | --- | --- |
| `52_230725` | 日文正文 + 公式 | 721 字符纯英文摘要 |
| `40_10569` | 空值 + `high` | 995 字符英文摘要（p7，`high` 合理） |
| `42_103` | 空值 + `empty` | 1062 字符英文摘要（p1，`mid`） |
| `42_185` | 机构行 | 1083 字符英文摘要 |
| `42_93` | 作者 + 机构 | 1257 字符英文摘要 |

- 当前 11 篇 `title_en` 全部有值；`abstract_en` 11/11 非空。
- 残余：`2025_1` 的 `abstract_en` 末尾混入 1 行日文（“して東側が…”，共 11 个假名）。原因见 §2.4。
- 残余：`_AUTHOR_ROW` 现在要求括号内至少 2 个纯字母词，单字罗马化作者行可能回归；尚无对应测试。

#### P0-4 `layout_ja` 实现 — 85%

- 复刻 `merge_out.order_blocks` 的“full 块按 y 交错、body 块左栏后右栏”逻辑，替换旧的左边缘最大空隙法。
- `40_10569` p1 的栏边界从错误的 429 纠正为 620；`52_230725` p0 从误判双栏纠正为单栏。
- `40_10569` + `52_230725` 共 14 页，其中 7 个双栏页与 `merge_out` 的反转数为 **0**（修复前 342 处）。
- Trae 全量回归（99 页）发现 **12 个单栏页实际是双栏但 `detected=single`**：`2025_1` p7/p13、`40_10588` p4、`42_103` p5/p13、`42_185` p1/p6、`42_93` p8/p10、`52_230302` p7、`5_55` p8、`9_1` p9。根因是 `_column_boundary_ja` 的“两侧各 ≥2 块”门槛在每栏仅 1 块时判不出双栏；这是 P1-6 的输入。
- 已知设计债：`layout_ja._order_blocks_ja` 与 `merge_out.order_blocks` 是两份复制逻辑，未来可能漂移。

#### P0-5 查看器 — 100%

- 日文文献显示“中文 · 日文”双语标签（标题/作者/机构/摘要/期刊/年卷期页/关键词/参考文献）。
- 字段级“待复核”警告：空摘要、`abstract_en` 含假名、`abstract_en` 与机构高度相似、`title_en` 以 Key words 开头、作者 0 人、作者混入章节词。
- 版面叠加：双栏边界线、`body/front` 分区、阅读序序号；截图 `40_10569_p1.png`（576 KB）、`52_230725_p1.png`（675 KB）。
- 残余：警告只是提示，不修数据；`abstract` 为空的提示会一直存在，直到后端能判定“原文无”。

#### P1-1 参考文献日文化 — 70%（review changes requested）

当前 `main` 共抽出 **233 条**参考文献，其中 `title=null` 24 条；但“字段存在”不等于“字段正确”：

- `2025_1`：文献区标题是 `文 献`（字间空格），`unify` 阶段的 `regress.REF_HEAD` 不匹配，页面 `in_ref=false`，`refs_doc` 直接输出“无文献区”，**0 条**；GT 逐页核对为 **35 条（34 唯一）**，不是 40+。
- `52_230725`：p7 `u6_6` 一个 Text 块内有 7 行、7 条文献，`_split_entries_block` 只切出 **3 条**，且作者/题名/出处错位（如 `Boersch, H` 的题名被写成 `: Experimentelle Bestimmung...`）。
- `40_10569`：19 条，16 条 `lang=ko`；`references[0]` 的 `authors` 含“1) 小林祥泰監修: 脳卒中データバンク 2009. 東京”，`title` 却是“中山書店”——典型的日文条目字段串位。
- `lang` 判定（`metapy/refs.py:657`）只有 `ko`/`en` 两类，汉字多即判 `ko`；全语料 **50 条**日文条目被标成 `ko`，没有 `ja`。
- 英文条目反而较稳：`42_185` 18 条、`52_230302` 42 条、`5_55` 33 条，`title=null` 很少。

**WorkBuddy `T-20261112-WB-REFS-JA`（`810de5a`）现状**：

| doc | pred | GT 唯一 | recall | title_ok | author_ok | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `2025_1` | 21 | 34 | **0.618** | **0.294** | **0.618** | 不通过（缺 13 条） |
| `40_10569` | 19 | 19 | 0.947 | 0.789 | 0.947 | 接近（缺 #16） |
| `52_230725` | 7 | 7 | **1.000** | 0.857 | **1.000** | 通过 |

Review 记录：`coordination/reviews/T-20261112-WB-REFS-JA.md`。阻塞点：第 17 页 `u16_3` 的 `all(_ja_line_selfcontained)` 不成立，只切出 3 条；第 16 页 `u15_4` 另有 4 条被过滤；多条英文 `title` 被填成 journal；`Sumirah` 条被页脚受付污染。

#### P1-2 引文句 cspan — 45%

- 当前共 **332 条**：`exact` 312、`partial` 5、`unlinked` 15（exact 率 94%，但这是规则标签，不是人工准确率）。
- 数字上标形态（`$ ^{1)} $`、`^{2,3)}`）在日文文献上工作良好；`NARR` 正则（`metapy/cspan.py:35`）只认 ASCII `(...)` 和 `(1998)` 形态，日文常见的 `（山田, 2018）`、`山田（2018）` 不识别。
- `2025_1` 因 refs 为 0，cspan 也是 0；`52_230725` 7 条中 6 条 `unlinked`（文献表只有 3 条可回链）；`52_230302` 4 条 `unlinked`。
- cspan 的“对号”依赖 `references[].authors_raw`，refs 字段错位会直接传导为 unlinked。

#### P1-3 本篇来源 issue — 60%

| 字段 | 覆盖 | 说明 |
| --- | --- | --- |
| `year` | 11/11 | 全部有值 |
| `pages` | 11/11 | 全部有值 |
| `volume` | 11/11 | 全部有值（`2025_1` 的 `63` 来自页眉“活断層研究 63号 1~17 2025”） |
| `issue` | 6/11 | 部分为原文无期号（需人工确认） |
| `journal` | 8/11 | 缺 `2025_1`（活断層研究）、`5_55`、`9_1`（Proteome Letters） |
| `keywords` | 4 条 / 1 篇 | 只有 `2025_1` 抽到 4 个日文关键词；多数文献只有英文 `Key words`，需区分“原文无日文关键词”与“漏抽” |

#### P1-4 frefs — 15%

- 全语料只有 `42_93` 抽出 3 条脚注文献，其余 10 篇为 0。
- 日文论文多数用“参考文献”而不是编号脚注，0 条可能是正确结果；但此前记录过 `42_93` 页脚误报，尚未系统复核。
- **需你确认**：日文语料是否要求 frefs（脚注引文）能力，还是只保留 refs。若不需要，本项目应明确“frefs 对日文语料不适用”，避免用 0 条误判为缺陷。

#### P1-5 `layout_ja` 全量回归 — 100%

- 语料实际 **99 页 / 11 篇**（此前写 110 页是笔误）：39 个双栏页、60 个单栏页。
- Trae `T-20261112-TRAE-LAYOUT-FULL` 已逐页回归：99/99 CSV 覆盖，39 个双栏页反转 **0**，12 个单栏差异页逐页判定为“实为双栏但 `layout_ja` 欠检”，不是映射误差。
- 截图 12 张（6 页整页 + 6 页放大）；正式 `out/` 未写，哈希仍 `09a8820b…`。
- 报告：`coordination/tasks/T-20261112-TRAE-LAYOUT-FULL/handoff.md`；review：`coordination/reviews/T-20261112-TRAE-LAYOUT-FULL.md`。

#### P1-6 `layout_ja` 双栏欠检修复 — 0%

- 12 页实为双栏但 `detected=single`：`2025_1` p7/p13、`40_10588` p4、`42_103` p5/p13、`42_185` p1/p6、`42_93` p8/p10、`52_230302` p7、`5_55` p8、`9_1` p9。
- 根因：`_column_boundary_ja` 要求分隔线两侧各 ≥2 个窄块；当每栏只有 1 个块（如单段落跨栏）时判不出双栏。
- 修复方向：对“每侧 1 块但几何上明显分栏”的页面增加几何兜底（左右块 x 区间不重叠 + 中间间隙），但不得把真正的单栏页误判为双栏；用 Trae 的 99 页回归复测。

#### P2-1 金标准 — 60%

- 已建 `eval/ja_gold.json`：
  - 11 篇文档的 title/title_en/authors/affiliations/journal/year/volume/issue/pages；
  - 8 篇日文摘要全文（另 3 篇原文无日文摘要，GT 记 `null`）；11 篇英文摘要；
  - 3 篇参考文献 GT：`2025_1` 35 条（34 唯一，1 条原文重复）、`40_10569` 19 条、`52_230725` 7 条。
- 已建 `eval/gold_eval.py`（只读比对）与 `eval/validate_gold.py`（结构校验）；基线报告 `eval/reports/baseline_current.md`。
- 未完成：其余 8 篇 refs GT 仍 pending；第 12 篇文件未找到；title/author 相似度阈值与重复条目口径需最终确认。
- 影响：refs 任务现在有可量化的 recall/title/author 验收，不再用“条数”当代理指标。

#### P2-2 规范化 / 术语 — 0%

- 目前只有 `metapy/common.py:80` 的兼容字 NFKC 折叠（用于比对），不是对正文/摘要/文献的全文规范化。
- 用户已确认范围：NFKC + 新旧字体统一 + 送假名标准化；作用字段 title/author/abstract/body/refs；DOI、KAKENHI 编号、术语表词汇强保护；保留 `raw_text` 与 `normalized_text` 双向映射。规格已定，实现未开始。

#### P2-3 翻译 — 0%

- 代码中没有任何翻译实现。
- 用户已确认范围：字段 title/abstract/keywords；输出中文；隔离到 `out_llm_trial/`；初期不设硬门槛，只做人工抽检。实现未开始。

#### P2-4 正式 out 重生成 — 0%（按决定冻结）

- 正式 `out/`：1151 文件，全量清单哈希 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`，与冻结记录一致。
- 10 篇有 `metadata.json`；`2025_1` 没有（只有 merged/unified/viewer）。
- 用户决定：继续冻结；新预览放 `out_preview/`，不写正式 `out/`。
- 当前代码已领先预览：摘要 8/11 vs 预览 4/10；52/40/42_103 的英文摘要修复只存在于代码和临时副本。

---

## 2. 差距分析

### 2.1 参考文献：为什么 2025_1 是 0 条

**根因有三层，必须同时修：**

1. **文献区识别在 `unify` 阶段完成，且正则不容字间空格。**
   `unify.py:422` 用 `regress.REF_HEAD` 判断 `Section-header` 是否文献标题；`REF_HEAD`（`regress.py:14`）只匹配连续的“参考文献/引用文献/文献/References”。日文排版常把标题排成 `文 献`、`引 用 文 献`，`2025_1` 的 `u15_7` 正是 `文 献`，因此 `in_ref=false`，`refs_doc` 在 `refs.py:1355` 直接返回“无文献区”。
   `metapy/common.py:418` 已有 `JP_REF_HEAD`，但它只覆盖“参考文献/引用文献”，不含裸“文献”，也没有被 `unify`/`refs` 使用。

2. **条目切分假设“空行/编号分段”，不假设“一行一条”。**
   `_split_entries_block`（`refs.py:7`）对日文文献常见的“一个 Text 块里每行一条”不友好。`52_230725` 的 `u6_6` 有 7 行、7 条，只切出 3 条，其余被合并或丢弃。

3. **字段解析是韩文著录语法优先。**
   `_extract_fields`（`refs.py:456`）主要处理“저자, 연도, 제목”这类韩文/英文逗号著录；日文常见“著者(年): 題名. 誌名, 巻, 頁”或“著者（年）「題名」...”没有专门分支，导致作者、题名、出处、出版社串位。
   `lang`（`refs.py:657`）只有 `ko`/`en`，汉字多即 `ko`，所以 50 条日文条目全部标错。

**影响：**

- `2025_1` 的 refs/cspan 都是 0，查看器文献区和引文区为空；
- `52_230725` 的 7 条文献只显示 3 条，cspan 6 条无法回链；
- 所有依赖 `references[].authors_raw` 的 cspan 对号质量下降；
- 无法建立“文献条目”金标准，因为连条目边界都不稳定。

### 2.2 cspan：日文括注形态未覆盖

- `NARR`（`cspan.py:35`）只匹配 ASCII 括号 + `19xx/20xx` 年份；日文文献大量使用全角 `（` `）`，且作者与年份之间可能没有逗号（`山田（2018）`、`（山田 2018）`）。
- 数字上标形态工作良好，所以“日文引文句完全不能用”不成立；缺口集中在**作者-年份括注**。
- 由于 refs 字段错位，cspan 的 `linked_refs` 回链会指向错误条目或落 `unlinked`；`2025_1` 因 refs 为 0 直接 0 条。

### 2.3 layout_ja：实现已对齐，验证覆盖不足

- `layout_ja` 与 `merge_out` 是两份复制逻辑：前者吃 unified 共识块，后者吃 mineru 单渠道块。块集合不同，单栏页上可能出现“同一页两种顺序”，即使双栏页完全一致。
- 人工核对只覆盖 2 篇 14 页；其余 9 篇 96 页没有逐页结论。自动比对出现的 1–5 处差异，可能是 IoU 映射把宽块/公式块映射错，也可能是真实顺序分歧，需要逐页看。
- 影响：查看器 overlay 只在 2 篇上做过视觉验收；如果其他篇有真实反转，用户会看到序号与阅读顺序不符。

### 2.4 作者与英文摘要的残余

- **作者分隔符**：`2025_1` 的“・木村治夫”“・谷口 薫”保留了前导“・”，`*1\dagger` 也未清洗。`front.py` 已处理裸上标 `^{...}`，但没有处理 `・` 前缀和 `\dagger` 组合。
- **`abstract_en` 日文尾行**：`2025_1` 有独立 `Abstract` 头，`_collect_abstract` 走“有头”分支；该分支没有“遇日文行即止”的条件（`_is_en_abstract_start` 的语言停止只在无头/else 分支使用），于是把紧随其后的 1 行日文正文收进英文摘要。影响 1 篇、11 个假名，但属于“英文摘要混入日文”的明确缺陷。
- **单字罗马化作者行**：`_AUTHOR_ROW` 现在要求括号内至少 2 个纯字母词，单字罗马化（如 `(Kogure)`）可能不再被识别为作者行；当前语料未触发，但没有回归测试。

### 2.5 issue：日文刊名模式不足

- `_jname_from_line`（`issue.py:133`）的锚点偏韩文/英文（`학회지`、`Journal`、`Letters` 等）。`2025_1` 的“活断層研究 63号 1~17 2025”没有被识别为刊名；`5_55`、`9_1` 同样缺失。
- `keywords` 只有 `2025_1` 抽到 4 个日文词；多数文献只有英文 `Key words`，需要区分“原文无日文关键词”与“漏抽”，否则会把 0 当缺陷。
- 年份/页码已全覆盖，卷/期大部分正确；问题集中在刊名和关键词。

### 2.6 评测：没有金标准，无法谈准确率

- 没有 `eval/ja_gold.json`；`audit_accuracy.py` 不是比对工具。
- 影响：所有验收只能写“字段非空/长度/假名数/条目数”这类代理指标；无法回答“摘要是否忠实”“文献作者是否切对”“cspan 是否真的对号”。
- 这也是为什么本报告把完成度定义为“工程完成度”，并在每项后标注“不是准确率”。

### 2.7 交付：正式 out 与代码不同步

- 正式 `out/` 是 2026-11-12T1413 的预览：摘要 4/10 有值；当前代码 8/11。
- `2025_1` 在正式 `out/` 里没有 `metadata.json`，只有 merged/unified/viewer；这意味着“11 篇”里只有 10 篇能进入元数据对比。
- 影响：用户现在打开查看器，看到的仍是旧摘要/旧作者/旧英文摘要；代码修复没有体现在交付物里。
- 这是 A 方案的预期代价，不是事故；但必须在“验收/交付”时明确说明，否则会被误认为修复无效。

### 2.8 影响排序

| 缺口 | 影响面 | 严重度 |
| --- | --- | --- |
| refs 日文化 | 文献表、cspan 回链、查看器、金标准 | 高 |
| cspan 全角/作者-年份 | 引文句、审计页 | 中高 |
| 无金标准 | 所有“准确率”结论 | 高（验收层面） |
| `layout_ja` 全量未验证 | 阅读序 overlay | 中 |
| `2025_1` 无正式 metadata | 交付完整性 | 中高 |
| 作者“・”/英文摘要日文尾行 | 单篇质量 | 中 |
| issue 刊名/关键词 | 来源字段 | 中低 |
| 规范化/翻译未定义 | 未来能力 | 待定 |

---

## 3. 下一步任务规划

### 3.1 优先级总表

| 优先级 | 任务 ID | 任务 | 建议 owner | 依赖 | 验收标准（摘要） |
| --- | --- | --- | --- | --- | --- |
| P0 | `T-20261112-WB-REFS-JA` | 日文参考文献抽取 | WorkBuddy | 无 | `2025_1` GT recall=1.0（34/34 唯一，35 条含 1 条原文重复）；`52_230725` 7/7；`40_10569` title/author 抽检；日文条目 `lang=ja`；回归测试全过 |
| P0 | `T-20261112-WB-ABS-EN-JA` | `abstract_en` 遇日文行终止 | WorkBuddy | 无 | `2025_1` 的 `abstract_en` 假名数=0；11 篇全部无日文尾行；abs 自检通过 |
| P0 | `T-20261112-DS-GOLD-SCHEMA` | 日文金标准 schema 与比对骨架 | DeepSeek | 已确认字段 | **已完成**：`eval/ja_gold.json` + `eval/gold_eval.py` + 基线报告；不写 `out/` |
| P0 | `T-20261112-USER-OUT-DECISION` | 是否解冻 `out/` / 补 `2025_1` | 用户 + DeepSeek | 用户拍板 | 明确“继续冻结”或“生成新预览”；若解冻，`2025_1` 必须有 `metadata.json` |
| P1 | `T-20261112-WB-CSPAN-JA` | 日文全角括注/作者-年份 | WorkBuddy | `WB-REFS-JA` | 6 个合成用例通过；`2025_1` cspan ≥10；`52_230725` unlinked ≤2；exact ≥95% |
| P1 | `T-20261112-TRAE-LAYOUT-FULL` | 11 篇 99 页 layout/viewer 全量回归 | Trae | 无 | **已完成**：99 页逐页表；39 个双栏页 0 反转；12 单栏差异逐页判定；12 张截图；12/12 测试；merge `12e5c2a` |
| P1 | `T-20261112-WB-LAYOUT-DETECT` | 12 页双栏欠检修复 | WorkBuddy | Trae 回归报告 | 12 页全部 `detected=double`；39 个已知双栏页仍 0 反转；不新增单栏误判；99 页回归复测 |
| P1 | `T-20261112-WB-ISSUE-JA` | 日文刊名/关键词 | WorkBuddy | 无 | `journal` 11/11；有日文关键词的篇目不漏；无回归 |
| P1 | `T-20261112-WB-AUTHOR-CLEAN` | 作者“・”/`\dagger` 清洗 | WorkBuddy | 无 | `2025_1` 作者无前导“・”、无 `\dagger`；其他篇人数不变 |
| P2 | `T-20261112-WB-FREFS-JA` | frefs 日文适用性 | WorkBuddy | 用户确认是否需要 | 明确“需要/不需要”；需要则 `42_93` 误报复核 + 日文脚注样例 |
| P2 | `T-20261112-DS-GOLD-EXPAND` | 其余 8 篇 refs GT + 第 12 篇补入 | DeepSeek | 用户确认第 12 篇 | refs GT 覆盖 11/11；`eval/validate_gold.py` PASS；基线可复算 |
| P2 | `T-20261112-DS-NORM-SPEC` | 规范化/术语规格 | 用户 + DeepSeek | 用户给范围 | 规格文档 + 样例；不含实现 |
| P2 | `T-20261112-DS-TRANS-SPEC` | 翻译规格 | 用户 + DeepSeek | 用户给范围 | 规格文档 + 样例；不含实现 |
| P2 | `T-20261112-DS-OUT-REGEN` | 新预览生成 | DeepSeek | P0/P1 稳定 + 用户同意 | 新 preview manifest；旧预览可回滚；哈希可复算 |

> P0 的四项里，`USER-OUT-DECISION` 不是代码任务，但它决定“交付物何时更新”，必须显式挂起，不能默认解冻。
> 用户已确认优先级：**refs > cspan/layout > 金标准**。金标准配置已提前完成，用于给 refs/cspan 提供验收尺子；它不在关键路径上，但 refs 合并前必须用它复测。

### 3.2 任务详述

#### T-20261112-WB-REFS-JA（P0，WorkBuddy）

- **目标**：让日文参考文献“找得到、切得开、字段对、语言对”。
- **范围**：`metapy/refs.py`、`metapy/common.py`、`regress.py`；不改 `unify.py`、`m3.py`、`viewer.py`、`test_pipeline.py`、`webapp.py`，不写正式 `out/`。
- **做法建议**：
  1. 文献区回退：`refs_doc` 在 `in_ref` 为空时，本地扫描 `JP_REF_HEAD` 变体（允许字间空格：`文\s*献`、`引\s*用\s*文\s*献`、`参\s*考\s*文\s*献`），从最后一个命中页到文末视为文献区；已有 `in_ref` 的页面保持原逻辑。
  2. 条目切分：文献区内若一个 Text 块多行、且每行都像独立条目（含年份 + 句末/页码），按行切；保留现有空行/编号切分作为优先路径。
  3. 字段解析：新增日文著录分支：`著者(年): 題名. 誌名, 巻, 頁`、`著者（年）「題名」...`、`著者, 年, 「題名」, 出版社`；作者只取年份前的主段，题名/出处/出版社按标点角色回填。
  4. `lang`：出现假名即 `ja`（优先于汉字计数的 `ko`）；纯拉丁仍 `en`。
  5. 不改 `unify` 的 `in_ref` 语义；`regress.REF_HEAD` 可加空格容忍，但不得因此重跑正式 `out/`。
- **验收**：
  - `2025_1` 参考文献 recall=1.0（GT 35 条、34 唯一；含 1 条原文重复 #22）；title 相似度 ≥0.90、authors token 命中 ≥0.60。
  - `52_230725` 7 行 → 7 条，`title` 不再以 `:` 开头。
  - `40_10569` 抽 5 条，作者/题名/出处不串位。
  - 日文条目 `lang=ja` 占比 ≥90%；英文条目 `lang=en` 不变。
  - `py -m metapy.refs` 自检全过；`py -m unittest -q test_pipeline.py` 12/12；`compileall` 通过。
  - 正式 `out/` 哈希仍 `09a8820b…`。

#### T-20261112-WB-ABS-EN-JA（P0，WorkBuddy）

- **目标**：英文摘要遇到日文行即止，消除 `2025_1` 的 11 个假名尾行。
- **范围**：仅 `metapy/abs.py`。
- **做法建议**：在“有 `Abstract` 头”的 `_collect_abstract` 分支中，对每个候选行计算日文比例；一旦 >0.15 或命中 `JP_SECTION_TAG`/`JP_ABS_HEAD`，终止收集。不要影响英文摘要内部的英文机构名/英文句子。
- **验收**：`2025_1` `abstract_en` 假名=0、长度仍 >1000；其余 10 篇 `abstract_en` 逐字节不变（或仅 `generated` 变化）；`py -m metapy.abs` 3/3；12/12 测试。

#### T-20261112-DS-GOLD-SCHEMA（已完成，DeepSeek）

- **状态**：2026-11-12 完成。`eval/ja_gold.json` 已建 11 篇文档字段/摘要 + 3 篇 61 条 refs；`eval/gold_eval.py` 可只读比对；`eval/validate_gold.py` 结构校验 PASS；基线 `eval/reports/baseline_current.md`。
- **2025_1 计数**：35 条（34 唯一，1 条原文重复）；recall 分母 34；`title`/`author` 硬字段。
- **范围**：不写 `out/`；`audit_accuracy.py` 仍归 WorkBuddy，本次未改。
- **后续**：`T-20261112-DS-GOLD-EXPAND` 补其余 8 篇 refs，并在第 12 篇文件到位后补入。

#### T-20261112-DS-GOLD-EXPAND（P2，DeepSeek）

- **目标**：把 refs GT 从 3 篇扩到 11 篇（或 12 篇），让 refs recall 有全语料分母。
- **范围**：`eval/ja_gold.json` 的 `references` 字段；不改抽取代码。
- **验收**：8 篇各 ≥ 当前 refs 条数；`validate_gold.py` PASS；基线重算；仍不写 `out/`。
- **依赖**：第 12 篇文件（若确有）；否则按 11 篇。

#### T-20261112-WB-CSPAN-JA（P1，WorkBuddy）

- **目标**：支持日文全角括注和作者-年份形态，并改善回链。
- **范围**：仅 `metapy/cspan.py`。
- **做法建议**：
  - `NARR` 增加全角 `（...）` 与无逗号形态：`（山田, 2018）`、`（山田 2018）`、`山田（2018）`、`山田(2018)`。
  - 年份前后允许 `a/b` 后缀；作者段允许 `・`、`　`（全角空格）、`et al.`。
  - 回链仍走 `references[].authors_raw`；refs 修好后，`2025_1` 应能产生 cspan。
- **验收**：6 个合成用例（全角/半角/无逗号/多作者/同年 a-b/无回链）通过；`2025_1` cspan ≥10；`52_230725` unlinked ≤2；全语料 exact ≥95%（当前 94%）；不回归现有 332 条。
- **依赖**：`WB-REFS-JA` 合并后做，否则 `2025_1` 仍无文献可回链。

#### T-20261112-TRAE-LAYOUT-FULL（P1，Trae）

- **目标**：把“2 篇 14 页”的验证扩到“11 篇 99 页”，给出逐页结论，而不是只给汇总。
- **范围**：只读 `metapy/layout_ja.py`、`merge_out.py`；写 `out_llm_trial/trae_layout_full/` 报告/截图；`viewer.py` 仅在发现渲染缺陷时改。
- **做法**：复用 `T-20261112-TRAE-LAYOUT` 的 IoU≥0.5 映射；对每页输出 `matched/inversions/columns/reading_order`；对单栏页的差异逐页标注“映射误差/块集合差异/真实反转”。
- **验收**：99 页 CSV/Markdown 表；39 个双栏页 0 反转；单栏差异每页有结论；12 张截图；`test_pipeline.py` 12/12；正式 `out/` 哈希不变。
- **结果**：已完成并合并 `12e5c2a`；99/99 页覆盖、39/39 双栏 0 反转、12 页单栏差异判定为 `layout_ja` 欠检；viewer 两个修复（`8570767` 恢复 overlay、`7daf70f` 序号配色）一并合并。

#### T-20261112-WB-LAYOUT-DETECT（P1，WorkBuddy）

- **目标**：修复 Trae 报告的 12 页双栏欠检。
- **范围**：仅 `metapy/layout_ja.py`；不改 `merge_out.py`、`unify.py`、`m3.py`。
- **做法建议**：在 `_column_boundary_ja` 的“两侧各 ≥2 块”之外增加几何兜底：左右两组块 x 区间不重叠、中间间隙 ≥20px、两组 y 区间有重叠；每侧仅 1 块时也判双栏；但必须保证 60 个已知单栏页不误判。
- **验收**：12 页全部 `detected=double`；39 个已知双栏页仍 0 反转；60 个已知单栏页不新增双栏；Trae 99 页回归复测；`test_pipeline.py` 12/12。

#### T-20261112-WB-ISSUE-JA（P1，WorkBuddy）

- **目标**：日文刊名 11/11；有日文关键词的篇目不漏。
- **范围**：仅 `metapy/issue.py`。
- **验收**：`2025_1` 刊名=活断層研究；`5_55`/`9_1` 至少补上 `Proteome Letters`；`year/pages` 不变；`keywords` 对 `2025_1` 保持 4 条，其他篇若原文无日文关键词则允许 0；issue 自检 15/15。

#### T-20261112-WB-AUTHOR-CLEAN（P1，WorkBuddy）

- **目标**：清洗作者分隔符与上标残留。
- **范围**：仅 `metapy/front.py`。
- **验收**：`2025_1` 作者 5 人，无前导“・”，无 `\dagger`；`40_10569` 12 人、`43_10814` 7 人、`42_93` 3 人不变；front 自检通过。

#### T-20261112-WB-FREFS-JA（P2，WorkBuddy，待确认）

- **目标**：明确日文语料是否需要 frefs；需要则复核 `42_93` 页脚误报，不需要则在文档中标注“不适用”。
- **依赖**：用户确认。未确认前不投入开发。

#### T-20261112-DS-NORM-SPEC / DS-TRANS-SPEC（P2，用户 + DeepSeek）

- **目标**：把“规范化/术语”“翻译”从口号变成可验收规格。
- **需用户先给**：作用字段、目标形式、术语表来源、翻译目标语言/模型/输出位置/质量门槛。
- **产出**：规格文档 + 1 篇样例，不写实现。

#### T-20261112-DS-OUT-REGEN（P2，DeepSeek）

- **目标**：在 P0/P1 稳定且用户同意后，生成新预览。
- **前置**：用户明确解冻；`2025_1` 补 `metadata.json`；新 preview manifest + 回滚点；旧预览保留。
- **验收**：新 `out_manifest_sha256` 可复算；旧预览快照仍可恢复；查看器抽检 3 篇。

### 3.3 串并行安排

| 阶段 | WorkBuddy | Trae | DeepSeek |
| --- | --- | --- | --- |
| 第 1 周 | `WB-REFS-JA`（串行，主线） | `TRAE-LAYOUT-FULL`（并行，只读 metapy + viewer） | 评审 refs；准备 gold schema；监控 out 哈希 |
| 第 1 周末 | `WB-ABS-EN-JA`（小任务，紧接 refs） | 交回归报告 | 合并 refs；跑 12 测试；更新 board |
| 第 2 周 | `WB-CSPAN-JA`（依赖 refs）→ `WB-ISSUE-JA` | 复核 cspan/refs 在查看器中的显示（等 refs 合并） | 合并 cspan；gold 样例；评审 issue |
| 第 2 周末 | `WB-AUTHOR-CLEAN`（小任务） | 截图/视觉验收 | 全量回归；决定是否解冻 |
| 第 3 周 | 按用户确认做 frefs/规范化 | 新预览的查看器验收 | 新预览生成（若解冻） |

> WorkBuddy 的任务按工具串行：同一时间只做一个，避免 worktree 内多任务交叉。Trae 只有在其改动文件与 WorkBuddy 不重叠时可并行；本轮 Trae 只读 `metapy`、写 `viewer.py`/临时报告，满足并行条件。

---

## 4. 分工建议：WorkBuddy vs Trae

| 工具 | 适合的任务 | 理由 | 不适合 |
| --- | --- | --- | --- |
| **WorkBuddy** | `metapy/refs.py`、`cspan.py`、`abs.py`、`front.py`、`issue.py`、`common.py`、`regress.py`、`audit_accuracy.py` 的解析/正则/字段逻辑 | 这些文件在所有权矩阵里归 WorkBuddy；它已完成 WB-ABS、WB-META2、WB-EN-ABS、WB-LAYOUTFIX，熟悉日文正则与临时副本验证流程；解析类任务需要反复跑单篇 stage，WorkBuddy 的串行模式合适 | 查看器视觉/截图（Trae owner）；`merge_out.py`/`test_pipeline.py`（DeepSeek owner）；跨文件合并 |
| **Trae CN** | `viewer.py` 展示层、layout overlay、截图与浏览器验收、全量回归报告 | `viewer.py` 归 Trae；T-VIEWER/T-LAYOUT 已证明它能做浏览器实测、截图、CSS/JS 契约检查；回归任务只读 `metapy`，不改抽取逻辑，风险低 | refs/cspan 字段解析（不是它的 owner，且需要大量 Python 正则迭代）；`unify/m3` 冻结文件 |
| **DeepSeek（本会话）** | 集成、评审、`merge_out.py`、`test_pipeline.py`、`coordination/**`、`docs/**`、金标准 schema、最终合并 | Integrator 角色；负责 `merge_check`、tag、merge record、out 哈希；`merge_out` 与 `test_pipeline` 是 DeepSeek owner；跨 owner 的共享排序逻辑由我收敛 | 不应替 WorkBuddy 改 `metapy` 抽取逻辑（会破坏 owner 边界）；不应在没有用户同意时解冻 `out/` |

**为什么 refs 给 WorkBuddy 而不是 Trae：** refs 是“正则 + 字段角色 + 语料抽样”的深水区，需要反复读 unified 块、跑 `metapy.refs` 自检、对比 `references[]` 字段；WorkBuddy 的既有 handoff 显示它按“before/after 表 + 临时副本 + 自检”工作，适合这类任务。Trae 的优势在浏览器/DOM/截图，不在 Python 著录语法。

**为什么全量 layout 回归给 Trae 而不是 WorkBuddy：** 这是“验证”而不是“实现”；Trae 已有 T-LAYOUT 的 IoU 映射脚本与截图流程，且 `viewer.py` 归它；WorkBuddy 应把时间放在 refs/cspan 的抽取逻辑上。若回归发现 `layout_ja` 真实反转，再由 WorkBuddy 修 `layout_ja.py`，DeepSeek 修 `merge_out.py`（若需要）。

---

## 5. 可直接复制的下一步提示词

### 5.1 给 WorkBuddy（P0：日文参考文献抽取）

```text
你是 WorkBuddy，本项目的日文元数据抽取实现者。请严格按以下提示执行，不要扩大范围。

【仓库与环境】
- 主仓库：D:\处理工具\2\multidoc-ocr-compare-main
- 你的工作树：D:\处理工具\2\multidoc-ocr-compare-main\.worktrees\workbuddy
- 你的分支：agent/workbuddy/main（当前应在 75a3da1；开工前 git fetch + rebase main）
- Git 不在 PATH：用 D:\workbuddy\resources\vendor\PortableGit\cmd\git.exe，或 coordination\git.cmd
- Python 用 py，不要用 python（本机 python 是 WindowsApps 空壳）
- 控制台中文/日文输出可能乱码：先 $env:PYTHONIOENCODING='utf-8'
- 协作环境变量：
  $env:COORD_ROOT='D:\处理工具\2\multidoc-ocr-compare-main\coordination'
  $env:REPO_ROOT='D:\处理工具\2\multidoc-ocr-compare-main\.worktrees\workbuddy'

【必读】
1. AGENTS.md
2. coordination/README.md
3. docs/RULES.md
4. docs/JA_IMPROVEMENT_PLAN_2026-11-12.md（本报告）
5. coordination/tasks/T-20261112-WB-EN-ABS/handoff.md（了解上一轮风格）
6. docs/JA_GOLD_2026-11-12.md 与 eval/ja_gold.json（2025_1/40_10569/52_230725 的 refs GT）
7. metapy/refs.py、metapy/common.py、regress.py 的相关函数

【背景】
- 正式 out/ 处于 A 方案冻结：禁止对 out/ 运行 metadata.py/pipeline.py/webapp.py 的写操作。
- 所有验证必须在临时副本：out_llm_trial/wb_refs_ja_eval/<doc>。
- 当前 11 篇日文文献中，2025_1 的参考文献抽 0 条；52_230725 的 7 行文献只切出 3 条；40_10569 的日文条目字段串位；lang 把日文标成 ko。
- 这不是“再加一个正则”就能解决，必须同时处理：文献区识别、条目切分、字段解析、语言标注。

【任务】
T-20261112-WB-REFS-JA：日文参考文献抽取修复。

【已确认的证据（请先复现）】
1. 2025_1：
   - out/2025_1/merged.md 第 405 行附近有“##  文献”；
   - out/2025_1/unified/page_15.json（物理第 16 页）的 Section-header u15_7 文本是“文 献”（字间空格）；
   - 该页 in_ref=false；py metadata.py 2025_1 --stage refs 输出“无文献区”；
   - 文献区实际从该页延续到文末，条目为“著者, 年, 「題名」, 出版社”与“著者(年): 題名. 誌名, 巻, 頁”混合。
2. 52_230725：
   - out/52_230725/unified/page_6.json 的 Text u6_6 有 7 行、7 条文献；
   - 当前只产出 3 条，且第 1 条 title 以“: Experimentelle...”开头，作者/题名错位。
3. 40_10569：
   - out/40_10569/metadata.json 的 references[0]：authors 含“1) 小林祥泰監修: 脳卒中データバンク 2009. 東京”，title=“中山書店”，lang=ko。
4. metapy/refs.py:657 的 lang 只有 ko/en 二分类；metapy/common.py:418 已有 JP_REF_HEAD，但没有被 refs/unify 使用；regress.py:14 的 REF_HEAD 不匹配“文 献”。

【允许修改的文件（仅这些）】
- metapy/refs.py
- metapy/common.py
- regress.py
禁止修改：unify.py、metapy/m3.py、viewer.py、test_pipeline.py、webapp.py、pipeline.py、out/**、out_llm_trial/previews/**、channels.local.json。
如果发现必须改 unify.py 才能修，停下来在 board 标 blocked，不要动手。

【实现要求】
A. 文献区回退（不改 unify 语义）
   - refs_doc 在 pdata 没有任何 in_ref 页面时，本地扫描 unified 页：
     找 Section-header/Page-header/Text 首行匹配“文\s*献”“引\s*用\s*文\s*献”“参\s*考\s*文\s*献”“References”的最后一页；
     从该页到文末作为 ref_pages；已有 in_ref 的文档保持原逻辑，不要改变其页集合。
   - 注意：不要修改 unified/page_*.json 的 in_ref 字段；只在 refs.py 内部使用局部 ref_pages。
B. 条目切分
   - 文献区内，若一个 Text 块含多行，且每行满足“含 19xx/20xx 年份 + 行末有句点/页码/出版社”之一，按行切；
   - 保留现有空行/编号切分作为优先路径；不要破坏英文/韩文条目。
C. 字段解析
   - 新增日文著录分支，至少覆盖：
     1) 著者, 年, 「題名」, 出版社/誌名, 巻, 頁
     2) 著者(年): 題名. 誌名, 巻, 頁
     3) 著者（年）「題名」...
   - 作者只取年份前的主段；题名/出处/出版社按标点角色回填；不要把“著者: 題名”里的冒号后内容留在 authors。
D. 语言
   - lang：含假名 → ja；纯拉丁 → en；否则保持 ko（或按现有规则）。
E. 兼容
   - 不得改变 42_185(18 条)、52_230302(42 条)、5_55(33 条) 的英文条目字段；不得改变 42_93(49 条) 的条目数。

【开工流程】
1. git status 必须干净；git fetch + git rebase main。
2. 领取任务：
   py coordination/claim.py create T-20261112-WB-REFS-JA --owner workbuddy --title "日文参考文献抽取修复" --files metapy/refs.py,metapy/common.py,regress.py
   py coordination/claim.py set-status T-20261112-WB-REFS-JA --owner workbuddy --status in_progress
3. 对每个文件加锁 + guard：
   py coordination/lock.py acquire metapy/refs.py --owner workbuddy --task T-20261112-WB-REFS-JA --ttl 1800
   py coordination/guard.py record metapy/refs.py --owner workbuddy
   （common.py、regress.py 同样）
4. 复制临时副本（只复制 json，不复制 jpg/html）：
   robocopy out\2025_1 out_llm_trial\wb_refs_ja_eval\2025_1 /S /XF *.jpg *.png *.html /NFL /NDL /NJH /NJS /NP
   robocopy out\52_230725 out_llm_trial\wb_refs_ja_eval\52_230725 /S /XF *.jpg *.png *.html /NFL /NDL /NJH /NJS /NP
   robocopy out\40_10569 out_llm_trial\wb_refs_ja_eval\40_10569 /S /XF *.jpg *.png *.html /NFL /NDL /NJH /NJS /NP
5. 在临时副本上跑：
   py metadata.py 2025_1 --out out_llm_trial/wb_refs_ja_eval --stage refs
   py metadata.py 52_230725 --out out_llm_trial/wb_refs_ja_eval --stage refs
   py metadata.py 40_10569 --out out_llm_trial/wb_refs_ja_eval --stage refs
6. 实现、反复验证、跑测试：
   py -m metapy.refs
   py -m unittest -v test_pipeline.py
   py -m compileall -q metapy/refs.py metapy/common.py regress.py
   py -c "import ner_lite; assert ner_lite.selfcheck()==0"
   py eval/gold_eval.py --pred out_llm_trial/wb_refs_ja_eval --doc 2025_1
   py eval/gold_eval.py --pred out_llm_trial/wb_refs_ja_eval --doc 52_230725
7. 确认正式 out/ 未变：用 Python 重算 out_manifest_sha256，仍为 09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091。
8. 提交（一个 commit）：
   fix(metapy): Japanese reference extraction (heading/split/fields/lang)

   Task: T-20261112-WB-REFS-JA
   Tool: workbuddy
   Base: <base_sha>
   Tests: refs selftest OK; unittest 12/12; ner_lite OK
9. 写 coordination/tasks/T-20261112-WB-REFS-JA/handoff.md，必须含：
   - 改动文件与关键函数；
   - before/after 表：2025_1 条数、52_230725 条数、40_10569 抽样 5 条字段；
   - 测试命令与结果；
   - 正式 out/ 哈希前后；
   - 已知残余/下一步。
10. task 置 review（handoff_to: deepseek），释放锁，更新 board。

【验收标准（必须逐条回答）】
- [ ] 2025_1 参考文献 recall=1.0（GT 34 唯一 / 35 含重复）；title/author 达到 GT 阈值；`py eval/gold_eval.py --pred <tmp> --doc 2025_1` 复算。
- [ ] 52_230725 7 行 → 7 条；title 不以“:”开头；作者/题名不再互换。
- [ ] 40_10569 抽 5 条：作者、题名、出处、年、卷页不串位。
- [ ] 日文条目 lang=ja 占比 ≥90%；42_185/52_230302/5_55 的英文条目字段不变。
- [ ] 42_93 条目数仍为 49；不得为了修日文把英文/韩文条目改坏。
- [ ] refs 自检、12/12 unittest、ner_lite selfcheck、compileall 全过。
- [ ] 正式 out/ 哈希仍 09a8820b…；没有写 out/。
- [ ] handoff 有 before/after 和哈希证据。

【报告格式】
完成后第一段写结论（PASS/FAIL + 关键数字），第二段写改动，第三段写测试，第四段写残余与建议。不要贴大段代码。
```

### 5.2 给 Trae CN（P1：11 篇全量 layout/viewer 回归）

```text
你是 Trae CN，本项目的查看器 owner 与视觉验证者。请严格按以下提示执行，本轮以“验证”为主，不要改抽取逻辑。

【仓库与环境】
- 主仓库：D:\处理工具\2\multidoc-ocr-compare-main
- 你的工作树：D:\处理工具\2\multidoc-ocr-compare-main\.worktrees\trae
- 你的分支：agent/trae/main（当前应在 75a3da1；开工前 git fetch + rebase main）
- Git 不在 PATH：用 D:\workbuddy\resources\vendor\PortableGit\cmd\git.exe，或 coordination\git.cmd
- Python 用 py，不要用 python
- 先 $env:PYTHONIOENCODING='utf-8'
- 协作环境变量：
  $env:COORD_ROOT='D:\处理工具\2\multidoc-ocr-compare-main\coordination'
  $env:REPO_ROOT='D:\处理工具\2\multidoc-ocr-compare-main\.worktrees\trae'

【必读】
1. AGENTS.md
2. coordination/README.md
3. coordination/tasks/T-20261112-TRAE-LAYOUT/handoff.md（上一轮 IoU 映射与截图方法）
4. coordination/tasks/T-20261112-WB-LAYOUTFIX/handoff.md（layout_ja 对齐 merge_out 的口径）
5. docs/JA_IMPROVEMENT_PLAN_2026-11-12.md（本报告 §2.3、§3.2）
6. metapy/layout_ja.py、merge_out.py、viewer.py 的相关函数

【背景】
- 正式 out/ 处于 A 方案冻结：禁止对 out/ 运行 metadata.py/pipeline.py/webapp.py 的写操作。
- 上一轮 T-20261112-TRAE-LAYOUT 只验证了 40_10569（7 页）与 52_230725（7 页），共 14 页；其中双栏页 7 个。
- 全语料实际是 11 篇、99 页、39 个双栏页。本轮要把验证扩到全量，并解释单栏页上与 merge_out 的顺序差异。
- 已知：layout_ja 吃 unified 共识块，merge_out 吃 mineru 单渠道块；块集合不同，单栏页可能出现“同一页两种顺序”。不要直接把所有差异当 bug，要逐页判定。

【任务】
T-20261112-TRAE-LAYOUT-FULL：11 篇 99 页 layout/viewer 全量回归。

【输入】
- out/<doc>/unified/page_*.json（含 layout.reading_order/col/zone/detected/boundary）
- out/<doc>/unified/_layout_ja.json
- out/<doc>/merged/page_*.json（mineru 渠道块）
- 文档：2025_1, 40_10569, 40_10588, 42_103, 42_185, 42_93, 43_10814, 52_230302, 52_230725, 5_55, 9_1
- 注意：2025_1 没有 metadata.json，只有 merged/unified/viewer；不要因此跳过它。

【允许做的事】
- 只读 metapy/**、merge_out.py；
- 写 out_llm_trial/trae_layout_full/**（脚本、CSV、report.md、截图；该目录 Git 忽略）；
- 如发现 viewer.py 渲染缺陷，可改 viewer.py（这是你的 owner 文件），但必须单独提交、说明理由；
- 禁止改 metapy/**、merge_out.py、unify.py、m3.py、test_pipeline.py、webapp.py、out/**。

【实现要求】
A. 逐页比对
   - 对每篇每页：取 merged/page_N.json 的 mineru 渠道块 → merge_out.order_blocks(blocks, W) → 按 IoU≥0.5 映射到 unified 块 → 取 layout.reading_order；
   - 统计：matched 块数、相邻逆序对数（inversions）、detected（single/double）、列序；
   - 输出 CSV：doc,page,detected,matched,inversions,columns,note。
B. 差异判定
   - 双栏页：必须 0 反转；若不为 0，给出具体 uid/顺序，标“真实反转”；
   - 单栏页：若 inversions>0，逐页判定为“IoU 映射误差 / 块集合差异（unified vs mineru）/ 真实反转”，并给出证据（uid、box、文本片段）；
   - 不允许只给汇总数字；每页都要有结论。
C. 查看器视觉
   - 用临时副本重建 6 页查看器（不要写正式 out/）：
     2025_1 p1、2025_1 p3、40_10569 p1、42_103 p5、52_230725 p1、52_230725 p3
   - 检查：双栏边界线、左/右栏标签、阅读序序号、front/body 分区是否与原图一致；
   - 截图存 out_llm_trial/trae_layout_full/shots/，确保可读（不要只截 1px 区域）。
D. 回归
   - py -m unittest -q test_pipeline.py → 12/12
   - py -c "import ner_lite; assert ner_lite.selfcheck()==0"
   - py -m compileall -q viewer.py（若改）
   - 正式 out/ 全量哈希仍 09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091

【开工流程】
1. git status 干净；git fetch + rebase main。
2. 领任务：
   py coordination/claim.py create T-20261112-TRAE-LAYOUT-FULL --owner trae --title "11篇layout/viewer全量回归" --files viewer.py
   py coordination/claim.py set-status T-20261112-TRAE-LAYOUT-FULL --owner trae --status in_progress
3. 若改 viewer.py：加锁 + guard（同 T-VIEWER 流程）。
4. 产出报告与截图；若 viewer.py 有改动，提交：
   fix(viewer): <具体缺陷>

   Task: T-20261112-TRAE-LAYOUT-FULL
   Tool: trae
   Tests: unittest 12/12; compileall OK
5. 写 coordination/tasks/T-20261112-TRAE-LAYOUT-FULL/handoff.md，含：
   - 99 页汇总表（按文档分组）；
   - 双栏 39 页反转表；
   - 单栏差异逐页判定；
   - 截图清单与浏览器实测结论；
   - 测试与 out 哈希；
   - 发现的真实缺陷/建议。
6. task 置 review（handoff_to: deepseek），释放锁（若加锁）。

【验收标准（必须逐条回答）】
- [ ] 11 篇 99 页全部有 CSV 行，无跳页。
- [ ] 39 个双栏页反转数全为 0；若有，逐页给出 uid/顺序。
- [ ] 单栏页差异逐页判定，不允许“可能是映射误差”这种无证据结论。
- [ ] 6 张截图存在、可读，且能看到双栏线/栏标签/阅读序序号。
- [ ] 12/12 测试通过；viewer.py 若改，compileall 通过。
- [ ] 正式 out/ 哈希仍 09a8820b…；没有写 out/。
- [ ] handoff 里有“哪些页需要 WorkBuddy 修 layout_ja、哪些需要 DeepSeek 修 merge_out”的明确清单。

【报告格式】
第一段结论（PASS/FAIL + 双栏页反转数 + 单栏差异页数），第二段 99 页汇总，第三段双栏表，第四段单栏差异判定，第五段截图与测试，第六段建议。不要贴大段代码。
```

---

## 6. 已确认决策与仍需补充

### 6.1 已确认（2026-11-12，用户）

| # | 决策 | 对计划的影响 |
| --- | --- | --- |
| 1 | **GT 由 DeepSeek 自建**；摘要给**全文**；refs 必含 title/author/year/journal/venue/vol/issue/page/doi | 已交付 `eval/ja_gold.json`（11 篇字段/摘要 + 3 篇 61 条 refs） |
| 2 | **2025_1 实际条数为准**；≥40 视为正常但**不强行截断**；**Recall=1.0（宁多勿漏）**；**title/author 必须准确**；其他字段允许噪声 | 实际 GT 35 条（34 唯一，1 条原文重复），recall 分母 34；验收改为 GT recall，不再用“≥40 条” |
| 3 | refs 必须支持日文“参考文献/引用文献”区块；**脚注引文不做结构化解析**，纯文本保留，标记 skip | frefs 任务降为 P2/不开发；`skipped.footnote_refs="skip"` 写入 GT |
| 4 | normalizer：**NFKC + 新旧字体统一 + 送假名标准化**；作用 **title/author/abstract/body/refs**；**DOI/KAKENHI/术语表强保护**；保留 **raw_text ↔ normalized_text 双向映射** | P2 规格已定；实现时必须有白名单与映射表 |
| 5 | 翻译：**title/abstract/keywords → 中文**；只写 `out_llm_trial/`；**初期不设硬门槛**，人工抽检 | P2 规格已定；不动正式 `out/` |
| 6 | **正式 out/ 继续冻结**；新预览放 **`out_preview/`** | 交付/验收仍用 `out/` 旧预览；新预览另开目录 |
| 7 | 优先级：**refs > cspan/layout > 金标准** | 金标准配置已提前完成，用于验收；不占关键路径 |
| 8 | **2025_1 是正式语料**，不剔除；按“第 12 篇”计覆盖率 | 但工作区实际只有 11 篇，见 §6.2 |

### 6.2 仍需你补充 / 确认

1. **第 12 篇文件缺失（阻塞覆盖率口径）**
   - `uploads/`、`out/`、备份目录都只有 11 个 PDF；没有找到第 12 篇。
   - 当前 GT：`corpus.expected_docs=12`、`present_docs=11`；请提供缺失 PDF，或确认“按 11 篇计、2025_1 为第 11 篇”。
2. **2025_1 实际 35 条 vs 你估计的 ≥40**
   - 我逐页对照 PDF 第 16-17 页，确认 35 条（含 1 条原文重复 #22）；如果你手上有 40 条的清单，请指出我漏了哪几页/哪几条。
3. **refs GT 是否扩到 8 篇**
   - 当前只对 `2025_1`/`40_10569`/`52_230725` 建了 refs GT；其余 8 篇 `pending`。
   - 是否现在扩到 11 篇（工作量大），还是等 WorkBuddy refs 合并后再补？
4. **重复条目口径**
   - `2025_1` #22 与 #6 是原文重复；当前 recall 分母 34。是否要求解析器输出 35 条（含重复）才算 1.0？
5. **title/author 相似度阈值**
   - 当前工程阈值：title ≥0.90、author token ≥0.60、匹配主键 title ≥0.82。是否接受？还是要逐字精确/允许异体字？
6. **normalizer 的“新旧字体”与“送假名”具体表**
   - 需要你提供或确认：旧字体→新字体映射表、送假名统一规则（例如「行なう→行う」）、术语表来源（`ner_glossary.json` 还是单独文件）。
7. **翻译模型/接口**
   - 用哪个模型（DeepSeek/其他）、是否走 `channels.json` 的 LLM 配置、输出 JSON 结构（逐字段还是整篇）。
8. **`out_preview/` 的命名与保留策略**
   - 新预览是否按时间戳（`out_preview/2026-11-12T.../`）？保留几份？是否需要 manifest 与回滚脚本？

---

## 附录 A：当前语料快照（临时副本，当前代码）

> 口径：`out_llm_trial/ja_status_1112/<doc>`，依次跑 `m3 → refs → frefs → front → abs → cspan → issue → layout_ja → entity`；未写正式 `out/`。

| 文档 | 页 | 日文摘要 | 英文摘要 | 作者 | 参考文献 | 引文句 | 双栏页 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `2025_1` | 17 | 0（原文无要旨） | 1446（含 11 假名） | 5（2 个带“・”） | 0 | 0 | 8 |
| `40_10569` | 7 | 366 | 995 | 12 | 19 | 44 | 4 |
| `40_10588` | 6 | 397 | 1339 | 10 | 20 | 42 | 3 |
| `42_103` | 13 | 251 | 1062 | 1 | 19 | 15 | 6 |
| `42_185` | 7 | 232 | 1083 | 1 | 18 | 25 | 3 |
| `42_93` | 10 | 469 | 1257 | 3 | 49 | 59 | 2 |
| `43_10814` | 5 | 399 | 1140 | 7 | 8 | 31 | 2 |
| `52_230302` | 7 | 0（英文摘要） | 1216 | 2 | 42 | 38 | 3 |
| `52_230725` | 7 | 0（英文摘要） | 721 | 1 | 3 | 7 | 3 |
| `5_55` | 9 | 386 | 783 | 3 | 33 | 30 | 3 |
| `9_1` | 11 | 434 | 1279 | 6 | 22 | 41 | 2 |
| **合计** | **99** | **8/11 有值** | **11/11 非空** | — | **233** | **332** | **39** |

补充：

- 参考文献 `title=null` 24 条；`lang=ko` 50 条（日文条目被误标），`lang=en` 183 条。
- 引文句：`exact` 312、`partial` 5、`unlinked` 15。
- `journal` 8/11；`year` 11/11；`pages` 11/11；`volume` 11/11；`issue` 6/11；`keywords` 4 条（仅 `2025_1`）。
- 正式 `out/` 有 `metadata.json` 的是 10 篇；`2025_1` 没有。

## 附录 B：复现方式与哈希

```powershell
# 1) 复制（只复制 json，避免 176MB 图片）
robocopy out\2025_1 out_llm_trial\ja_status_1112\2025_1 /S /XF *.jpg *.png *.html /NFL /NDL /NJH /NJS /NP

# 2) 依次跑 stage（示例）
$env:PYTHONIOENCODING='utf-8'
py metadata.py 2025_1 --out out_llm_trial\ja_status_1112 --stage m3
py metadata.py 2025_1 --out out_llm_trial\ja_status_1112 --stage refs
py metadata.py 2025_1 --out out_llm_trial\ja_status_1112 --stage frefs
py metadata.py 2025_1 --out out_llm_trial\ja_status_1112 --stage front
py metadata.py 2025_1 --out out_llm_trial\ja_status_1112 --stage abs
py metadata.py 2025_1 --out out_llm_trial\ja_status_1112 --stage cspan
py metadata.py 2025_1 --out out_llm_trial\ja_status_1112 --stage issue
py metadata.py 2025_1 --out out_llm_trial\ja_status_1112 --stage layout_ja
py metadata.py 2025_1 --out out_llm_trial\ja_status_1112 --stage entity
```

正式 `out/` 全量哈希（Python，按 `path|bytes|sha256` 小写排序）：

```python
import hashlib, os
root = "out"; lines = []
for dp, dn, fn in os.walk(root):
    for f in fn:
        p = os.path.join(dp, f); rel = os.path.relpath(p, ".").replace(os.sep, "/")
        b = open(p, "rb").read()
        lines.append("%s|%d|%s" % (rel, len(b), hashlib.sha256(b).hexdigest()))
lines.sort(key=lambda s: s.split("|")[0].lower())
print(len(lines), hashlib.sha256("\n".join(lines).encode()).hexdigest())
# 期望：1151 09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091
```

## 附录 C：完成度口径

- 每项的“完成度”= 已通过验收的子项 / 当前定义的子项；子项定义见 §1.2 与 §3.2 验收清单。
- 没有金标准的项，不给“准确率”；只给“工程完成度”。
- 等权总体 = 15 项算术平均，仅用于横向比较，不用于对外承诺。
- 正式 `out/` 的哈希是本报告所有“未写 out”结论的唯一硬证据；任何任务结束都应重算一次。
