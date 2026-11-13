# 日文金标准（Golden GT）配置说明

- 版本：2026-11-12
- 文件：`eval/ja_gold.json`
- 校验脚本：`eval/validate_gold.py`
- 比对脚本：`eval/gold_eval.py`
- 基线报告：`eval/reports/baseline_current.md` / `.json`

---

## 1. 范围与数量

| 项目 | 数量 | 说明 |
| --- | --- | --- |
| 语料文档 | **11 篇** | `uploads/` 与 `out/` 实际只有 11 个 PDF；用户口径的“第 12 篇”未找到，已在 GT 的 `corpus.missing_note` 标注 |
| 文档级字段 | 11/11 | title、title_en、authors、affiliations、journal、year、volume、issue、pages |
| 日文摘要全文 | 8/11 | 原文有日文要旨的 8 篇；另 3 篇原文无日文要旨（`2025_1`、`52_230302`、`52_230725`），GT 记为 `null` |
| 英文摘要 | 11/11 | 作为补充字段，便于检查“英文摘要混入日文” |
| 参考文献 GT | **61 条 / 3 篇** | `2025_1` 35 条、`40_10569` 19 条、`52_230725` 7 条 |
| 其余 8 篇 refs | pending | 暂未建 GT；`references_status="pending"`，不参与 refs recall 分母 |

> 2025_1 的 35 条中有 1 条是原文重复著录（#22 与 #6 同为“中田 高・今泉俊文編 2002”）。GT 保留两条并标 `duplicate_of=6`；比对脚本按标题去重，**recall 分母为 34**。如果验收要求“原始条目 35 条全中”，请把脚本的 `gt_refs_unique` 改成不去重。

---

## 2. 2025_1 的 GT 计数

- 原文参考文献区：PDF 第 16-17 页；标题为 `文 献`（字间空格），实际从第 16 页右栏顶部开始，延续到第 17 页左/右栏。
- GT 条目：**35 条**（含 1 条重复），去重后 **34 条**。
- 字段：`title`、`authors`、`year`、`journal`、`volume`、`issue`、`pages`、`doi` 全部有键；`title`/`authors`/`year`/`journal` 全部非空。
- 人工核对方式：逐条对照 `out/2025_1/pages/page_15.jpg`、`page_16.jpg` 图像与 `unified/page_15.json`、`page_16.json` 文本；#30 的 AGERS 续行已合并为一条。
- **注意**：用户原估“≥40 视为正常”，实际原文只有 35 条（34 唯一）。GT 按原文实际，不凑数、不截断。

### 验收断言（给 WorkBuddy 的 refs 任务）

1. `2025_1` 条目级 recall = **1.0**（34/34 唯一，或 35/35 含重复；以 GT 的 `gt_refs_unique` 口径为准）。
2. `title` 必须非空，且与 GT 的相似度 ≥0.90；允许 OCR 异体字（如 `涉/渉`）但不得是机构名/作者名/页码。
3. `authors` 必须非空，GT 作者段的 token 命中率 ≥0.60；不得把“著者: 題名”的冒号后内容留在 authors。
4. `year`、`journal`、`volume`、`issue`、`pages`、`doi` 允许噪声，但必须尽量回填；不设单独硬门槛，人工抽检兜底。
5. 宁多勿漏：允许 extra entries；extra 不扣 recall，但要在报告中列出。

---

## 3. 文件结构与字段

