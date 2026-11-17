# 竖排日文处理

## 范围

只作用于**页面级竖排检测**与**字段后处理**，不改变横向论文路径。

## 流程

```text
merged -> unify
  -> vertical   # 竖排题名/作者候选 + 脚注候选
  -> normalize  # normalized 主字段 + sidecar
  -> viewer
```

## 命令

```bash
python stages.py <doc> vertical
python stages.py <doc> vertical,normalize,viewer
```

`pipeline.py` 在元数据阶段后自动执行竖排回写。

## 产物字段

`metadata.json` 可能新增：

```json
{
  "title": {"value": "...", "uid": "...", "confidence": {"source": "vertical_layout"}},
  "title_source": "vertical",
  "vertical_layout": {
    "vertical": true,
    "confidence": 0.98,
    "title_candidates": [],
    "author_candidates": []
  },
  "footnote_candidates": [
    {"page": 1, "uid": "...", "text": "注1 ..."}
  ],
  "reference_candidates": [
    {"page": 14, "uid": "...", "title": "...", "year": "1924", "source": "...", "confidence": "high"}
  ],
  "citation_spans": [
    {"page": 6, "uid": "...", "citation_text": "前掲", "kind": "vertical_inline"}
  ],
  "footnote_count": 1
}
```

有明确题名/来源/年份的高置信注记会写入 `references`，其余只留在
`reference_candidates`；不用说明性注记伪造参考文献。

旧题名/作者保留在：

```text
title_before_vertical
authors_before_vertical
```

## 评测

```bash
python eval/vertical_eval.py \
  --after out \
  --before out_llm_trial/vertical_ab/before_009b5bc \
  --json eval/reports/vertical_10.json \
  --md eval/reports/vertical_10.md
```

GT：

```text
eval/vertical_gold_10.json
```

## 限制

- 题名/作者只读取 `unified/page_0.json`；
- 07 号论文第一页没有作者块，作者为空是已确认结果；
- 只收集有明确标记的脚注候选，不生成 `references`；
- 古典文学论文没有标准参考文献表时，refs 为 0 属于数据事实，不伪造；
- 没有 UI/外观改动。
