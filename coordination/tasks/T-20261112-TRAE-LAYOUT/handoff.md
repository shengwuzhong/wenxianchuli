# T-20261112-TRAE-LAYOUT handoff（review 轮，依赖 T-20261112-WB-LAYOUTFIX）

- 任务：1:3 查看器展示日文 layout_ja 阅读序/前区标注；复核 WB 修复后的双栏阅读序
- 工具 / 分支：trae / `agent/trae/T-20261112-TRAE-LAYOUT`
- viewer 提交：`dcc598e`（本轮未改 viewer.py）；本轮合并 `main` → `8a38d18`（含 `71c1d05 merge: T-20261112-WB-LAYOUTFIX`）
- 改动文件：仅 `viewer.py`（+130/−6，上轮）；本轮 0 代码改动，无需新提交
- 未改 `metapy/**`、`webapp.py`、`app.js`、`test_pipeline.py`；未写正式 `out/`

## 0. 前置确认

- `T-20261112-WB-LAYOUTFIX`：status=done，`coordination/merges/T-20261112-WB-LAYOUTFIX.json` 存在，`main` 含 `71c1d05`
- `git merge main` 成功（无冲突），合并带入 `metapy/layout_ja.py`（+161 行改动）、`metapy/abs.py`、`metapy/front.py`、`metapy/common.py`

## 1. WB 修复带来的数据变化（影响双栏页数量）

`layout.boundary` 现在统一为页面几何中线（620，之前 52_230725 是 517），栏归属与 merge_out 对齐，因此 detected 也变了：

| 文档/页 | 修复前 | 修复后 |
| --- | --- | --- |
| 52_230725 p0 | double | **single** |
| 40_10569 p3 | single | **double** |
| 40_10569 p6 | double | **single** |

双栏页合计 **8 → 7**（任务书按 8 页验收；实际重跑后为 7 页，见下表，另附检测变化原因）。

## 2. 反转数表（layout.reading_order vs merge_out.order_blocks，IoU≥0.5 映射）

做法：同页取 `merged/page_N.json` 的 mineru 渠道块 → `merge_out.order_blocks` 排序 → IoU≥0.5 映射到 unified 块 → 检查 `reading_order` 单调不降；反转数=相邻逆序对数。

| 文档 | 页 | 匹配块 | 反转数 | 列序 |
| --- | --- | --- | --- | --- |
| 52_230725 | p2 | 5 | **0** | 00011 |
| 52_230725 | p4 | 4 | **0** | 0011 |
| 52_230725 | p6 | 3 | **0** | 001 |
| 40_10569 | p0 | 2 | **0** | 01 |
| 40_10569 | p1 | 9 | **0**（修复前为 1） | 000001111 |
| 40_10569 | p3 | 4 | **0** | 0011 |
| 40_10569 | p5 | 5 | **0** | 00111 |
| **合计** | 7 页 | — | **0** | 全部左栏先于右栏 |

修复前后对比：8 页 / 反转合计 **1** → 7 页 / 反转合计 **0**。之前唯一的 40_10569 p1 反转（左栏顶部块 ro=11）已消除。

## 3. 查看器产物（临时副本，未写正式 out/）

- 重跑：`py metadata.py <doc> --out out_llm_trial/trae_layout_eval2 --stage layout_ja` → 双栏 3 / 4，标注块 79 / 73
- 重建：`--viewer` → `out_llm_trial/trae_layout_eval2/<doc>/viewer_compare.html`（280 / 339 块，unified 驱动）
- 条带示例：
  - 52_230725 p3：`双欄 layout | 境界 x=620 | 正文 body 10 块 | 左栏 3 块 #2–#5 | 右栏 3 块 #6–#8 | 読順 0→9`
  - 40_10569 p1：`双欄 layout | 境界 x=620 | 前区 front 10 块 | 正文 body 5 块 | 左栏 1 块 #10 | 右栏 1 块 #14 | 読順 0→14`

### 截图（Edge headless，本地 http.server）

- `out_llm_trial/trae_layout_eval2/shots/52_230725_p1.png`（单栏：`単欄 layout` + `栏标记: 无(单栏)`，序号徽章不暗示左右栏）
- `out_llm_trial/trae_layout_eval2/shots/40_10569_p1.png`（双栏：`双欄`/`境界 x=620`/左右栏/読順 + 原图圆序号 + 红色虚线分界）

### before/after diff

- `out_llm_trial/trae_layout_eval2/layout_overlay_diff2.diff`
  - before = `main` 版 viewer.py（无叠加）用**新数据**重建；after = 当前 viewer
  - 52_230725 96 行、40_10569 90 行差异（条带 + 序号徽章）

## 4. 回归 / 校验

- `py -3 -m unittest -q test_pipeline.py` → **OK（12 tests）**
- `py -3 -m compileall -q viewer.py` → 0
- `py -3 -c "import ner_lite; assert ner_lite.selfcheck()==0"` → OK
- 正式 `out/` 未改动：按 `previews/2026-11-12T1413/out_manifest.tsv` 格式重算 1151 个文件，与存档**逐字节相同**，
  `sha256("\n".join(lines))` 仍为 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`

## 5. 结论与遗留

- 双栏阅读序与 `merge_out.order_blocks` 一致：**7/7 双栏页反转 0**（修复前 8 页中 1 页有 1 处反转）
- 双栏页从 8 变 7 是 WB 修复的正常结果（52 p0、40 p6 → 单栏；40 p3 → 双栏），不是漏检
- viewer 无需改代码；分支保留 `agent/trae/T-20261112-TRAE-LAYOUT`（含 viewer 提交 `dcc598e` + 本轮 main 合并 `8a38d18`）
- 遗留：可视化条带的 `#a–#b` 是阅读序索引（0 起），与 merge_out 的位置不逐个相等，只保证左右栏先后与栏内 y 单调；这是设计口径
- `handoff.md` 按协议只写入不入库
