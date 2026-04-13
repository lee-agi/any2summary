/**
 * Article content extraction module.
 * Ported from cli.py _ArticleHTMLParser class.
 *
 * Extracts article content, metadata, images, and tables from HTML.
 *
 * NOTE: This module is designed for Service Worker environment.
 * DOM parsing is done via chrome.scripting.executeScript in page context,
 * or via regex fallback for fetch-based extraction.
 */

/**
 * Normalize article text by collapsing whitespace.
 * @param {string} text
 * @returns {string}
 */
function normalizeArticleText(text) {
  return (text || "").replace(/\s+/g, " ").trim();
}

/**
 * Resolve a URL relative to a base URL.
 * @param {string} url
 * @param {string} baseUrl
 * @returns {string}
 */
function resolveUrl(url, baseUrl) {
  if (!url) return "";
  if (!baseUrl) return url;

  try {
    return new URL(url, baseUrl).href;
  } catch {
    return url;
  }
}

/**
 * DOM parsing function to be executed in page context via chrome.scripting.executeScript.
 * This function must be self-contained (no external dependencies).
 *
 * NOTE: This function runs in PAGE CONTEXT (not Service Worker), so it CAN use
 * document, window, and DOMParser. The test should exclude this function.
 *
 * @returns {Object} Parsed article data
 */
function parseArticleInPageContext() {
  // PAGE_CONTEXT_FUNCTION_START
  const normalizeText = (text) => (text || "").replace(/\s+/g, " ").trim();

  const doc = document;
  const pageUrl = window.location.href;

  // Extract title
  let title = "";
  const titleEl = doc.querySelector("title");
  if (titleEl) {
    title = normalizeText(titleEl.textContent);
  }
  if (!title) {
    const h1El = doc.querySelector("h1");
    if (h1El) {
      title = normalizeText(h1El.textContent);
    }
  }

  // Extract description from meta tags
  let description = "";
  const descMeta =
    doc.querySelector('meta[name="description"]') ||
    doc.querySelector('meta[property="og:description"]') ||
    doc.querySelector('meta[name="twitter:description"]');
  if (descMeta) {
    description = normalizeText(descMeta.getAttribute("content"));
  }

  // Extract author
  let author = "";
  const authorMeta =
    doc.querySelector('meta[name="author"]') ||
    doc.querySelector('meta[property="article:author"]');
  if (authorMeta) {
    author = normalizeText(authorMeta.getAttribute("content"));
  }

  // Extract publish date
  let publishDate = "";
  const dateMeta =
    doc.querySelector('meta[property="article:published_time"]') ||
    doc.querySelector('meta[name="date"]') ||
    doc.querySelector('meta[property="og:updated_time"]');
  if (dateMeta) {
    publishDate = dateMeta.getAttribute("content");
  }

  // Extract favicon
  let iconHref = null;
  const iconLink =
    doc.querySelector('link[rel="icon"]') ||
    doc.querySelector('link[rel="shortcut icon"]') ||
    doc.querySelector('link[rel="apple-touch-icon"]');
  if (iconLink) {
    iconHref = iconLink.getAttribute("href");
  }

  // Extract Open Graph image
  let ogImage = "";
  const ogImageMeta = doc.querySelector('meta[property="og:image"]');
  if (ogImageMeta) {
    try {
      ogImage = new URL(ogImageMeta.getAttribute("content"), pageUrl).href;
    } catch {
      ogImage = ogImageMeta.getAttribute("content");
    }
  }

  // Extract paragraphs
  const paragraphs = [];
  const paragraphEls = doc.querySelectorAll("p, li, article p, article li, main p, main li");
  for (const el of paragraphEls) {
    if (el.closest("script, style, nav, footer, header")) {
      continue;
    }
    const text = normalizeText(el.textContent);
    if (text && text.length > 20) {
      paragraphs.push(text);
    }
  }

  // Extract images
  const imageUrls = [];
  const imgEls = doc.querySelectorAll("img");
  for (const img of imgEls) {
    const src = img.getAttribute("src") || img.getAttribute("data-src");
    if (src) {
      try {
        const resolved = new URL(src, pageUrl).href;
        if (!imageUrls.includes(resolved)) {
          imageUrls.push(resolved);
        }
      } catch {
        if (!imageUrls.includes(src)) {
          imageUrls.push(src);
        }
      }
    }
  }

  // Extract tables
  const tableUrls = [];
  const tableEls = doc.querySelectorAll("table");
  for (const table of tableEls) {
    const id = table.getAttribute("id");
    if (id) {
      tableUrls.push(`${pageUrl}#${id}`);
    }
  }

  // Extract main content
  const unwantedSelectors = [
    "script", "style", "nav", "footer", "header", "aside",
    ".sidebar", ".comments", ".advertisement", ".ad",
    "#comments", ".social-share", ".related-posts",
  ];

  // Clone body and remove unwanted elements
  const bodyClone = doc.body.cloneNode(true);
  for (const selector of unwantedSelectors) {
    const elements = bodyClone.querySelectorAll(selector);
    for (const el of elements) {
      el.remove();
    }
  }

  // Try to find main content container
  const contentSelectors = [
    "article", '[role="main"]', "main", ".post-content",
    ".article-content", ".entry-content", ".content",
    "#content", ".post", ".article",
  ];

  let contentEl = null;
  for (const selector of contentSelectors) {
    contentEl = bodyClone.querySelector(selector);
    if (contentEl) break;
  }

  if (!contentEl) {
    contentEl = bodyClone;
  }

  // Extract text content with structure
  const lines = [];
  const blockTags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre", "div"];
  const blocks = contentEl.querySelectorAll(blockTags.join(", "));

  for (const block of blocks) {
    const text = normalizeText(block.textContent);
    if (text && text.length > 10) {
      lines.push(text);
    }
  }

  const mainContent = [...new Set(lines)].join("\n\n");

  return {
    title,
    description,
    author,
    publishDate,
    iconHref,
    ogImage,
    paragraphs,
    imageUrls,
    tableUrls,
    mainContent,
    url: pageUrl,
  };
  // PAGE_CONTEXT_FUNCTION_END
}

