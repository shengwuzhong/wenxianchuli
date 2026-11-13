# Handoff — T-20261113-WB-ISSUE-JA（日文 issue 刊名/关键词）

- 分支：`agent/workbuddy/T-20261113-WB-ISSUE-JA`（基线 main `51af5f9`）
- 改动：仅 `metapy/issue.py`（+约 90 行）；未碰 refs/cspan/entity/layout/viewer/merge_out/unify/m3/test_pipeline/out/**
- 路线：正则 + 小词典（DOI 前缀表），无 LLM、无 doc/page 硬编码

## 实现要点

1. 日文页眉「刊名 N号」：`_BOUNDARY` 增裸 `N号` 边界，新增 `_JP_GO` → volume（「活断層研究 63号 1~17 2025」→ 活断層研究 / 63 / 2025 / 1-17）。
2. 同号去重：英文页眉「No. 63」会与 `63号` 撞号，若 period 值==volume 且支持页少于 volume 支持页 → 期置 null，audit 记 `issue_dropped_same_as_volume`（2025_1 期=null 而非 63）。
3. J-STAGE 型 DOI：`_DOI_VIP = \.(\d{1,3})\.(\d{1,3})_(\d{1,4})` → 卷/期（`jpros.5.2_55` → 5/2；`jpros.9.1_1` → 9/1）。
4. DOI 前缀→刊名小表 `_DOI_JOURNAL = {"10.14889": "Proteome Letters"}`：页眉只有拉丁刊名时 journal 取 DOI 前缀（confidence.source=`doi`），journal_en 仍走页眉。
5. 缺 `metadata.json` 不再整篇跳过：front/abs 未跑的篇目（2025_1）仍落 issue 字段，不写空 title/authors。
6. 关键词：沿用 `KW_LINE`（已含 キーワード），补验证「头词独占一行 + 次行 4 词条（，分隔）」形态；`キーワード` 无 ASCII → keywords[]，英文 `Key words` 只进 keywords_en，不反推日文。

## 11 篇 journal（after）

| doc | journal | journal_en | year | vol | issue | pages |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 2025_1 | 活断層研究 | Active Fault Research | 2025 | 63 | – | 1-17 |
| 40_10569 | 脳卒中 | – | 2018 | 40 | – | 343-349 |
| 40_10588 | 脳卒中 | – | 2018 | 40 | – | 382-387 |
| 42_103 | 診断病理 | – | 2025 | 42 | 2 | 103-115 |
| 42_185 | 診断病理 | – | 2025 | 42 | 3 | 185-191 |
| 42_93 | 診断病理 | – | 2025 | 42 | 2 | 93-102 |
| 43_10814 | 脳卒中 | – | 2021 | 43 | – | 201-205 |
| 52_230302 | 岩石鉱物科学 | – | 2023 | 52 | – | 1-7 |
| 52_230725 | 岩石鉱物科学 | – | 2023 | 52 | – | 1-7 |
| 5_55 | Proteome Letters（DOI） | Proteome Letters | 2020 | 5 | 2 | 55-63 |
| 9_1 | Proteome Letters（DOI） | Proteome Letters | 2024 | 9 | 1 | 1-11 |

journal 11/11；journal_en 11/11。

## before → after（三篇）

| doc | journal | year | vol | issue | pages | keywords |
| --- | --- | --- | --- | --- | --- | --- |
| 2025_1 | 无（整篇跳过）→ 活断層研究 | – → 2025 | – → 63 | – → – | – → 1-17 | 0 → **4** |
| 5_55 | None → Proteome Letters | 2020 | 5 | None → **2** | 55-63 | 0（英 4） |
| 9_1 | None → Proteome Letters | 2024 | 9 | None → **1** | 1-11 | 0（英 4） |

其余 8 篇 year/volume/issue/pages 逐字段比对无变化（脚本核对）。

## 关键词

- 2025_1：`['奈良盆地東縁断層帯','地中レーダ','スタッキング処理','群列ボーリング掘削調査']`，keywords_en=0（原文英文行无头词，不反推）。
- 其余篇 keywords 均 0（原文只有英文 Key words 板），keywords_en 数量不变。

## 测试 / 回归

- `py -m metapy.issue` → **25/25 PASS**（原 21 例 + 新增 4 例：活断層研究号型页眉、jpros.5.2_55、jpros.9.1_1、キーワード 独占行 4 词条 + 英文不反推）
- `py -m unittest test_pipeline.py` → 12/12 OK；`compileall metapy/issue.py` 通过
- 正式 `out/` 哈希不变：1151 文件 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`
- 复现：`out_llm_trial/wb_issue_ja/out_copy`（临时副本跑 11 篇 --stage issue）

## 残余（非阻塞）

- 2025_1 仍无 title/authors/refs（front/refs 未跑），本轮只补 issue 段；若上游补跑需重跑 issue 保持一致。
- `_DOI_JOURNAL` 目前仅一条前缀（10.14889）；后续遇新日文刊按表追加即可，不做通配猜测。
- `52_230302/52_230725` 期号原文无（页眉「岩石鉱物科学(2023) 52」），保持 null。
