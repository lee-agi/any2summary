/**
 * 使用 Chrome downloads API 保存摘要为 Markdown 文件
 *
 * 文件命名规则与 cli.py 保持一致：
 * 格式：【{domain}】{title}-{year}-M{month}_summary.md
 * 示例：【Tech】iPhone新品发布-2024-M01_summary.md
 */

/**
 * Domain 规范化映射表（与 cli.py _normalize_domain_label 保持一致）
 * 中文 → 英文标签，或规范化已有的标签
 */
const DOMAIN_MAPPING = {
  // 中文 → 英文
  "科技": "Tech",
  "技术": "Tech",
  "technology": "Tech",
  "科学": "Science",
  "science": "Science",
  "人工智能": "AI",
  "ai": "AI",
  "大模型": "LLM",
  "llm": "LLM",
  "智能体": "Agent",
  "agent": "Agent",
  "商业": "Business",
  "商务": "Business",
  "business": "Business",
  "财经": "Finance",
  "金融": "Finance",
  "finance": "Finance",
  "教育": "Education",
  "学习": "Education",
  "education": "Education",
  "娱乐": "Entertainment",
  "entertainment": "Entertainment",
  "生活": "Lifestyle",
  "lifestyle": "Lifestyle",
  "体育": "Sports",
  "sports": "Sports",
  "医疗": "Medical",
  "医学": "Medical",
  "medical": "Medical",
  "健康": "Health",
  "health": "Health",
  "法律": "Legal",
  "legal": "Legal",
  "产品": "Product",
  "product": "Product",
  // 常见平台（保留原名）
  "youtube": "YouTube",
  "bilibili": "Bilibili",
  "twitter": "Twitter",
  "x": "Twitter",
  "weibo": "Weibo",
  "zhihu": "Zhihu",
  "medium": "Medium",
  "substack": "Substack",
};

/**
 * 规范化 domain 标签（与 cli.py _normalize_domain_label 保持一致）
 * @param {string} domain - 原始 domain 标签
 * @returns {string} 规范化后的英文标签
 */
function normalizeDomainLabel(domain) {
  if (!domain) return "General";

  const text = String(domain).trim();
  if (!text) return "General";

  const lower = text.toLowerCase();

  // 先尝试精确匹配
  if (DOMAIN_MAPPING[text]) {
    return DOMAIN_MAPPING[text];
  }

  // 再尝试小写匹配
  if (DOMAIN_MAPPING[lower]) {
    return DOMAIN_MAPPING[lower];
  }

  // 如果已经是合法的英文标签，保留原样
  if (/^[A-Za-z0-9][A-Za-z0-9_\- ]*$/.test(text)) {
    return text;
  }

  return "General";
}

/**
 * 从URL提取domain，支持从 metadata 中获取 category
 * 优先级：metadata.category > URL hostname 映射
 *
 * @param {string} url - 页面 URL
 * @param {Object} metadata - 元数据对象（可选）
 * @param {string} [metadata.category] - 内容分类
 * @param {string[]} [metadata.categories] - 内容分类数组
 * @returns {string} 规范化的 domain 名称
 */
function extractDomain(url, metadata = {}) {
  // 优先从 metadata 提取 category（确保空字符串不会触发）
  const category = (metadata.category || metadata.categories?.[0] || "").trim();
  if (category) {
    return normalizeDomainLabel(category);
  }

  // 回退到 URL hostname 映射
  try {
    const hostname = new URL(url).hostname;
    // 域名映射表：常见视频/内容网站
    const domainMap = {
      "youtube.com": "YouTube",
      "www.youtube.com": "YouTube",
      "bilibili.com": "Bilibili",
      "www.bilibili.com": "Bilibili",
      "twitter.com": "Twitter",
      "x.com": "Twitter",
      "medium.com": "Medium",
      "substack.com": "Substack",
      "zhihu.com": "Zhihu",
      "www.zhihu.com": "Zhihu",
      "weibo.com": "Weibo",
      "weibo.cn": "Weibo",
    };
    const mapped = domainMap[hostname];
    if (mapped) return mapped;

    // 清理 www 前缀并规范化
    const cleanHost = hostname.replace(/^www\./, "");
    return normalizeDomainLabel(cleanHost);
  } catch {
    return "General";
  }
}