/**
 * Parse article HTML using regex (fallback for Service Worker).
 * Less accurate than DOM parsing but works without DOM APIs.
 * @param {string} htmlText - HTML content
 * @param {string} pageUrl - URL of the page
 * @returns {Object}
 */
function parseArticleHtmlWithRegex(htmlText, pageUrl = null) {
  // Extract title
  let title = "";
  const titleMatch = htmlText.match(/<title[^>]*>([^<]*)<\/title>/i);
  if (titleMatch) {
    title = normalizeArticleText(titleMatch[1]);
  }
  if (!title) {
    const h1Match = htmlText.match(/<h1[^>]*>([^<]*)<\/h1>/i);
    if (h1Match) {
      title = normalizeArticleText(h1Match[1]);
    }
  }

  // Extract meta description
  let description = "";
  const descMatch = htmlText.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']*)["']/i) ||
    htmlText.match(/<meta[^>]*content=["']([^"']*)["'][^>]*name=["']description["']/i) ||
    htmlText.match(/<meta[^>]*property=["']og:description["'][^>]*content=["']([^"']*)["']/i);
  if (descMatch) {
    description = normalizeArticleText(descMatch[1]);
  }

  // Extract author
  let author = "";
  const authorMatch = htmlText.match(/<meta[^>]*name=["']author["'][^>]*content=["']([^"']*)["']/i) ||
    htmlText.match(/<meta[^>]*content=["']([^"']*)["'][^>]*name=["']author["']/i);
  if (authorMatch) {
    author = normalizeArticleText(authorMatch[1]);
  }

  // Extract publish date
  let publishDate = "";
  const dateMatch = htmlText.match(/<meta[^>]*property=["']article:published_time["'][^>]*content=["']([^"']*)["']/i);
  if (dateMatch) {
    publishDate = dateMatch[1];
  }

  // Extract OG image
  let ogImage = "";
  const ogMatch = htmlText.match(/<meta[^>]*property=["']og:image["'][^>]*content=["']([^"']*)["']/i);
  if (ogMatch) {
    ogImage = resolveUrl(ogMatch[1], pageUrl);
  }

  // Extract paragraphs (simple regex extraction)
  const paragraphs = [];
  const pMatches = htmlText.matchAll(/<p[^>]*>([^<]+(?:<[^/p][^>]*>[^<]*<\/[^p][^>]*>)*[^<]*)<\/p>/gi);
  for (const match of pMatches) {
    // Strip HTML tags from paragraph content
    const text = normalizeArticleText(match[1].replace(/<[^>]*>/g, ""));
    if (text && text.length > 20) {
      paragraphs.push(text);
    }
  }

  // Extract images
  const imageUrls = [];
  const imgMatches = htmlText.matchAll(/<img[^>]*(?:src|data-src)=["']([^"']+)["']/gi);
  for (const match of imgMatches) {
    const resolved = resolveUrl(match[1], pageUrl);
    if (resolved && !imageUrls.includes(resolved)) {
      imageUrls.push(resolved);
    }
  }

  // Simple main content extraction: get all text between body tags, strip scripts/styles
  let mainContent = "";
  const bodyMatch = htmlText.match(/<body[^>]*>([\s\S]*)<\/body>/i);
  if (bodyMatch) {
    let bodyContent = bodyMatch[1];
    // Remove script and style tags with content
    bodyContent = bodyContent.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "");
    bodyContent = bodyContent.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "");
    bodyContent = bodyContent.replace(/<nav[^>]*>[\s\S]*?<\/nav>/gi, "");
    bodyContent = bodyContent.replace(/<footer[^>]*>[\s\S]*?<\/footer>/gi, "");
    bodyContent = bodyContent.replace(/<header[^>]*>[\s\S]*?<\/header>/gi, "");
    // Strip remaining HTML tags
    mainContent = normalizeArticleText(bodyContent.replace(/<[^>]*>/g, " "));
  }

  return {
    title,
    description,
    author,
    publishDate,
    iconHref: null,
    ogImage,
    paragraphs,
    imageUrls,
    tableUrls: [],
    mainContent,
  };
}

/**
 * Fetch and parse article content from URL using chrome.scripting.executeScript.
 * Falls back to fetch + regex parsing if scripting is not available.
 * @param {string} url
 * @param {number} [tabId] - Optional tab ID to use for scripting
 * @param {AbortSignal} [signal] - Optional abort signal
 * @returns {Promise<Object>}
 */
export async function fetchArticleContent(url, tabId = null, signal = null) {
  // Try to use chrome.scripting.executeScript if tabId is provided
  if (tabId && typeof chrome !== "undefined" && chrome.scripting) {
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: parseArticleInPageContext,
      });

      if (results && results[0] && results[0].result) {
        console.log("[ArticleParser] Extracted article via scripting API");
        return {
          ...results[0].result,
          rawHtml: null, // Not available via scripting
        };
      }
    } catch (error) {
      console.warn("[ArticleParser] Scripting API failed, falling back to fetch:", error.message);
    }
  }

  // Fallback: fetch HTML and parse with regex
  console.log("[ArticleParser] Using fetch + regex fallback for:", url);

  const response = await fetch(url, {
    headers: {
      Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
    signal,
  });

  if (!response.ok) {
    throw new Error(`获取文章内容失败: ${response.status}`);
  }

  const htmlText = await response.text();
  const parsed = parseArticleHtmlWithRegex(htmlText, url);

  return {
    ...parsed,
    rawHtml: htmlText,
  };
}

/**
 * Format article content for summarization.
 * @param {Object} article - Parsed article object
 * @returns {string}
 */
export function formatArticleForSummary(article) {
  const parts = [];

  if (article.title) {
    parts.push(`标题: ${article.title}`);
  }

  if (article.author) {
    parts.push(`作者: ${article.author}`);
  }

  if (article.publishDate) {
    parts.push(`发布日期: ${article.publishDate}`);
  }

  if (article.description) {
    parts.push(`描述: ${article.description}`);
  }

  parts.push("");
  parts.push("正文内容:");
  parts.push("");

  if (article.mainContent) {
    parts.push(article.mainContent);
  } else if (article.paragraphs && article.paragraphs.length > 0) {
    parts.push(article.paragraphs.join("\n\n"));
  }

  // Add image references
  if (article.imageUrls && article.imageUrls.length > 0) {
    parts.push("");
    parts.push("文章图片:");
    article.imageUrls.slice(0, 10).forEach((url, i) => {
      parts.push(`[图片 ${i + 1}]: ${url}`);
    });
  }

  // Add table references
  if (article.tableUrls && article.tableUrls.length > 0) {
    parts.push("");
    parts.push("文章表格:");
    article.tableUrls.forEach((url, i) => {
      parts.push(`[表格 ${i + 1}]: ${url}`);
    });
  }

  return parts.join("\n");
}

/**
 * Extract article metadata for display.
 * @param {Object} article
 * @returns {Object}
 */
export function extractArticleMetadata(article) {
  return {
    title: article.title || "",
    author: article.author || "",
    description: article.description || "",
    publishDate: article.publishDate || "",
    thumbnail: article.ogImage || (article.imageUrls && article.imageUrls[0]) || "",
    wordCount: countWords(article.mainContent || article.paragraphs?.join(" ") || ""),
    estimatedReadingMinutes: estimateReadingTime(
      article.mainContent || article.paragraphs?.join(" ") || ""
    ),
  };
}

/**
 * Count words in text (handles both CJK and Latin text).
 * @param {string} text
 * @returns {number}
 */
function countWords(text) {
  if (!text) return 0;

  // Count CJK characters
  const cjkChars = (text.match(/[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]/g) || []).length;

  // Count non-CJK words
  const nonCjkText = text.replace(/[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]/g, " ");
  const latinWords = nonCjkText.split(/\s+/).filter((w) => w.length > 0).length;

  return cjkChars + latinWords;
}

/**
 * Estimate reading time in minutes.
 * @param {string} text
 * @returns {number}
 */
function estimateReadingTime(text) {
  const wordCount = countWords(text);
  // Assume 300 words per minute for Chinese, 200 for English
  const wordsPerMinute = 250;
  return Math.max(1, Math.ceil(wordCount / wordsPerMinute));
}

// Export for testing
export { parseArticleHtmlWithRegex, parseArticleInPageContext };
