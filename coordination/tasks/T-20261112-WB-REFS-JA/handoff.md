# Handoff — T-20261112-WB-REFS-JA（round 2 定向修复）

- 工具：workbuddy
- 分支：agent/workbuddy/main
- Base：e71f2a5
- 本轮代码 commit：ddd8621
- 改动：仅 `metapy/refs.py`
- 状态：review，handoff_to=deepseek

## 结论

PASS。2025_1 两条空作者记录均已修复，author 为空数从 2 降为 0；三篇 GT 验收线及四篇兼容计数全部通过。

## #24 / #25 before → after

| GT | before | after |
| --- | --- | --- |
| 2025_1 #24 西岡等「桜井地域の地質」 | `authors=[]`、`authors_raw=null`、`year=2018`、误带 AGERS DOI | 5 位作者完整，`year=2001`、`doi=null`；raw 截止 `141p.`，不含 AGERS/DOI |
| 2025_1 #25 尾崎等「奈良地域の地質」 | `authors=[]`、`authors_raw=null` | 7 位作者完整，`year=2000` |

实现：日文引号分支定位第一个完整 `「…」/『…』`，取题名前最近的 19xx/20xx，并将年份前全部作者段交给作者切分；AGERS 续行遇到当前日文引号条目时不再并入，无法回接上一页 Sumirah 时丢弃。Sumirah 的 `year=2018` 保持不变。

## author 为空检查

```text
author_empty=[]
```

2025_1 共 35 条（含重复），所有条目均有 `authors_raw` 或 `authors`。

## 三篇 GT 指标

| doc | recall | title_ok | author_ok | 结果 |
| --- | ---: | ---: | ---: | --- |
| 2025_1 | 1.000（35/34） | 0.912 | 1.000 | PASS |
| 40_10569 | 0.947（18/19） | 0.789 | 0.947 | PASS，无下降 |
| 52_230725 | 1.000（7/7） | 0.857 | 1.000 | PASS，无下降 |

## 兼容计数

| doc | 预期 | 实际 |
| --- | ---: | ---: |
| 42_185 | 18 | 18 |
| 42_93 | 49 | 49 |
| 5_55 | 33 | 33 |
| 52_230302 | 43 | 43 |

## 测试与哈希

- `py -m metapy.refs`：48/48 PASS。
- `py -m unittest -v test_pipeline.py`：12/12 OK。
- `py -m compileall -q metapy/refs.py metapy/common.py regress.py`：OK。
- `py -c "import ner_lite; assert ner_lite.selfcheck()==0"`：OK。
- 正式 `out/`：1151 文件，前后 SHA-256 均为 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`。
- 所有生成结果仅写入 `out_llm_trial/wb_refs_ja_eval3/`，未写正式 `out/`。

## 残余

- 40_10569 #16 Tokunaga 仍缺 1 条，recall=0.947，沿用 review 的非阻塞结论。
- 2025_1 増田副题、Patria 截断、Sumirah 题名缺 `Riau Province` 为既有非阻塞题名噪声；本轮未扩大范围。
