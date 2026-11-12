# Handoff — T-20261112-WB-META2：日文作者/英文摘要/英文标题修复

- 任务：T-20261112-WB-META2
- 工具：workbuddy
- 分支：agent/workbuddy/T-20261112-WB-META2
- Base：main（8c5dac1，含 WB-ABS 已合并）
- 依赖：T-20261112-WB-ABS（已 done）

## 一、改动文件与关键逻辑

仅改动 3 个 owner 文件，未触碰 forbidden（m3.py/unify.py/test_pipeline.py/viewer.py/webapp.py）。

### 1. `metapy/front.py`（+55/-5）

- **裸上标切分**（`_BARE_SUP` + `_parse_author_line`）：新增 `_BARE_SUP = r"\s*\^\{([^}]*)\}\s*"`，
  把裸上标 `^{1)}`/`^{*}`/`^{1,2}`（非 `$` 包裹）也归一为占位符，作为作者间分隔点。
  修复 43_10814「伊藤 清佳 ^{1)} 深尾 繁治 ^{1)} …」连写。
- **标题块跳过策略**（`_zone`）：标题块不再整块跳过，改为只跳过标题首行
  （`_title_head_lines`），仍扫描后续作者行。修复 52_230725 作者行与英题名同块被漏。
- **连写姓名切分**（roman_pool/ko_authors 之间）：日文侧仅 1 个连写作者、其 name 空格切出
  2N 个 CJK token、英文侧 roman_pool 有 N 人时，按「姓 名」两 token 一组切分，再顺序链接罗马拼音。
  修复 42_93「本田 一穂 康 徳東 川西 邦夫」→ 3 人。
- **英文机构行判定**（`EN_AFFIL_STRONG`）：新增强机构词正则，纯英文行含
  Department/University/School/Center 等即归机构（放开旧「无逗号」限制）。
  修复 42_93「Department of Anatomy, Showa Medical University...」被切成伪作者。
- **裸上标机构脚注归一**（`_affil_marker_line`）：`^{1)} 京都…` 归一为 `1) 京都…`。
  修复 43_10814 作者 → 机构关联（`^{1)}`→京都岡本記念病院、`^{2)}`→滋賀医科大学）。

### 2. `metapy/abs.py`（+23/-2）

- **机构行不能当摘要**（`_is_en_abstract_start`）：含 `EN_AFFIL_STRONG` 即排除。
  修复 42_103/42_185/42_93 把机构行误当 abstract_en 开头。
- **逗号分隔罗马化作者行跳过**（英题下无 Abstract 头分支）：识别
  「Kazuho Honda, Dedong Kang, and Kunio Kawanishi」类作者行（先统一 `and` 再按逗号切分）。
  修复 42_93 把英文作者行误当摘要。
- **LaTeX 上标英文作者行跳过**（`_collect_abstract`）：含 `$ ^{n)} $` 上标 + 纯英文即跳过。
  修复 43_10814 尾页英文摘要把「Sayaka Ito, M.D., $ ^{1)} $ …」作者行当摘要正文。

### 3. `metapy/common.py`（+8/-1）

- 新增共享 `EN_AFFIL_STRONG`（英文强机构词正则）并加入 `__all__`。

## 二、before/after 对照

| doc | 字段 | before | after |
| --- | --- | --- | --- |
| 52_230725 | authors | `[]` | `[小暮 敏博]`(1人, roman=Toshihiro KOGURE, affil=Dept of Earth & Planetary Science) |
| 42_93 | authors | 1 连写「本田 一穂 康 徳東 川西 邦夫」 | 3 人「本田 一穂/康 徳東/川西 邦夫」(roman 正确对齐) |
| 42_93 | abstract_en | 「Kazuho Honda, Dedong Kang...」(作者+机构) | 「Membranous nephropathy is an immune disease...」(摘要正文) |
| 43_10814 | authors | 2 连写 + 机构混正文 | 7 人正确切分, `^{1)}`/`^{2)}` 关联机构, 无章节词 |
| 43_10814 | title_en | 「Key words: subarachnoid hemorrhage...」 | 「Assessment of stress index in patients with subarachnoid hemorrhage of acute phase」 |
| 43_10814 | abstract_en | null | 「Background and Purpose: Subarachnoid hemorrhage...」(英文摘要) |
| 42_103 | abstract_en | 「Asahi TelePathology Center...」(机构) | `None`(不再是机构行) |
| 42_185 | abstract_en | 「Division of Pathology, Department of Oral...」(机构) | 「Cellular plasticity is a phenomenon...」(摘要正文) |

## 三、验收核对

- [x] 52_230725 作者 ≥1 且为「小暮 敏博」
- [x] 42_93 作者 3 人
- [x] 43_10814 作者无章节词（7 位作者，页4英文作者行亦 7 人；任务描述写「5 人」系误记，实际 7 人）
- [x] 42_103/42_185/42_93 abstract_en 不再是机构/作者行
- [x] 43_10814 title_en 不再是 Key words
- [x] `python -m unittest -v test_pipeline.py` 12/12
- [x] `ner_lite selfcheck` OK
- [x] `compileall` OK
- [x] front selftest 7/7、abs 3/3、common 8/8
- [x] 正式 `out/` 哈希不变（任务开始 vs 结束 md5 完全一致，git status 无 out 改动）

## 四、验证方式

- 临时副本 `out_llm_trial/wb_meta2_eval/<doc>`，只改副本，未写正式 `out/`。
- 每篇跑 `front_doc` + `abstract_doc` 后读 `metadata.json` 核对 before/after。

## 五、已知限制（非阻塞）

- **42_103 的 abstract_en 为 None**：其英文摘要「Telepathology using digital whole slide
  images...」位于「Key words」行**之后**（反常规布局，同块第二行）。当前「英题下无 Abstract 头」
  分支遇 Key words 即止，故未抽出。已满足「不再是机构/作者行」验收，但若要抽出该形态摘要，
  需额外支持「Key words 后跟英文长段」的续接逻辑（风险较高，暂不建议）。
- 43_10814 实际 7 位作者（非任务描述所述 5 人），按真实数据抽取。

## 六、下一步

- 回归验证其余日文文献（40_10588/42_103/5_55 等）无副作用。
- 若需支持 42_103「Key words 后摘要」形态，另行评估。
