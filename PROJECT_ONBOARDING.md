# 项目快速上手指南（multidoc-ocr-compare）

> 本报告由只读分析 + 一次安全的离线实测生成。除新增本文件、安装三个纯 Python 依赖、生成 `_attic/examples/demo/` 离线产物外，**未改动任何业务代码**。

---

## 1. 项目速览

- **一句话定位**：把同一份 PDF（扫描版学术论文，偏韩/中/英）交给 MinerU、dots.ocr、PaddleOCR-VL 三家 OCR/文档解析引擎，将各自结果映射到**同一坐标系**，逐页逐块并排对照，回答的不是"哪家分高"而是"三家分歧时是文档怪还是某家坏了"（归因 attribution）。
- **主要功能**：
  1. 150dpi 渲染 PDF 页面图（`pipeline_io.render_pages`）
  2. 三路并行获取引擎产物（缓存优先 → 云端 API → MinerU 桌面版 CDP 兜底）
  3. 各引擎坐标统一标定到页图像素空间（`adapt_*`）
  4. 单渠道查看器 `viewer_<channel>.html` + 1:3 对照查看器 `viewer_compare.html`（悬停/点击联动、引用分组、脚注高亮）
  5. 跨渠道逐页合并 `merged/`（`merge_out.py`）+ 跨引擎归并组 `unified/` + 覆盖率指标（`unify.py`）
  6. 结构化元数据抽取（标题/作者/机构/摘要/关键词/参考文献，`metadata.py` + `metapy/`）
  7. 实体抽取（资助/软件/数据集，LLM 提名 + 程序定位，`ner_lite.py`）
  8. 拖拽式 Web 工作台（`webapp.py`，纯标准库，零额外依赖）
- **技术栈**：Python（纯标准库 + 3 个运行依赖），`pypdfium2`（PDF 渲染）、`Pillow`（图片）、`websocket-client`（仅 MinerU 桌面 CDP）；无框架、无数据库、无 Docker、无构建工具。
- **License**：MIT（`LICENSE`）。
- **当前分析的分支/commit**：本地目录**不是 git 仓库**（`.git` 不存在，为直接下载解压的 zip 快照），无法确认精确 commit；README 首页仓库为 `KieranFinn/multidoc-ocr-compare`（**未确认**对应 commit，因 git remote 不可用）。
- **是否推荐本地试用**：**是**。零 token 可离线跑通全链路（合成 demo），有真实 PDF 时仅 `dots` 渠道即可零 token 起步。

---

## 2. 功能地图

| 功能 | 用户入口 | 核心代码位置 | 说明 |
|---|---|---|---|
| 离线冒烟/自检 | `python _attic/examples/make_demo.py` | `_attic/examples/make_demo.py` | 生成合成 PDF + 三家 mock 产物 |
| 三渠道 OCR 主链路 | `python pipeline.py <pdf>` | `pipeline.py::main` | 渲染→获取→适配→合并→归一化→查看器 |
| 页面渲染 | pipeline 内部第①步 | `pipeline_io.py::render_pages` | 150dpi JPEG，`.src_mtime` 增量缓存 |
| 引擎产物获取/归档/标定/适配 | pipeline 内部第②③步 | `pipeline_io.py`（`fetch_*`/`preserve_raw`/`adapt_*`） | 三路 `ThreadPoolExecutor` 并行 |
| 单渠道查看器 | 产物 `viewer_<ch>.html` | `viewer.py::build_viewer` | 原图 + 块框 + 块文本联动 |
| 1:3 对照查看器 | 产物 `viewer_compare.html` | `viewer.py::build_compare_viewer` | 四栏分色、引用分组、脚注定位 |
| 跨渠道合并 | `python merge_out.py` / pipeline 第④步 | `merge_out.py::merge_doc` | 逐页合并 → `merged/` |
| 跨引擎归一化 | `python unify.py <doc>` | `unify.py::unify_doc` | 归并组 + `_unified_summary.json` 指标 |
| 结构化元数据 | `python metadata.py <doc> --stage ...` | `metadata.py`（CLI）+ `metapy/` | 11 行壳，实现全在 `metapy/` |
| 实体抽取 | `python ner_lite.py <doc|all|selfcheck>` | `ner_lite.py` | LLM 提名 + 折叠匹配定位 |
| Web 拖拽工作台 | `python webapp.py` → `127.0.0.1:8765` | `webapp.py` + `app.js` | 拖 PDF 自动跑 pipeline |
| 参考文献质检 | `python regress.py` | `regress.py` | 截断/作者/跨页拼接检查 |
| MinerU 桌面版 CDP 兜底 | pipeline 自动触发 | `mineru_drive.py` | 仅 Windows，需桌面 App |

---

## 3. 代码架构

### 精简目录树

