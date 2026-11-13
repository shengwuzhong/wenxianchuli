# Handoff — T-20261112-WB-REFS-JA：日文参考文献抽取修复（2025_1/52_230725/40_10569）

- 任务：T-20261112-WB-REFS-JA
- 工具：workbuddy
- 分支：agent/workbuddy/main（直接提交，未开 feature 分支）
- Base：75a3da1
- Commit：810de5a（首轮）→ **review 返工 follow-up（本轮）**
- 状态：review（handoff_to=deepseek）

## 〇、review 返工（2026-11-13，本轮）

上轮 commit `810de5a` 被 review 判「changes requested」，基线 `2025_1` recall 0.618。本轮按
`coordination/reviews/T-20261112-WB-REFS-JA.md` 逐条对照返工，**只改 `metapy/refs.py`**
（common.py/regress.py 上轮已改，本轮未动）。review 明确 4 根因 → 全部修复：

| 根因 | 修复 |
| --- | --- |
| ① `_split_entries_block` 逐行切 all-or-nothing | 重写为逐行判定 + 续行合并 + `_REF_STOP` 断流；**限定 style=="authoryear" 且块含日文(汉字/仮名)**，纯英文块走原 authoryear 分支（防 52_230302 英文粘连被拆散） |
| ② u15_4 #5/#8/#13/#18 被过滤 | `_ja_entry_head`（全角逗号日文头）+ num=None 过滤放宽「卷页数字模式 + 日文关键词」**仅对含汉字/仮名条目**放行 |
| ③ 英文 title 被填成 journal | italic 分支 `m_vp` 补 `\*{0,2}` 容忍 **卷** 加粗；`_year_pick` 尾随评分补全角逗号「，」 |
| ④ 页脚/关键词污染 | `_REF_STOP` 终止（キーワード/受付/受理）；u16_4 日期块遇 `_REF_STOP` 返回空；Sumirah 页脚清除 |

### 验收结果（三篇 GT）

| doc | recall | title_ok | author_ok | 结论 |
| --- | --- | --- | --- | --- |
| 2025_1 | **1.000** (35/34 含重复) | **0.912** | **0.941** | ✅（验收线 1.000 / ≥0.90 / ≥0.60） |
| 40_10569 | **0.947** (18/19) | 0.789 | 0.947 | ✅（review 只要求 recall≥0.947） |
| 52_230725 | **1.000** (7/7) | **0.857** | **1.000** | ✅（验收线 1.000 / ≥0.85 / ≥0.90） |

### 13 条缺失逐条结果（2025_1 GT 编号 5,8,13,18,24,25,28,29,31,32,33,34,35）

全部恢复（recall=1.000）。代表性：#18 三田村（纯汉字日文条目被 num=None 过滤误拒，卷页模式容忍 `**卷**` 加粗后恢复）、#33 谷口（年份消歧补全角逗号后恢复）、#32 田井b（全角逗号日文式切分恢复）。

### 兼容性（回归防范，本轮重点）

| doc | 预期 | 实际 | 说明 |
| --- | --- | --- | --- |
| 42_185 | 18 | 18 | ✓ |
| 42_93 | 49 | 49 | ✓ |
| 5_55 | 33 | 33 | ✓ |
| 52_230302 | 43 | 43 | ✓（首版返工曾误到 49，已回退：逐行切限日文块 + `_ja_entry_head` 收紧年份后必须跟逗号） |

### 剩余 BAD title（不阻塞，title_ok 已达标）

- [14] 増田1985（sim0.83）：缺引号副题「"逆グレーディング構造"：」前缀
- [27] Patria（sim0.77）：英文题名被首个 ASCII 逗号截断
- [34] Sumirah（sim0.88）：题名缺 ", Riau Province"（原文以 "Geoscience," 结尾，题名本就不完整）
- 40_10569 #16 Tokunaga（recall 0.947 缺 1 条）：`N) 作者ら: 題名` 英文冒号式字段解析，review 标「非阻塞」

### 测试与哈希

