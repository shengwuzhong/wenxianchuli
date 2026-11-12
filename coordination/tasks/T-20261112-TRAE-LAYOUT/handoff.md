# T-20261112-TRAE-LAYOUT handoff

- 任务：在 1:3 查看器中展示日文 layout_ja 的阅读序/前区标注
- 工具 / 分支：trae / `agent/trae/T-20261112-TRAE-LAYOUT`
- commit：`dcc598e`（base `main` = `8c5dac1`，与 `agent/trae/main` 同点）
- 改动文件：`viewer.py`（+130/−6）；未新增 `static/`。
- 未改 `metadata.json` schema、`webapp.py`、`app.js`、`test_pipeline.py`、`metapy/**`；未写正式 `out/`。

## 1. 改了什么（只读展示，不改数据）

数据源：`unified/page_N.json` 每块的 `layout = {detected, boundary, col, zone, reading_order}`（`metapy/layout_ja.py` 写回）。新增 `_layout_overlay(u_list, W, H)`，返回「页顶条带 html + 原图叠加 svg」，在 `build_compare_viewer` 的每页 section 里拼装：

1. **页顶条带**（`<h2>` 与 1:3 网格之间）：
   - `双欄 layout` / `単欄 layout`（`layout.detected`），双栏另出 `境界 x=<boundary>`
   - `前区 front n 块`（可点击，跳前区首块）、`正文 body m 块`
   - 双栏：`左栏 k 块 #a–#b` / `右栏 j 块 #c–#d`（每栏块数 + 阅读序范围，可点击跳该栏首块）；单栏只出 `栏标记: 无(单栏)`
   - `読順 0→N`（可点击跳阅读序首块）
2. **原图叠加**（SVG `<g class="layg">`）：
   - 每个块一个圆序号徽章，位置在块左上外侧（右栏块放右侧），直径≈3% 页宽，白底描边，不压正文
   - 颜色：前区紫、左栏蓝、右栏琥珀、单栏青绿、结构性/通栏块灰（不参与栏流）
   - 双栏页画 `boundary` 红色虚线分界
3. **开关**：header 新增 `layout 标注` 按钮（`#layoutbtn`，默认 `on`），切 `body.layoff` 隐藏 `.layg`/`.layb`；条带是元数据，不随开关隐藏。
4. **点击跳转**：条带 chip 与原图徽章都带 `data-layu="<uid>"`，复用 `jumpToUid` 跳块并闪烁；无 uid 时按 `rect[data-u]` 兜底闪烁。

只有页面存在 `layout` 数据时才渲染条带/徽章/按钮；`VIEWER_TMPL`（单渠道查看器）里 `@@LAYOUTBTN@@` 被替换为空，行为不变。

### 归类口径（与显示正确性直接相关）

- `layout.boundary` 是**栏归属阈值**而不是几何中线（左栏块常越过它），所以不能用「跨 boundary」判通栏；改为**宽度 > 0.65×页宽 = 通栏**，通栏块不计入左/右栏、徽章为灰。
  - 例：52_230725 p1 的 Footnote 是通栏块，修正前会被算成「左栏 #9–#9」假栏标记。
- 单栏页正文序号用青绿（`sgl`），避免蓝色被误读成左栏。

## 2. 验证（临时副本，未写正式 `out/`）

产物目录（`out_llm_trial/` 已 gitignore）：

- 改动后：`out_llm_trial/trae_layout_eval/{52_230725,40_10569}/viewer_compare.html`
- 改动前基线：`out_llm_trial/trae_layout_eval_before/...`（`git show HEAD:viewer.py` 导出旧版 + 运行时替换 `pipeline.build_compare_viewer`，未 checkout 工作区）
- before/after 文本 diff：`out_llm_trial/trae_layout_eval/layout_overlay_diff.diff`

### 2.1 产物自检

| 项 | 52_230725 | 40_10569 |
| --- | --- | --- |
| 页数 / 条带数 | 7 / 7 | 7 / 7 |
| 序号徽章 | 79 | 73 |
| `layoutbtn` 存在 | 是 | 是 |
| div 开闭配平差 | 0 | 0 |

条带样例（52_230725 p1）：`双欄 layout | 境界 x=517 | 前区 front 6 块 | 正文 body 7 块 | 右栏 2 块 #6–#7 | 読順 0→12`（该页左栏是摘要区，属 front，故无左栏 chip）。
条带样例（40_10569 p1）：`双欄 layout | 左栏 4 块 #4–#7 | 右栏 1 块 #5–#5`。

### 2.2 双栏左右顺序 vs `merge_out.order_blocks`

做法：同一页取 `merged/page_N.json` 的 mineru 渠道块交给 `merge_out.order_blocks` 排序，用 IoU≥0.5 映射到 unified 块，检查其 `reading_order` 是否单调不降（反转数）。

| 文档 | 双栏页 | 结果 |
| --- | --- | --- |
| 52_230725 | p1/p2/p3/p4/p5 | 反转 0，列序 `00011` / `0011` / `001` 等，全部左栏先于右栏 |
| 40_10569 | p1 | **反转 1**：列序 `000001111`，左栏顶部一块（box y=161）被 layout_ja 判为 ro=11，排在右栏之后 |
| 40_10569 | 其余双栏页 | 反转 0 |

结论：7/8 双栏页与 `merge_out.order_blocks` 完全一致；40_10569 第 1 页存在 1 处分歧，来自 `metapy/layout_ja.py` 的 content 判定（该块未进 content 集合，按 rank 2 排到最后）。viewer 如实展示该数据，未做纠正（`metapy/**` 不在本任务 owner）。若验收要求 100% 一致，需要 WorkBuddy 侧修 `layout_ja._content_blocks`。

### 2.3 浏览器实测（本地 `http.server` + 浏览器代理）

- 条带 chip + 原图序号徽章渲染：PASS
- 点 `layout 标注`：7 个可见 `.layg` → 0 → 再点恢复 7：PASS
- 点 `読順` chip：scrollY 0 → 476：PASS
- 控制台无 JS 错误：PASS（两次读取均为空）
- 未做真实截图文件（工具侧只在会话内回传），证据以 diff + 上述实测记录为准

### 2.4 回归

- `py -3 -m unittest -v test_pipeline.py` → **Ran 12 tests, OK**
- `py -3 -c "import ner_lite; assert ner_lite.selfcheck()==0"` → OK
- `py -3 -m compileall -q viewer.py` → 0

### 2.5 正式 `out/` 哈希

按 `out_llm_trial/previews/2026-11-12T1413/out_manifest.tsv` 的同一格式重算全树（path|size|sha256，1151 文件）：

- 重新生成的 manifest 与存档**逐字节相同**
- `sha256("\n".join(lines))` = `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`，与验收值一致

## 3. 已知限制

- 阅读序徽章依赖 unified 产物存在 `layout`；未跑 `layout_ja` 的文档不渲染条带/按钮（不报错）。
- 40_10569 p1 的 1 处顺序分歧见 2.2，需 metapy 侧修，viewer 不纠正。
- 徽章按块绘制，页码/页眉/图表也会有序号（灰色），页数多时视觉密度较高；可用 `layout 标注` 一键隐藏。
- 条带数字是阅读序**索引**（0 起），与 `merge_out.order_blocks` 的位置并不逐个相等，只保证「左栏整体先于右栏 + 栏内自上而下」。
- `handoff.md` 按协议只写入不入库（提交仅含 `viewer.py`）。