```
multidoc-ocr-compare-main/
├── pipeline.py          # 主编排 + 旧接口 re-export（356 行）
├── pipeline_io.py       # 获取/归档/标定/适配（914 行）
├── viewer.py            # 查看器 + md2html + 元数据面板（1252 行）
├── webapp.py / app.js   # 拖拽工作台（535 / 145 行）
├── merge_out.py         # 跨渠道逐页合并（190 行）
├── unify.py             # 跨引擎归并组 + 指标（534 行）
├── metadata.py          # 元数据 CLI 壳（10 行）
├── metapy/              # 元数据实现（m3/refs/front/abs/issue/cspan/common/...）
├── ner_lite.py          # 实体抽取（527 行）
├── mineru_drive.py      # MinerU 桌面 CDP 驱动（132 行）
├── regress.py           # 参考文献质检
├── test_pipeline.py     # 单测（10 case）
├── requirements.txt     # 3 个运行依赖
├── channels.json        # 基线配置（标定/模型/超时，无 token）
├── channels.local.example.json
├── docs/                # architecture/channels/calibration/RULES/REVIEW...
├── examples/13625974/   # 一个真实运行结果（已 checkin）
├── _attic/              # 退役代码 + 离线 demo（make_demo.py + examples/demo/）
└── .github/workflows/ci.yml
```

### 启动入口

- **CLI 主入口**：`pipeline.py`（`if __name__ == "__main__": main()`，第 355 行）
- **Web 入口**：`webapp.py`（第 499 行起），`start.bat` / `start.sh` 仅 `python webapp.py`
- **独立工具**：`merge_out.py` / `unify.py` / `metadata.py` / `ner_lite.py` / `regress.py` 均可单独跑

### 核心模块职责表

| 模块 | 职责 |
|---|---|
| `pipeline.py` | 顶层编排：解析参数 → 渲染 → 三路并行获取 → 适配 → 合并 → 归一化 → 建查看器；保留大量 re-export 兼容旧 import |
| `pipeline_io.py` | 渲染页图、inbox 扫描、缓存复用、云端 API 抓取、坐标标定、三类适配器、页数守卫 |
| `viewer.py` | 生成单渠道/对照 HTML，`md2html`、LaTeX 轻量转换、元数据面板 |
| `merge_out.py` | 三渠道逐页合并 → `merged/` + `merged.md` |
| `unify.py` | 跨引擎归并分组 → `unified/` + 覆盖率/1:1/orphan 指标 |
| `metapy/` | 元数据各 stage（跨页拼接 m3、参考文献 refs、题录 front、摘要 abs、期刊 issue、引文 cspan、LLM 兜底 llmrep、双语 dual） |
| `ner_lite.py` | 实体抽取：LLM 提名 → 折叠匹配定位 → 右向外延标注 |
| `mineru_drive.py` | MinerU 桌面 App 的 CDP 驱动（仅 Windows） |
| `webapp.py` | 纯标准库 HTTP 服务 + 上传/状态/配置/标注 API + 目录监视线程 |

### 核心流程 / 数据流

```
input.pdf
  ├─① render_pages()          pages/page_N.jpg (150dpi) + .src_mtime
  ├─② 三路并行获取            缓存 → API → mineru CDP 兜底（每路独立 enabled/token 判断）
  ├─③ adapt_*()               统一中间表示 {页: [{cat, box, text, img}]}，box 换算到页图像素
  ├─④ merge_out.py            逐页合并 → merged/page_N.json + merged.json + merged.md
  ├─⑤ unify.py                跨引擎归并组 → unified/page_N.json + _unified_summary.json
  └─⑥ build_viewer()          viewer_<ch>.html / viewer_compare.html / index.html
         └─(可选) metadata.py  消费 merged/unified → metadata.json + _metadata_report.html
         └─(可选) ner_lite.py  消费 unified → out_llm_trial/.../ner_lite/
```

**关键点**：④⑤⑥ 都在 `pipeline.main` 内顺序调用，任一步失败只记日志不阻断查看器；`unify` 硬依赖 `merged/`（顺序是硬约束）。可用 `--no-merge` / `--no-unify` 跳过。

### 配置加载机制（三层，后者覆盖前者）

1. `channels.json` —— 入库基线（标定/模型/超时/开关，**无 token**）
2. `channels.local.json` —— 个人私有覆盖（gitignored），只写改动键
3. 环境变量 `MINERU_API_TOKEN` / `PADDLE_API_TOKEN` —— 覆盖两个 token

`--channels <file>` 会**完全替换**基线并停用 2/3 层（离线 demo 用）。每次调用重读合并配置（`pipeline_io.load_cfg` / `ensure_cfg`），改标定或 token 下个文档即生效。

### 扩展点 / 二次开发建议

