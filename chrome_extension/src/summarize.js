/**
 * Main summarization module.
 * Integrates content detection, extraction, and AI summarization.
 *
 * Supports:
 * - YouTube videos (transcript extraction + summarization)
 * - Articles (HTML parsing + summarization)
 * - General URLs (direct AI summarization)
 * - Audio/Video transcription via local companion server
 */

import { detectContentType, isYouTubeUrl } from "./contentDetector.js";
import { fetchYouTubeTranscript } from "./youtubeTranscript.js";
import { fetchArticleContent, formatArticleForSummary, extractArticleMetadata } from "./articleParser.js";
import { buildVideoPrompt, buildArticlePrompt, SIMPLE_URL_PROMPT, DOMAIN_PROMPT } from "./prompts.js";
import { normalizeDomainLabel } from "./fileSaver.js";
import { buildLengthPromptModifier } from "./config.js";

/**
 * Check if local companion server is available.
 * @param {string} serverUrl - The local server URL
 * @param {AbortSignal} [signal] - Optional abort signal
 * @returns {Promise<Object|null>} Server health info or null if unavailable
 */
async function checkLocalServerHealth(serverUrl, signal) {
  try {
    const response = await fetch(`${serverUrl}/api/health`, {
      method: "GET",
      headers: { "Accept": "application/json" },
      signal,
    });
    if (response.ok) {
      return response.json();
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Call local server for audio transcription.
 * @param {string} url - The video/audio URL to transcribe
 * @param {Object} settings - Settings including local_server_url
 * @param {Object} options - Additional options
 * @param {AbortSignal} [options.signal] - Optional abort signal
 * @returns {Promise<Object>} Transcription result with speakers and transcript
 */
async function callLocalServerTranscribe(url, settings, options = {}) {
  const serverUrl = settings.local_server_url || "http://127.0.0.1:8765";

  console.log("[Summarize] Calling local server for transcription:", url);

  const response = await fetch(`${serverUrl}/api/transcribe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url,
      language: options.language || "en",
      max_speakers: options.maxSpeakers,
      known_speaker_names: options.knownSpeakerNames,
      streaming: options.streaming !== false,
    }),
    signal: options.signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("[Summarize] Local server transcription error:", errorText);
    throw new Error(`本地服务转写失败: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Call local server for full summarization.
 * @param {string} url - The URL to summarize
 * @param {Object} settings - Settings
 * @param {Object} options - Additional options
 * @param {AbortSignal} [options.signal] - Optional abort signal
 * @returns {Promise<Object>} Summarization result
 */
async function callLocalServerSummarize(url, settings, options = {}) {
  const serverUrl = settings.local_server_url || "http://127.0.0.1:8765";

  console.log("[Summarize] Calling local server for summarization:", url);

  const response = await fetch(`${serverUrl}/api/summarize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url,
      language: options.language || "en",
      azure_summary: true,
      azure_streaming: options.streaming !== false,
      force_azure_diarization: options.forceAzureDiarization || false,
    }),
    signal: options.signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("[Summarize] Local server summarization error:", errorText);
    throw new Error(`本地服务摘要失败: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Check if local server is enabled and available.
 * @param {Object} settings
 * @param {AbortSignal} [signal] - Optional abort signal
 * @returns {Promise<boolean>}
 */
async function isLocalServerAvailable(settings, signal) {
  if (!settings.local_server_enabled) {
    return false;
  }
  const health = await checkLocalServerHealth(settings.local_server_url, signal);
  return health !== null && health.status === "ok";
}

/**
 * Build request headers for Azure OpenAI API.
 * @param {Object} settings
 * @returns {Object}
 */
function buildHeaders(settings) {
  const headers = {
    "Content-Type": "application/json",
  };
  if (settings.api_key) {
    headers["api-key"] = settings.api_key;
  }
  return headers;
}

/**
 * Build API URL based on settings.
 * @param {Object} settings
 * @returns {string}
 */
function buildUrl(settings) {
  const base = settings.azure_endpoint.replace(/\/$/, "");
  // Responses API uses /openai/v1/responses (Azure AI Foundry format, no api-version needed)
  // Chat Completions API uses /openai/deployments/{deployment}/chat/completions
  if (settings.use_responses_api) {
    return base + "/openai/v1/responses";
  }
  const url = new URL(base + "/openai/deployments/" + settings.deployment + "/chat/completions");
  url.searchParams.set("api-version", settings.azure_api_version || "2025-04-01-preview");
  return url.toString();
}

/**
 * Build request body for Responses API.
 * @param {string} systemPrompt
 * @param {string} userPrompt
 * @param {Object} settings
 * @param {Object} options
 * @returns {Object}
 */
function buildResponsesApiBody(systemPrompt, userPrompt, settings, options) {
  const input = [];

  if (systemPrompt) {
    input.push({
      role: "system",
      content: [{ type: "input_text", text: systemPrompt }],
    });
  }

  input.push({
    role: "user",
    content: [{ type: "input_text", text: userPrompt }],
  });

  return {
    model: settings.deployment,
    input,
    max_output_tokens: options.max_output_tokens || 16384,
  };
}

/**
 * Build request body for Chat Completions API.
 * @param {string} systemPrompt
 * @param {string} userPrompt
 * @param {Object} settings
 * @param {Object} options
 * @returns {Object}
 */
function buildChatCompletionsBody(systemPrompt, userPrompt, settings, options) {
  const messages = [];

  if (systemPrompt) {
    messages.push({ role: "system", content: systemPrompt });
  }

  messages.push({ role: "user", content: userPrompt });

  return {
    messages,
    model: settings.deployment,
    temperature: options.temperature ?? 0.3,
    max_tokens: options.max_output_tokens || 16384,
  };
}

/**
 * Call Azure OpenAI API.
 * @param {string} systemPrompt
 * @param {string} userPrompt
 * @param {Object} settings
 * @param {Object} options
 * @param {AbortSignal} [options.signal] - Optional abort signal
 * @returns {Promise<Object>}
 */
async function callAzureOpenAI(systemPrompt, userPrompt, settings, options) {
  const endpoint = buildUrl(settings);
  const headers = buildHeaders(settings);

  const body = settings.use_responses_api
    ? buildResponsesApiBody(systemPrompt, userPrompt, settings, options)
    : buildChatCompletionsBody(systemPrompt, userPrompt, settings, options);

  console.log("[Summarize] Request URL:", endpoint);
  console.log("[Summarize] Request body preview:", JSON.stringify(body, null, 2).slice(0, 500) + "...");

  const response = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: options.signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("[Summarize] Error response:", errorText);
    throw new Error(`API 调用失败: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Extract text from API response.
 * @param {Object} response
 * @param {Object} settings
 * @returns {string}
 */
function extractResponseText(response, settings) {
  if (settings.use_responses_api) {
    // Responses API format
    if (response.output_text) {
      return response.output_text;
    }

    // Try to extract from output array
    const output = response.output || response.data || [];
    if (Array.isArray(output)) {
      const texts = [];
      for (const item of output) {
        if (item.content) {
          if (Array.isArray(item.content)) {
            for (const part of item.content) {
              if (part.text) texts.push(part.text);
            }
          } else if (typeof item.content === "string") {
            texts.push(item.content);
          }
        }
      }
      if (texts.length > 0) {
        return texts.join("\n");
      }
    }

    return JSON.stringify(response);
  }

  // Chat Completions API format
  const choices = response.choices || [];
  if (choices.length > 0) {
    return choices[0].message?.content || "";
  }

  return "";
}

/**
 * Process YouTube video URL.
 * @param {string} url
 * @param {Object} settings
 * @param {Object} options
 * @param {AbortSignal} [options.signal] - Optional abort signal
 * @returns {Promise<Object>}
 */
async function processYouTubeVideo(url, settings, options) {
  console.log("[Summarize] Processing YouTube video:", url);

  let segments, metadata;

  try {
    // Fetch transcript (use local server if enabled for proxy support)
    const result = await fetchYouTubeTranscript(url, {
      preferredLanguages: options.preferredLanguages || ["en", "zh-Hans", "zh-Hant"],
      serverUrl: settings.local_server_url,
      useLocalServer: settings.local_server_enabled,
      signal: options.signal,
    });
    segments = result.segments;
    metadata = result.metadata;
    console.log("[Summarize] Fetched", segments.length, "transcript segments");
  } catch (transcriptError) {
    // Re-throw abort errors immediately
    if (transcriptError.name === "AbortError") {
      throw transcriptError;
    }

    // Transcript fetch failed, try local server audio transcription as fallback
    console.warn("[Summarize] Transcript fetch failed:", transcriptError.message);

    const localServerReady = await isLocalServerAvailable(settings, options.signal);
    if (localServerReady) {
      console.log("[Summarize] Falling back to local server audio transcription");
      return processWithLocalServer(url, settings, options);
    }

    // Local server not available, re-throw error for outer handler
    throw transcriptError;
  }

  // Build prompt with optional length modifier
  const { systemPrompt, userPrompt } = buildVideoPrompt(segments, {
    ...metadata,
    url,
  });

  // Apply length prompt modifier if summary_length is specified
  const lengthModifier = buildLengthPromptModifier(options.summary_length);
  const finalSystemPrompt = systemPrompt + lengthModifier;

  // Call API
  const response = await callAzureOpenAI(finalSystemPrompt, userPrompt, settings, options);
  const summary = extractResponseText(response, settings);

  return {
    contentType: "video",
    summary,
    segments,
    metadata,
    output_text: summary,
  };
}

/**
 * Process article URL.
 * @param {string} url
 * @param {Object} settings
 * @param {Object} options
 * @param {AbortSignal} [options.signal] - Optional abort signal
 * @returns {Promise<Object>}
 */
async function processArticle(url, settings, options) {
  console.log("[Summarize] Processing article:", url);

  // Fetch and parse article (pass tabId for DOM parsing via scripting API)
  const article = await fetchArticleContent(url, options.tabId, options.signal);
  const articleContent = formatArticleForSummary(article);
  const metadata = extractArticleMetadata(article);

  console.log("[Summarize] Extracted article:", metadata.title);

  // Build prompt with optional length modifier
  const { systemPrompt, userPrompt } = buildArticlePrompt(articleContent, {
    ...metadata,
    url,
    imageUrls: article.imageUrls,
  });

  // Apply length prompt modifier if summary_length is specified
  const lengthModifier = buildLengthPromptModifier(options.summary_length);
  const finalSystemPrompt = systemPrompt + lengthModifier;

  // Call API
  const response = await callAzureOpenAI(finalSystemPrompt, userPrompt, settings, options);
  const summary = extractResponseText(response, settings);

  return {
    contentType: "article",
    summary,
    metadata,
    output_text: summary,
  };
}

/**
 * Process generic URL (fallback).
 * @param {string} url
 * @param {Object} settings
 * @param {Object} options
 * @param {AbortSignal} [options.signal] - Optional abort signal
 * @returns {Promise<Object>}
 */
async function processGenericUrl(url, settings, options) {
  console.log("[Summarize] Processing generic URL:", url);

  const userPrompt = `${SIMPLE_URL_PROMPT}${url}`;

  // Call API
  const response = await callAzureOpenAI("", userPrompt, settings, options);
  const summary = extractResponseText(response, settings);

  return {
    contentType: "url",
    summary,
    output_text: summary,
  };
}

/**
 * Process video/audio URL using local companion server.
 * @param {string} url
 * @param {Object} settings
 * @param {Object} options
 * @param {AbortSignal} [options.signal] - Optional abort signal
 * @returns {Promise<Object>}
 */
async function processWithLocalServer(url, settings, options) {
  console.log("[Summarize] Processing via local server:", url);

  // First try transcription only, then summarize with Azure
  const transcribeResult = await callLocalServerTranscribe(url, settings, {
    language: options.preferredLanguages?.[0] || "en",
    streaming: true,
    signal: options.signal,
  });

  // Convert transcription result to segments format
  const segments = transcribeResult.transcript || [];

  // Build prompt from segments
  const { systemPrompt, userPrompt } = buildVideoPrompt(segments, {
    url,
    ...transcribeResult.metadata,
  });

  // Call Azure for summarization
  const response = await callAzureOpenAI(systemPrompt, userPrompt, settings, options);
  const summary = extractResponseText(response, settings);

  return {
    contentType: "video",
    summary,
    segments,
    metadata: transcribeResult.metadata,
    output_text: summary,
    source: "local_server",
  };
}

/**
 * Main entry point: summarize URL based on content type.
 * @param {string} targetUrl
 * @param {Object} settings
 * @param {Object} options
 * @param {AbortSignal} [options.signal] - Optional abort signal
 * @returns {Promise<Object>}
 */
export async function summarizeUrl(targetUrl, settings, options = {}) {
  // Check cache
  const cacheKey = `any2summary:${settings.deployment}:${targetUrl}`;
  if (settings.cache_enabled) {
    try {
      const { [cacheKey]: cached } = await chrome.storage.session.get(cacheKey);
      if (cached) {
        console.log("[Summarize] Cache hit for:", targetUrl);
        return cached;
      }
    } catch {
      // chrome.storage.session may not be available in all contexts
    }
  }

  // Detect content type
  const contentType = await detectContentType(targetUrl, {
    useHttpDetection: options.useHttpDetection !== false,
    signal: options.signal,
  });

  console.log("[Summarize] Detected content type:", contentType);

  let result;

  try {
    // Process based on content type
    if (isYouTubeUrl(targetUrl)) {
      result = await processYouTubeVideo(targetUrl, settings, options);
    } else if (contentType === "article") {
      result = await processArticle(targetUrl, settings, options);
    } else if (contentType === "video" || contentType === "audio") {
      // For video/audio from other platforms, try local server first
      const localServerReady = await isLocalServerAvailable(settings, options.signal);
      if (localServerReady) {
        console.log("[Summarize] Using local server for video/audio transcription");
        result = await processWithLocalServer(targetUrl, settings, options);
      } else {
        console.log("[Summarize] Local server not available, falling back to generic URL");
        result = await processGenericUrl(targetUrl, settings, options);
      }
    } else {
      result = await processGenericUrl(targetUrl, settings, options);
    }
  } catch (error) {
    // Re-throw abort errors immediately
    if (error.name === "AbortError") {
      throw error;
    }

    console.warn("[Summarize] Content extraction failed, falling back to generic URL:", error.message);
    // Fallback to generic URL processing
    result = await processGenericUrl(targetUrl, settings, options);
  }

  // Cache result
  if (settings.cache_enabled) {
    try {
      await chrome.storage.session.set({ [cacheKey]: result });
    } catch {
      // Ignore storage errors
    }
  }

  return result;
}

/**
 * Summarize with specific content type (skip auto-detection).
 * @param {string} targetUrl
 * @param {"video"|"article"|"url"} contentType
 * @param {Object} settings
 * @param {Object} options
 * @returns {Promise<Object>}
 */
export async function summarizeWithContentType(targetUrl, contentType, settings, options = {}) {
  console.log("[Summarize] Processing as:", contentType);

  switch (contentType) {
    case "video":
    case "audio":
      if (isYouTubeUrl(targetUrl)) {
        return processYouTubeVideo(targetUrl, settings, options);
      }
      // For non-YouTube videos, try local server
      const localServerReady = await isLocalServerAvailable(settings);
      if (localServerReady) {
        return processWithLocalServer(targetUrl, settings, options);
      }
      // Fallback for non-YouTube videos without local server
      return processGenericUrl(targetUrl, settings, options);

    case "article":
      return processArticle(targetUrl, settings, options);

    case "url":
    default:
      return processGenericUrl(targetUrl, settings, options);
  }
}

/**
 * Get content preview (metadata only, no summarization).
 * @param {string} targetUrl
 * @param {Object} options
 * @returns {Promise<Object>}
 */
export async function getContentPreview(targetUrl, options = {}) {
  const contentType = await detectContentType(targetUrl, {
    useHttpDetection: options.useHttpDetection !== false,
  });

  const preview = {
    url: targetUrl,
    contentType,
    metadata: null,
    hasTranscript: false,
  };

  try {
    if (isYouTubeUrl(targetUrl)) {
      const { metadata } = await fetchYouTubeTranscript(targetUrl, {
        preferredLanguages: options.preferredLanguages || ["en", "zh-Hans", "zh-Hant"],
      });
      preview.metadata = metadata;
      preview.hasTranscript = true;
    } else if (contentType === "article") {
      const article = await fetchArticleContent(targetUrl);
      preview.metadata = extractArticleMetadata(article);
    }
  } catch (error) {
    console.warn("[Summarize] Preview extraction failed:", error.message);
  }

  return preview;
}

/**
 * 从摘要内容推断 domain 标签（与 cli.py _infer_domain_from_summary 保持一致）
 *
 * @param {string} summary - 摘要内容
 * @param {Object} settings - 设置对象
 * @param {AbortSignal} [signal] - Optional abort signal
 * @returns {Promise<string|null>} 规范化的 domain 标签，失败返回 null
 */
export async function inferDomainFromSummary(summary, settings, signal = null) {
  const text = String(summary || "").trim();
  if (!text) return null;

  // 需要 API key 和 endpoint
  if (!settings.api_key || !settings.azure_endpoint) {
    return null;
  }

  try {
    const endpoint = buildUrl(settings);
    const headers = buildHeaders(settings);

    // 截取前 2000 字符避免 token 过多
    const truncatedText = text.substring(0, 2000);

    const body = settings.use_responses_api
      ? buildResponsesApiBody(DOMAIN_PROMPT, truncatedText, settings, { max_output_tokens: 50 })
      : buildChatCompletionsBody(DOMAIN_PROMPT, truncatedText, settings, { max_output_tokens: 50 });

    console.log("[Summarize] Inferring domain from summary...");

    const response = await fetch(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      console.warn("[Summarize] Domain inference API call failed:", response.status);
      return null;
    }

    const data = await response.json();
    const content = extractResponseText(data, settings);

    // 清理和规范化 domain
    const candidate = content
      .trim()
      .replace(/[【】\[\]「」『』""'']/g, "")
      .split(/[,，\n]/)[0]
      .trim();

    if (!candidate) return null;

    // 使用 normalizeDomainLabel 进行规范化
    const normalized = normalizeDomainLabel(candidate);
    console.log("[Summarize] Inferred domain:", candidate, "->", normalized);

    return normalized !== "General" ? normalized : candidate;
  } catch (error) {
    if (error.name === "AbortError") {
      throw error;
    }
    console.warn("[Summarize] Domain inference failed:", error.message);
    return null;
  }
}

// Export helper functions for options page
export { checkLocalServerHealth };
