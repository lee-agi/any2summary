/**
 * Prompt template management module.
 * Ported from cli.py SUMMARY_PROMPT and ARTICLE_SUMMARY_PROMPT.
 *
 * Contains prompt templates for different content types.
 */

/**
 * Video/Podcast summary prompt template.
 * Used for YouTube videos, podcasts, and other media content.
 */
export const VIDEO_SUMMARY_PROMPT = `你是一个可以帮助用户完成AI等相关播客、视频等多模态信息的翻译和总结助手。

你需要完成如下任务：
1. 如果原始是youtube资源或播客音频资源，要保留视频或音频中的时间线。
2. 如果是非中文字幕，将口语化的表达或非关键信息翻译成中文，专业表达和关键信息不要翻译，若翻译务必要附带上原始表达，以保留最准确的原始语言所传达的信息。
3. 如果内容很长（比如超过2000字），可以先给出"摘要"，可以根据"主题"做分段，每段的标题即为提取的"主题"，每段300字左右。如果是多人对话，每段以\`说话人\`的姓名开始，按不同的\`说话人\`分段，每段内同一个人连续的说话内容务必要合成一段，不需要和时间线脚本中的分段方式一致。\`说话人\`的姓名要根据全文推导，最好不要用A、B、C等代替。
4. 将你认为重要的、insightful、非共识的内容直接在原文中markdown加粗标识，特别重要的可以markdown语法高亮，以便阅读，但加粗/高亮的内容不宜太多。


注意：
1. 翻译要求：1）专业词汇和人名不要翻译，例如\`agent\`、\`llm\`、\`Sam\`不要翻译，或后面加上原始词，比如费曼图（Feynman diagram）。2）翻译过程中千万不要有任何原始信息的压缩、省略或遗漏，仅可以删掉一些无意义的口语表达或广告内容，比如uh、yeah等。3）始终用第一人称翻译，不要用转述的方式。
2. markdown格式输出，输出格式可参考（但不必一定遵守）：\`##摘要：最好不超过5句话，除非必要，比如信息密度特别高，可包含一些非共识的insight。\\n\\n##原始全文\\n###<主题1>（00:00:00 - 00:05:03）\\n**<说话人名1>**：<xxx>。\\n**<说话人名2>**：<xxx>。\\n###<主题2>（00:05:03 - 00:09:52）\\n**<说话人名2>**：<xxx>。\\n**<说话人名1>**：<xxx>。......\`。\`<>\`中是需要你分析后充的内容，其中"摘要"是二级标题，"原始全文"是二级标题，"<主题编号>"是三级标题。
3. "原始全文"中要包含完成的原始信息，禁止做任何信息压缩或总结，以方便追溯原意。
`;

/**
 * Article summary prompt template.
 * Used for web articles, blog posts, and text content.
 */
export const ARTICLE_SUMMARY_PROMPT = `你是一个英文文章翻译和总结助手。你的任务是先自动抓取原文（包括关键图表等），然后分析该文章中的内容。

你的输出包含:
## 总结
最好不超过5句话，除非必要，比如信息密度特别高的文章可超过5句，包含一些非共识的insight会更好。

## 要点
1. 要点最好以层次化、结构化的方式展现。
2. 每一个要点必须是一个观点/结论/事实。
3. 要点之间最好有逻辑关系，当然要以忠实于原文为基础。

## 翻译要求
1. 如果是非中文，先将口语化的表达或非关键信息翻译成中文，专业表达和关键信息不要翻译，若要翻译务必要附带上原文，以保留最准确的原始语言所传达的信息。
2. 专业词汇和人名不要翻译，例如\`agent\`、\`llm\`、\`Sam\`不要翻译，或后面加上原始词，例如费曼图（Feynman diagram）。
3. 翻译过程中千万不要压缩、省略或遗漏任何原始语言传达的信息，仅可以删掉一些无意义的口语表达或广告内容，比如uh、yeah等。
4. 将你认为重要的、insightful、非共识的内容直接在原文中markdown加粗标识，特别重要的可以markdown语法高亮，以便阅读，但加粗/高亮的内容不宜太多。
`;

/**
 * Domain classification prompt.
 * Used to classify content into domains.
 */
export const DOMAIN_PROMPT = `你将收到一段中文摘要，请根据内容判断最贴切的领域标签。直接输出一个中文标签，避免解释或补充说明。`;

/**
 * Simple URL summary prompt (fallback).
 * Used when content extraction fails.
 */
export const SIMPLE_URL_PROMPT = `请总结此链接的内容，输出markdown格式：`;

/**
 * Get the appropriate prompt for a content type.
 * @param {"video"|"audio"|"article"|"url"} contentType
 * @returns {string}
 */
