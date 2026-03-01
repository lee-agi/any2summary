# any2summary 项目说明

## 开发规范

### 版本号管理
- **每次增加 feature 都必须更新版本号**
- 遵循语义化版本规范（SemVer）：
  - MAJOR（主版本号）：不兼容的 API 修改
  - MINOR（次版本号）：向下兼容的功能新增
  - PATCH（修订号）：向下兼容的 Bug 修复
- 更新位置：
  - `CLAUDE.md` 版本历史部分（必须）
  - `pyproject.toml` version 字段（发布时）
  - `chrome_extension/manifest.json` version 字段（Chrome 扩展发布时）

## 核心功能

### CLI 子命令
- `any2summary` - 默认摘要处理命令
- `any2summary serve` - 启动本地 Companion Server
- `any2summary doctor` - 健康检查诊断工具（支持 `--fix` 和 `--json`）
- `any2summary init` - 交互式配置向导

### 主要参数
- `--url` / `--file` - 输入源（互斥，必选其一）
- `--summary-length` - 摘要长度控制 (brief/standard/detailed/full)
- `--azure-summary` - 启用 Azure GPT 摘要
- `--force-azure-diarization` - 强制使用 Azure 转写

### doctor 命令参数
- `--fix` - 尝试自动修复可解决的问题（如创建 .env 文件、安装缺失依赖）
- `--json` - 输出 JSON 格式结果供程序化使用

## 可选依赖
- `pip install any2summary[ui]` - rich 进度条美化
- `pip install any2summary[pdf]` - PDF 文件处理
- `pip install any2summary[server]` - Companion Server
- `pip install any2summary[all]` - 所有可选依赖

## 关键模块

### cli.py 核心函数
- `run()` - CLI 入口，分发子命令
- `_run_doctor_command()` - 健康检查（支持 --fix/--json）
- `_run_init_command()` - 配置向导
- `_run_summarize_command()` - 主摘要流程
- `_run_single_local_file()` - 本地文件处理
- `_process_local_file()` - 文件类型检测与处理
- `generate_translation_summary()` - Azure 摘要生成
- `_update_progress_bar()` - 进度条渲染（支持 rich 降级）
- `_extract_audio_from_video()` - 从视频提取音频（带进度显示）
- `_run_multiple()` - 批量 URL 处理（带整体进度）
- `_split_wav_file()` - 音频分割（带进度显示）

### errors.py 错误码模块
- `ErrorCode` - 错误码枚举（配置类 1000-1099，依赖类 1100-1199，网络类 1200-1299）
- `ErrorInfo` - 错误详情数据类（含 auto_fix 自动修复函数）
- `ERROR_CATALOG` - 错误码到详情的映射表
- `get_error_info()` - 获取错误详情
- `map_http_status_to_error()` - HTTP 状态码映射到错误码
- `create_package_error()` - 动态创建包缺失错误

### 文件类型支持
- 音频: `.mp3`, `.m4a`, `.wav`, `.flac`, `.aac`, `.ogg`
- 视频: `.mp4`, `.mkv`, `.webm`, `.avi`, `.mov`
- 文档: `.pdf`

### 摘要长度配置
| 级别 | max_tokens | 说明 |
|------|------------|------|
| brief | 2048 | 3-5 句话简洁总结 |
| standard | 8192 | 默认标准摘要 |
| detailed | 16384 | 详细展开要点 |
| full | 32768 | 完整翻译不压缩 |

## 测试文件
- `test/test_cli_doctor.py` - doctor 命令测试（含 --fix/--json）
- `test/test_cli_init.py` - init 命令测试
- `test/test_cli_local_file.py` - 本地文件处理测试
- `test/test_cli_summary_length.py` - 摘要长度控制测试
- `test/test_cli_progress.py` - 进度条渲染测试
- `test/test_cli_ffmpeg_progress.py` - FFmpeg 进度监控测试
- `test/test_errors.py` - 错误码模块测试

## 环境变量
- `AZURE_OPENAI_ENDPOINT` - Azure 端点
- `AZURE_OPENAI_API_KEY` - API 密钥
- `AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT` - 转写部署名
- `AZURE_OPENAI_SUMMARY_DEPLOYMENT` - 摘要部署名

## Chrome 扩展

