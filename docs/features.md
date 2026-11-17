# 功能清单

> 目标：围绕实体抽取的准确性与精度，明确保留、可选和已移除的功能。  
> 标注 `[新增]` 表示相对基线 `baseline-2026-11-12` 新增或实质增强。

## 1. 必需功能

| 功能 | 说明 | 入口 | 状态 |
| --- | --- | --- | --- |
| PDF 页面渲染 | 150dpi 页图，供 OCR 与原文定位 | `pipeline.py` | 保留 |
| 多渠道 OCR | MinerU / dots.ocr / PaddleOCR-VL 三渠道获取与缓存 | `pipeline_io.py` | 保留 |
| 跨页拼接 | `m3` 合并跨页段落 | `metapy/m3.py` | 保留 |
| 统一层 | 三渠道统一坐标/块/置信 | `unify.py` | 保留 |
| 逐页合并 | 跨渠道生成 `merged/` | `merge_out.py` | 保留 |
| 标题 | 日文/英文标题 | `metapy/front.py` | 保留 |
| 作者 | 作者切分、上标、清洗 | `metapy/front.py` | 保留 |
| 机构 | 机构与作者 marker 关联 | `metapy/front.py` | 保留 |
| 摘要 | 日文摘要 + 英文摘要 | `metapy/abs.py` | 保留 |
| 期刊/年/卷/期/页 | 页眉、DOI、J-STAGE 等来源 | `metapy/issue.py` | 保留 |
| 关键词 | 日文 `キーワード` / 英文 Key words 分开 | `metapy/issue.py` | 保留 |
| 正文 | 统一层 + 阅读序输出 | `unify.py` / `metapy/layout_ja.py` | 保留 |
| 参考文献 | 结构化条目、题名/作者/来源/DOI | `metapy/refs.py` | 保留 |
| 引文句 | 全角括注、作者-年份、上标、回链 | `metapy/cspan.py` | 保留 |
| 字段证据 | 每个字段保留 page/uid/bbox/evidence/confidence | `metadata.json` | 保留 |
| 1:3 对照 | 原图 + 三渠道文本对照 | `viewer.py` | 保留 |
| 异常复核队列 | 缺失/低置信/未回链，点击定位原文 | `viewer.py` | `[新增]` |
| 引文索引 | 按页/句聚合引文，点击定位 | `viewer.py` | `[新增]` |
| 金标准评测 | 字段 GT 比对、版面 99 页门禁 | `eval/` | `[新增]` |
| 文本规范化 | NFKC/旧字体/送假名/保护/映射 | `metapy/normalize.py` | `[新增]` |
| 日文分词 | SudachiPy 分词、句子切分、内容词候选；缺依赖时正则降级 | `metapy/ja_tokenize.py` | `[新增]` |
| 元号/日期规范化 | 令和/平成/昭和/大正/明治及 R/H/S/T/M -> 西历；支持年月日 | `metapy/ja_date.py` | `[新增]` |
| 人名/机构规范化 | 姓名/罗马字/机构 key，去邮编和地址，统一法人写法 | `metapy/ja_names.py` | `[新增]` |
| 自动关键词 | 无关键词行时从题名/摘要/正文抽内容词 | `metapy/ja_keywords.py` | `[新增]` |
| 参考文献二次切分 | 修复题名/作者/刊名错位、截断、缺失页卷 | `metapy/ref_split.py` | `[新增]` |
| 引文消歧 | 同書/前掲/ibid/同著者同年；歧义时记 resolve_note | `metapy/cite_resolve.py` | `[新增]` |
| 竖排阅读序 | 竖排检测、右到左分列、列内 y 序；横向路径不变 | `metapy/vertical_layout.py` | `[P0]` |
| 竖排题名/作者候选 | 右列题名打分、作者候选；章节标题排除 | `metapy/front_vertical.py` | `[P1]` |
| 竖排字段回写 | 仅替换明显错误题名、补空作者；raw/旧值保留 | `metapy/vertical_meta.py` | `[P2]` |
| 竖排脚注候选 | 注N/※/＊/〔注〕候选；不伪造 references | `metapy/vertical_notes.py` | `[P3]` |
| 竖排评测 | 10 篇题名/作者/字段 GT + 前后对比 | `eval/vertical_eval.py` | `[P4]` |
| 规范化 sidecar | `metadata_normalized.json` + 主字段 normalized（raw 保留） | `metapy/normalize_meta.py` + `metadata.py --stage normalize` | `[新增]` |

