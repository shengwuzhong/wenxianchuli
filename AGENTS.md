# 三工具协作规则（AGENTS.md）

> 适用工具：**DeepSeek（本会话，Integrator）**、**WorkBuddy**、**Trae CN**。
> 每个工具在新会话开始时必须先读本文件，再读 `coordination/README.md`。
> 基线：`c5e8fcc` / tag `baseline-2026-11-12`。不要改写基线历史。

## 0. 一句话规则

**一文件一 owner；同一文件同一时刻只有一个 writer；Git 是唯一事实源；`out/` 是生成物，不是协作对象。**

## 1. 运行模式

- **推荐：同一 Git 仓库 + 三个 worktree**
  - `.worktrees/deepseek`、`.worktrees/workbuddy`、`.worktrees/trae`；
  - 每个工具只在自己的 worktree 里编辑；
  - 通过 `agent/<tool>/...` 分支合并，Integrator 合并到 `main`。
- **兜底：字面同一目录**
  - 同一时刻只允许一个工具持有 `coordination/WRITER.lock`；
  - 其他工具只读；写完释放锁；
  - 没有并行写，只有并行读。

> worktree 模式：`coordination/` 状态默认放**主工作区**。在 worktree 中运行脚本时设置
> `COORD_ROOT=<主工作区>\coordination`、`REPO_ROOT=<当前 worktree>`。文件锁/guard 对
> **共享文件**（`channels.json`、`AGENTS.md`、`coordination/**`）和“字面同一目录”模式最有用；
> 分支内文件由 Git 隔离，跨 worktree 不共享 hash 语义。

已创建（2026-11-12，基线 `4931d6c`）：

| 工具 | 工作树 | 分支 |
| --- | --- | --- |
| DeepSeek | `.worktrees/deepseek` | `agent/deepseek/main` |
| WorkBuddy | `.worktrees/workbuddy` | `agent/workbuddy/main` |
| Trae CN | `.worktrees/trae` | `agent/trae/main` |

每个工具只打开自己的工作树。PowerShell 示例：

```powershell
$main = 'D:\处理工具\2\multidoc-ocr-compare-main'
$env:COORD_ROOT = Join-Path $main 'coordination'
$env:REPO_ROOT  = Join-Path $main '.worktrees\deepseek'
```

## 2. 所有权矩阵

### WorkBuddy（2026-11-12 已改，基线已收）

| 文件 | 说明 |
| --- | --- |
| `metapy/entity.py` | 新增：正文/基金/软件/数据集四类实体补全 |
| `audit_accuracy.py` | 新增：字段准确率自检 |
| `metapy/layout_ja.py` | 新增：日文版面旁路（栏检测/前区/阅读序） |
| `app.js` | 修改：自动跳转双保险 |
| `metapy/issue.py` | 修改：日文期刊/卷/期页眉格式 |
| `pipeline_io.py` | 修改：Paddle 排队超时 7200s→600s 兜底 |
| `regress.py` | 修改：参考文献标题正则补“文献” |
| `metapy/refs.py` | 修改：编号正则补半角右括号 |
| `metapy/cspan.py` | 修改：`^{n}` 上标数字引文 |
| `channels.local.json` | 私有配置：queue_timeout / dots.enabled（**永不提交**） |
| `metapy/abs.py` | 修改：无摘要时置信度标 empty |
| `metapy/common.py` | 修改：JP_SECTION_TAG / JP_AFFIL_HEAD / HEAD_EXCLUDE 扩展 |
| `metapy/front.py` | 修改：日文作者切分/机构脚注/栏目名排除 |
| `unify.py` | 修改：`intra_group` 统一 P20 行高（**冻结例外**，见 §5） |
| `metapy/__init__.py` | 修改：接入 `layout_ja_doc` + CLI stage |
| `webapp.py` | 修改：`run_metadata` 串联加入 `layout_ja` |

### DeepSeek（本会话 / Integrator）

| 文件 | 说明 |
| --- | --- |
| `AGENTS.md`、`coordination/**` | 协作协议、锁/守卫/状态/合并检查 |
| `pipeline.py` | 主编排（只做兼容性维护） |
| `merge_out.py` | 逐页合并（阅读序修复在此做，不碰 `unify.py`） |
| `metadata.py` | 元数据 CLI 壳 |
| `ner_lite.py` | 实体抽取（LLM 提名 + 程序定位） |
| `test_pipeline.py` | 回归测试 |
| `requirements.txt`、`.gitignore`、`.gitattributes`、`.github/**` | 工程配置 |
| `docs/**`、`README*.md`、`PROJECT_ONBOARDING.md` | 文档（如需改，先与 WorkBuddy 协调） |

### Trae CN

| 文件 | 说明 |
| --- | --- |
| `viewer.py` | 单渠道/1:3 查看器 |
| `start.bat`、`start.sh` | 启动包装 |
| 新增静态资源（如 `static/**`、`templates/**`） | 前端资源 |

### Shared / Frozen / Generated

| 类别 | 路径 | 规则 |
| --- | --- | --- |
| Shared | `channels.json` | 只有 Integrator 能改；其他人提交 diff |
| Shared | `examples/**` | 只读；要改先开 task |
| Frozen | `metapy/m3.py` | **全员只读**，不得改 |
| Generated | `out/**`、`out_llm_trial/**`、`uploads/**`、`inbox/**` | 禁止手改；由 pipeline 生成 |
| Generated | `__pycache__/**`、`*.log`、`_server.lock`、`.workbuddy/**`、`.worktrees/**` | 禁止提交 |

