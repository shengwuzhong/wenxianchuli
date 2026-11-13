# Handoff — T-20261113-TRAE-META-EXPORT

- 工具：trae
- 分支：agent/trae/T-20261113-TRAE-META-EXPORT（基于 main）
- Commit：b6db88e
- 状态：review（handoff_to: deepseek）
- 范围：仅 `viewer.py`；未 merge/merge_check。

## 改了什么
1. 新增 `_META_EXPORT_KEYS`、`_meta_export_payload(meta)`（17 字段，`{value,...}` 解包）、`_meta_export_btn(meta)`（float 右对齐按钮，空字段 disabled）。
2. `_meta_ov_band` 返回串的标题行插入 `%s`（按钮）。
3. `COMPARE_TMPL` 新增 `.mfx` 样式与 `metaExport(btn)` JS（pretty JSON + Blob 下载 `<doc>_metadata.json`）。

## 验证
- 52_230725：17 键，refs 7 / cspan 8，`json.loads` 通过。
- 40_10569：17 键，refs 19 / cspan 44，`json.loads` 通过。
- 2025_1：metadata 仅 doc/references/citation_spans → 导出 3 键，不报错。
- 浏览器三篇点击均无 console error；test_pipeline 12/12；compileall OK；out 哈希 mismatch 0。

## 遗留 / 注意
- 浏览器沙箱未落盘，未产出真实 .json 文件；载荷已由 Python `html.unescape` + `json.loads` 在同源 HTML 上验证。
- 与其它 viewer 分支（缩略图/引文索引）同区不冲突：本分支只加 `.mfx` 与 `metaExport`。
- 空字段策略为"按实际存在导出"，不做 schema 补 null；若需固定 schema 另开 task。

## 下一步
Integrator 评审 → merge_check → 合到 main；合并后建议在正式 out（有 metadata 的文档）点一次按钮确认下载文件名为 `<doc>_metadata.json`。
