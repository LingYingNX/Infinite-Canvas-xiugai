<!-- FOR AI AGENTS - Human readability is a side effect, not a goal -->
<!-- Managed by agent: keep sections and order; edit content, not structure -->
<!-- Last updated: 2026-10-23 | Last verified: 2026-10-23 -->

# AGENTS.md

**Precedence:** the **closest `AGENTS.md`** to the files you're changing wins. Root holds global defaults only.

## Index of scoped AGENTS.md

本仓库仅根目录一个 `AGENTS.md`（`CLAUDE.md` 为其符号链接），无子目录级 scope 文件。`detect-scopes.sh` 未发现需独立规则的目录。

英文工具/命令名保留原文；说明文字用中文，与仓库既有文档（README、*使用说明.md）一致。

## Setup

依赖安装与服务启动见上方 Commands 表（Windows 用 `.\安装依赖.bat` + `.\run.bat`，macOS 用 `bash mac-安装依赖.sh` + `bash mac-启动服务.sh`）。便携 Python 3.10 在 `python/`，离线 wheel 在 `packages/`，通常无需额外环境配置；Playwright 回归不在这套离线依赖内，需系统 Python 另装 Playwright 与 Chromium。

## Overview

「无限画布 Infinite-Canvas 精简修改版」是一个 AI 图像/视频创作画布应用：

- 后端：单文件 FastAPI 服务 `main.py`（Python 3.10，随仓库捆绑的便携解释器）。
- 前端：原生 HTML/CSS/JS 画布应用，位于 `static/`（`index.html`、`canvas-list.html` 等）。
- 资源：ComfyUI workflows 在 `workflows/`；本地素材、上传、输出在 `assets/` 与 `output/`（大部分已被 `.gitignore` 忽略）。
- 附带「即梦/Gemini/OpenAI CLI」安装脚本在 `CLI/`（按 windows/macos/linux 分平台），即梦配套脚本在 `tools/`；Chrome 素材导入扩展与 Photoshop UXP 插件也在 `tools/`。
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

依赖（`requirements.txt`）：`fastapi`、`uvicorn`、`requests`、`pydantic`、`python-multipart`、`httpx`、`pillow`、`websockets`。版本已锁定；新增依赖先确认 `packages/` 有对应 Python 3.10 wheel，或同步更新离线包。

## Build/Tests

无统一测试框架、CI 或 lint 配置（`detect-project.sh` 返回 unknown/none）；下列脚本是项目唯一的验证入口。

- 画布交互回归：`python tools/regression/canvas_interaction.py`（30 条 Playwright 用例；需系统 Python + Playwright + Chromium，自动启停 3000 端口）。服务已运行时改用 `python tools/regression/canvas_interaction.py --no-server`。
- 安全与数据自检：`.\python\python.exe tools/regression/security_regression.py`（10 项：私网 SSRF、密钥同源绑定、原子写、ZIP/请求体限制、任务回收、跨源与 WebSocket、局域网令牌）。
- 前端静态守卫：`node tools/test-smart-canvas-guards.js` 与 `node tools/test-canvas-list-keyboard.js`。
- 后端改动自检：`.\python\python.exe -c "import ast; ast.parse(open('main.py',encoding='utf-8').read())"`（语法门），再启动 `run.bat` 冒烟首页 HTTP 200。
- 发布前组合检查：`main.py` 改动跑语法门 + 安全回归 + 首页冒烟；画布或列表页改动跑 Playwright 30 条与对应 Node 守卫。

## File Map

| 路径 | 作用 |
|------|------|
| `main.py` | 后端 FastAPI 入口，路由、静态资源挂载、WebSocket、图片处理 |
| `static/` | 前端页面与资源（`js/`、`css/`、`images/`、`system-prompts/`、`runninghub/`、`vendor/`） |
| `data/` | 运行时数据（`canvases/`、`conversations/`、`projects.json`、`api_providers.json`、`.access_token` 等；多数被 `.gitignore` 忽略） |
| `assets/`、`output/` | 素材与生成输出（大部分被 `.gitignore` 忽略） |
| `workflows/` | ComfyUI / 绘图 workflow JSON |
| `CLI/` | 即梦/Gemini/OpenAI CLI 安装与启动脚本（`windows/`、`macos/`、`linux/`） |
| `API/` | `API/.env` 是本机密钥与绑定配置（已忽略）；提交模板为 `API/.env.example`，不要写真实 Key |
| `python/`、`packages/` | 便携 Python 解释器与离线 wheel 包 |
| `tools/` | 回归脚本、缓存戳同步、即梦 CLI 辅助脚本、Chrome 导入扩展、Photoshop UXP 插件 |
| `resources/` | mira 服务配置，放在 `configs/`；整个目录被 `.gitignore` 忽略，属本机部署数据 |

## Code style

- 后端 Python：跟随 `main.py` 现有风格（标准库 + `fastapi`/`requests`/`httpx`/`pillow`）；新增依赖前先确认 `packages/` 或 `requirements.txt` 已覆盖。
- 前端：原生 JS，不引入框架；请求/错误处理复用页内已抽取的公共 helper。
- 精简项目原则：少造抽象、复用已有 helper、不新增无必要的依赖。

## Security

