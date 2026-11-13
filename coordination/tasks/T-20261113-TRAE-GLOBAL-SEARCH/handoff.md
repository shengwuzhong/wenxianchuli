# Handoff — T-20261113-TRAE-GLOBAL-SEARCH

- 工具：trae
- 分支：agent/trae/T-20261113-TRAE-GLOBAL-SEARCH（基于 main）
- Commit：c6d2d72
- 状态：review（handoff_to: deepseek）
- 范围：仅 `viewer.py`；未 merge、未 merge_check。

## 改了什么
1. `COMPARE_TMPL` header 内新增 `#qwrap`（`#q` 输入框 + `#qres` 结果浮层），并新增 `.qrow/.qh/.qs/mark` 样式。
2. 新增 `<script type="application/json" id="searchdata">@@SEARCHDATA@@</script>`。
3. 新增 `_search_index_json(meta)`：metadata（题录/摘要/来源/作者/关键词/正文）+ references + citation_spans 的扁平索引 `[类型, 页码, uid, 文本]`，`</` 转义为 `<\/`。
4. 新增前端 IIFE：输入即搜（小写子串，上限 60 条）、片段截取 + `<mark>` 高亮、点击定位 `section#p{page-1}` 并高亮 `[data-u=uid]`、空结果「无命中」、Esc/点外部关闭。
5. `build_compare_viewer` 末尾 `v.replace("@@SEARCHDATA@@", ...)`。

## 验证
- 40_10569（80 行索引）：题录/摘要/来源/作者/正文/文献/引文 七类齐全；「脳卒中」45、「本田」13（首行作者·p1）、「データバンク」命中文献、「zzzqqqxxx」无命中。
- 2025_1（81 行，仅文献 35 + 引文 46）：「Huzita」2 条、无命中分支正常。
- 52_230725（20 行）：「岩石」4 条。
- 点击首条 → scrollY 5615、1 个 `cite-on` 块；三篇 console 0 error。
- unittest 12/12；compileall OK；`out/` 1151 文件哈希 mismatch 0。

## 遗留 / 注意
- 结果上限 60 条（计数为实际命中数）。
- 正文索引截断至 4000 字符（超长正文尾部不参与搜索）。
- 全角/半角、大小写之外不做同义词归一；如需模糊/分词另开 task。

## 下一步
Integrator 评审 → merge_check → 合到 main；合并后用正式 out（含 metadata 的文档）抽查一次标题词与文献题名命中。
