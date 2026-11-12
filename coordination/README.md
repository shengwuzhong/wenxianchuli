# coordination：三工具协作工作台

本目录只做协作，不参与文档处理逻辑。生产代码在仓库根目录与 `metapy/`。

## 目录

```
coordination/
├── claim.py      领任务 / 改状态
├── lock.py       文件租约锁（TTL + heartbeat + stale 接管）
├── guard.py      编辑前后 sha256 校验（compare-and-swap）
├── board.py      每个工具自己的状态板（单写者）
├── status.py     只读聚合：任务 / 锁 / 状态板
├── merge_check.py 合并前闸门（review / 路径 / 测试）
├── git.cmd       本机 Git 入口（Git 不在 PATH）
├── owners.json   机器可读的所有权矩阵
├── tasks/        任务 JSON（入库）
├── reviews/      评审 JSON（入库）
├── merges/       合并记录（入库）
├── patches/      跨 owner 的补丁交接（入库）
├── locks/        运行期锁（忽略）
├── guards/       运行期 hash（忽略）
├── board/        运行期状态板（忽略）
└── runs/         运行期日志（忽略）
```

## 0. 准备

本机 Git 不在 PATH，统一用：

```bat
coordination\git.cmd --version
```

或在 PowerShell 里：

```powershell
$git = 'D:\workbuddy\resources\vendor\PortableGit\cmd\git.exe'
& $git status
```

脚本会自动找这个路径；可用 `GIT_EXE` 覆盖。

## 1. 每个任务的完整流程

### 1.1 领任务

```bash
python coordination/claim.py create T-20261112-001 \
    --owner deepseek \
    --title "双栏阅读序修复" \
    --priority P1 \
    --files merge_out.py,test_pipeline.py \
    --acceptance "unittest 10/10; 52_230725 首页抽检通过"
```

- `--files` 是**允许改动的文件前缀**，逗号分隔；
- `--forbidden` 追加禁止路径；
- `--allow-frozen unify.py` 只有冻结例外才用；
- 任务已存在时退出码 3，不会覆盖。

### 1.2 开始

```bash
python coordination/claim.py set-status T-20261112-001 --owner deepseek --status in_progress
python coordination/board.py set --tool deepseek --task T-20261112-001 \
    --state in_progress --files merge_out.py
```

### 1.3 加锁 + 记 hash

每个要改的文件：

```bash
python coordination/lock.py acquire merge_out.py --owner deepseek \
    --task T-20261112-001 --ttl 1800
python coordination/guard.py record merge_out.py --owner deepseek
```

> 锁只防同时写；`guard` 防“你读完之后别人又改了”。两者都要。

### 1.4 编辑后

```bash
python coordination/guard.py check merge_out.py
python -m unittest -v test_pipeline.py
python -c "import ner_lite; assert ner_lite.selfcheck() == 0"
python -m compileall -q .
```

hash 不一致时**不要覆盖**：退出码 4，先看 `git diff` / `git log`，重新读、手动合并。

### 1.5 交接

```bash
python coordination/lock.py release merge_out.py --owner deepseek
python coordination/claim.py set-status T-20261112-001 --owner deepseek \
    --status review --handoff-to workbuddy
python coordination/board.py set --tool deepseek --task T-20261112-001 \
    --state review --files merge_out.py
```

并在 `coordination/tasks/T-20261112-001/handoff.md` 写：改了什么、验证、遗留、下一步。

### 1.6 评审

评审人写 `coordination/reviews/T-20261112-001.json`：

```json
{
  "task": "T-20261112-001",
  "reviewer": "workbuddy",
  "verdict": "approve",
  "checks": {
    "scope_match": true,
    "tests_pass": true,
    "no_frozen_changes": true,
    "no_generated_changes": true,
    "no_secrets": true
  },
  "notes": "..."
}
```

### 1.7 合并闸门

```bash
python coordination/merge_check.py T-20261112-001 --base main
```

它检查：

1. task 存在且 `status=review`；
2. `reviews/<task>.json` 存在且 `verdict=approve`；
3. 工作区干净；
4. 当前不是 `main`；
5. 变更文件在 `allowed_files` 内；
6. 没有 `metapy/m3.py`、`out/`、`uploads/`、`channels.local.json`、`out_llm_trial/` 等；
7. `unify.py` 只有在 `allow_frozen` 里才放行；
8. 跑 `test_pipeline.py` + `ner_lite.selfcheck()`（`--no-tests` 可跳过）。

### 1.8 合并后

- `coordination/merges/T-20261112-001.json` 记录 merge commit / tag / 时间；
- `claim.py set-status ... --status done`；
- `board.py set ... --state done`。

## 2. 锁 / 状态命令速查

```bash
python coordination/lock.py list
python coordination/lock.py heartbeat merge_out.py --owner deepseek
python coordination/lock.py release merge_out.py --owner deepseek

python coordination/guard.py list
python coordination/guard.py show merge_out.py

python coordination/board.py show
python coordination/board.py show --tool trae

python coordination/status.py
python coordination/status.py --json
```

## 3. 冲突处理

| 情况 | 处理 |
| --- | --- |
| 锁被占用 | 等 / 换任务；不要删别人的锁 |
| 锁过期 | `acquire` 自动移到 `locks/_stale/` 并接管，保留审计 |
| hash 不一致 | 停止；重新读；手动合并；不要覆盖 |
| Git 冲突（不同行） | 文件 owner 解决；Integrator 复核 |
| Git 冲突（同一语义区） | 回退一方重做；不要 accept ours/theirs 了事 |
| 需要改别人 owner 的文件 | 开 task / 放 patch；不要直接改 |
| 需要改 `unify.py` | task 加 `--allow-frozen unify.py` + Integrator 审查 + 日文抽检 |
| 需要改 `metapy/m3.py` | 不允许；先改规则 |

## 4. 三工具的建议用法

- **DeepSeek**：Integrator；维护 `coordination/`、`pipeline.py`、`merge_out.py`、`metadata.py`、`ner_lite.py`、测试；负责合并。
- **WorkBuddy**：`metapy/`、`pipeline_io.py`、`unify.py`（例外）、`app.js`、`webapp.py`；改前开 task。
- **Trae CN**：`viewer.py`、`start.*`、静态资源；改前开 task。

> owner 矩阵以 `AGENTS.md` 与 `owners.json` 为准；如能力变化，先改这两份文件（Integrator 审）。

## 5. 注意

- 本目录脚本只用 Python 标准库；
- 所有运行期文件都在 `.gitignore` 里（`locks/`、`guards/`、`board/`、`runs/`）；
- `tasks/`、`reviews/`、`merges/`、`patches/` 入库，便于审计；
- 不要把 `channels.local.json`、`out/`、`uploads/`、`out_llm_trial/` 加进 Git。