```json
{
  "schema_version": "1.0",
  "corpus": {"expected_docs": 12, "present_docs": 11, "missing_note": "..."},
  "verification": {"tier_a": ["2025_1", "40_10569", "52_230725"], "...": "..."},
  "docs": [
    {
      "doc": "2025_1",
      "source_pdf": "uploads/2025_1.pdf",
      "pages": 17,
      "title": "...",
      "title_en": "...",
      "authors": ["..."],
      "affiliations": ["..."],
      "journal": "活断層研究",
      "year": "2025",
      "volume": "63",
      "issue": null,
      "pages_range": "1-17",
      "abstract": null,
      "abstract_en": "...",
      "abstract_paragraphs": 1,
      "keywords": ["..."],
      "references": [
        {
          "num": 1,
          "venue_type": "book",
          "authors": "物理探査学会編",
          "title": "物理探査ハンドブック 増補改訂版",
          "year": "2016",
          "journal": "物理探査学会",
          "volume": null,
          "issue": null,
          "pages": "1045p",
          "doi": null,
          "raw": "物理探査学会編, 2016, 「物理探査ハンドブック 増補改訂版」, 物理探査学会, 1045p.",
          "source": {"page": 16, "uid": "u15_8"},
          "verified": true
        }
      ],
      "references_status": "verified",
      "skipped": {"footnote_refs": "skip (not in scope; keep as plain text)"}
    }
  ]
}
```

字段约定：

- `venue_type`：`journal` / `book` / `report` / `web` / `conference`。书籍/报告的 `journal` 存放出版社/机构（满足“journal/venue 必须包含”）。
- `source`：GT 条目的来源页与 unified uid，便于回查；不是比对字段。
- `raw`：原文行，保留全角/半角与 OCR 原样；normalizer 的 `raw_text ↔ normalized_text` 映射以它为起点。
- `verified`：本条 GT 已人工核对。
- `references_status`：`verified` / `pending`；pending 的文档不参与 refs recall。

---

## 4. 比对口径

`eval/gold_eval.py` 默认只读 `out/<doc>/metadata.json`，不写 `out/`。

| 字段 | 口径 |
| --- | --- |
| title / title_en / journal / year / volume / issue / pages | NFKC + 小写 + 去空白/标点后完全相等 |
| authors | GT 每个作者名在 pred 作者列表中模糊命中；输出 recall 与 pred 人数 |
| abstract / abstract_en | NFKC 折叠后的 `difflib.SequenceMatcher` 相似度；另报 pred 假名数 |
| references | 以 title 相似度 ≥0.82 为主键；title 不中时用 author+year 强匹配兜底；每条 pred 只能用一次 |
| refs recall | 匹配到的 GT 唯一条目 / GT 唯一条目 |
| refs title/author | 匹配条目中 title 相似度 ≥0.90 / 作者 token 命中 ≥0.60 的比例 |

注意：`abstract` 的 GT 是**原文全文**；如果 pred 只抽了首段/被截断，相似度会下降，但长度差也会暴露。

---

## 5. 基线（当前代码，2026-11-12）

预测目录：`out_llm_trial/ja_status_1112`（临时副本，当前 `main` 代码）。

| doc | title | authors | journal | year | vol | issue | pages | abstract | abstract_en | refs recall | refs title | refs author |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025_1 | OK | 1.0 / 5 | **X** | OK | **X** | **X** | OK | - | 0.981（含日文尾行） | **0.000** | 0.000 | 0.000 |
| 40_10569 | OK | 1.0 / 12 | OK | OK | OK | OK | OK | 1.000 | 1.000 | **0.263** | 0.000 | 0.263 |
| 40_10588 | OK | 1.0 / 10 | OK | OK | OK | OK | OK | 1.000 | 1.000 | - | - | - |
| 42_103 | OK | 1.0 / 1 | OK | OK | OK | OK | OK | 1.000 | 1.000 | - | - | - |
| 42_185 | OK | 1.0 / 1 | OK | OK | OK | OK | OK | 1.000 | 1.000 | - | - | - |
| 42_93 | OK | 1.0 / 3 | OK | OK | OK | OK | OK | 1.000 | 1.000 | - | - | - |
| 43_10814 | OK | 1.0 / 7 | OK | OK | OK | OK | OK | 1.000 | 1.000 | - | - | - |
| 52_230302 | OK | 1.0 / 2 | OK | OK | OK | OK | OK | - | 1.000 | - | - | - |
| 52_230725 | OK | 1.0 / 1 | OK | OK | OK | OK | OK | - | 1.000 | **0.429** | 0.143 | 0.429 |
| 5_55 | OK | 1.0 / 3 | **X** | OK | OK | **X** | OK | 1.000 | 1.000 | - | - | - |
| 9_1 | OK | 1.0 / 6 | **X** | OK | OK | **X** | OK | 1.000 | 1.000 | - | - | - |