- **新增 OCR 渠道**：实现 `adapt_xxx(path, sizes) -> dict|str`，返回 `{页:[块]}` 或整篇字符串（md 模式），在 `pipeline.main` 的 `jobs`/`chans` 里注册即可（见 `docs/architecture.md`）。
- **统一中间表示**：所有适配器只认 `{cat, box, text, img}` 结构，`cat` 类别映射见 `NS`/`TMAP_MINERU`/`TMAP_PADDLE`。
- **元数据新增字段**：在 `metapy/` 加 stage，`metadata.py` 只做 CLI 分发。
- **新实体类型**：`ner_lite.py` 的 Nominate 提示词 + Locate 折叠匹配，改动集中。

### 关键文件阅读顺序 Top 10

1. `README.md`（英文主 README，最详尽）
2. `docs/architecture.md`（六步架构 + 失败语义）
3. `pipeline.py::main`（主流程一目了然）
4. `pipeline_io.py`（获取/适配/标定核心）
5. `docs/channels.md`（三渠道请求流 + quirks）
6. `viewer.py`（查看器生成）
7. `unify.py`（归并组 + 指标）
8. `metapy/common.py` + `metapy/refs.py`（元数据核心）
9. `ner_lite.py`（实体抽取契约）
10. `webapp.py`（工作台 + API）

---

## 4. 本地运行

### 4.1 环境要求

- **Python**：CI 在 3.10 / 3.12 验证；本机实测 **3.13.14 也可跑通**（离线 demo + 单测全过）。
- **OS**：除 MinerU 桌面 CDP 兜底仅 Windows 外，其余平台中立（Windows / macOS / Linux 均可）。
- **依赖**：`requirements.txt` 三个纯 Python 库，无 postinstall 脚本、无系统包。
- **网络/账号**：离线 demo 与单测**零依赖**；真实 PDF 跑 `dots` 渠道零 token（默认连小红书公共实例）；`paddle` / `mineru` 需各自 token。
- **GPU/Docker**：均不需要。

### 4.2 最快跑通路径（离线，无网络无 token，已实测）

```bash
cd D:/处理工具/2/multidoc-ocr-compare-main

# 1) 安装依赖
python -m pip install -r requirements.txt

# 2) 生成合成 demo 输入（合成 PDF + 三家 mock 产物）
python _attic/examples/make_demo.py

# 3) 跑全链路（渲染→适配→合并→归一化→查看器）
python pipeline.py _attic/examples/demo/samples/demo_kr.pdf \
    --mineru _attic/examples/demo/inbox/demo_kr__mineru \
    --dots   _attic/examples/demo/inbox/demo_kr__dots \
    --paddle _attic/examples/demo/inbox/demo_kr__paddle \
    --channels _attic/examples/demo/channels.json \
    --out _attic/examples/demo/out/demo_kr

# 4) 打开总览
python -m http.server -d _attic/examples/demo/out/demo_kr
# 浏览器访问 http://127.0.0.1:8000/index.html
```

### 4.3 开发模式运行（Web 工作台 + 真实 PDF）

```bash
# 有 token 则先复制配置，填 mineru/paddle 的 token（dots 无需 token）
cp channels.local.example.json channels.local.json

# 方式 A：拖拽工作台（纯标准库）
python webapp.py          # 自动打开 http://127.0.0.1:8765（端口占用自动顺延 8765-8774）

# 方式 B：命令行跑自己的 PDF
python pipeline.py mypaper.pdf        # 自动使用所有已配 token 的渠道

# 独立工具
python unify.py <doc>                 # 已有 merged/ 时单独归一化
python metadata.py <doc> --stage refs # 结构化元数据各 stage
python ner_lite.py <doc>              # 实体抽取
```

### 4.4 Docker/容器方式

**无**。项目未提供 Dockerfile / docker-compose，README 亦无容器方案。建议用 Python 虚拟环境隔离：

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

### 4.5 环境变量与配置表

| 变量/配置 | 是否必填 | 默认值 | 作用 | 示例 |
|---|---|---|---|---|
| `channels.json` | 是（基线，已带） | 仓库内置 | 标定/模型名/超时/开关 | — |
| `channels.local.json` | 否 | 无 | 个人 token 覆盖，gitignored | 复制 example 填 token |
| `MINERU_API_TOKEN` | 否 | 空 | 覆盖 MinerU token（CI 用） | `export MINERU_API_TOKEN=sk-...` |
| `PADDLE_API_TOKEN` | 否 | 空 | 覆盖 Paddle token | `export PADDLE_API_TOKEN=...` |
| `KCI_LLM_KEY` | 否 | 空 | 元数据 LLM 兜底 + ner_lite 的密钥（不落盘） | `export KCI_LLM_KEY=...` |
| `dots_api.base` | 否 | `https://dotsocr.xiaohongshu.com` | dots 公共实例地址 | 自部署时改 |
| `llm.enabled` | 否 | `false` | 元数据 LLM 兜底开关 | `true` |
| 端口 | 否 | `8765` | webapp 端口（占用自动顺延至 8774） | — |