export function getPromptForContentType(contentType) {
  switch (contentType) {
    case "video":
    case "audio":
      return VIDEO_SUMMARY_PROMPT;
    case "article":
      return ARTICLE_SUMMARY_PROMPT;
    case "url":
    default:
      return SIMPLE_URL_PROMPT;
  }
}

/**
 * Build the full prompt with content.
 * @param {string} systemPrompt - The system prompt template
 * @param {string} content - The actual content to summarize
 * @param {Object} metadata - Optional metadata (title, url, etc.)
 * @returns {{systemPrompt: string, userPrompt: string}}
 */
export function buildPromptWithContent(systemPrompt, content, metadata = {}) {
  const userParts = [];

  if (metadata.title) {
    userParts.push(`标题: ${metadata.title}`);
  }

  if (metadata.url) {
    userParts.push(`来源: ${metadata.url}`);
  }

  if (metadata.author) {
    userParts.push(`作者: ${metadata.author}`);
  }

  if (metadata.publishDate) {
    userParts.push(`发布日期: ${metadata.publishDate}`);
  }

  if (userParts.length > 0) {
    userParts.push("");
    userParts.push("---");
    userParts.push("");
  }

  userParts.push(content);

  return {
    systemPrompt,
    userPrompt: userParts.join("\n"),
  };
}

/**
 * Build prompt for video/podcast content with transcript.
 * @param {Array<{start: number, end: number, text: string, speaker?: string}>} segments
 * @param {Object} metadata
 * @returns {{systemPrompt: string, userPrompt: string}}
 */
export function buildVideoPrompt(segments, metadata = {}) {
  const timeline = formatSegmentsAsTimeline(segments);

  const userParts = [];

  if (metadata.title) {
    userParts.push(`标题: ${metadata.title}`);
  }

  if (metadata.url) {
    userParts.push(`来源: ${metadata.url}`);
  }

  if (metadata.author) {
    userParts.push(`作者/频道: ${metadata.author}`);
  }

  if (metadata.lengthSeconds) {
    userParts.push(`时长: ${formatDuration(metadata.lengthSeconds)}`);
  }

  if (userParts.length > 0) {
    userParts.push("");
    userParts.push("---");
    userParts.push("");
  }

  userParts.push("原始 ASR 片段如下：");
  userParts.push("");
  userParts.push(timeline);

  return {
    systemPrompt: VIDEO_SUMMARY_PROMPT,
    userPrompt: userParts.join("\n"),
  };
}

/**
 * Build prompt for article content.
 * @param {string} articleContent
 * @param {Object} metadata
 * @returns {{systemPrompt: string, userPrompt: string}}
 */
export function buildArticlePrompt(articleContent, metadata = {}) {
  const userParts = [];

  if (metadata.title) {
    userParts.push(`标题: ${metadata.title}`);
  }

  if (metadata.url) {
    userParts.push(`来源: ${metadata.url}`);
  }

  if (metadata.author) {
    userParts.push(`作者: ${metadata.author}`);
  }

  if (metadata.publishDate) {
    userParts.push(`发布日期: ${metadata.publishDate}`);
  }

  if (userParts.length > 0) {
    userParts.push("");
    userParts.push("---");
    userParts.push("");
  }

  userParts.push("文章内容：");
  userParts.push("");
  userParts.push(articleContent);

  // Add image references if available
  if (metadata.imageUrls && metadata.imageUrls.length > 0) {
    userParts.push("");
    userParts.push("---");
    userParts.push("");
    userParts.push("文章包含的图片：");
    metadata.imageUrls.slice(0, 10).forEach((url, i) => {
      userParts.push(`[图片 ${i + 1}]: ${url}`);
    });
  }

  return {
    systemPrompt: ARTICLE_SUMMARY_PROMPT,
    userPrompt: userParts.join("\n"),
  };
}

/**
 * Format transcript segments as timeline.
 * @param {Array<{start: number, end: number, text: string, speaker?: string}>} segments
 * @returns {string}
 */
function formatSegmentsAsTimeline(segments) {
  return segments
    .map((seg) => {
      const startTime = formatTimestamp(seg.start);
      const endTime = formatTimestamp(seg.end);
      const speaker = seg.speaker ? `${seg.speaker}: ` : "";
      return `${startTime} - ${endTime} | ${speaker}${seg.text}`;
    })
    .join("\n");
}

/**
 * Format seconds to HH:MM:SS timestamp.
 * @param {number} seconds
 * @returns {string}
 */
function formatTimestamp(seconds) {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Format duration in seconds to human-readable string.
 * @param {number} seconds
 * @returns {string}
 */
function formatDuration(seconds) {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hrs > 0) {
    return `${hrs}小时${mins}分钟`;
  }
  if (mins > 0) {
    return `${mins}分钟${secs}秒`;
  }
  return `${secs}秒`;
}
