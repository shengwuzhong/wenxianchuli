# 文档导航

## 先读什么

| 顺序 | 文档 | 适合谁 |
| --- | --- | --- |
| 1 | [../README.zh-CN.md](../README.zh-CN.md) / [../README.md](../README.md) | 第一次接触项目 |
| 2 | [features.md](features.md) | 想知道工具具体能做什么 |
| 3 | [project-structure.md](project-structure.md) | 想找代码/目录 |
| 4 | [architecture.md](architecture.md) | 想理解主流程 |
| 5 | [channels.md](channels.md) / [calibration.md](calibration.md) | 要接 OCR 渠道、校坐标 |
| 6 | [../eval/](../eval/) / [evaluation/ja-gold.md](evaluation/ja-gold.md) | 要评测字段/版面准确率 |
| 7 | [changes-since-baseline.md](changes-since-baseline.md) | 想知道相对原版新增了什么 |

## 开发/内部记录

| 文档 | 内容 |
| --- | --- |
| [internal/rules.md](internal/rules.md) | 工作规则 |
| [internal/review-log.md](internal/review-log.md) | 历史评审记录 |
| [internal/review-metadata-anomalies.md](internal/review-metadata-anomalies.md) | 元数据异常案例 |
| [internal/task-ner.md](internal/task-ner.md) | NER 任务说明 |
| [internal/ja-improvement-plan.md](internal/ja-improvement-plan.md) | 日文改进计划 |
| [evaluation/ja-gold.md](evaluation/ja-gold.md) | 日文金标准说明 |
| [../coordination/README.md](../coordination/README.md) | 多工具协作协议与任务记录 |

## 命名和格式

- 文档统一 `kebab-case.md`；
- 日期不再写入文件名，写在标题或提交记录里；
- 运行产物不进入文档目录；
- 评测数据放 `eval/`，报告放 `eval/reports/`；
- 示例产物放 `examples/`。

## 当前功能边界

当前默认界面只保留：

- 三渠道 1:3 对照；
- metadata 字段面板；
- 参考文献表；
- 引文索引；
- 实体复核队列。

缩略图、全局搜索、翻译切换、多套导出、layout 诊断按钮、块框叠加已从默认界面移除。详见 [features.md](features.md)。
