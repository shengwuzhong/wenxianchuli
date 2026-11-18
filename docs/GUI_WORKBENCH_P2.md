# GUI 工作台 P2：Paddle 账号与日额度

## 目标

P2 只解决一件事：**两个工作区可以独立选择 Paddle 账号，并按账号分别记账 PDF 页额度**。
没有改动 OCR 识别逻辑，也没有自动发起任何 OCR 任务。

## 账号模型

- 账号库：`.workbench/accounts.json`（本地、git 忽略、原子写、尽量 chmod 0600）。
- 一条账号记录：`key`、`label`、`token`、`daily_pages`。
- `key` 创建后不可改；`token` 只在新增时必填，编辑时留空表示保留原 token。
- 两个工作区 A/B 各自映射到一个账号；同一账号可以同时分配给 A、B，此时共用同一份额度。
- 界面上只显示 token 掩码（前 4 位 + `…` + 后 4 位），日志只写账号 key，不写 token。
- 旧的单账号 `.workbench/quota.json` 会自动迁移为 `shared` 账号；首次启动会从
  `PADDLE_API_TOKEN`、`channels.local.json` 或 `channels.json` 读取本机 token，
  生成 `primary` 账号。不会把 token 写进 Git。

## 额度模型

- 额度单位是 **PDF 页**，不是文档数。1000 篇 × 20 页 = 20,000 页。
- 每个账号独立维护 `日额度 / 今日已用 / 剩余`，默认 20,000 页/天，可在账号窗口修改。
- 提交 Paddle 前按 PDF 页数预扣；超过剩余额度直接拒绝提交，不会先跑一半。
- 预扣按 `<工作区>/<文档>` 作为 reservation key；同一文档重复提交不会重复扣。
- 已排队任务保留入队时的账号；切换下拉框只影响**新任务**，不会改旧任务。
- 共享账号的 A/B 两区使用同一份额度账本；独立账号互不影响。

## 界面

主窗口第二行：

- `Paddle 账号` 下拉框：显示账号名称和 key；切换即写入当前工作区映射。
- `账号与额度…`：打开账号库窗口。
- 右侧提示：`key · 今日 used/limit 页 · 余 n · A/B 共用 / 区 A / 未分配`。

账号库窗口：

- 表格列：账号、名称、Token 掩码、日额度、今日已用、剩余、使用区。
- 编辑区：账号 key、名称、日额度（页）、Paddle token（`show="*"`）。
- 操作：新增、保存、删除、刷新、关闭、读取本机配置。
- 删除保护：仍被工作区映射、排队或运行任务使用的账号不能删；至少保留一个账号。
- 底部说明：日额度单位、A/B 共用规则。

## 任务链路

1. `Runner.submit` 把账号 key 写入 SQLite 任务行和内存队列。
2. 子进程启动前，`stages._child_entry` 把该任务的 `paddle_token` 写入子进程环境变量
   `PADDLE_API_TOKEN`；Zone B 不会继承 Zone A 的 token。
3. `_run_one` 找不到账号或 token 时直接失败，错误信息带账号 key，不会静默用错账号。
4. 历史记录带 `account` 字段；任务重启后仍从任务行的 `account` 恢复。

## 文件

- `workbench_state.py`：`QuotaBook`、`QuotaAccount`、`AccountStore`、`mask_token`；
  `TaskStore` 的 `account` 列和旧库迁移。
- `gui.py`：账号下拉、账号窗口、额度预检、启动提示中的账号摘要。
- `stages.py`：子进程按任务注入 `PADDLE_API_TOKEN`。
- `test_workbench_accounts.py`：独立/共享额度、日切换、旧账本迁移、账号增删改、
  任务账号跨重启保留。

## 验证

```powershell
py -3.11 -m py_compile gui.py stages.py workbench_state.py
py -3.11 -m unittest -q test_workbench_accounts.py test_workbench_state.py test_field_audit.py test_pipeline.py
py -3.11 D:\处理工具\2\_backups\gui-workbench-20261118\gui_p2_smoke.py
```

结果：账号/状态 15 个测试、字段 4 个、流水线 36 个，合计 55 个通过；GUI 冒烟通过。
截图：`_backups/gui-workbench-20261118/gui-p2-main.png`、`gui-p2-accounts.png`。

## 回退

- 只回退 P2、保留 P0/P1：`git reset --hard gui-workbench-p1-20261118`；账号下拉消失，旧单账号账本仍可读。
- 只撤销 P2 的单个修复：`git revert --no-edit 2715271`（或对应的 P2 修复提交）。
- 回退到 P0：`git reset --hard gui-workbench-p0-20261118`。
- P2 最终标签：`gui-workbench-p2-20261118`。
- 账号文件是本地运行数据，回退代码不会删除 `.workbench/accounts.json`；
  如需彻底清除，手动删除该文件（会丢失 token 和手工额度设置）。

## 边界与已知限制

- token 是本机明文配置（靠文件权限保护），不是加密保险箱；不要把该文件提交或外发。
- 额度是**预扣账本**，不是服务端账单；Paddle 失败后不会自动退还预扣页数，需按实际使用人工核对。
- 默认日额度 20,000 页来自当前账号策略，服务端可能调整；以控制台为准。
- 账号切换只影响新任务；已排队任务保留原账号，这是有意的可追溯行为。
- 当前不强制 A/B 使用不同账号；同一账号共用额度是允许的。
