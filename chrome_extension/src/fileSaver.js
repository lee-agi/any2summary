/**
 * 使用 Chrome downloads API 保存摘要为 Markdown 文件
 *
 * 文件命名规则与 cli.py 保持一致：
 * 格式：【{domain}】{title}-{year}-M{month}_summary.md
 * 示例：【YouTube】iPhone新品发布-2024-M01_summary.md
 */

/**
 * 从URL提取domain并映射为友好名称
 * @param {string} url - 页面 URL
 * @returns {string} 友好的domain名称
 */
function extractDomain(url) {
  try {
    const hostname = new URL(url).hostname;
    // 域名映射表：常见视频网站
    const domainMap = {
      "youtube.com": "YouTube",
      "www.youtube.com": "YouTube",
      "bilibili.com": "Bilibili",
      "www.bilibili.com": "Bilibili",
    };
    return domainMap[hostname] || hostname.replace(/^www\./, "");
  } catch {
    return "unknown";
  }
}

/**
 * 从日期字符串提取年月，格式为 {year}-M{month}
 * @param {string} dateStr - 日期字符串（如 "2024-01-15" 或 "2024-01"）
 * @returns {string} 格式化的年月字符串，如 "2024-M01"
 */
function deriveYearMonth(dateStr) {
  const now = new Date();
  let year = now.getFullYear();
  let month = now.getMonth() + 1;

  if (dateStr) {
    const match = dateStr.match(/(\d{4})-?(\d{2})/);
    if (match) {
      year = parseInt(match[1], 10);
      month = parseInt(match[2], 10);
    }
  }
  return `${year}-M${String(month).padStart(2, "0")}`;
}

/**
 * 黑名单清理标题（与cli.py一致）
 * - 删除非法字符：\ / : * ? " < > | `
 * - 删除空格
 * - 删除控制字符和零宽字符
 * - 删除emoji和其他特殊符号
 * @param {string} text - 原始标题
 * @returns {string} 清理后的标题
 */
function sanitizeFilenameBase(text) {
  if (!text) return "summary";

  let result = text
    // 删除非法字符（Windows/Mac/Linux 文件系统通用黑名单）
    .replace(/[\\/:*?"<>|`#@!$%^&()+=[\]{}~;',]/g, "")
    // 删除控制字符 (0x00-0x1F)
    .replace(/[\x00-\x1f]/g, "")
    // 删除零宽字符
    .replace(/[\u200b-\u200d\ufeff]/g, "")
    // 删除emoji (主要范围)
    .replace(/[\u{1F300}-\u{1F9FF}]/gu, "")
    .replace(/[\u{2600}-\u{26FF}]/gu, "")
    .replace(/[\u{2700}-\u{27BF}]/gu, "")
    // 删除所有空白字符（空格、制表符、换行等）
    .replace(/\s+/g, "")
    // 删除开头的点（避免隐藏文件）
    .replace(/^\.+/, "")
    // 截断到合理长度
    .substring(0, 100);

  // 如果结果为空或只包含点和横线，返回默认值
  if (!result || /^[.-]+$/.test(result)) {
    return "summary";
  }

  return result;
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
 * 示例：【YouTube】iPhone新品发布-2024-M01_summary.md
 *
 * @param {string} url - 页面 URL
 * @param {string} title - 页面标题
 * @param {Object} metadata - 元数据对象
 * @param {string} [metadata.publishDate] - 发布日期
 * @param {string} [metadata.uploadDate] - 上传日期（YouTube）
 * @returns {string} 生成的文件名
 */
function generateFilename(url, title, metadata = {}) {
  // 1. 提取 domain
  const domain = extractDomain(url);

  // 2. 提取年月（优先使用 publishDate，其次 uploadDate）
  const publishDate = metadata.publishDate || metadata.uploadDate || "";
  const yearMonth = deriveYearMonth(publishDate);

  // 3. 清理标题（黑名单策略）
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
