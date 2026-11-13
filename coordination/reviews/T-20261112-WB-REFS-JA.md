# Review — T-20261112-WB-REFS-JA（round 2，changes requested）

- 分支：`agent/workbuddy/main` @ `f7719f7`
- 基线：`main` @ `ca52320`（含 GT）
- 复核：把 `out/<doc>` 复制到 `out_llm_trial/wb_refs_review2`，用 WorkBuddy 分支代码跑 `--stage refs`，再用 `eval/gold_eval.py` 比对。
- 结论：**recall 已通过；author Not Null 未通过，需一次小修。**

## 1. 指标

| doc | pred | GT 唯一 | recall | title_ok | author_ok | author 为空 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2025_1 | 35 | 34 | **1.000** | 0.912 | 0.941 | **2** | 条件不通过 |
| 40_10569 | 19 | 19 | 0.947 | 0.789 | 0.947 | 0 | 通过（#16 非阻塞） |
| 52_230725 | 7 | 7 | **1.000** | 0.857 | **1.000** | 0 | 通过 |

测试：`metapy.refs` 48/48；`test_pipeline.py` 12/12；compileall OK；正式 `out/` 哈希仍 `09a8820b…`。

## 2. 阻塞问题

### 2.1 两条 author 为空（Not Null 失败）

2025_1 输出中：

- `西岡芳晴，尾崎正紀，寒川旭，山元孝広，宮地良典，2001，「桜井地域の地質」，地域地質研究報告（5万分の1地質図幅），地質調査所，141p.`
  → `authors=[]`, `authors_raw=null`, `year=2018`, `doi=10.1109/AGERS.2018.8554095`
- `尾崎正紀，寒川旭，宮崎一博，西岡芳晴，宮地良典，竹内圭史，田口雄作，2000，「奈良地域の地質」，地域地質研究報告（5万分の1地質図幅），地質調査所，162p.`
  → `authors=[]`, `authors_raw=null`, `year=2000`

GT 对应 #24/#25，author 必须非空。

### 2.2 #24 的 year/DOI 被 AGERS 续行污染

`u16_3` 的行序是：

```text
西岡芳晴，…，2001，「桜井地域の地質」…
Electronics and Remote Sensing Technology (AGERS), Doi:10.1109/AGERS.2018.8554095
田井昭子，1966a，…
尾崎正紀，…，2000，「奈良地域の地質」…
…
Sumirah, … 2018, Identify depth of peat … IEEE Asia-Pacific Conference on Geoscience,
```

`AGERS` 行是上一页 Sumirah 条目的续行，不是西岡条目的字段；当前被 `_split_entries_block` 并入“西岡”buf，导致 `_year_pick` 取 2018、DOI 挂到西岡，Sumirah 反而没有 DOI。

## 3. 根因

1. `_corner_biblio_fields` 假设 `segs[0]` 是单作者、`segs[1]` 是 `「」`题名：
   ```python
   segs = re.split(u"[,，]", e[:myear.start()])
   article = re.fullmatch(u"「([^」]+)」", segs[1])
   auth0 = segs[0]
   ```
   日文多作者是 `著者1，著者2，…，年，「題名」…`，题名不在 `segs[1]`，函数返回 `{}`，作者为空。

2. `_split_entries_block` 的“续行合并”把 `AGERS` 行并入当前 buf；它没有识别“这是 Sumirah 的跨页/跨栏续行”，也没阻止 DOI 行改写上一条的 year。

## 4. 只做这一处小修（不要重写逐行切分）

### 4.1 修 `_corner_biblio_fields`（或等价日文引号分支）

- 不再假设 `segs[1]` 是题名；在 `e[:myear.start()]`（或整条）里找第一个完整的 `「...」` / `『...』` 作为题名段，记 `ti`。
- `authors_raw = "，".join(segs[:ti])`（或等价：题名前的全部作者段）；`authors = _split_authors(authors_raw, ...)`。
- `year` 取题名段前最近的一个 19xx/20xx；不要把题名后的 DOI 年份当出版年。
- 保留 `layout`/`source`/`publisher` 现有语义；只修 author/year 取值。

### 4.2 修 AGERS 续行归属

- 当续行匹配 `^Electronics and Remote Sensing Technology \(AGERS\)|Doi:10\.1109/AGERS` 且当前 buf 是日文引号条目时，**不要并入当前 buf**。
- 优先把它并入 `Sumirah` 条目；做不到就丢弃该续行（用户允许其他字段噪声，但不能污染 #24 的 year/DOI）。
- 修完后 #24 必须：`authors` 非空（西岡芳晴等）、`year=2001`、`raw` 截止 `141p.`，不出现 AGERS；Sumirah 的 `year=2018` 不变。

### 4.3 不要动的部分

- 不要重写 `_ja_entry_head` / `_REF_STOP` / 逐行切分主逻辑；它们已让 recall 到 1.0。
- 不要改 `eval/ja_gold.json`、`viewer.py`、`test_pipeline.py`、`unify.py`、`m3.py`。
- 不要改 52/40 的已通过结果；52_230302 43 条不变。

## 5. 复测与通过线

```powershell
py metadata.py 2025_1 --out out_llm_trial/wb_refs_ja_eval3 --stage refs
py eval/gold_eval.py --pred out_llm_trial/wb_refs_ja_eval3 --doc 2025_1
py eval/gold_eval.py --pred out_llm_trial/wb_refs_ja_eval3 --doc 52_230725
```

- 2025_1：recall=1.000；**author 为空数=0**；author_ok>=0.90；title_ok>=0.90。
- 52_230725：recall=1.000，title_ok>=0.85，author_ok>=0.90。
- 40_10569：recall>=0.947（#16 仍可非阻塞）。
- 42_185 18、42_93 49、5_55 33、52_230302 43 不变；12/12 测试；out 哈希不变。

## 6. 非阻塞（本次可不修）

- 2025_1 `#14 増田1985` title 缺 `"逆グレーディング構造"：` 前缀。
- `#27 Patria` 英文题名被首个 ASCII 逗号截断。
- `#34 Sumirah` title 缺 `, Riau Province`（原文题名本身在 `Geoscience,` 处截断）。
- 40_10569 `#16 Tokunaga` 缺 1 条（长英文作者段），已在上轮 review 标非阻塞。
