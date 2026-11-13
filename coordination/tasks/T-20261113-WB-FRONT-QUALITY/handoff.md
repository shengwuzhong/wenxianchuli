# T-20261113-WB-FRONT-QUALITY handoff

分支 `agent/workbuddy/T-20261113-WB-FRONT-QUALITY`（基于 main f1f7f6f）
改动文件：`metapy/front.py`、`metapy/abs.py`（未触碰其他模块 / out/）

## A 作者清洗（front.py）

- `_jp_middot_to_sep`：日文中黒 `・`(U+30FB) 归一 —— 两侧同片假名判外来名中缀保留（`ジョン・スミス`），
  否则折成 `·` 与既有分隔符同级。根因：2025_1 作者行 `川嶋渉造^{*1\dagger} ・木村治夫…` 的中黒不在
  原分隔字符类里，切分后残留在名首。
- `_clean_author_name`：去首尾 `・`/`·`/`•`/逗号、LaTeX 匕首（`\dagger`/`\ddagger`）、`†`/`‡`、多余空白；
  不改姓名内部单一空格（`谷口 薫`）。
- `_clean_marker` + 就地 `mk[:]` 清洗：`*1\dagger` → `*1`（重建列表会丢后置占位符 marker，已用就地赋值）。
- 页眉 running-head 兜底作者同样过清洗。

### 2025_1 作者 before → after（同一 doc，临时副本）

| # | before | after |
|---|---|---|
| 1 | `川嶋涉造` / `*1\dagger` | `川嶋涉造` / `*1` |
| 2 | `・木村治夫` / `*2` | `木村治夫` / `*2` |
| 3 | `・谷口 薫` / `*3` | `谷口 薫` / `*3` |
| 4 | `中西利典` / `*4` | `中西利典` / `*4` |
| 5 | `堤 浩之` / `*5` | `堤 浩之` / `*5` |

作者数 5 → 5（未合并、未丢人）。

### 11 篇作者数（base → after，全部不变）

2025_1 5→5、40_10569 12、40_10588 10、42_103 1、42_185 1、42_93 3、43_10814 7、
52_230302 2、52_230725 1、5_55 3、9_1 6；合计 51 → 51。

## B abstract_en 日文残留（abs.py）

- 根因：2025_1 英文摘要块下方紧跟日文栏内续行 `して東側が相対的に隆起する…`，`_collect_abstract`
  只对「无 Abstract 头」路径设了日文终止，头路径无。
- `_collect_abstract(stop_on_ja=True)`：英摘要路径逐行遇日文（≥2 假名或日文比例>0.08）即止。
- `_en_language_guard`：成品兜底闸门，对 `abstract_en` 任何路径（头/无头/尾页 matter）逐行截断日文行，
  正常英文摘要（无假名）不触发。

| doc | abstract_en 假名数 before → after |
|---|---|
| 2025_1 | 11 → **0**（1446 → 1396 字符，仅删日文行，结尾为完整英文句） |
| 其余 10 篇 | 0 → 0（长度逐篇不变） |

## 回归

- `py -m metapy.front`：10/10 PASS（新增 3 例：2025_1 真实作者行、外来名中缀、名尾匕首）
- `py -m metapy.abs`：6/6 PASS（新增 3 例：stop_on_ja 截断、闸门截断、正常英摘要不截断）
- `py -m unittest test_pipeline.py`：Ran 12 tests OK
- `py -m compileall metapy/front.py metapy/abs.py`：通过
- 10 篇非目标文与 main 版基线逐字段一致（title / title_en / authors / abstract / abstract_en / affiliations 全等）
- `out/` 1151 文件哈希 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091` 不变

## 残余

- 2025_1 作者 affiliation 仍为空：脚注键为 `1)`、marker 为 `*1`，旧配对逻辑按字符串全等比较不命中
  （main 基线同样为空，非本次引入；修它需改 marker→机构配对语义，超出本任务「只清洗」范围）。
- 2025_1 无正式 `out/2025_1/metadata.json`（front 未产出），验证走临时副本
  `out_llm_trial/wb_front_quality/out_after`，不入库。
