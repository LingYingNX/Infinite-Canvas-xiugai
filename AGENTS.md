<!-- FOR AI AGENTS - Human readability is a side effect, not a goal -->
<!-- Managed by agent: keep sections and order; edit content, not structure -->
<!-- Last updated: 2026-10-14 | Last verified: 2026-10-14 -->

# AGENTS.md

**Precedence:** the **closest `AGENTS.md`** to the files you're changing wins. Root holds global defaults only.

## Index of scoped AGENTS.md

本仓库仅根目录一个 `AGENTS.md`（`CLAUDE.md` 为其符号链接），无子目录级 scope 文件。

英文工具/命令名保留原文；说明文字用中文，与仓库既有文档（README、*使用说明.md）一致。

## Setup

依赖安装与服务启动见上方 Commands 表（Windows 用 `.\安装依赖.bat` + `.\run.bat`，macOS 用 `bash mac-安装依赖.sh` + `bash mac-启动服务.sh`）。便携解释器与离线 wheel 已随仓库捆绑，通常无需额外环境配置。

## Overview

「无限画布 Infinite-Canvas 精简修改版」是一个 AI 图像/视频创作画布应用：

- 后端：单文件 FastAPI 服务 `main.py`（Python 3.10，随仓库捆绑的便携解释器）。
- 前端：原生 HTML/CSS/JS 画布应用，位于 `static/`（`index.html`、`canvas-list.html` 等）。
- 资源：ComfyUI workflows 在 `workflows/`；本地素材、上传、输出在 `assets/` 与 `output/`（大部分已被 `.gitignore` 忽略）。
- 附带「即梦/Gemini/OpenAI CLI」安装脚本在 `CLI/`（按 windows/macos/linux 分平台），即梦配套脚本在 `tools/`。
- 基于上游 [hero8152/Infinite-Canvas](https://github.com/hero8152/Infinite-Canvas) 精简，逐条记录见 `代码精简分析.md`。

> 注：`agent-rules` 自动探测（`detect-project.sh`）无法识别本项目（便携 Python + JS 混合，无 `pyproject.toml`/`package.json`），故本文件为人工撰写并人工维护，非脚本生成的骨架。

## Commands

在 Windows PowerShell 下运行（路径含中文/空格，用 `-LiteralPath`，保持 UTF-8）：

| 用途 | 命令 | 说明 |
|------|------|------|
| 安装依赖 | `.\安装依赖.bat` | 离线包在 `packages/`；依赖见 `requirements.txt` |
| 启动服务 | `.\run.bat` | 运行 `main.py`，服务 `http://127.0.0.1:3000/`，Ctrl+C 停止 |
| macOS 安装 | `bash mac-安装依赖.sh` | macOS 安装依赖 |
| macOS 启动 | `bash mac-启动服务.sh` | macOS 启动脚本 |
| 即梦 CLI 安装/登录 | `powershell -File .\tools\jimeng_cli_install.ps1` / `jimeng_cli_login.ps1` | 即梦 CLI |

依赖（`requirements.txt`）：`fastapi`、`uvicorn`、`requests`、`pydantic`、`python-multipart`、`httpx`、`pillow`。

## Build/Tests

无标准测试框架/CI/lint（`detect-project.sh` 均为 unknown/none）。

- 唯一回归：`tools/test-canvas-list-keyboard.js`（Node 脚本，回归画布列表键盘交互；需已装 Node.js）。
- 后端改动自检：`.\python\python.exe -c "import ast; ast.parse(open('main.py',encoding='utf-8').read())"`（语法门），再启动 `run.bat` 冒烟首页 HTTP 200。

## File Map

| 路径 | 作用 |
|------|------|
| `main.py` | 后端 FastAPI 入口，路由、静态资源挂载、WebSocket、图片处理 |
| `static/` | 前端页面与资源（`js/`、`css/`、`images/`、`system-prompts/`、`runninghub/`、`vendor/`） |
| `data/` | 运行时数据（`canvases/`、`conversations/`、`projects.json`、`api_providers.json` 等） |
| `assets/`、`output/` | 素材与生成输出（大部分被 `.gitignore` 忽略） |
| `workflows/` | ComfyUI / 绘图 workflow JSON |
| `CLI/` | 即梦/Gemini/OpenAI CLI 安装与启动脚本（`windows/`、`macos/`、`linux/`） |
| `API/` | `API/.env` 运行时 API Key 配置（明文，勿提交真实 Key） |
| `python/`、`packages/` | 便携 Python 解释器与离线 wheel 包 |
| `tools/` | 配套脚本与回归测试 |
| `resources/` | `configs/` 下 mira 服务配置（`mira-servers.json`、`mira-settings.json`） |

## Code style

- 后端 Python：跟随 `main.py` 现有风格（标准库 + `fastapi`/`requests`/`httpx`/`pillow`）；新增依赖前先确认 `packages/` 或 `requirements.txt` 已覆盖。
- 前端：原生 JS，不引入框架；请求/错误处理复用页内已抽取的公共 helper。
- 精简项目原则：少造抽象、复用已有 helper、不新增无必要的依赖。

## Security

- 全服务无鉴权，仅面向本机（127.0.0.1），不要暴露到公网。
- `API/.env`、`data/api_providers.json` 含真实凭据，禁止提交或写入日志。
- 禁止在工作区外递归删除/移动；先解析绝对路径再执行。

## Checklist

- [ ] 改 `main.py` 后跑语法门 + 启动冒烟
- [ ] 改构建/测试命令或目录结构时，同步更新本文件「Commands」「File Map」
- [ ] 改前端页面后，涉及列表页键盘交互时跑 `tools/test-canvas-list-keyboard.js`

## Patterns to Follow

- 错误处理收敛到 helper：如 `require_video_base_url`（main.py）统一「Base URL 未配置」400 报错，`raise_chat_upstream_http_error` / `raise_video_provider_http_error` 统一上游 HTTP 错误转换——新 provider 接口沿用同一模式，不要内联重复 raise。
- 轮询任务统一带 `time.monotonic()` deadline 与递增 delay（参考 `wait_for_video_task`）。
- 文件写入后用 `?v=` 缓存戳由 `sync_static_html_versions()` 自动刷新，html 中不手改版本号。

## When stuck

- 服务行为存疑：直接启动 `.\run.bat` 后用 `Invoke-WebRequest http://127.0.0.1:3000/...` 复现，报错看控制台输出。
- 文档与代码冲突：以代码为准，并回头更新本文件。

## 版本

`VERSION`：`2026.08.25`。`main.py` 读取该值用于自更新与静态资源缓存戳（`?v=` 由 `sync_static_html_versions()` 启动时自动刷新，提交时随附于 html 改动属预期）。
