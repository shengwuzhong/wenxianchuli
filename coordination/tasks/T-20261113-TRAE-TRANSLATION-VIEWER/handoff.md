# Handoff — T-20261113-TRAE-TRANSLATION-VIEWER

- 工具：trae
- 分支：agent/trae/T-20261113-TRAE-TRANSLATION-VIEWER（基于 main）
- Commit：a4c1838
- 状态：review（handoff_to: deepseek）
- 范围：仅 `viewer.py`；未 merge、未 merge_check。

## 改了什么
1. `COMPARE_TMPL` header 增加 `#langtoggle`；`_meta_ov_band` 顶部插入 `#transbox.hide`；新增 `#transbox` 样式。
2. 新增 JSON 载荷节点 `<script type="application/json" id="transdata">@@TRANSDATA@@</script>`。
3. 新增 `_load_translated(path)`（读同目录 `metadata_translated.json`，失败返回 None）与 `_trans_data_json(tr)`。
4. 前端 IIFE：默认原文 → 点击切中文，渲染「中文译文」卡片（标题/摘要/关键词）；`status!='ok'` 或全空 → 「暂无译文（status=…）/（无 metadata_translated.json）」；再点切回并隐藏。
5. `build_compare_viewer` 增加 `v.replace("@@TRANSDATA@@", ...)`。

## 验证
- 2025_1（ok）：卡片显示中文标题/摘要/三条关键词，按钮「中文↔原文」正常。
- 40_10569（unavailable）：`暂无译文（status=unavailable）`。
- 52_230725（ok 但三字段全空）：`暂无译文（status=ok）`。
- raw 标题/摘要仍在总览中，未被覆盖；三篇 console 0 error。
- unittest 12/12；compileall OK；`out/` 1151 文件哈希 mismatch 0。

## 遗留 / 注意
- 译文文件路径约定：`viewer_compare.html` 同目录的 `metadata_translated.json`。若 WorkBuddy 把译文放在 out/<doc>/ 根目录而 html 在别处，需要再约定。
- 52_230725 的 `status=ok` 但字段为空 → 前端按空字段兜底；建议 WorkBuddy 在写入时把这种情况标 `unavailable`。
- 译文卡片只读展示，不参与搜索索引（如需中文可搜另开 task）。

## 下一步
Integrator 评审 → merge_check → 合到 main；合并后与 WorkBuddy 对齐译文文件落盘位置并抽查一篇真实译文。