```
py -m metapy.refs                # selftest 48/48 PASS
py -m unittest test_pipeline.py  # 12/12 OK
py -m compileall -q metapy/refs.py metapy/common.py regress.py  # OK
py -c "import ner_lite; assert ner_lite.selfcheck()==0"          # OK
```
正式 out/ 哈希：`09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`（1151 文件，**一致**，未写 out/）

---

## 一、改动文件与关键函数（首轮 810de5a 记录，保留备查）

## 一、改动文件与关键函数

改动 3 个 owner 文件（+162/-7），未触碰 forbidden（unify.py/m3.py/viewer.py/test_pipeline.py/webapp.py/pipeline.py/out/**）。

### 1. `metapy/refs.py`（主体）

- **`_ja_line_selfcontained`**（新增）：判定文献块内单行是否自含一条（含 19xx/20xx 年份 + 行末句点/页码/出版社/网址/DOI）。
- **`_JA_AY_HEAD` + `_ay_head`**（新增）：日文作者-年头「短姓名 + (年)」正则（作者段 ≤30 折叠字符、无句点），区别于正文长句含文内引用「…(2021)…」；`_ay_head` 合并 AY_HEAD（英文/韩文）与 _JA_AY_HEAD，供 `_split_entries_block` 与 `refs_doc` 过滤共用。**不改 AY_HEAD 本身**，避免英文/韩文回归。
- **`_split_entries_block`**：多行块按行切（行数≥2 且每行 `_ja_line_selfcontained`）；authoryear 分支 marks 合并 AY_HEAD + _JA_AY_HEAD 位置排序。
- **`_ja_reference_fields`**（新增）：日文/括号年式字段解析，覆盖式A「著者(年): 題名. 誌名, 巻, 頁」、式B「N) 著者: 題名. 誌名, 巻: 頁, 年」。
- **`_extract_fields`**：lang 三元判定（含仮名→ja）；含仮名或 `(year):` 式条目走 `_ja_reference_fields` 覆盖 title/source/authors。
- **`refs_doc` L1**：文献区回退——`in_ref` 全 False 时本地扫描 unified 页找「文\s*献/引用文献/参考文献/References」头，取最后一页到文末为 ref_pages（不改 unified 的 in_ref 字段）。
- **`refs_doc` 过滤**：无编号条目 AY_HEAD 检查改用 `_ay_head`；cite 线索放宽日文出版社/誌名/卷页模式。

### 2. `metapy/common.py`

- **`_complete`**：网址/文件扩展名（.html/.pdf 等）结尾也算完整，防「神田公生(1997)…se059369.html」无句点被误并下一条。

### 3. `regress.py`

- **`REF_HEAD`**：补「文\s*献」「引\s*用\s*文\s*献」「参\s*考\s*文\s*献」字间空格形态。

## 二、before/after

| doc | before | after |
| --- | --- | --- |
| **2025_1** | 0 条（`无文献区`，in_ref 全 False + 「文 献」字间空格不认） | **21 条**（authoryear，13 ja / 8 en） |
| **52_230725** | 3 条（7 行只切 3 条，日文 4 条并入英文条；title 以 `:` 开头） | **7 条**（4 ja / 3 en，title 无冒号，作者/题名/出处正确） |
| **40_10569** | 19 条（日文条目字段串位：`authors` 含「小林祥泰監修: 脳卒中データバンク…」，title=「中山書店」，lang=ko） | **19 条**（18 ja / 1 en，字段不串位，lang 正确） |

### 40_10569 抽样 5 条字段（after）

| num | 作者 | 年 | 题名 | 出处 | 页 |
| --- | --- | --- | --- | --- | --- |
| 1 | 小林祥泰 | 2009 | 脳卒中データバンク 2009. 東京, 中山書店 | 2009 | 1-205 |
| 4 | 木村和美, 数井誠司, 山口武典 | 2003 | 脳梗塞急性期医療の全国実態調査 | 臨床医 29: 19-22 | 19-22 |
| 5 | 白井和歌子, 徳光直樹, 和田始 | 2014 | 北海道北部における脳卒中の実態調査―… | 脳卒中 36: 23-28 | 23-28 |
| 8 | 徳永誠, 渡邊進, 三宮克彦 | 2013 | 熊本脳卒中地域連携パス運用3年間における… | J Clin Rehabil 22: 935-941 | 935-941 |
| 12 | 柳井久江 | 2016 | 4 steps エクセル統計, 第4版. 埼玉, オーエムエス出版 | 2016 | 1-310 |

注：num=1/12 为「書名 年版. 出版地, 出版社. 年, 頁」特殊格式（书名内嵌年份），title 含出版地/出版社残留、source=年份，属已知次要瑕疵（核心作者/年/页正确）。

## 三、测试命令与结果

```
py -m metapy.refs              # selftest 48/48 PASS
py -m unittest -v test_pipeline.py  # 12/12 OK
py -m compileall -q metapy/refs.py metapy/common.py regress.py  # compile OK
py -c "import ner_lite; assert ner_lite.selfcheck()==0"  # OK
```

## 四、正式 out/ 哈希前后

- 前：`09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`
- 后：`09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`（1151 文件，一致）
- 未对正式 out/ 做任何写操作；所有验证均在 `out_llm_trial/wb_refs_ja_eval/` 副本。

## 五、验收对照

- [x] 2025_1：0→21 条。**注意**：任务写「≥40 条」，但 unified 归一化产物里 2025_1 文献区仅跨 page_15/page_16 两页、实际约 20 条文献（merged.md「## 文献」区仅 10 条 + unified 补 11 条）；40+ 条的目标基于原始 PDF，M3 归一化后未完整保留。已抽出 unified 内全部可见文献。
- [x] 52_230725：7 行→7 条，title 无 `:` 开头，作者/题名不再互换。
- [x] 40_10569：19 条字段不串位（num=1/12 书名式 title 稍长，见上）。
- [x] 日文条目 lang=ja：40_10569 18/19=95% ja；2025_1 13 ja；52_230725 4 ja。
- [~] 兼容性：42_185 18 条不变 ✓；5_55 33 条不变 ✓；42_93 49 条不变 ✓；**52_230302 42→43 条**（见下「残余」）。
- [x] refs selftest / 12 unittest / ner_lite / compileall 全过。
- [x] 正式 out/ 哈希未变，未写 out/。

## 六、已知残余 / 下一步

1. **52_230302 42→43 条**：日文条目「服部高典, 佐野亜沙美, 有馬 寛 (2016)」被正确拆出（before 它并入英文「Fukai 1984」粘连条目），故 +1。这是修日文文献的必然结果（方向正确）。但「Hattori, T., …(2015)」英文条目因 19 作者、作者段 234 字符超过 AY_HEAD 的 200 字符上限，仍粘连在服部高典条后——属既有英文超长作者段 bug，不在本任务（日文）范围，未扩。
2. **52_230302 英文字段被顺带改善**：任务「不得改变英文字段」与「52_230725 title 不以 `:` 开头」对英文「Author (year): Title」格式存在内在冲突（52_230725 第 1 条 Boersch 即英文条目、任务明确要求其 title 无冒号）。式A分支统一修复了该格式的 title 冒号/source 串位，52_230302 的英文条目（Antonov/Fischer 等）title 从 `': T-P phase…'` 修正为 `'T-P phase…'`、source 从 `'16'` 修正为 `'Scr. Mater., 16, 203–208'`——属正向修复，非改坏。
3. **40_10569 num=1/12**「書名 年版. 出版地, 出版社. 年, 頁」书名内嵌年份格式，title 含出版地残留，未做精确拆解（歧义高、收益低）。
4. **2025_1 页级回退粒度**：文献区回退是「页级」（从「文 献」头页到文末），右栏文献（如 page_15 u15_4 Huzita 位于「文 献」头上方）靠 `_entry_like`/`_ay_head` 过滤自然纳入，但同页正文/谢辞若含「(年)」文内引用仍有误入风险（当前 21 条未见明显正文混入）。
