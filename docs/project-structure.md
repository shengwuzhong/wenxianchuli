# 项目目录结构

本文件说明 `multidoc-ocr-compare` 的目录职责，以及哪些目录属于运行产物、开发记录或历史归档。  
目标：让新读者先知道“从哪里开始”，再知道“每个目录为什么存在”。

```text
multidoc-ocr-compare/
├─ README.md                     英文入口
├─ README.zh-CN.md               中文入口
├─ requirements.txt              Python 依赖
├─ start.bat / start.sh          本地启动脚本
├─ pipeline.py                   主流程：渲染 → 取渠道 → 适配 → 合并 → 归一化 → 查看器
├─ pipeline_io.py                渠道获取、坐标适配、缓存、配置读取
├─ unify.py                      三渠道统一层
├─ merge_out.py                  跨渠道逐页合并
├─ metadata.py                   元数据 CLI 入口
├─ webapp.py                     拖拽式 Web 工作台
├─ viewer.py                     单渠道 / 1:3 查看器
├─ app.js                        Web 工作台前端脚本
├─ ner_lite.py                   可选实体抽取（LLM 提名 + 程序定位）
├─ audit_accuracy.py             字段准确率自检
├─ regress.py                    回归辅助脚本
├─ test_pipeline.py              主回归测试
│
├─ metapy/                       元数据实现包
│  ├─ common.py                  共享阈值/日文判定/审计工具
│  ├─ m3.py                      跨页拼接
│  ├─ refs.py                    参考文献 + 脚注文献
│  ├─ front.py                   标题/作者/机构
│  ├─ abs.py                     摘要/英文摘要
│  ├─ issue.py                   期刊/年卷期页/关键词
│  ├─ cspan.py                   行内引文句
│  ├─ layout_ja.py               日文版面/阅读序
│  ├─ entity.py                  基金/软件/数据集（可选）
│  ├─ llmrep.py                  LLM 兜底/报告
│  ├─ dual.py                    LLM 对照实验
│  ├─ normalize.py               日文文本规范化核心
│  └─ normalize_meta.py          metadata 规范化 sidecar
│
├─ eval/                         评测与金标准
│  ├─ gold_eval.py               字段金标准比对
│  ├─ validate_gold.py           金标准结构校验
│  ├─ layout_eval.py             99 页版面检测门禁
│  ├─ ja_gold.json               日文字段金标准
│  ├─ layout_gold_99.csv         99 页版面真值
│  └─ reports/                   评测输出（可复算）
│
├─ docs/                         文档
│  ├─ README.md                  文档导航
│  ├─ project-structure.md       本文件
│  ├─ features.md                功能清单
│  ├─ changes-since-baseline.md  相对基线的变更
│  ├─ architecture.md            架构
│  ├─ channels.md                渠道配置
│  ├─ calibration.md             坐标标定
│  ├─ rules.md                   工作规则
│  ├─ review-log.md              开发评审记录
│  ├─ review-metadata-anomalies.md 元数据异常记录
│  ├─ task-ner.md                NER 任务说明
│  ├─ ja-gold.md                日文金标准说明
│  └─ ja-improvement-plan.md    日文改进计划
│
├─ examples/                     可直接打开的示例产物
│  └─ 13625974/                  11 页韩文期刊示例
│
├─ coordination/                 多工具协作记录（开发用，运行不需要）
├─ _attic/                       历史归档（不参与运行）
├─ .github/                      CI/仓库配置
├─ .gitignore                    运行产物与私有配置忽略规则
│
├─ out/                          [运行产物，不入库] 正式输出
├─ out_preview/                  [运行产物，不入库] 预览输出
├─ out_llm_trial/                [运行产物，不入库] 实验/评测临时输出
├─ uploads/                      [运行产物，不入库] 上传的 PDF
├─ inbox/                        [运行产物，不入库] 渠道产物投放目录
├─ .worktrees/                   [本地开发，不入库] 多工作树
├─ .workbuddy/                   [本地开发，不入库]
└─ __pycache__/                  [运行产物，不入库]
```

## 阅读顺序

1. `README.md` / `README.zh-CN.md`：项目是什么、怎么跑。
2. `docs/features.md`：当前到底有哪些功能，哪些是必需的。
3. `docs/architecture.md`：代码如何分层。
4. `docs/channels.md` + `docs/calibration.md`：接渠道、校坐标。
5. `eval/`：如何判断字段/版面是否正确。
6. `coordination/`：只有参与开发协作时才需要看。

## 命名约定

- Python 文件：`snake_case.py`。
- 文档文件：`kebab-case.md`。
- 配置文件：`channels.json`，本机覆盖用 `channels.local.json`（不入库）。
- 运行产物：只放 `out*/`、`uploads/`、`inbox/`，不要提交。
- 评测数据：放 `eval/`，报告放 `eval/reports/`。
- 不再用带日期的文档文件名；日期写在文档标题或提交记录里。

## 不应提交的内容

`.gitignore` 已覆盖：

- `out/`、`out_preview/`、`out_llm_trial/`
- `uploads/`、`inbox/`
- `channels.local.json`
- `__pycache__/`、`*.pyc`
- `.worktrees/`、`.workbuddy/`
- `coordination/locks/`、`board/`、`guards/`、`runs/`

注意：`out/` 是生成物，GitHub 上不应出现。示例产物放在 `examples/`。