基线结论：

- 文档级 title/作者/年/页已基本正确；`2025_1` 的 journal/volume 为空、issue 把“63号”误当 issue；`5_55`/`9_1` 缺 journal/issue。
- 摘要 8 篇 1.000；`2025_1` 的 `abstract_en` 0.981，原因是尾部混入 1 行日文（11 假名）。
- refs 是最大缺口：`2025_1` 0/34；`40_10569` 5/19（且 title 全错）；`52_230725` 3/7。
- 这些数字是“当前代码 vs 人工 GT”，不是模型自评。

### 5.1 WorkBuddy `T-20261112-WB-REFS-JA` 最终复测（`6b9d1f2` 已合并）

| doc | pred | GT 唯一 | recall | title_ok | author_ok | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `2025_1` | 35 | 34 | **1.000** | 0.912 | **1.000** | 通过（author 为空 0） |
| `40_10569` | 19 | 19 | 0.947 | 0.789 | 0.947 | 通过（#16 非阻塞） |
| `52_230725` | 7 | 7 | **1.000** | 0.857 | **1.000** | 通过 |

兼容计数：`42_185` 18、`42_93` 49、`5_55` 33、`52_230302` 43 不变。Review：`coordination/reviews/T-20261112-WB-REFS-JA.md`（round 3 approve）。

历史：首轮 `810de5a` 的 `2025_1` 为 21 条/recall 0.618；round 2 修到 35 条但 2 条 author 为空；round 3 修掉 #24/#25 后作者非空、#24 不再被 AGERS DOI 污染。

---

## 6. 使用方式

```powershell
# 校验 GT 结构
py eval/validate_gold.py

# 比对正式 out/（只有 10 篇有 metadata；2025_1 会显示 MISSING）
py eval/gold_eval.py

# 比对临时副本（当前代码）
py eval/gold_eval.py --pred out_llm_trial/ja_status_1112 `
    --json eval/reports/baseline_current.json `
    --md eval/reports/baseline_current.md

# 只比对一篇
py eval/gold_eval.py --pred out_llm_trial/ja_status_1112 --doc 2025_1
```

WorkBuddy 的 refs 任务应在临时副本上跑完后，用同一命令生成 `eval/reports/after_wb_refs.md`，并在 handoff 里贴出 `2025_1` 的 refs recall/title/author 三个数。

---

## 7. 已知限制 / 待补

1. **第 12 篇缺失**：`uploads/`、`out/`、备份目录都只有 11 个 PDF；未找到用户所说的第 12 篇。当前 GT 的 `corpus.expected_docs=12`、`present_docs=11`，请提供缺失文件或确认按 11 篇计。
2. **8 篇 refs 未建 GT**：`40_10588`、`42_103`、`42_185`、`42_93`、`43_10814`、`52_230302`、`5_55`、`9_1` 的 refs 仍是 `pending`；当前只覆盖 3 篇/61 条。
3. **摘要 GT 的来源**：8 篇日文摘要按原文全文转录；`2025_1`/`52_230302`/`52_230725` 只有英文摘要，GT 的 `abstract=null`。若你希望把英文摘要也算作 `abstract`，需要改 schema。
4. **书名/报告/网页的“journal”**：为满足“journal/venue 必须包含”，书籍/报告/网页把出版社/机构填进 `journal`；若你要单独的 `publisher`/`url` 字段，需扩展 schema。
5. **重复条目**：`2025_1` #22 与 #6 是原文重复；默认按标题去重，recall 分母 34。若验收要求 35 条全中，请说明。
6. **title/author 相似度阈值**：0.82/0.90/0.60 是工程阈值；若你要更严（逐字）或更松（异体字归一），需要你定。
7. **没有多段落摘要样本**：当前 11 篇的日文/英文摘要都是单段（8 篇日文 + 3 篇英文），`abstract_paragraphs=1`；用户要求“测试多段落抽取能力”，现有 GT 覆盖不到。需要补一篇多段摘要样本，或接受“按段拼接”的验收口径。