### 任务取消功能
Chrome 扩展支持取消正在进行的摘要任务：
- 使用 `AbortController` 实现真正的请求中断
- 点击取消按钮可立即中断所有正在进行的 fetch 请求
- 支持多标签页独立任务管理（每个标签页有独立的 AbortController）
- 快捷键触发的任务同样支持取消

### 关键文件
- `chrome_extension/src/background.js` - AbortController 管理、CANCEL_TASK 消息处理
- `chrome_extension/src/summarize.js` - 所有 fetch 调用传递 signal 参数
- `chrome_extension/src/youtubeTranscript.js` - YouTube 字幕获取支持取消
- `chrome_extension/src/articleParser.js` - 文章解析支持取消
- `chrome_extension/src/contentDetector.js` - 内容类型检测支持取消
- `chrome_extension/src/popup.js` - 取消按钮逻辑和状态切换
- `chrome_extension/src/popup.html` - 取消按钮 UI
- `chrome_extension/src/options.html` - 设置页面（折叠式高级配置、缓存管理、连接状态指示器）
- `chrome_extension/src/options.js` - 设置页面逻辑
- `chrome_extension/src/i18n.js` - 国际化工具模块
- `chrome_extension/_locales/` - 多语言消息文件

### Options 页面功能
- **配置分组**：基础配置（API、本地服务）默认展开，高级配置（摘要、语言、缓存、自动保存）折叠
- **缓存管理**：显示缓存大小和条目数，一键清空缓存（保留设置）
- **连接状态指示器**：本地服务卡片显示圆点指示器（绿色在线/红色离线/黄色检测中）
- **完整 i18n**：所有文案支持中英文切换

### 国际化 (i18n)
Chrome 扩展支持多语言，根据浏览器语言自动切换：
- 英文 (en) - 默认语言
- 简体中文 (zh_CN)
- 繁体中文 (zh_TW)

**核心文件**：
- `_locales/en/messages.json` - 英文消息
- `_locales/zh_CN/messages.json` - 简体中文消息
- `_locales/zh_TW/messages.json` - 繁体中文消息
- `src/i18n.js` - 国际化工具函数

**使用方式**：
- HTML: `<span data-i18n="messageKey">Fallback text</span>`
- JS: `import { i18n } from "./i18n.js"; i18n.statusRunning()`

### Chrome Web Store 发布
- **隐私政策**: `docs/privacy.html` (GitHub Pages 托管)
- **manifest.json**: 版本号 1.0.0，使用 `__MSG_*__` 国际化
- **商店资源**: `docs/store-assets/` (截图需手动截取)

### 任务状态
- `running` - 任务运行中（显示取消按钮）
- `completed` - 任务完成
- `failed` - 任务失败
- `cancelled` - 任务已取消

### 文件命名规则（与 CLI 对齐）

Chrome 扩展的文件命名逻辑与 CLI 保持一致：

**文件名格式**：`【{domain}】{title}-{year}-M{month}_summary.md`

**核心函数对照**（`fileSaver.js` ↔ `cli.py`）：

| Chrome 函数 | CLI 函数 | 说明 |
|------------|----------|------|
| `sanitizeFilenameBase()` | `_sanitize_filename_base()` | 仅删除 `\/:*?"<>|` 和空格 |
| `deriveYearMonth()` | `_derive_year_month()` | 支持 8 位数字、YYYY-MM、generatedAt 备选 |
| `normalizeDomainLabel()` | `_normalize_domain_label()` | Domain 中英文映射 |
| `extractDomain()` | `_extract_domain()` | 从 metadata/URL 提取 domain |

**日期解析优先级**：
1. `publishDate` / `uploadDate`（8 位数字 YYYYMMDD 或 YYYY-MM-DD）
2. `generatedAt`（当前日期作为备选）
3. 默认值 `1970-M01`

### 本地服务器 Metadata 字段格式

本地服务器（`server.py`）会将 yt-dlp 返回的 snake_case 字段名转换为 camelCase：

| yt-dlp 字段 (snake_case) | 服务器返回 (camelCase) |
|--------------------------|----------------------|
| `upload_date` | `uploadDate` |
| `webpage_url` | `webpageUrl` |
| `channel_id` | `channelId` |
| `view_count` | `viewCount` |
| `like_count` | `likeCount` |

**关键函数**：
- `server.py:_convert_metadata_to_camel_case()` - 将 metadata 转换为 camelCase

