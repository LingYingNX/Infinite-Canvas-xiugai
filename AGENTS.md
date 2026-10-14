# AGENTS.md

英文工具/命令名保留原文；说明文字用中文，与仓库既有文档（README、*使用说明.md）一致。

## 项目概览

「无限画布 Infinite-Canvas 精简修改版」是一个 AI 图像/视频创作画布应用：

- 后端：单文件 FastAPI 服务 `main.py`（Python 3.10，随仓库捆绑的便携解释器）。
- 前端：原生 HTML/CSS/JS 画布应用，位于 `static/`（`canvas.html`、`index.html`、`canvas-list.html` 等）。
- 资源：ComfyUI workflows 在 `workflows/`；本地素材、上传、输出在 `assets/` 与 `output/`（大部分已被 `.gitignore` 忽略）。
- 附带的「即梦 CLI」工具在 `CLI/`，配套安装/登录脚本在 `tools/`（`jimeng_cli_install.ps1`、`jimeng_cli_login.ps1`）。

项目基于上游 [hero8152/Infinite-Canvas](https://github.com/hero8152/Infinite-Canvas) 做了精简：清理重复代码与零引用函数、删除冗余备份文件，保留功能与操作方式。精简逐条记录见 `代码精简分析.md`。

> 注：`agent-rules` 的自动探测工具（`detect-project.sh`）无法识别本项目（非标准的便携 Python + JS 前端混合结构，无 `pyproject.toml`/`package.json` 等标准构建文件），故本文件为人工撰写，非脚本生成的骨架。

## 常用命令

在 Windows PowerShell 下运行（路径含中文/空格，请用 `-LiteralPath`，保持 UTF-8）：

| 用途 | 命令 | 说明 |
|------|------|------|
| 安装依赖 | `.\安装依赖.bat` | 离线包在 `packages/`；依赖见 `requirements.txt` |
| 启动服务 | `.\run.bat` | 运行 `main.py`，服务地址 `http://127.0.0.1:3000/`，访问后按 Ctrl+C 停止 |
| macOS 安装 | `bash mac-安装依赖.sh` | macOS 安装依赖 |
| macOS 启动 | `bash mac-启动服务.sh` | 对应 macOS 启动脚本 |
| 即梦 CLI 安装 | `powershell -File .\tools\jimeng_cli_install.ps1` | 安装即梦 CLI |
| 即梦 CLI 登录 | `powershell -File .\tools\jimeng_cli_login.ps1` | 登录即梦 CLI |

依赖清单（`requirements.txt`）：`fastapi`、`uvicorn`、`requests`、`pydantic`、`python-multipart`、`httpx`、`pillow`。

## 测试

项目没有配置标准的测试框架/构建工具（`detect-project.sh` 显示 `language/build_tool: unknown`、`test_framework: unknown`、`ci: none`）。

- 前端画布回归脚本：`tools/test-canvas-list-keyboard.js` —— Node 脚本，用于回归「画布列表页键盘交互」。运行前需已安装 Node.js。
- 尚未配置 pytest / CI / lint 等质量关卡。

## 目录结构（Pointer，不重复内容）

| 路径 | 作用 |
|------|------|
| `main.py` | 后端 FastAPI 入口，路由、静态资源挂载、WebSocket、图片处理 |
| `static/` | 前端页面与资源（`canvas.html`、`canvas-list.html`、`index.html`、`js/`、`css/`、`images/`） |
| `static/system-prompts/`、`static/runninghub/`、`static/vendor/` | 前端自带提示词/运行中心/第三方库 |
| `data/` | 运行时数据（项目、画布、会话、提示词库、API 提供商配置） |
| `assets/` | 素材（输入/输出/上传/素材库） |
| `output/` | 生成输出（已被 `.gitignore` 忽略） |
| `workflows/` | ComfyUI / 绘图 workflow 的 JSON 与配置 |
| `CLI/` | 即梦 CLI（`css/`、`js/`、`system-prompts/`、`vendor/`、`runninghub/`） |
| `API/` | 各平台 API 封装（`windows/`、`macos/`、`linux/`）与 `.env` 配置 |
| `python/` | 随仓库捆绑的便携 Python 解释器 |
| `packages/` | 离线依赖 wheel 包 |
| `tools/` | 配套脚本与回归测试 |
| `resources/` | 资源接入（`configs/`、`chrome-local-asset-importer/`、`photoshop-asset-connector/`、`regression/`） |

## 环境约束（Windows PowerShell）

- Shell 是 PowerShell，不是 bash。`2>/dev/null`、`grep`、`sed`、`ls -la` 是错的；改用 `2>$null` / `-ErrorAction SilentlyContinue`、`Select-String`、`Get-ChildItem`。
- 路径含中文与空格，用 `-LiteralPath`；文件 I/O 保持 UTF-8。
- 禁止在工作区外递归删除/移动，先解析绝对路径再执行。

## 代码规范

- 后端 Python：跟随 `main.py` 现有风格（标准库 + `fastapi`/`requests`/`httpx`/`pillow`）；新增依赖前先确认 `packages/` 或 `requirements.txt` 已覆盖。
- 前端：原生 JS，不引入框架；画布页请求/错误处理复用页内已抽取的公共 helper。
- 精简项目原则：少造抽象、复用已有 helper、不新增无必要的依赖。

## 更新策略

改动构建/测试命令或目录结构时，同步更新本文件的「常用命令」与「目录结构」小节；保持表格化、指向文件而非复制内容。

## 版本

`VERSION`：