/**
 * 从日期字符串提取年月，格式为 {year}-M{month}
 * 与 cli.py _derive_year_month 保持一致
 *
 * @param {string} publishDateRaw - 发布日期（如 "2024-01-15"、"2024-01" 或 "20240115"）
 * @param {string} [generatedAt=""] - 备选日期（如 "2024-01-15"）
 * @returns {string} 格式化的年月字符串，如 "2024-M01"
 */
function deriveYearMonth(publishDateRaw, generatedAt = "") {
  // 1. 支持 8 位纯数字 YYYYMMDD（与 CLI 一致）
  if (publishDateRaw && /^\d{8}$/.test(publishDateRaw)) {
    return `${publishDateRaw.slice(0, 4)}-M${publishDateRaw.slice(4, 6)}`;
  }

  // 2. 支持 YYYY-MM 或 YYYY-MM-DD 格式
  const match = publishDateRaw?.match(/^(\d{4})-(\d{2})/);
  if (match) {
    return `${match[1]}-M${match[2]}`;
  }

  // 3. 备选：使用 generatedAt（与 CLI 一致）
  const genMatch = generatedAt?.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (genMatch) {
    return `${genMatch[1]}-M${genMatch[2]}`;
  }

  // 4. 默认值（与 CLI 一致："1970", "01"）
  return "1970-M01";
}

/**
 * 清理标题用于文件名（与 cli.py _sanitize_filename_base 保持一致）
 * - 仅删除非法字符：\ / : * ? " < > |（8 个字符）
 * - 仅删除空格
 * @param {string} text - 原始标题
 * @returns {string} 清理后的标题
 */