**fileSaver.js 兼容性**：
- 同时支持 camelCase 和 snake_case 字段名
- camelCase 优先级高于 snake_case

## 版本历史
- v1.6.2: 修复 Azure OpenAI Responses API 路径 — 解除 enrichment hang
  - 新增 `_call_responses_api()` 辅助函数：用 raw httpx 替换 OpenAI SDK 调用 Responses API
  - 修复 URL: `/openai/responses?api-version=...`（不再使用错误的 `/openai/v1/responses`）
  - 修复认证: `api-key` header（不再使用 `Authorization: Bearer`）
  - 修复代理: 复用 `_create_azure_http_client(proxy=None)` 绕过本地代理
  - 内置 1 次重试（5xx/429），3s backoff
  - `_build_responses_base_url()`: `/openai/v1` → `/openai`
  - `generate_translation_summary` 和 `_infer_domain_from_summary` 两处 Responses API 调用迁移至 `_call_responses_api()`
  - 删除 `AZURE_OPENAI_RESPONSES_BASE_URL` 环境变量依赖（该变量是对 `/openai/v1` bug 的 workaround）
  - 新增 2 个测试 + 更新 2 个已有测试

- v1.6.1: 转写流程日志可观测性增强
  - **服务器日志**：`/api/transcribe` 端点添加详细请求/响应日志
  - **CLI 日志**：`perform_azure_diarization()` 添加关键步骤进度日志（缓存检查、音频准备、分割、API 调用）
  - **Chrome 扩展错误传播**：API 错误（Azure/transcription/diarization/本地服务/HTTP 4xx/5xx）不再静默回退，会正确显示给用户
  - **消息通道修复**：`background.js` 确保 `sendResponse` 在所有代码路径中被调用，修复 "message channel closed" 错误
  - 修复 Chrome 扩展下载音频后未执行转写的调试难题

- v1.6.0: 易用性增强三件套
  - **智能错误诊断**：引入错误码体系（`errors.py`），doctor 命令支持 `--fix` 自动修复和 `--json` 输出
  - **进度可视化增强**：FFmpeg 音频提取、批量 URL 处理、音频分割均显示进度条
  - **Chrome Options 简化**：折叠式高级配置、缓存管理 UI、本地服务连接状态指示器
  - 新增测试：`test_errors.py`、`test_cli_ffmpeg_progress.py`
  - i18n 补全：Options 页面所有文案支持多语言

- v1.5.0: 本地服务器 Metadata 字段名修复
  - `server.py` 添加 `_convert_metadata_to_camel_case()` 函数
  - `/api/youtube/transcript` 端点返回 camelCase metadata
  - `/api/transcribe` 端点添加 video metadata 获取并转换为 camelCase
  - `fileSaver.js` 增加 snake_case 字段名兼容作为保险
  - 修复本地服务器模式下文件名显示 "General" 和 "1970-M01" 的问题

- v1.4.0: Chrome 扩展 YouTube Title 为空问题修复
  - `background.js` 添加 title fallback，空标题显示为 "未知标题"（与 CLI 一致）
  - `background.js` 清理标题中的特殊字符（`:`, `/`, `\`, `` ` ``）
  - `fileSaver.js` extractDomain() 修复空字符串 category 导致的 "General" 问题
  - 文件名 domain 现在能正确显示 "YouTube" 而非 "General"

- v1.3.0: Chrome Web Store 发布准备
  - 国际化支持（英文、简体中文、繁体中文）
  - 隐私政策页面 (`docs/privacy.html`)
  - manifest.json 优化（版本号 1.0.0，i18n 支持）
  - `i18n.js` 国际化工具模块

- v1.2.0: Chrome 扩展与 CLI 文件命名对齐
  - `sanitizeFilenameBase()` 简化为仅删除 `\/:*?"<>|` 和空格（保留 emoji）
  - `deriveYearMonth()` 支持 8 位纯数字格式 YYYYMMDD
  - 添加 `generatedAt` 作为日期备选，默认值改为 `1970-M01`

- v1.1.0: Chrome 扩展任务取消功能
  - AbortController 实现真正的请求中断
  - 取消按钮 UI
  - 多标签页独立任务管理

- v1.0.0: 初始版本
  - doctor/init 子命令
  - --file 本地文件支持
  - --summary-length 摘要长度控制
  - rich 进度条优化
