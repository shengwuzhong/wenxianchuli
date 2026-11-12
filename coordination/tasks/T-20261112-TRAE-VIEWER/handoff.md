# T-20261112-TRAE-VIEWER handoff

- 任务：查看器日文元数据面板与字段警告
- 工具 / 分支：trae / `agent/trae/T-20261112-TRAE-VIEWER`
- commit：`9aa5e95`（base `main` = `569ec8c`）
- 改动文件：`viewer.py`（+144/−23）；未新增 `static/`，样式写在 `COMPARE_TMPL` 内联 CSS。
- 未改 `metadata.json` schema、未写 `out/`、未改 `app.js` / `webapp.py` / `metadata.py` / `metapy/**` / `test_pipeline.py`。

## 1. 改了什么（只做展示层）

### 1.1 字段标签日文化/双语化

新增 `_META_LABELS` + `_meta_labels(ja)`：日文文献给「中文 · 日文」，非日文返回原中文标签（逐字一致，已用脚本核对 16 个键）。

| 字段 | 韩文/中文（原样） | 日文 |
| --- | --- | --- |
| title | 标题 | 日文标题 · 標題 |
| title_en | 标题(英) | 英文标题 · Title |
| authors | 作者 | 作者 · 著者 |
| affiliations | 机构 | 机构 · 機関 |
| abstract | 摘要(韩) | 日文摘要 · 要旨 |
| abstract_en | 摘要(英) | 英文摘要 · Abstract |
| journal / journal_en | 期刊 / 期刊(英) | 期刊 · 誌名 / 期刊(英) · Journal |
| year / volume / issue / pages | 年 / 卷 / 期 / 页 | 年 · 発行年 / 卷 · 巻 / 期 · 号 / 页码 · 頁 |
| keywords / keywords_en | 关键词 / 关键词(英) | 关键词 · キーワード / 关键词(英) · Keywords |
| references / footnote | 参考文献 / 脚注 | 参考文献 · 文献 / 脚注 |

日文判定 `_meta_is_ja(meta)`：题录/摘要/关键词/机构里出现 ≥3 个仮名（复用 `metapy.common._JP_KANA_RE`）。谚文/纯汉字文档不命中，面板文案与行序保持原样。

### 1.2 字段级警告（只提示，不改数据）

`_meta_warnings(meta, ja)` → `{字段: [文案]}`，渲染为红色 `待复核` 徽标 + 琥珀提示文（`title` 属性同文案）。仅日文文献启用。

| 触发条件 | 文案 |
| --- | --- |
| `abstract` 为 null/空 | 日文摘要未抽取/原文无 |
| `abstract_en` 含假名 | 疑似机构/非英文摘要(含假名) |
| `abstract_en` 与某条 `affiliations` dice ≥ 0.6 | 疑似机构/非英文摘要(与机构高度相似) |
| `abstract_en` 短(≤160 字/≤20 词)且含机构名样式词 | 疑似机构/非英文摘要(机构名样式) |
| `title_en` 以 `Key words` / `Keywords` 开头 | 疑似关键词行 |
| 作者 0 人 | 作者可能异常: 未抽取到作者 |
| 作者名命中章节词（`JP_SECTION_TAG` / はじめに・対象と方法 等） | 作者可能异常: 混入章节词 … |

空摘要/0 作者这类「没有行可挂」的字段，在**总览横带**和**第 1 页横带**的组首各补一行 `mf warn` 提示行；有值的字段（title_en / abstract_en / authors）直接在原行上挂徽标。组内追加位置紧贴同组，未破坏「组头只出一次 + 按组配平 `</div>`」的拼装逻辑（三个产物 div 开闭配平，差 0）。

### 1.3 点击跳转

未改任何 JS。新增行沿用既有 `data-u` 机制；警告行不带 uid（无证据可跳），可点击字段行行为不变。

## 2. 验证（全部用 `out_llm_trial` 临时目录，未写 `out/`）

产物目录（`out_llm_trial/` 已在 `.gitignore`，不入库）：

- 改动后：`out_llm_trial/trae_viewer_eval/{52_230725,40_10569,42_103}/viewer_compare.html`
- 改动前基线：`out_llm_trial/trae_viewer_eval_before/...`（用 `git show HEAD:viewer.py` 导出旧版、运行时替换 `pipeline.build_compare_viewer` 重建，**未 checkout/未改动工作区文件**）
- 文本 diff（三个文档的 metadata 面板，含总览横带与每页横带）：
  `out_llm_trial/trae_viewer_eval/meta_panel_diff.diff`

结果（`待复核` 计数 = 总览横带 + 第 1 页横带）：

| 文档 | 命中警告 | 计数 |
| --- | --- | --- |
| 52_230725 | 空摘要 / abstract_en 含假名 / 作者 0 人 | 6 |
| 40_10569 | 空摘要 | 2 |
| 42_103 | 空摘要 / abstract_en=机构名样式(`Asahi TelePathology Center, Asahi General Hospital`) | 4 |

补充：43_10814（未在验收清单内）离线校验命中「疑似关键词行 + 作者混入 はじめに、対象と方法」。

浏览器验证（`py -3 -m http.server` 本地服务 + 浏览器代理，52_230725 页）：

- 页面出现「日文标题 · 標題」与红色「待复核」徽标：PASS
- 控制台无 JS 错误（`browser_console_messages` 两次均为空）：PASS
- 点击 `data-u=u0_2` 的标题行走滚动到证据区并高亮：PASS（滚动位置 0 → 462）

回归：

- `py -3 -m unittest -v test_pipeline.py` → `Ran 10 tests ... OK`
- `py -3 -c "import ner_lite; assert ner_lite.selfcheck() == 0"` → OK
- `py -3 -m compileall -q viewer.py` → exit 0

## 3. guard 说明（非冲突）

`coordination/guard.py check viewer.py` 报 hash 不一致是**本人编辑所致**，不是第三方改动：
recorded `69aef86b…` 与 `git show HEAD:viewer.py` 的 sha256 `69aef86b…` 完全一致；当前 `71c3708e…` 即本次提交内容。

## 4. 已知限制

- `abstract` 为空时只提示，不补数据；日文摘要若本就不在文献中（40_10569 / 42_103 属此类），提示会长期存在，需要后端 `metapy/abs.py` 判定「原文无」才能消警——不在本任务 owner 范围。
- `abstract_en` 机构型判定是启发式：短文本 + 机构词，或与 `affiliations` 的 dice ≥0.6；纯英文短摘要若恰含 `Center/Institute` 等词可能误报（当前语料未出现）。
- 假名 -> 日文的判定阈值 3，若某韩文文献的英文栏混入大量日文符号会被误判为日文；当前 `out/` 全部为日文文献，未出现。
- 面板文案只覆盖任务列出的 13 类字段；`引文句`/`citation_spans` 分组标题保持原样。
- `handoff.md` 按协议只写入不入库（提交只含 `viewer.py`），`merge_check.py` 的「工作区干净」需要评审时用 `git status` 判断本文件。
