# T-20261113-WB-LAYOUT-V2 handoff

## 结论
PASS（首轮实现）。30 页 audited：29 double / 1 single / 0 ambiguous；42_103 p13 判 double，属允许结果。
42_185 p1=double，43_10814 p3=single；39 个已知双栏全部保持 double。
 audited 外新增 5 页 double，逐页图像复核均为真实双栏；全量 99 页现为 73 double / 26 single。

## 改动
- 保留投票法；仅投票失败时，在首页前区之外的 Text/Footnote 正文带做几何兜底。
- 每侧至少一个 Text，x 分离、gap>=20、y 包络重叠；跨线块按 full，不再要求划分全页。
- 排除贴近所属图片的短图注/缩略语；新增每栏单块及左栏先读自检。`_order_blocks_ja` 未改。

## 30 页 before/after
| doc | page | before | after |
|---|---:|---|---|
| 2025_1 | 7 | single | double |
| 2025_1 | 13 | single | double |
| 40_10588 | 4 | single | double |
| 42_103 | 5 | single | double |
| 42_103 | 13 | single | double（允许 ambiguous/double） |
| 42_185 | 1 | single | double |
| 42_185 | 6 | single | double |
| 42_93 | 8 | single | double |
| 42_93 | 10 | single | double |
| 52_230302 | 7 | single | double |
| 5_55 | 8 | single | double |
| 9_1 | 9 | single | double |
| 2025_1 | 2 | single | double |
| 2025_1 | 3 | single | double |
| 2025_1 | 12 | single | double |
| 40_10588 | 5 | single | double |
| 42_103 | 3 | single | double |
| 42_185 | 4 | single | double |
| 42_93 | 2 | single | double |
| 42_93 | 3 | single | double |
| 43_10814 | 1 | single | double |
| 43_10814 | 3 | single | single |
| 52_230302 | 4 | single | double |
| 52_230725 | 2 | single | double |
| 52_230725 | 4 | single | double |
| 52_230725 | 6 | single | double |
| 9_1 | 2 | single | double |
| 9_1 | 5 | single | double |
| 9_1 | 7 | single | double |
| 9_1 | 10 | single | double |

## 39 个已知双栏与新增 double
- 2025_1 p1/4/8/9/10/14/15/16；40_10569 p1/2/4/6；40_10588 p1/2/3：均不变。
- 42_103 p1/2/6/7/9/11；42_185 p2/3/5；42_93 p5/7：均不变。
- 43_10814 p2/4；52_230302 p2/3/5；52_230725 p3/5/7：均不变。
- 5_55 p2/5/7；9_1 p3/4：均不变。
- 新增 40_10569 p7：上部参考文献左右双栏，下部英文摘要跨栏。
- 新增 42_103 p8：跨栏图 4 下方左右正文双栏。
- 新增 42_103 p10：跨栏表 6 下方左右正文双栏。
- 新增 5_55 p1：题录/摘要跨栏，「1 序論」起左右正文双栏。
- 新增 9_1 p1：题录/摘要跨栏，「1 序論」起左右正文双栏。

## 测试与哈希
- `py -m metapy.layout_ja`：PASS（含每栏单块、左栏先读合成用例）。
- `py -m unittest -v test_pipeline.py`：12/12 OK。
- `py -m compileall -q metapy/layout_ja.py`：OK；`ner_lite.selfcheck()`：OK。
- 正式 out/：1151 文件，前后均为 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`。
- 代码 commit：`c5c2972`；临时产物：`out_llm_trial/wb_layout_v2_eval/`。

## 残余
其余 25 个旧单栏页未逐页人工审计；合并后的 99 页阅读序复测由 Trae 执行。
