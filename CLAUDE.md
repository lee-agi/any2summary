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

## 版本历史
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