- 默认只监听 `127.0.0.1`。确需局域网访问时在 `API/.env` 设置 `APP_BIND_HOST=0.0.0.0`，并按需配置 `TRUSTED_WEB_ORIGINS`；API 仍会校验同源令牌 Cookie、Origin 或本机来源。
- 局域网或 DNS Rebinding 场景要求先打开一次页面取得 HttpOnly Cookie；直接调用 `/api/*` 返回 `403`。WebSocket 跨源握手以关闭码 `1008` 拒绝。
- 请求体、单文件上传、ZIP 解包、画布导出和画布任务分别受 `MAX_REQUEST_BODY_BYTES`、`MAX_UPLOAD_FILE_BYTES`、`MAX_ARCHIVE_BYTES`、`MAX_ARCHIVE_ENTRIES`、`CANVAS_EXPORT_MAX_ITEMS`、`CANVAS_EXPORT_MAX_BYTES`、`CANVAS_TASK_RETENTION_SECONDS`、`CANVAS_TASK_MAX_ENTRIES` 限制；调整前先确认上游需要的最大尺寸。
- 已保存的供应商 Key 只发往与供应商 `base_url` 同源的地址；不得把 Key 与任意请求 URL 混用。远程 URL 必须先拒绝私网、回环和保留地址。
- `API/.env`、`data/api_providers.json`、`data/.access_token`、`resources/configs/` 含真实凭据或本机配置，禁止提交或写入日志。
- Gemini CLI 的图片工具默认关闭；仅在明确需要时设置 `GEMINI_CLI_IMAGE_TOOLS=1`。
- 禁止在工作区外递归删除/移动；先解析绝对路径再执行。

## Checklist

- [ ] 改 `main.py` 后跑语法门 + 启动冒烟
- [ ] 改鉴权、存储、上传、更新逻辑后跑 `tools/regression/security_regression.py`
- [ ] 改构建/测试命令或目录结构时，同步更新本文件「Commands」「File Map」
- [ ] 改智能画布保存/提示词后跑 `node tools/test-smart-canvas-guards.js`
- [ ] 改列表页键盘交互后跑 `node tools/test-canvas-list-keyboard.js`
- [ ] 改画布交互或发版前跑 `python tools/regression/canvas_interaction.py`（30 条）

## Patterns to Follow

- 错误处理收敛到 helper：如 `require_video_base_url`（main.py）统一「Base URL 未配置」400 报错，`raise_chat_upstream_http_error` / `raise_video_provider_http_error` 统一上游 HTTP 错误转换——新 provider 接口沿用同一模式，不要内联重复 raise。
- 轮询任务统一带 `time.monotonic()` deadline 与递增 delay（参考 `wait_for_video_task`）。
- 文件写入后用 `?v=` 缓存戳由 `sync_static_html_versions()` 自动刷新，html 中不手改版本号。
- JSON/文本状态统一走 `atomic_write_json()` / `atomic_write_text()`，避免崩溃或并发写留下半个文件。
- 前端无构建步骤：直接改 `static/` 下的原生 HTML/CSS/JS，不引入框架；请求与错误处理复用页内已有 helper。

## When stuck

- 服务行为存疑：直接启动 `.\run.bat` 后用 `Invoke-WebRequest http://127.0.0.1:3000/...` 复现，报错看控制台输出。
- 文档与代码冲突：以代码为准，并回头更新本文件。

## Release

用户说“**更新版本号推送**”时，按下面顺序执行；只推代码不会让用户端检测到更新。

1. 先确认改动已通过检查：`main.py` 改动跑 `ast.parse` + 启动冒烟 + `tools/regression/security_regression.py`；画布改动跑 `python tools/regression/canvas_interaction.py`（30 条，使用系统 Python + Playwright）；列表页改动跑 `node tools/test-canvas-list-keyboard.js`。
2. 把 `VERSION` 改成更大的日期式版本（如 `2026.10.17`），必须严格大于线上版本，否则 `version_gt` 判定不出更新。
3. 同步 `static/update-notes.json`：`version` 与 `VERSION` 一致，`updated_at` 写当前时间，`items` 写本次更新。必须是严格 JSON——字符串内换行要写成 `\n`，裸换行会让 Python 解析失败。
4. 运行 `.\python\python.exe tools\sync_static_versions.py` 刷新全站 `?v=` 缓存戳（会改动多个 `static/*.html`，属预期）。
5. 提交 `VERSION`、`main.py`（如有）、`static/*.html`、`static/update-notes.json`，提交信息用 `release: <版本> <摘要>`；不要把 `.agents/` 加入提交。普通代码提交只加本次相关文件。
6. `git push origin main`。推送后 `raw.githubusercontent.com` 有约 1–5 分钟 CDN 缓存，可用 GitHub API `contents/VERSION` 核对远端真实内容。
7. 复验：临时把本地 `VERSION` 改成旧值 → `GET /api/check-update` 应返回 `update_available: true` 且 `latest.update_notes.items` 非空 → 立即还原 `VERSION`。

自动更新只覆盖 `main.py`、`VERSION`、`static/*`（见 `update_allowed_file`）；`workflows/`、`tools/`、`python/`、`packages/`、`API/`、`resources/` 不会随更新下发。

## 版本

`VERSION`：`2026.10.17`。`main.py` 读取该值用于自更新与静态资源缓存戳（`?v=` 由 `sync_static_html_versions()` 启动时自动刷新，提交时随附于 html 改动属预期）。