## 2. 可选功能

| 功能 | 说明 | 入口 | 状态 |
| --- | --- | --- | --- |
| 基金抽取 | 科研費/JSPS/KAKENHI/課題番号等，必须有 evidence | `metapy/entity.py` | 可选 |
| 软件抽取 | ImageJ/Fiji/SPSS/GSAS 等，必须有 evidence | `metapy/entity.py` | 可选 |
| 数据集抽取 | PDB/NCBI/UniProt 等，必须有 evidence | `metapy/entity.py` | 可选 |
| LLM 兜底/对照 | 仅在配置可用时启用 | `metapy/llmrep.py` / `metapy/dual.py` | 可选，默认关闭 |
| 脚注文献 frefs | 日文语料多数不适用；Web 默认不再运行 | `metapy/refs.py` | 可选/默认关闭 |

可选实体原则：

- 没有明确原文证据就不输出；
- 不在主界面占固定位置；
- 不为了覆盖率继续扩词典；
- 不把“0 条”当作失败。

## 3. 上游 84f9b47 新增工具

以下来自原作者仓库，已作为独立模块合入；本地核心仍优先保留，因此它们不是默认主链的一部分：

| 功能 | 入口 | 用途 |
| --- | --- | --- |
| 桌面 GUI 工作台 | `gui.py` / `启动GUI.bat` | 图形化选择文档、阶段和渠道 |
| 阶段级重跑 | `stages.py` | 只重跑 refs/front/abs/issue/cspan 等阶段 |
| 质检/不变量 | `qc.py` / `metapy/audit_invariant.py` | 检查产物完整性和字段不变量 |
| 字段值后验审计 | `metapy/audit_value.py` | 对已抽字段做二次校验 |
| 归档 | `archive.py` | 运行产物归档 |
| 并发/跨进程 | `crossproc.py` | 批处理并发与进程协调 |
| 文档编号 | `docid.py` | 统一文档 ID 解析 |
| 上游示例元数据 | `examples/13625974/metadata*.json` | 查看器示例的 metadata/audit |

注意：这些模块可以独立运行。当前合并采用**分层策略**：

- `pipeline.py`、`webapp.py`、`metadata.py`、`pipeline_io.py`、`unify.py`、`app.js` 采用上游新版本；
- `metapy/` 的日文抽取模块（`front/abs/refs/issue/cspan`、`layout_ja`、`entity`、`normalize`）和 `viewer.py` 保留本地版本；
- 因此本地日文能力和复核队列不被上游覆盖。

## 4. 当前查看器保留的交互

- 三渠道 1:3 对照；
- metadata 字段面板；
- 参考文献表；
- 引文索引；
- 实体复核队列；
- 点击字段/引文定位到原文块并高亮。

当前默认界面**不再包含**：

- 逐页缩略图导航；
- 全局搜索；
- 中文译文切换；
- refs CSV/BibTeX 导出；
- 元数据 JSON 导出；
- 引文 CSV 导出；
- layout 诊断按钮；
- 块框叠加。

原因：这些功能与实体抽取精度无直接关系，或属于下游导出/展示，不利于主流程保持简单。

## 5. 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# Web 工作台
python webapp.py
# http://127.0.0.1:8765

# 单文档主流程
python pipeline.py uploads/<doc>.pdf

# 元数据
python metadata.py <doc> --stage refs
python metadata.py <doc> --stage front
python metadata.py <doc> --stage abs
python metadata.py <doc> --stage issue
python metadata.py <doc> --stage cspan
python metadata.py <doc> --stage entity
python metadata.py <doc> --stage normalize

# 评测
python eval/gold_eval.py
python eval/layout_eval.py --pred out --min-recall 1.0 --max-fp 0
```

## 6. 精度相关说明

- `confidence` 是规则/模型置信度，不是人工准确率；
- 实体的真实 precision/recall 必须用 `eval/ja_gold.json` 和人工复核结果计算；
- 基金/软件/数据集是可选实体，不计入必需实体的召回分母；
- 参考文献、引文句应分别统计：
  - 条目召回；
  - 题名准确率；
  - 作者准确率；
  - 回链准确率。
