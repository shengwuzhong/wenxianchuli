# 相对基线的变更清单

## 判断依据

- 基线：Git tag `baseline-2026-11-12`
- 当前：`main` 最新提交
- 对照命令：

```bash
git diff --name-status baseline-2026-11-12..HEAD
git diff --stat baseline-2026-11-12..HEAD
```

说明：`baseline-2026-11-12` 是协作基线，不代表正式产品版本；如果你的“原有版本”指另一个 commit/tag，请提供，我会重新生成对照。

## 新增文件

### 核心代码

| 文件 | 用途 | 标注 |
| --- | --- | --- |
| `metapy/normalize.py` | 日文文本规范化核心：NFKC、旧字体、送假名、DOI/KAKENHI/术语保护、raw↔normalized 映射 | **新增** |
| `metapy/normalize_meta.py` | metadata 规范化 sidecar：`metadata_normalized.json` | **新增** |
| `eval/gold_eval.py` | 字段金标准比对 | **新增** |
| `eval/validate_gold.py` | 金标准结构校验 | **新增** |
| `eval/layout_eval.py` | 99 页版面检测门禁（recall / false positive） | **新增** |

### 评测数据

| 文件 | 用途 | 标注 |
| --- | --- | --- |
| `eval/ja_gold.json` | 日文字段金标准 | **新增** |
| `eval/layout_gold_99.csv` | 99 页版面真值 | **新增** |
| `eval/reports/*.json` / `*.md` | 评测报告 | **新增** |

### 文档

| 文件 | 用途 | 标注 |
| --- | --- | --- |
| `docs/evaluation/ja-gold.md` | 日文金标准说明（原名 `JA_GOLD_2026-11-12.md`） | **新增/重命名** |
| `docs/internal/ja-improvement-plan.md` | 日文改进计划（原名 `JA_IMPROVEMENT_PLAN_2026-11-12.md`） | **新增/重命名** |
| `docs/README.md` | 文档导航 | **新增** |
| `docs/project-structure.md` | 目录结构与用途 | **新增** |
| `docs/features.md` | 当前功能清单 | **新增** |
| `docs/changes-since-baseline.md` | 本文件 | **新增** |
| `AGENTS.md` | 多工具协作规则 | **新增** |
| `coordination/**` | 任务/评审/合并/锁记录（开发用，运行不需要） | **新增** |

### 文档重命名

| 原名 | 新名 |
| --- | --- |
| `docs/RULES.md` | `docs/internal/rules.md` |
| `docs/REVIEW.md` | `docs/internal/review-log.md` |
| `docs/REVIEW_METADATA_ANOMALIES.md` | `docs/internal/review-metadata-anomalies.md` |
| `docs/TASK_NER.md` | `docs/internal/task-ner.md` |
| `docs/JA_GOLD_2026-11-12.md` | `docs/evaluation/ja-gold.md` |
| `docs/JA_IMPROVEMENT_PLAN_2026-11-12.md` | `docs/internal/ja-improvement-plan.md` |

## 新增/增强功能

| 功能 | 说明 | 标注 |
| --- | --- | --- |
| 日文作者/机构增强 | 作者切分、上标清洗、机构 marker 对齐 | **新增** |
| 英文摘要日文残留闸门 | `2025_1` 假名 11→0 | **新增** |
| 日文 issue 抽取 | journal 11/11；J-STAGE DOI 卷期；日文关键词 | **新增** |
| 日文参考文献 | `2025_1` 35/35、`40_10569` 19/19、`42_185` 18/18 | **新增/增强** |
| 日文引文句 | 全角括注、作者-年份、回链、去重 | **新增** |
| 日文版面 V2 | 99 页真值 85/85 double，0 假阳性 | **新增** |
| 阅读序修复 | 13 个新增双栏页反转 36→0 | **新增** |
| 可选实体 v2 | funding/software/datasets，evidence 约束 | **增强** |
| 实体复核队列 | 缺失/低置信/未回链，点击定位 | **新增** |
| 引文索引 | 按页/句聚合，支持定位 | **新增** |
| normalizer | 核心 + sidecar + `metadata.py --stage normalize` | **新增** |
| 评测门禁 | 字段金标准、版面 recall/fp | **新增** |

## 相对基线修改的现有文件

- `merge_out.py`：阅读序/合并修正；
- `metadata.py`：新增 `normalize` stage；
- `metapy/abs.py`、`front.py`、`issue.py`、`refs.py`、`cspan.py`、`layout_ja.py`、`entity.py`、`common.py`：日文抽取与清洗增强；
- `pipeline.py`、`pipeline_io.py`、`viewer.py`、`webapp.py`：渠道/查看器/工作台增强；
- `test_pipeline.py`、`regress.py`：回归覆盖；
- `README.md`、`README.zh-CN.md`：文档更新；
- `.gitignore`：运行产物与私有配置忽略。

## 上游 84f9b47 新增模块

2026-11-13 从原作者仓库拉取并合入以下新模块：

| 文件 | 用途 | 标注 |
| --- | --- | --- |
| `gui.py` / `dashboard.css` / `启动GUI.bat` | 桌面 GUI 工作台 | **上游新增** |
| `stages.py` | 阶段级重跑 | **上游新增** |
| `qc.py` | 质检/不变量检查 | **上游新增** |
| `archive.py` | 产物归档 | **上游新增** |
| `crossproc.py` | 并发/跨进程 | **上游新增** |
| `docid.py` | 文档编号 | **上游新增** |
| `metapy/audit_invariant.py` | 不变量审计 | **上游新增** |
| `metapy/audit_value.py` | 字段值后验审计 | **上游新增** |
| `examples/13625974/metadata*.json` | 示例 metadata/audit | **上游新增** |

**未直接采用**上游对 `pipeline.py`、`webapp.py`、`metadata.py`、`viewer.py` 等核心文件的重构，因为这些文件与本地日文抽取、复核队列、normalizer 改动直接冲突；当前保留本地主链，上游新增模块作为独立工具合入。

## 当前剔除的功能

以下功能曾实现，但在“实体抽取准确性优先”的整理中从默认界面移除：

- 逐页缩略图导航；
- 全局搜索；
- 中文译文切换；
- refs CSV/BibTeX 导出；
- 元数据 JSON 导出；
- 引文 CSV 导出；
- layout 诊断按钮；
- 块框叠加；
- Web 默认 frefs 阶段。

`metapy/refs.py` 中仍保留 frefs 实现，CLI 可用，但 Web 默认不跑。
