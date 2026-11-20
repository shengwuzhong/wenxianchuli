# T-20261120-WB-NERPATH · NER 产物路径归位：凭据与回滚说明

> 工具：WorkBuddy ｜ 执行时间：2026-11-20 09:52（本地）｜ 关联代码：`ner_lite.py`（`_leaf()`）

## 1. 为什么动

`stages._st_ner` 把**区根** `out_llm_trial` 传给 `ner_lite.write_outputs(dst=...)`，而该函数把 `dst` 当最终目录，
产物因此落到 `out_llm_trial/<doc>/`；但 `stages.ARTIFACTS["ner"]`、`gui._ner_done`、`entview.cells_for`
只认 `out_llm_trial/fds_extract/ner_lite/<doc>/ner_lite.json`。后果是阶段日志显示 ok、GUI 的 NER 列恒为“未跑”。

代码侧修法：`ner_lite._leaf()` 归一产物根（区根自动补 `fds_extract/ner_lite`，叶子直传幂等），
`selfcheck` 增第 9 项断言防回归。数据侧修法：把历史错位目录搬回标准位置，即本文件记录的这次操作。

## 2. 做了什么（事实）

| 项 | 值 |
| --- | --- |
| 操作 | 每篇一个目录整体 `os.rename`（同卷），**不拷贝、不合并、不覆盖** |
| 迁移条数 | 204 |
| 拒绝（目标已存在） | 0 |
| 失败 | 0 |
| 迁移前叶子目录数 | 106 |
| 迁移后叶子目录数 | 310 |
| 迁移后顶层残留 NER 目录 | 0 |

迁移后新跑 1 篇（`00214_jjrt_66_11_66_11_1485`，端到端验证落点与模型），故快照为 **311** 篇。

## 3. 能证明什么

1. **没有漏迁**：`tools/ner_migrate.py --plan` 现网干跑 = `待迁 0 篇`；顶层不含任何 `ner_lite.json` 的文档目录。
2. **没有错迁**：快照内 311 篇的 `ner_lite_audit.json` 中 `doc` 字段与目录名 **311/311 一致**（`doc_name_mismatch: []`）。
3. **内容未被改动**：snapshot 记录了每篇 3 个文件的 `bytes + sha256`，`--verify` 重算结果
   `缺失 0 / 新增 0 / 变更 0`。每篇文件数恒为 3（`ner_lite.json` / `ner_lite_audit.json` / `_audit.html`）。
4. **数量自洽**：`106（迁移前）+ 204（迁移）= 310（迁移后）`，与两次独立命令的输出一致。
5. **来源一致**：311 篇 audit 的 `model` 全为 `DeepSeek-V4.1-Flash`（zjlab-maas 通道）。

## 4. 不能证明什么（缺口，如实记录）

- 这次迁移**是先用一段临时脚本执行的，没有 write-ahead 日志**，所以**逐篇 `src → dst` 的对应表事后无法从磁盘反推**：
  同卷 rename 会保留目录的 `ctime`/`mtime`（已实测：`50_1_50_1_25` 的 ctime=11-19 10:06，`00012_...` 的 ctime=11-19 14:57，
  两者都等于其内容时间，不带“是否被移动”的痕迹）。
- 因此 `coordination/migrations/T-20261120-WB-NERPATH.json` 的性质是**迁移后现状快照 + 完整性校验依据**，
  **不是当时的迁移日志**。它的 `migration.manifest_nature` 字段已显式标注这一点。
- 字段语义（避免误读）：`dst` = 现路径，确定；`candidate_src` = 该篇若曾错位、当时应在的源路径，属**推断**，
  配 `src_verified: false`；`file_count` / `total_bytes` / `files[].sha256` 均为实测。故本文件不能驱动逐篇回滚，
  回滚走 `--relocate-top` 的全量对称往返（§5.2）。
- 也无法用 `gui_runs.jsonl` 反推：历史里 `ner` 阶段 `ok` 的去重文档是 302 篇 ≠ 204，说明早期版本的 `_st_ner`
  曾写对过路径，两类来源在产物上不可区分。

这个缺口是流程性的，不是数据性的：缺口影响“能否逐篇还原当时的动作”，不影响“现在的数据是否完整、是否正确”。

## 5. 回滚

### 5.1 需要回滚的是什么

代码修复**不建议回滚**——回滚代码等于恢复“跑成功但看不见”的坏状态。真正可回滚的只有路径布局。

### 5.2 脚本化回滚（可逆、可校验）

```bash
# 0) 先验一遍现状，确认基线没漂
python tools/ner_migrate.py --verify coordination/migrations/T-20261120-WB-NERPATH.json
#    期望: 缺失 0 / 新增 0 / 变更 0   (exit 0)

# 1) 干跑：看会搬哪些（默认不动盘）
python tools/ner_migrate.py --relocate-top coordination/migrations/T-20261120-WB-NERPATH.json
#    实测: 拟搬回顶层 311 篇；顶层撞名 0 条

# 2) 真回滚（把叶子产物整体搬回 out_llm_trial/<doc>/，即迁移前布局）
python tools/ner_migrate.py --relocate-top coordination/migrations/T-20261120-WB-NERPATH.json \
    --apply -m coordination/migrations/T-20261120-WB-NERPATH.rollback.jsonl

# 3) 反悔：用 rollback 日志再搬回来（同一套写前日志，幂等）
python tools/ner_migrate.py --apply -m coordination/migrations/T-20261120-WB-NERPATH.redo.jsonl
```

注意第 2 步的代价：`--relocate-top` 按快照**全量**搬，会把原本就在叶子里的 106 篇也一起搬到顶层——
因为缺口（§4）使得“哪 204 篇”无法区分。全量上移 ↔ 全量下移是**对称且可校验**的往返：
搬回来后再跑 `--verify`，仍应得到 `缺失 0 / 新增 0 / 变更 0`（`--self-test` 已把这条往返写成断言）。

回滚后的现实影响：GUI 的 NER 列会重新全部显示“未跑”，实体视图变空——这正是修复前的状态。

### 5.3 单篇回滚（不依赖脚本）

```bash
move "out_llm_trial\fds_extract\ner_lite\<doc>" "out_llm_trial\<doc>"
```

搬完必须满足：目录内仍是 3 个文件；`ner_lite_audit.json` 的 `doc` 等于目录名；`ner_lite.json` 可解析。

## 6. 复现与自检

```bash
python tools/ner_migrate.py --self-test
# self-test OK: plan/apply/快照/校验/回滚/整体搬回 全通
python ner_lite.py selfcheck
# selfcheck OK: {... "records": 5 ...}
```

`--self-test` 在临时目录里构造“2 篇错位 + 1 篇正确 + 1 个非产物目录（check3）”，断言：
只迁 2 篇、不碰 check3、快照含 3 篇、`--verify` 零差异、`--rollback` 往返后校验和不变、
`--relocate-top` 全量上移再下移后原快照仍逐字节成立。

## 7. 以后同类迁移的规矩（脚本已内置）

1. `--apply` 必须带 `-m <manifest.jsonl>`，**先落账再 rename**（write-ahead，崩溃可续跑/可回退）。
2. 默认 dry-run；目标已存在一律拒绝，不合并、不覆盖。
3. 单目录整体 rename，不逐文件拷贝。
4. 迁完立刻 `--verify`，把 `sha256` 差异贴进交接。
