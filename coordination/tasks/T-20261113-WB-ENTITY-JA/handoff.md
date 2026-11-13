# Handoff — T-20261113-WB-ENTITY-JA（日文实体提取 v2）

- 分支：`agent/workbuddy/T-20261113-WB-ENTITY-JA`（基线 main `0938658`）
- 改动：仅 `metapy/entity.py`（+191/−65）；未碰 refs/cspan/layout_ja/viewer/merge_out/unify/m3/test_pipeline/out/**
- 路线：纯规则 + 闭合词典；无 LLM

## 实现要点

1. 基金：新增日文致谢判定 `_is_funding_sent` = 致谢动词（助成/支援/研究費/補助金/交付）**且** 机构/项目/编号共现；机构表补 厚生労働省/農林水産省/経産省/環境省/内閣府/総務省/AMED/NEDO；项目表补 科研費/科学研究費(補助金/助成事業)/KAKENHI/学術研究助成基金/特別研究員奨励費/GteX；编号强约束 `_FUNDING_NO_STRICT`（JP18H05224 / JPMJGX23B3 / 22J21462 / 課題番号）。
2. 基金取块：`load_body_blocks(include_ref=True)` 额外收 in_ref 页 —— 日文「謝辞」常与文献表同页，整页被判 literature 时 ack 句仍在（只供 funding，不参与 body）。
3. 软件：NFKC 全角归一 + 下标回映（`ＳＰＳＳ ２６` 可匹配，evidence 仍取原文全角）；补 JMP/EZR/エクセル統計/GSAS/Z-Rietveld/LabSolutions/SPW/Origin/KaleidaGraph/Photoshop/Illustrator/QGIS/Metashape；修正「首个别名必 break」bug（Fiji 等次别名原先永不生效）。
4. 数据集：补 pdbj / protein data bank / uniprotkb / swiss-prot / cinii research / NDLサーチ / 国立国会図書館サーチ；Caption 块纳入软件/数据集抽取（图注里的库名）。
5. 词边界：`R` 收紧为前后非字母数字 + 软件语境闸门；去掉裸 `geo/sra/refseq/pubmed` 泛词别名。
6. 每条实体必带 `evidence_span`（原文切片，空则丢弃）；文献表页(in_ref)不参与 software/datasets。

## before → after（临时副本 `out_llm_trial/wb_entity_ja/out_copy`）

| doc | funding | software | datasets |
| --- | --- | --- | --- |
| 40_10569 | 0→0 | 0→1 | 0→0 |
| 40_10588 | 0→0 | 0→0 | 0→0 |
| 42_103 | 0→0 | 0→0 | 0→0 |
| 42_185 | 0→0 | 0→0 | 0→0 |
| 42_93 | 0→0 | 1→0 | 0→0 |
| 43_10814 | 0→0 | 2→1 | 0→0 |
| 52_230302 | 0→1 | 0→2 | 0→0 |
| 52_230725 | 0→0 | 0→0 | 0→0 |
| 5_55 | 0→0 | 0→0 | 2→2 |
| 9_1 | 1→1 | 0→1 | 0→0 |
| 合计 | **1→2** | **3→5** | **2→3** |

## 新增样本（抽检）

1. `52_230302` funding `JSPS JP18H05224` ← 「本稿で紹介した筆者らによる研究は, JSPS 科研費 (JP18H05224), 特別研究員奨励費(22J21462)の助成を受けたものである。」（原在 in_ref 页，旧逻辑整页丢弃）
2. `9_1` funding `GX 技術創出事業 JPMJGX23B3` ← 「本研究の一部は、革新的 GX 技術創出事業 (GteX) の研究費 (JPMJGX23B3, 代表：馬場 健史) の助成を受けたものである。」（旧实体名仅「(GteX)」，现补项目名+编号）
3. `52_230302` software `GSAS` / `Z-Rietveld` ← 「…解析プロファイルはGSASやZ-Rietveldなどの解析ソフトを用いて…」
4. `40_10569` software `4 Steps エクセル統計` ← 「統計ソフトは4 Steps エクセル統計 ^{12)} を用いた.」
5. `9_1` software `LabSolutions` ← 「装置制御及びデータ処理：LabSolutions ソフトウェア (Shimadzu, Ver.5.99 SP2)」
6. `5_55` datasets `NCBI` ← 图注「NCBI database was the subject to find out aptamer-…」（Caption 块，原靠旧版块集合偶然命中，本次显式支持）

## 测试 / 回归

- `py -m metapy.entity` → **10/10 PASS**（原 5 例 + 新增 5 例：日文 JSPS/文部科学省、泛致谢不入库、全角ＳＰＳＳ、PDB+NDL Search、报告书目引用不入库）
- `py -m unittest test_pipeline.py` → **12/12 OK**；`compileall metapy/entity.py` 通过
- 正式 `out/` 哈希不变：1151 文件 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`

## 残余（非阻塞）

- `2025_1` 无 `metadata.json`（front 阶段未产出），entity 阶段按契约跳过 → 该篇正文里 `SPW Ver. 2` 未入库；如需覆盖须先跑 front，不在本任务范围。
- `42_93` / `43_10814` 旧 `R` 实体为假阳性（`PLA2R`、IRB 编号 `R2019-073`），收紧边界后不再入库；语料内无真实「R 软件」用法。
- `42_185 / 40_10588 / 42_103 / 52_230725` 正文确无基金声明与软件/数据集专名（只有「ビューワー・ソフト」等泛词），保持 0。
- 语料内无 DDBJ / CiNii / GenBank 正文证据，词典已补但本批无命中。
