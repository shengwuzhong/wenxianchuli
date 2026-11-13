# Handoff — T-20261112-WB-LAYOUT-DETECT

- 工具：workbuddy
- 分支：agent/workbuddy/T-20261112-WB-LAYOUT-DETECT
- Base：b235fbe183020c7094c5a82455eb58200d48e972
- 状态：blocked（两轮验收失败，代码已回退）

## 结论

FAIL。第二轮为 68 double / 31 single，目标仅 11/12 变双栏；42_185 p1 仍 single，另有 17 个已知单栏页被误判。已触发停止条件，未尝试第三方案，`metapy/layout_ja.py` 已恢复至 Base，guard 校验通过。

## 改动

第一轮仅试投几何兜底；第二轮补充“候选线必须划分全部候选块，不得忽略跨线块”。两轮均保留原投票法和 `_order_blocks_ja`。

```text
if vote is None:
  Text/Footnote, width<=0.60W, 非页缘
  x in 0.30W..0.70W; left/right 各至少 1 块
  x 区间分离且 gap>=20px; y 区间重叠
  取 gap 最大、再取最接近中线者
```

`_selftest` 曾加入两栏各 1 块、y 重叠且左栏先读的合成用例；随失败代码一并回退，未保留。

## 12 页 before/after（第二轮）

| doc | page | before | after | boundary x | 左/右块数 | 备注 |
| --- | ---: | --- | --- | ---: | ---: | --- |
| 2025_1 | 7 | single | double | 620 | 1/3 | 目标命中 |
| 2025_1 | 13 | single | double | 620 | 1/2 | 目标命中 |
| 40_10588 | 4 | single | double | 620 | 3/1 | 目标命中 |
| 42_103 | 5 | single | double | 620 | 2/1 | 目标命中 |
| 42_103 | 13 | single | double | 620 | 1/4 | 目标命中 |
| 42_185 | 1 | single | single | - | - | 第二轮仍欠检 |
| 42_185 | 6 | single | double | 620 | 2/1 | 目标命中 |
| 42_93 | 8 | single | double | 620 | 2/1 | 目标命中 |
| 42_93 | 10 | single | double | 620 | 1/4 | 目标命中 |
| 52_230302 | 7 | single | double | 620 | 1/1 | 目标命中 |
| 5_55 | 8 | single | double | 620 | 1/1 | 目标命中 |
| 9_1 | 9 | single | double | 620 | 1/2 | 目标命中 |

## 回归

- 39 个已知双栏：均仍 double，无 double→single；阅读序反转未复测，留 Trae 合并后复测。
- 60 个已知单栏：17 页被误判为 double，验收失败。
- 第二轮变化页：11 个目标页 + 以下 17 个非目标页；42_185 p1 无变化。
- 非目标误判：2025_1 p2/p3/p12；40_10588 p5；42_103 p3；42_185 p4；42_93 p2/p3；43_10814 p1/p3；52_230302 p4；52_230725 p2/p4/p6；9_1 p2/p5/p7/p10。
- 第一轮曾为 75 double / 24 single；第二轮收紧为 68/31，但仍不符合 51/48。

## 测试与哈希

- 两轮均只运行临时副本的 `--stage layout_ja`；第二轮验收失败后按指令停止，未继续运行 selftest/unittest/compileall/ner_lite。
- 正式 `out/` 未写入；1151 文件，前后 SHA-256 均为 `09a8820b6e21dbee3f34c3af19d428ac1672234a7b00c32dd7900a8e2b72b091`。
- 临时候选产物：`out_llm_trial/wb_layout_detect_eval/`；正式代码已回退。

## 残余

规定的几何兜底在真实单栏页上仍会接受满足间隙/y 重叠条件的窄块分组，且无法覆盖 42_185 p1；需要 Integrator 重新判定约束或补充语料规则。本轮不再调阈值、不更换算法、不修改其他 owner 文件。