---

## 5. 验证是否跑通

### 最小验证命令与预期输出（均已实测通过）

```bash
# 1) 单元测试（10 case，无网络无 token）
python -W error::ResourceWarning -m unittest -v test_pipeline.py
# 预期：Ran 10 tests ... OK

# 2) 实体抽取离线自检
python ner_lite.py selfcheck
# 预期：selfcheck OK: {... "records": 5, "locations": 10, "dropped_anchor_miss": 1 ...}

# 3) 离线 demo 全链路（见 4.2）
# 预期日志末尾：三家渠道各 OK，raw_blocks=22, groups=7, orphans=1
```

### 我实际执行的结果（成功）

| 步骤 | 结果 |
|---|---|
| `pip install -r requirements.txt` | ✅ 成功：pypdfium2-5.15.2 / Pillow-13.0.0 / websocket-client-1.9.2 |
| `python -m unittest test_pipeline.py` | ✅ **10/10 通过**（0.302s） |
| `python ner_lite.py selfcheck` | ✅ selfcheck OK |
| `python _attic/examples/make_demo.py` | ✅ 生成 6 个 demo 文件 |
| `python pipeline.py ... demo_kr.pdf` | ✅ 全链路 344ms，三渠道各 7/7/8 块，FFFD=0 |
| 产物完整性校验（11 项） | ✅ 全部 `-s` 非空 |

---

## 6. 常见问题与风险

- **Python 版本**：README/CI 声明 3.10/3.12，本机 3.13 实测可跑；若遇依赖装不上可降级到 3.10-3.12。
- **端口冲突**：webapp 默认 8765，占用会自动顺延到 8774；`start.bat` 有 `_server.lock` 单实例锁，重复双击不会叠服务。
- **渠道拿不到产物**：不会报错，`index.html` 标注"未提供"，其余照常——这是**设计行为**，不是 bug。
- **需要 token 的渠道**：`paddle` / `mineru` 无 token 时自动跳过；`dots` 零 token（连公共实例），是最快拿到真实结果的路。
- **`--channels` 语义**：会完全替换配置并**停用 local 层和环境变量**，离线 demo 里能保证不误读本机 token。
- **强制重跑**：缓存命中后不重取，删 `out/<doc>/raw/<渠道>_api` 才重取。
- **Windows 专属**：仅 `mineru_drive.py`（MinerU 桌面版 CDP 兜底）；其余跨平台。
- **上游不稳定**：三渠道都是第三方服务，端点/格式随时变，README 已声明"研究/工程工具，非托管服务"。
- **安全/数据**：上传 PDF 与产物落在本机 `uploads/`、`out/`、`inbox/`（已 gitignore），token 只写 `channels.local.json`（gitignored）或环境变量，**不落盘到仓库**。
- **README 与代码一致性**：`_attic/` 里的 `docs/` 是旧文档副本，权威文档以根 `docs/` 为准；`metadata.py` 只有 10 行，实现全在 `metapy/`（README 已说明）。
- **`channels.json` 里的 `mineru.token` 为空**：README 提到桌面版，但 token 字段为空是正常基线态（桌面版无 token 概念）。

---

## 7. 建议的后续阅读与改动顺序

1. 先看 `examples/13625974/index.html`（本地打开）感受最终产物形态。
2. 读 `README.md` + `docs/architecture.md` 建立心智模型。
3. 用自己的真实 PDF 跑 `dots` 单渠道（零 token），看 `viewer_dots.html`。
4. 配 `paddle`/`mineru` token，跑三渠道，看 `viewer_compare.html` 的分歧归因。
5. 跑 `metadata.py` 各 stage，理解结构化字段抽取。
6. 需要扩展时，从 `pipeline_io.py::adapt_*` 或 `metapy/` 入手。

---

## 8. 未确认问题

- **精确 commit/分支**：本地无 `.git`，无法给出；README 指向 `KieranFinn/multidoc-ocr-compare` 的 `main` 分支（推测，未确认）。
- **真实云渠道（dots/paddle/mineru）未实测**：本次仅离线 mock，未调用任何真实 API（需 token/配额），故真实请求流的端点细节以 `docs/channels.md` 为准，未现场验证。
- **MinerU 桌面 CDP 兜底未实测**：需 Windows 桌面 App + 运行环境，未执行。
- **元数据各 stage 与 ner_lite 的真实文档效果**：仅 `selfcheck` 离线验证通过，真实语料精度以 README"Status and limitations"的自述为准（未复现）。
- **Python 3.13 非官方验证版本**：CI 仅 3.10/3.12，本机 3.13 通过是额外验证，非上游承诺。
