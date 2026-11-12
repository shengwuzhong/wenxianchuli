# Review — T-20261112-WB-REFS-JA（changes requested）

- 分支：`agent/workbuddy/main` @ `810de5a`
- 复核基线：`main` @ `a838400`（含 GT）
- 复核命令：
  - `py eval/gold_eval.py --pred out_llm_trial/wb_refs_review --doc 2025_1`
  - 同上 `--doc 40_10569` / `--doc 52_230725`
- 预测来源：把 `out/<doc>` 复制到 `out_llm_trial/wb_refs_review`，用 **WorkBuddy 分支代码**跑 `--stage refs`。

## 结论

**不批准合并**，请补一个 follow-up commit。`52_230725` 已达标，`40_10569` 接近达标，但 `2025_1` 未达到用户确认的 GT 验收线。

## 指标（GT vs WorkBuddy 分支）

| doc | pred | gold unique | recall | title_ok | author_ok | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| 2025_1 | 21 | 34 | **0.618** | **0.294** | **0.618** | 不通过 |
| 40_10569 | 19 | 19 | 0.947 | 0.789 | 0.947 | 接近（缺 #16） |
| 52_230725 | 7 | 7 | **1.000** | 0.857 | **1.000** | 通过 |

## 2025_1 缺失的 13 条（GT 编号）

`5, 8, 13, 18, 24, 25, 28, 29, 31, 32, 33, 34, 35`

- 第 17 页 `u16_3` 的 13 条基本全丢（只出 Patria/Reimer/受付 3 条）；
- 第 16 页 `u15_4` 缺 `#5 堀川`, `#8 石田`, `#13 木村 2013`, `#18 三田村`。

## 根因（代码级）

1. **`_split_entries_block` 的“按行切”是 all-or-nothing**
   `metapy/refs.py:47-49`：
   ```python
   lines = [...]
   if len(lines) >= 2 and all(_ja_line_selfcontained(ln) for ln in lines):
       按行切
   ```
   `u16_3` 同时含文献行、`キーワード`、`奈良盆地…`、`The eastern…`、`(2025年10月31日受理)`，`all()` 为假 → 落到 authoryear 分支；`_JA_AY_HEAD` 只认「短姓名+(年)」，只切出 3 条。
   要求：**逐行判定 + 续行合并**，不能要求整块 every line 都是文献；关键词/受付/页眉页脚行要显式剔除或终止。

2. **`u15_4` 的 4 条被过滤**
   `#5/#8/#13/#18` 都是标准日文 `著者, 年, 題名, 誌名, 巻, 頁`；目前被 `_entry_like`/`_looks_cite`/`_ja_line_selfcontained` 之一拒掉。需要按行拆时逐行放行，不要用整块结果反推。

3. **英文条目 title 被填成 journal**
   `Furutani/Hongo/Huzita/Kimura/Neal` 的 `title` 现在是 `Journal of Geosciences...` / `Review...` / `Earth-Science Reviews`，说明 `_ja_reference_fields` 的式 A 把 `Title. Journal, vol, pages` 的 Title 丢了，source 占了 title。
   要求：`Author, year, Title. Journal, vol, pages` 必须优先取 Title；可参考 `52_230725` 已修好的 `Boersch` 条。

4. **页脚/关键词污染**
   `Sumirah` 条的 title 变成 `年10月31日受理`，year=2025；`u16_3` 尾部的 `キーワード`/受付行被当成条目。
   要求：在条目收集阶段遇到 `キーワード`、`(20xx年x月x日受付)`、`(20xx年x月x日受理)` 即终止/跳过。

## 非阻塞问题（可后续）

- `40_10569 #16`（Tokunaga 2014）缺失：英文 6 作者 + 长作者段；若修 2025_1 时顺手处理，可到 19/19。
- `40_10569 #1/#12` 书名式条目的 title 含出版地/出版社残留；用户说其他字段允许噪声，暂不阻塞。
- `52_230302 42→43` 是修日文条目的正向结果；19 作者英文条粘连是既有 bug，另开任务。
- `2025_1` 的 journal/volume/issue 是 `issue` 阶段的问题，不是 refs 任务；但 2025_1 目前无正式 metadata，复测时只看 refs。

## 复测要求

```powershell
# 1) 把 WorkBuddy 分支代码跑在临时副本上
py metadata.py 2025_1 --out out_llm_trial/wb_refs_ja_eval --stage refs

# 2) GT 复测
py eval/gold_eval.py --pred out_llm_trial/wb_refs_ja_eval --doc 2025_1
py eval/gold_eval.py --pred out_llm_trial/wb_refs_ja_eval --doc 52_230725

# 3) 通过线
# 2025_1: recall=1.000 (34/34 unique), title_ok>=0.90, author_ok>=0.60
# 52_230725: recall=1.000, title_ok>=0.85, author_ok>=0.90
# 40_10569: recall>=0.947（最好 1.000）
```

## 备注

- `2025_1` 的 GT 是 35 条（34 唯一；#22 与 #6 原文重复）。recall 分母按 34；如果 WorkBuddy 输出 35 条含重复，也接受。
- GT 文件：`eval/ja_gold.json`；说明：`docs/JA_GOLD_2026-11-12.md`。
