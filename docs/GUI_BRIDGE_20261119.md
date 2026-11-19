# 本地任务台（GUI 旁挂）— 2026-11-19

## 目标

上游 `gui.py` 继续作为主界面（元数据、质检、笔记、entview）。
本地 A/B 分区、任务库、Paddle 账号额度、自动导入作为**旁挂任务台**接入，
不重写上游主表，不把 3900 行 GUI 推倒重来。

## 入口

主界面工具栏新增「本地任务」。

- A 区：`out/`、`uploads/`
- B 区：`zones/zone_b/out/`、`zones/zone_b/uploads/`
- 任务库：A `.workbench/state_a.db`；B `zones/zone_b/.workbench/state.db`
- 账号：`.workbench/accounts.json`
- 额度：`.workbench/quota.json`

## 文件

| 文件 | 作用 |
| --- | --- |
| `workbench_runner.py` | 无 Tk 的 `Runner` / `RunnerHub`：持久队列、账号、额度、快照、子进程 |
| `local_task_window.py` | 任务台与账号额度窗口 |
| `gui.py` | 仅新增按钮和 `_open_local_tasks`，主表逻辑未改 |
| `test_workbench_runner.py` | 扫描状态、账号分配/Hub 关闭测试 |

## 行为

- 任务台启动时 A/B 两个 Runner 均为暂停；手动「开始解析」或「继续」才会跑。
- 「自动监视 uploads」默认关闭；打开后只处理基线之后的新文件，历史文件不自动跑。
- 提交前按 PDF 页数预扣本地额度；超过当前账号余额会拒绝并提示。
- 账号切换只影响**新任务**；已排队任务保留入队时的 account key。
- 每次覆盖式重跑前调用 `wb.snapshot_doc`；快照失败则拒绝覆盖。
- 同一篇已有活子进程（`.run.lock` PID 存活）时不会重复提交。
- 任务台关闭时暂停两个 Runner；子进程由 Runner 自己收尾。

## 验收

- 全量测试：`139 tests OK (skipped=30)`。
- 侧车烟雾：`SIDECAR_ROWS 282`、`ZONES ['A','B']`、`ACCOUNTS ['pp','primary']`、
  `SIDECAR_SMOKE_OK`；未触发 OCR/网络。
- 截图：`_backups/gui-bridge-20261119/sidecar.png`（1080x620）。

## 回退

回退点：tag `pre-gui-bridge-20261119`（`ff38c82`）。

- 仅撤销侧车：`git revert <sidecar-commit>`；
- 彻底回到合并后状态：`git reset --hard pre-gui-bridge-20261119`（会丢未提交改动，先备份）。

侧车没有改 `out/`/`zones/` 数据；回退代码不会移动产物，但任务库/额度文件仍在
`.workbench/` 与 `zones/zone_b/.workbench/`，可保留或按需备份。

## 已知限制

- 上游主表不直接显示本地 TaskStore 状态；任务台是独立窗口。
- B 区由本地任务台写，上游 workspace 只读展示；不要同时用两套入口跑同一篇。
- 自动导入默认关闭，先手动验证。
- 额度是本地预扣，不是 AI Studio 服务端用量；服务端用量仍需控制台核对。
- 26/43_2 的 dots 缺失不在侧车修复范围；按两渠道降级，等服务恢复再手动补。
