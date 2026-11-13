# Review — T-20261112-WB-REFS-JA（round 3，approve）

- 分支：`agent/workbuddy/main` @ `ed01fc0`（代码 `ddd8621`）
- 基线：`main` @ `e71f2a5`
- 复核：复制 `out/` 到 `out_llm_trial/wb_refs_review3`，用 WorkBuddy 分支代码跑 `--stage refs`，再用 `eval/gold_eval.py` 比对。
- 结论：**Approve**。

## 指标

| doc | pred | GT 唯一 | recall | title_ok | author_ok | author 为空 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2025_1 | 35 | 34 | **1.000** | 0.912 | **1.000** | **0** | PASS |
| 40_10569 | 19 | 19 | 0.947 | 0.789 | 0.947 | 0 | PASS（#16 非阻塞） |
| 52_230725 | 7 | 7 | **1.000** | 0.857 | **1.000** | 0 | PASS |

兼容计数：42_185 18、42_93 49、5_55 33、52_230302 43，均不变。

## #24 / #25 复核

- `2025_1 #24`：`authors_raw` = 西岡芳晴，尾崎正紀，寒川旭，山元孝広，宮地良典；`year=2001`；`raw` 截止 `141p.`；`doi=null`，不再含 AGERS。
- `2025_1 #25`：`authors_raw` = 尾崎正紀，寒川旭，宮崎一博，西岡芳晴，宮地良典，竹内圭史，田口雄作；`year=2000`。
- `2025_1` 35 条作者均非空；`author_empty=[]`。

## 测试与哈希

- `metapy.refs` 48/48 PASS
- `test_pipeline.py` 12/12 OK
- `compileall` OK；`ner_lite selfcheck` OK
- 正式 `out/` 1151 文件，哈希仍 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`

## 非阻塞残余

- 2025_1 #14 増田副题、#27 Patria 截断、#34 Sumirah 缺 `, Riau Province`：title_ok 0.912，仍过 ≥0.90；不阻塞。
- 40_10569 #16 Tokunaga 缺 1 条：recall 0.947，沿用上轮非阻塞结论。
- 42_93 有 1 条既有 author 为空（Neves 2022），非本轮引入。
