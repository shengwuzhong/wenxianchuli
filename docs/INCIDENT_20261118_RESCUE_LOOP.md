# 2026-11-18 自动补跑死循环事件

## 现象

浏览器工作台任务列表在 2 秒内反复出现同一篇：

- 文档：`26_Supplement_26_229`
- 状态：`部分异常` / `运行中`
- 任务数：短时间累积 21 个同一文档的任务
- 产物：`out/26_Supplement_26_229/index.html`、`metadata.json` 的修改时间持续刷新

## 根因

`webapp.py` 的 `watch_uploads()` 每 2 秒调用一次 `rescue_scan()`。

`rescue_scan()` 的判定是：

1. `out/<doc>/index.html` 已存在；
2. `raw/<channel>` 与 `raw/<channel>_api` 都不存在；
3. `uploads/<doc>.pdf` 还在。

`26_Supplement_26_229` 满足以上条件：`raw/` 只有 `mineru_api` 和 `paddle_api`，没有 dots 产物。

旧逻辑只做“活动任务去重”：

```python
if not _create_job_if_absent(jid, d, rescue=",".join(miss)):
    continue
```

任务很快失败后就不再是活动任务，于是下一次 2 秒扫描又创建一个完整 pipeline 任务，形成：

```text
扫描发现 dots 缺失 -> 新建任务 -> 快速失败 -> 仍缺 dots -> 再新建任务 -> ...
```

`RUN_LOCK.locked()` 在扫描到提交之间存在竞态，不能作为熔断。

## 触发条件

GUI 的「浏览器工作台」按钮会启动 `webapp.py`。两个进程都会监视 `uploads/`，且 webapp 会自动补跑缺失渠道；同一篇文档因此被反复提交。

## 修复

`webapp.py`：

- `rescue_scan()` 增加 30 秒扫描节流；
- 同一文档两次自动补跑至少间隔 600 秒；
- 同一文档累计自动补跑 3 次后停止，并提示人工检查渠道；
- 渠道补齐后清空该文档的熔断计数；
- 新增 `_rescue_allowed()` / `_rescue_mark()`，逻辑可单测。

`gui.py`：

- 检测到 8765 已有旧 webapp 时，拒绝并行打开并提示先结束 `webapp.py`；
- 启动旧 webapp 前弹出风险确认，默认「否」。

## 验证

`test_webapp_rescue.py`：

- 冷却与 3 次上限；
- 不同文档互不影响；
- 同一文档连续扫描 5 次只提交 1 次。

## 恢复

1. 结束 `webapp.py` / `gui.py` 进程；
2. 删除残留 `_server.lock`、`.locks/ocr_api/slot_0`（确认 PID 已不存在）；
3. 用桌面 GUI 重新启动，不要同时开旧浏览器工作台；
4. `26_Supplement_26_229` 当前产物已快照到 `versions/26_Supplement_26_229/20261118-151516`；如需补齐 dots，请在 GUI 中确认渠道可用后只补该缺失渠道。