function sanitizeFilenameBase(text) {
  if (!text) return "summary";

  // 与 cli.py _sanitize_filename_base 保持一致：
  // sanitized = re.sub(r"[\\:*?\"<>|]", "", text)
  // sanitized = sanitized.replace(" ", "")
  let sanitized = text.replace(/[\\/:*?"<>|]/g, "");
  sanitized = sanitized.replace(/ /g, "");

  return sanitized || "summary";
}

/**
 * 清理子目录路径，确保符合 Chrome downloads API 要求
 * - 移除绝对路径前缀（开头的 /）
 * - 移除以 . 开头的目录段（隐藏目录）
 * - 移除目录遍历字符 ..
 * - 如果清理后为空，回退到默认的 "any2summary"
 * @param {string} subdirectory - 原始子目录路径
 * @returns {string} 清理后的子目录路径
 */
function sanitizeSubdirectory(subdirectory) {
  if (!subdirectory) return "any2summary";

  // 移除开头的斜杠（绝对路径转相对路径）
  let cleaned = subdirectory.replace(/^\/+/, "");

  // 按路径分隔符拆分
  const segments = cleaned.split("/");

  // 过滤掉无效的目录段
  const validSegments = segments.filter((seg) => {
    if (!seg) return false; // 空段
    if (seg === "..") return false; // 目录遍历
    if (seg.startsWith(".")) return false; // 隐藏目录
    return true;
  });

  // 重新拼接路径
  cleaned = validSegments.join("/");

  // 如果清理后为空，使用默认值
  if (!cleaned) {
    return "any2summary";
  }

  return cleaned;
}

/**
 * 生成与 cli.py 一致的文件名
 *
 * 格式：【{domain}】{title}-{year}-M{month}_summary.md
 * 示例：【Tech】Claude最新语言模型发布-2025-M01_summary.md
 *
 * @param {string} url - 页面 URL
 * @param {string} title - 页面标题
 * @param {Object} metadata - 元数据对象（同时支持 camelCase 和 snake_case 字段名）
 * @param {string} [metadata.publishDate] - 发布日期 (camelCase)
 * @param {string} [metadata.publish_date] - 发布日期 (snake_case)
 * @param {string} [metadata.uploadDate] - 上传日期 (camelCase)
 * @param {string} [metadata.upload_date] - 上传日期 (snake_case)
 * @param {string} [metadata.category] - 内容分类
 * @param {string[]} [metadata.categories] - 内容分类数组
 * @param {string} [metadata.generatedAt] - 生成时间 (camelCase)
 * @param {string} [metadata.generated_at] - 生成时间 (snake_case)
 * @returns {string} 生成的文件名
 */
function generateFilename(url, title, metadata = {}) {
  // 1. 提取 domain（优先使用 metadata.category）
  const domain = extractDomain(url, metadata);

  // 2. 提取年月（优先使用 publishDate，其次 uploadDate，最后 generatedAt）
  // 同时兼容 camelCase 和 snake_case 字段名（服务器端可能返回不同格式）
  const publishDate =
    metadata.publishDate || metadata.publish_date ||
    metadata.uploadDate || metadata.upload_date || "";
  const generatedAt = metadata.generatedAt || metadata.generated_at || "";
  const yearMonth = deriveYearMonth(publishDate, generatedAt);

  // 3. 清理标题（与 CLI 一致的策略）
  const sanitizedTitle = sanitizeFilenameBase(title || "");

  // 4. 组合：【domain】title-year-Mmonth_summary.md
  return `【${domain}】${sanitizedTitle}-${yearMonth}_summary.md`;
}

/**
 * 将 Blob 转换为 Data URL
 * @param {Blob} blob - 文件 Blob
 * @returns {Promise<string>} Data URL
 */
function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Failed to convert blob to data URL"));
    reader.readAsDataURL(blob);
  });
}

/**
 * 构建 Markdown 内容，包含元信息
 * @param {string} url - 原始 URL
 * @param {string} summary - 摘要内容
 * @param {string} title - 页面标题
 * @returns {string} 完整的 Markdown 内容
 */
function buildMarkdownContent(url, summary, title) {
  const now = new Date().toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
  const header = `---
title: ${title || "Untitled"}
source: ${url}
saved_at: ${now}
---

`;
  return header + summary;
}

/**
 * 使用 Chrome downloads API 保存摘要为 Markdown 文件
 * @param {string} url - 原始页面 URL
 * @param {string} summary - 摘要内容
 * @param {string} title - 页面标题
 * @param {string} subdirectory - 保存子目录（默认 "any2summary"）
 * @param {Object} metadata - 元数据对象（包含 publishDate、uploadDate 等）
 * @returns {Promise<number>} 下载 ID
 */
export async function saveSummaryAsMarkdown(url, summary, title, subdirectory = "any2summary", metadata = {}) {
  const filename = generateFilename(url, title, metadata);
  const content = buildMarkdownContent(url, summary, title);
  const blob = new Blob([content], { type: "text/markdown; charset=utf-8" });
  const dataUrl = await blobToDataUrl(blob);

  // 清理子目录路径（处理绝对路径、隐藏目录等）
  const safeSubdirectory = sanitizeSubdirectory(subdirectory);

  // 构建完整路径
  const fullPath = `${safeSubdirectory}/${filename}`;

  return new Promise((resolve, reject) => {
    chrome.downloads.download(
      {
        url: dataUrl,
        filename: fullPath,
        saveAs: false, // 静默保存，不弹窗
        conflictAction: "uniquify", // 如果文件存在，自动重命名
      },
      (downloadId) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          console.log(`[FileSaver] Summary saved: ${fullPath} (download ID: ${downloadId})`);
          resolve(downloadId);
        }
      }
    );
  });
}

