# GUI 工作台 P0：双区、持久队列、配额与启动闸门

日期：2026-11-18
范围：桌面工作台 `gui.py`（`启动GUI.bat`），不涉及浏览器 `webapp.py`。

## 回退点

- 标签：`pre-gui-workbench-20261118`
- 基线提交：`44af4a5b97c67528c9463615237ff9a55575aa99`
- 备份目录：`D:\处理工具\2\_backups\gui-workbench-20261118`

回退代码：

```bat
D:\workbuddy\resources\vendor\PortableGit\cmd\git.exe reset --hard pre-gui-workbench-20261118^{}
```

回退只影响代码；`zones/`、`.workbench/`、`versions/` 是运行数据，不会被 Git 回退。
如需连同运行数据回退，先停止 GUI，再手动移动上述目录。

## 已实现

### 1. 两个物理隔离区

| 区 | uploads | out | archive | 状态库 |
| --- | --- | --- | --- | --- |
| A · 主库 | `uploads/` | `out/` | `archive/` | `.workbench/state_a.db` |
| B · 分库 | `zones/zone_b/uploads/` | `zones/zone_b/out/` | `zones/zone_b/archive/` | `zones/zone_b/.workbench/state.db` |

顶部下拉框切换区；两个区各有一个持久队列和运行器，可同时跑。A 区沿用历史目录，
B 区完全在 `zones/zone_b/` 下，NER 产物、任务库、历史、偏好都不共用。

### 2. 启动「继续」闸门

启动后 700ms 弹出窗口，按钮固定为「继续」「暂不继续」：

- 「继续」：恢复两个区的排队/中断任务，并解锁批量执行；
- 「暂不继续」或关闭窗口：只读浏览，所有重跑/重试/缺口按钮禁用；
- 任何提交入口再次检查 `_paused`，不能绕过弹窗直接跑。

### 3. 持久任务队列

每个区一个 SQLite `tasks` 表，记录文档、阶段、清缓存渠道、触发方式、状态、页数、
起止时间、错误。GUI 崩溃或关机后，重新打开可恢复 `queued`/`interrupted` 任务。
同一文档在运行/排队时拒绝重复入队；已在 `out/<doc>/.run.lock` 里记录子进程 PID，
恢复时先检查 PID 是否仍活着，避免重复跑。

### 4. Paddle 页配额

- 账本：`.workbench/quota.json`（A/B 共用一个账号时共用此账本）
- 默认：20,000 页/日
- 提交前按 PDF 页数汇总并预留；页数读不出来时拒绝提交，不绕过配额
- 已有 Paddle 产物的文档不重复预留
- 失败/重试按“最坏情况已消耗”保留预留，日切自动归零

### 5. 重跑缺口

只处理两类缺口：

1. 缺 MinerU / dots / Paddle 产物；
2. 实体抽取状态为 `not_checked` 或 `extraction_failed`。

`absent_confirmed` 和 `not_applicable` 不会被重跑。缺渠道时跑全链但只清缺失渠道缓存；
只有实体缺口时只跑 `ner` 段。提交前显示篇数、Paddle 页数和余额，需人工确认。

### 6. 覆盖前版本快照

任何会写产物的任务执行前，把 `out/<doc>/` 完整复制到：

```text
<区根>/versions/<doc>/<YYYYmmdd-HHMMSS>/
```

并写 `_snapshot.json`。保留最近 3 份。快照失败则拒绝执行，不覆盖现有产物。
这是真实复制，不是硬链接：部分阶段会原地重写文件，硬链接不能保证时间点。

## 验证

```bat
py -3.11 -m py_compile gui.py workbench_state.py stages.py ner_lite.py
py -3.11 -m unittest -q test_workbench_state.py
py -3.11 -m unittest -q test_pipeline.py
```

当前结果：状态测试 9/9，流水线测试 36/36；GUI 双区切换、启动闸门与任务库重开恢复已冒烟。
截图：`D:\处理工具\2\_backups\gui-workbench-20261118\gui-p0.png`。

## 已知限制 / 下一阶段

- 配额账本目前是 `shared` 单账号；每区独立账号与独立日限额属于 P2。
- 「实体」列只显示有/无/失败/未查；完整字段状态、`absent_confirmed` 负证据和人工复核属于 P1。
- 版本快照是整目录真实复制，长期大量重跑会占磁盘；后续可增加按阶段快照或保留策略配置。
- `stages.availability` 已支持区根路径，但其他直接调用全局 `out_llm_trial` 的脚本仍需逐个复核。
