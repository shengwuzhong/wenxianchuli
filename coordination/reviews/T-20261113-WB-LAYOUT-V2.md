# Review — T-20261113-WB-LAYOUT-V2（changes requested）

- 分支：`agent/workbuddy/T-20261113-WB-LAYOUT-V2` @ `d369015`（代码 `c5c2972`）
- 独立复测：`py eval/layout_eval.py --pred out_llm_trial/wb_layout_v2_review`
- 结论：**30 页目标通过；全量 truth99 未通过；代码保留，补 13 页后合并。**

## 指标

| 口径 | 结果 |
| --- | --- |
| 30 页 audited | 29 double / 1 single（42_103 p13 判 double，允许） |
| 42_185 p1 | double ✓ |
| 43_10814 p3 | single ✓ |
| 39 个已知双栏 | 全部 double ✓ |
| 全量 99 页 pred | 73 double / 26 single |
| truth99 目标 | 85 double / 13 single / 1 ambiguous |
| 真 double 命中 | **72/85，recall 0.8471** |
| 假阳性 | **0** |
| 漏判 | **13 页** |

漏判：
`2025_1 p6/p17`、`40_10569 p3`、`42_103 p12`、`42_185 p7`、
`42_93 p1/p4/p6/p9`、`52_230302 p1/p6`、`52_230725 p1`、`5_55 p4`。

## 判断

- V2 的正文带 + 允许跨线块方向正确，**0 假阳性**，比旧 39/99 明显提升；
- 但只覆盖“两侧都有 Text 块”的页面；13 个漏判集中在：
  - 一侧是图/旋转表（`2025_1 p6`、`42_93 p4/p6`、`5_55 p4`）；
  - 参考文献整栏被 OCR 并成跨线块（`2025_1 p17`、`42_103 p12`、`42_185 p7`、`42_93 p9`、`52_230302 p6`）；
  - 首页题录/摘要后正文双栏（`42_93 p1`、`52_230302 p1`、`52_230725 p1`）；
  - `40_10569 p3` 一侧表格/一侧正文。
- 不需要推翻 V2；在同一分支补这 13 页，保持 0 FP。

## 测试与哈希

- `metapy.layout_ja` selftest PASS
- `test_pipeline.py` 12/12
- compileall / ner_lite OK
- 正式 `out/` 哈希仍 `09a8820b…`

## 通过线

- truth99：**85/85 double**，0 false positive；
- 43_10814 p3 single，42_185 p1 double；42_103 p13 允许 double/ambiguous；
- 不新增 audited 30 页之外的假阳性。