/**
 * 格式化时间戳为 HH:MM:SS 格式
 * @param {number} seconds - 秒数
 * @returns {string} 格式化的时间戳
 */
function formatTimestamp(seconds) {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hrs > 0) {
    return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

/**
 * 构建 Timeline Markdown 内容
 * @param {string} url - 原始 URL
 * @param {Array<{start: number, end: number, text: string, speaker?: string}>} segments - 片段数组
 * @param {string} title - 页面标题
 * @param {Object} metadata - 元数据对象
 * @returns {string} Timeline Markdown 内容
 */
function buildTimelineContent(url, segments, title, metadata = {}) {
  const now = new Date().toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" });
  const lines = [];

  // YAML Front Matter
  lines.push("---");
  lines.push(`title: ${title || "Untitled"} - Timeline`);
  lines.push(`source: ${url}`);
  lines.push(`saved_at: ${now}`);
  lines.push(`segment_count: ${segments.length}`);
  lines.push("---");
  lines.push("");

  // 标题
  lines.push(`# ${title || "Untitled"} - 时间线`);
  lines.push("");

  // 元信息
  if (metadata.author) {
    lines.push(`- 作者/频道: ${metadata.author}`);
  }
  if (metadata.lengthSeconds) {
    const duration = formatTimestamp(metadata.lengthSeconds);
    lines.push(`- 时长: ${duration}`);
  }
  lines.push(`- 片段数: ${segments.length}`);
  lines.push("");

  // Timeline 表格
  lines.push("## 时间线");
  lines.push("");
  lines.push("| 时间 | 说话人 | 内容 |");
  lines.push("|------|--------|------|");

  for (const seg of segments) {
    const startTime = formatTimestamp(seg.start);
    const endTime = formatTimestamp(seg.end);
    const timeRange = `${startTime} - ${endTime}`;
    const speaker = seg.speaker || "-";
    // 转义表格中的管道符
    const text = (seg.text || "").replace(/\|/g, "\\|").replace(/\n/g, " ");
    lines.push(`| ${timeRange} | ${speaker} | ${text} |`);
  }

  return lines.join("\n");
}

/**
 * 使用 Chrome downloads API 保存时间线为 Markdown 文件
 * 文件命名：与 summary 文件相同，但后缀为 _timeline.md
 *
 * @param {string} url - 原始页面 URL
 * @param {Array<{start: number, end: number, text: string, speaker?: string}>} segments - 片段数组
 * @param {string} title - 页面标题
 * @param {string} subdirectory - 保存子目录（默认 "any2summary"）
 * @param {Object} metadata - 元数据对象
 * @returns {Promise<number>} 下载 ID
 */
export async function saveTimelineAsMarkdown(url, segments, title, subdirectory = "any2summary", metadata = {}) {
  // 生成与 summary 一致的基础文件名，但后缀改为 _timeline.md
  const summaryFilename = generateFilename(url, title, metadata);
  const filename = summaryFilename.replace("_summary.md", "_timeline.md");

  const content = buildTimelineContent(url, segments, title, metadata);
  const blob = new Blob([content], { type: "text/markdown; charset=utf-8" });
  const dataUrl = await blobToDataUrl(blob);

  const safeSubdirectory = sanitizeSubdirectory(subdirectory);
  const fullPath = `${safeSubdirectory}/${filename}`;

  return new Promise((resolve, reject) => {
    chrome.downloads.download(
      {
        url: dataUrl,
        filename: fullPath,
        saveAs: false,
        conflictAction: "uniquify",
      },
      (downloadId) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          console.log(`[FileSaver] Timeline saved: ${fullPath} (download ID: ${downloadId})`);
          resolve(downloadId);
        }
      }
    );
  });
}

// 导出辅助函数供其他模块使用
export { normalizeDomainLabel, extractDomain };
