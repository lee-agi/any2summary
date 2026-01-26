# any2summary 项目说明

## 核心功能

### CLI 子命令
- `any2summary` - 默认摘要处理命令
- `any2summary serve` - 启动本地 Companion Server
- `any2summary doctor` - 健康检查诊断工具
- `any2summary init` - 交互式配置向导

### 主要参数
- `--url` / `--file` - 输入源（互斥，必选其一）
- `--summary-length` - 摘要长度控制 (brief/standard/detailed/full)
- `--azure-summary` - 启用 Azure GPT 摘要
- `--force-azure-diarization` - 强制使用 Azure 转写

## 可选依赖
- `pip install any2summary[ui]` - rich 进度条美化
- `pip install any2summary[pdf]` - PDF 文件处理
- `pip install any2summary[server]` - Companion Server
- `pip install any2summary[all]` - 所有可选依赖

## 关键模块

### cli.py 核心函数
- `run()` - CLI 入口，分发子命令
- `_run_doctor_command()` - 健康检查
- `_run_init_command()` - 配置向导
- `_run_summarize_command()` - 主摘要流程
- `_run_single_local_file()` - 本地文件处理
- `_process_local_file()` - 文件类型检测与处理
- `generate_translation_summary()` - Azure 摘要生成
- `_update_progress_bar()` - 进度条渲染（支持 rich 降级）

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
- `test/test_cli_doctor.py` - doctor 命令测试
- `test/test_cli_init.py` - init 命令测试
- `test/test_cli_local_file.py` - 本地文件处理测试
- `test/test_cli_summary_length.py` - 摘要长度控制测试
- `test/test_cli_progress.py` - 进度条渲染测试

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
- `chrome_extension/src/i18n.js` - 国际化工具模块
- `chrome_extension/_locales/` - 多语言消息文件

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
