# T-20261113-WB-LAYOUT-V2 handoff

## 结论
PASS（13 页续修首轮通过）。`layout_eval`：double recall **1.0000（85/85）**，false positive **0**，precision 1.0000。
pred=86 double / 13 single（含 1 个 ambiguous）；42_103 p13=double，符合允许口径。
42_185 p1=double，43_10814 p3=single；39 个已知双栏全部保持 double，无新增假阳性。

## 本轮改动
- 保留投票法、原 Text 正文带兜底及 `_order_blocks_ja`；只追加漏判检测。
- 跨线 Text 优先从 unified `members` 子块恢复左右栏，要求真实 y 区间重叠；非文献页要求栏顶对齐。
- 支持一侧 Text、另一侧 Picture/Table，排除无 Text 页及浮图后的单栏绕排。
- 无子块时仅文献页以中线 + 多个行首编号/作者年份证据保守判定。
- 首页节头支持罗马数字，节头仅将 front 底界前移；图/表短注不进入正文带。

## 13 页 before/after
| doc | page | before | after |
|---|---:|---|---|
| 2025_1 | 6 | single | double |
| 2025_1 | 17 | single | double |
| 40_10569 | 3 | single | double |
| 42_103 | 12 | single | double |
| 42_185 | 7 | single | double |
| 42_93 | 1 | single | double |
| 42_93 | 4 | single | double |
| 42_93 | 6 | single | double |
| 42_93 | 9 | single | double |
| 52_230302 | 1 | single | double |
| 52_230302 | 6 | single | double |
| 52_230725 | 1 | single | double |
| 5_55 | 4 | single | double |

## 回归与 layout_eval
- 命令：`py eval/layout_eval.py --pred out_llm_trial/wb_layout_v2_eval2 --min-recall 1.0 --max-fp 0`。
- gold：85 double / 13 single / 1 ambiguous；漏判 double=0，single→double=0，未判=0。
- 39 页基线：2025_1 p1/4/8/9/10/14/15/16；40_10569 p1/2/4/6；40_10588 p1/2/3。
- 42_103 p1/2/6/7/9/11；42_185 p2/3/5；42_93 p5/7；43_10814 p2/4。
- 52_230302 p2/3/5；52_230725 p3/5/7；5_55 p2/5/7；9_1 p3/4：全部仍 double。
- 新增假阳性：无；临时产物：`out_llm_trial/wb_layout_v2_eval2/`。

## 测试与哈希
- `py -m metapy.layout_ja`：PASS。
- `py -m unittest -v test_pipeline.py`：12/12 OK。
- `py -m compileall -q metapy/layout_ja.py`：OK；`ner_lite.selfcheck()`：OK。
- 正式 out/：1151 文件，前后均为 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`。
- follow-up commit：`cf385d0`。

## 残余
检测真值无残余；合并后的 99 页阅读序复测由 Trae 执行。
