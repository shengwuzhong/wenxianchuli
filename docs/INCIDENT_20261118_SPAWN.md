# 2026-11-18 Windows spawn 引导失败

## 现象

P3 启动后恢复旧排队任务时，多个子进程同时报：

```text
An attempt has been made to start a new process before the current process
has finished its bootstrapping phase.
```

部分子进程 exit code 为 1 或 4294967295；GUI 会立即重新拾取排队任务，形成密集拉起。

## 根因

`gui.Runner` 有多个任务线程，会并发调用 `stages.run_batch()`。Windows 使用
`spawn` 启动子进程；多个线程同时执行 `Process.start()` 时，子进程可能在父进程
主模块 bootstrap 完成前启动，触发上述 `RuntimeError`。

`spawn_probe.py` 用 8 个线程并发跑 `index` 阶段复现了该错误。

## 修复

`stages.py` 增加模块级 `_SPAWN_LOCK`，只串行化 `Process.start()` 这一步；
子进程内部仍并行执行。8 线程探针从“递归重跑/报错”变为 8/8 正常，
`python` 与 `pythonw` 均通过。

## 回退

```powershell
git revert --no-edit <spawn-lock-commit>
```

或回到 P3 标签：

```powershell
git reset --hard gui-workbench-p3-20261118
```

## 恢复步骤

被中断的 12 个任务已标记为 failed（错误 `P3 spawn bootstrapping; 已停止，需手动重跑`），
不会在下次启动时自动恢复。确认后手动选中重跑。