> 需要改别人 owner 的文件：**不要直接改**。在 `coordination/tasks/` 开 task，或在 `coordination/patches/` 放 `.patch`，由 owner 应用。

## 3. 开始编辑前（每个任务必做）

1. `git status` 必须干净；脏工作区先处理，不要带着别人的改动开工。
2. `git fetch` + `git rebase main`（在自己的 worktree/分支）。
3. 领取任务：
   ```bash
   python coordination/claim.py create T-YYYYMMDD-NNN --owner <tool> \
       --title "..." --files <逗号分隔的允许文件> 
   python coordination/claim.py set-status T-YYYYMMDD-NNN --owner <tool> --status in_progress
   ```
4. 对每个要改的文件加锁：
   ```bash
   python coordination/lock.py acquire <file> --owner <tool> --task T-... --ttl 1800
   ```
5. 记录 hash：
   ```bash
   python coordination/guard.py record <file> --owner <tool>
   ```
6. 更新自己的 board：
   ```bash
   python coordination/board.py set --tool <tool> --task T-... --state in_progress --files <file>
   ```

## 4. 编辑后 / 交接前

1. `python coordination/guard.py check <file>` 必须通过；不一致立即停止，不要覆盖。
2. 跑测试：
   ```bash
   python -m unittest -v test_pipeline.py
   python -c "import ner_lite; assert ner_lite.selfcheck() == 0"
   python -m compileall -q .
   ```
3. 提交（一个 commit 一件事）：
   ```text
   fix(scope): summary

   Task: T-YYYYMMDD-NNN
   Tool: <tool>
   Base: <base_sha>
   Tests: unittest 10/10; ner_lite selfcheck OK
   ```
4. 写 `coordination/tasks/T-.../handoff.md`：改了什么、验证、遗留、下一步。
5. 更新 task：`set-status ... --status review --handoff-to <tool>`。
6. 释放锁：`python coordination/lock.py release <file> --owner <tool>`。
7. 更新 board：`--state review`。

## 5. 冻结与例外

- `metapy/m3.py`：**永久冻结**，任何工具不得改。
- `unify.py`：原本冻结；WorkBuddy 在 2026-11-12 的 `intra_group` P20 行高改动已由用户确认并纳入基线 `c5e8fcc`。
  - 后续任何 `unify.py` 改动：task 必须写 `--allow-frozen unify.py`；
  - 必须通过 `merge_check.py` + Integrator 审查 + 日文抽检（`52_230725`、`40_10569`）；
  - 没有 `allow_frozen` 的 `unify.py` 改动一律拒绝合并。
- `channels.local.json`：私有配置，**永不提交**；只允许本地修改。

## 6. 文件锁 / hash 守卫

- 锁是协作协议，不是 OS 锁；TTL 默认 1800 秒；每 10 分钟 heartbeat。
- 锁被占用：等待、换任务，或找 owner；**不要删别人的锁**。
- 锁过期：`lock.py acquire` 会移到 `locks/_stale/` 并接管，保留审计。
- hash 不一致：说明别人在你读之后改了文件；停止，重新读，手动合并。
- 写文件用“临时文件 + rename”（脚本已实现）；不要直接截断写。

## 7. 合并 / 评审

- 只有 Integrator 合并到 `main`；工具不直接 push `main`。
- 合并前：
  ```bash
  python coordination/merge_check.py T-... --base main
  ```
  它会检查：review approve、工作区干净、非 main 分支、变更文件在 allowed_files、无 frozen/generated/secrets、测试通过。
- 合并后写 `coordination/merges/T-...json`，打 tag，更新 task `done`。
- 有冲突：文件 owner 解决；跨文件/共享文件由 Integrator 解决；**不要 accept ours/theirs 了事**。

## 8. 禁止事项

- 禁止 `git push --force`、`git reset --hard` 共享分支。
- 禁止对别人的 worktree 执行 `git clean` / `git checkout -- .`。
- 禁止整文件格式化（关闭保存时自动格式化）。
- 禁止手改 `out/`、`out_llm_trial/`、`uploads/`、`inbox/`。
- 禁止提交 `channels.local.json`、`_server.lock`、`__pycache__`、`.workbuddy/`、`.worktrees/`。
- 禁止同时运行两个 `pipeline.py`/`webapp.py` 处理同一文档；实验用 `--out out_agent/<tool>/<doc>`。
- 禁止在未领 task、未加锁的情况下编辑共享文件。

## 9. Git 路径

本机 Git 不在 PATH。统一使用：

```text
D:\workbuddy\resources\vendor\PortableGit\cmd\git.exe
```

或：

```bat
coordination\git.cmd status
```

脚本会自动使用上述路径；如需覆盖，设置环境变量 `GIT_EXE`。

## 10. 升级 / 求助

- 锁冲突、hash 冲突、合并冲突无法解决 → 在 `coordination/board/<tool>.json` 标 `blocked`，并通知 Integrator。
- Integrator 默认是本会话（DeepSeek）；人类保留 `main` 最终合并权与 veto。
