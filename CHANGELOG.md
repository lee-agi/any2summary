# Changelog

## 1.0.2 - 2026-01-24
- Chrome 扩展修复 YouTube 字幕获取失败时的回退逻辑：当字幕不可用时（如视频无字幕、语言不匹配），自动回退到本地服务音频转录能力，而非简单发送 URL 给 AI。
- 新增测试 `test_youtube_transcript_fallback.py` 验证回退逻辑正确性。
- **修复本地服务器 API 请求格式问题**：`/api/transcribe` 和 `/api/summarize` 端点现使用 Pydantic 模型接收 JSON 请求体，与 Chrome 扩展的 `fetch()` 调用格式匹配（此前服务器期望查询参数而非请求体，导致 422 错误）。

## 1.0.1 - 2026-01-22
- Chrome 扩展修复 Popup 状态丢失问题：使用 `DOMContentLoaded` + `document.readyState` 双重保险确保 DOM 就绪后再恢复状态。
- Chrome 扩展增强调试日志：所有模块添加带前缀的日志输出（`[Popup]`/`[SidePanel]`/`[Storage]`/`[Background]`），便于追踪状态保存和恢复流程。

## 1.0.0 - 2025-02-13
- 首次公开版本，提供播客、视频与文章的一键处理：下载、转录、可选 Azure 说话人分离，以及 Markdown 摘要输出。
- 支持批量 URL 并发处理，保持输出顺序一致。
- 文章模式保留图片与表格链接，生成 Markdown 便于直接纳入笔记系统。
- Chrome 扩展补齐默认图标集（16/48/128 px），避免加载失败并新增清单校验。
- Chrome 扩展新增 side_panel 支持与通知权限：弹窗/后台广播状态到侧栏，摘要完成或失败时推送浏览器通知。
- Chrome 扩展增加快捷键 `Ctrl+Shift+S` 触发摘要（macOS 上 Ctrl=Command），并在错误/成功时均推送通知。
- Azure diarization 增加流式中断兼容（RemoteProtocolError/httpcore.RemoteProtocolError），保留已收集 chunk 并记录 WARNING；支持分段级 checkpoint (`diarization.partial.json`) 断点续跑；对单段网络/传输错误内建最多两次尝试，重试前写入 checkpoint。
- 测试体系强化：新增 `e2e` 标记及凭据检查工具，默认跳过真实 Azure 调用；要求通过环境变量/CI Secrets 注入最小权限密钥，避免日志泄漏。
