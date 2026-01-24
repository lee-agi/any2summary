/**
 * YouTube transcript/subtitle fetching module.
 * Ported from cli.py fetch_transcript_with_metadata() function.
 *
 * Fetches YouTube video transcripts using YouTube's internal API.
 * Supports local server proxy for regions where YouTube is blocked.
 */

import { extractYouTubeVideoId } from "./contentDetector.js";

/**
 * 通过本地服务获取 YouTube 字幕
 * 本地服务会使用系统代理，适用于无法直接访问 YouTube 的地区
 *
 * @param {string} url - YouTube 视频 URL
 * @param {string} serverUrl - 本地服务 URL
 * @param {Object} options - 选项
 * @returns {Promise<{segments: Array, metadata: Object}>}
 */
async function fetchTranscriptViaLocalServer(url, serverUrl, options) {
  const params = new URLSearchParams({
    url,
    languages: (options.preferredLanguages || ["en", "zh-Hans", "zh-Hant"]).join(","),
  });

  const response = await fetch(`${serverUrl}/api/youtube/transcript?${params}`);
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`本地服务获取字幕失败: ${response.status} ${errorText}`);
  }
  return response.json();
}

/**
 * Fetch YouTube video transcript.
 * 优先使用本地服务（如果启用），回退到直接 fetch。
 *
 * @param {string} url - YouTube video URL
 * @param {Object} options - Options
 * @param {string[]} options.preferredLanguages - Preferred languages in order (default: ["en", "zh-Hans", "zh-Hant"])
 * @param {string} options.serverUrl - Local server URL (if local server is enabled)
 * @param {boolean} options.useLocalServer - Whether to use local server
 * @returns {Promise<{segments: Array<{start: number, end: number, text: string}>, metadata: Object}>}
 */
export async function fetchYouTubeTranscript(url, options = {}) {
  const {
    preferredLanguages = ["en", "zh-Hans", "zh-Hant", "ja", "ko"],
    serverUrl,
    useLocalServer,
  } = options;

  // 如果本地服务可用，优先使用（支持系统代理）
  if (useLocalServer && serverUrl) {
    try {
      console.log("[YouTube] 尝试通过本地服务获取字幕（支持代理）");
      const result = await fetchTranscriptViaLocalServer(url, serverUrl, {
        preferredLanguages,
      });
      console.log("[YouTube] 本地服务获取成功");
      return result;
    } catch (error) {
      console.warn("[YouTube] 本地服务获取失败，回退到直接 fetch:", error.message);
      // 继续尝试直接 fetch
    }
  }

  // 直接 fetch 方式
  const videoId = extractYouTubeVideoId(url);
  if (!videoId) {
    throw new Error("无法从 URL 提取 YouTube 视频 ID");
  }

  // Fetch YouTube page to get player response
  const pageUrl = `https://www.youtube.com/watch?v=${videoId}`;
  let pageResponse;
  try {
    pageResponse = await fetch(pageUrl);
  } catch (fetchError) {
    throw new Error(
      `无法访问 YouTube，请启用本地服务并配置系统代理: ${fetchError.message}`
    );
  }

  if (!pageResponse.ok) {
    throw new Error(`获取 YouTube 页面失败: ${pageResponse.status}`);
  }

  const pageHtml = await pageResponse.text();

  // Extract ytInitialPlayerResponse from page
  const playerResponse = extractPlayerResponse(pageHtml);
  if (!playerResponse) {
    throw new Error("无法解析 YouTube 播放器响应");
  }

  // Extract metadata
  const metadata = extractVideoMetadata(playerResponse);

  // Get caption tracks
  const captionTracks = playerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
  if (!captionTracks || captionTracks.length === 0) {
    throw new Error("该视频没有可用字幕");
  }

  // Find best matching caption track
  const selectedTrack = selectCaptionTrack(captionTracks, preferredLanguages);
  if (!selectedTrack) {
    throw new Error("未找到匹配的字幕语言");
  }

  // Fetch transcript
  const transcriptUrl = selectedTrack.baseUrl;
  const segments = await fetchTranscriptFromUrl(transcriptUrl);

  return {
    segments,
    metadata: {
      ...metadata,
      language: selectedTrack.languageCode,
      languageName: selectedTrack.name?.simpleText || selectedTrack.languageCode,
    },
  };
}

/**
 * Extract ytInitialPlayerResponse from YouTube page HTML.
 * @param {string} html
 * @returns {Object|null}
 */
function extractPlayerResponse(html) {
  // Try multiple patterns to extract player response
  const patterns = [
    /ytInitialPlayerResponse\s*=\s*({.+?});(?:\s*var\s+|\s*<\/script>)/s,
    /ytInitialPlayerResponse\s*=\s*({.+?});/s,
  ];

  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (match) {
      try {
        return JSON.parse(match[1]);
      } catch {
        continue;
      }
    }
  }

  // Alternative: look for player response in ytcfg
  const ytcfgMatch = html.match(/ytcfg\.set\(({.+?})\);/s);
  if (ytcfgMatch) {
    try {
      const ytcfg = JSON.parse(ytcfgMatch[1]);
      if (ytcfg.PLAYER_VARS?.embedded_player_response) {
        return JSON.parse(ytcfg.PLAYER_VARS.embedded_player_response);
      }
    } catch {
      // Continue
    }
  }

  return null;
}

/**
 * Extract video metadata from player response.
 * @param {Object} playerResponse
 * @returns {Object}
 */
function extractVideoMetadata(playerResponse) {
  const videoDetails = playerResponse?.videoDetails || {};
  const microformat = playerResponse?.microformat?.playerMicroformatRenderer || {};

  return {
    videoId: videoDetails.videoId || "",
    title: videoDetails.title || microformat.title?.simpleText || "",
    author: videoDetails.author || microformat.ownerChannelName || "",
    channelId: videoDetails.channelId || microformat.ownerProfileUrl?.split("/").pop() || "",
    lengthSeconds: parseInt(videoDetails.lengthSeconds || "0", 10),
    viewCount: parseInt(videoDetails.viewCount || "0", 10),
    description: videoDetails.shortDescription || microformat.description?.simpleText || "",
    publishDate: microformat.publishDate || "",
    uploadDate: microformat.uploadDate || "",
    thumbnail: videoDetails.thumbnail?.thumbnails?.slice(-1)[0]?.url ||
               microformat.thumbnail?.thumbnails?.slice(-1)[0]?.url || "",
  };
}

/**
 * Select the best matching caption track based on preferred languages.
 * @param {Array} captionTracks
 * @param {string[]} preferredLanguages
 * @returns {Object|null}
 */
function selectCaptionTrack(captionTracks, preferredLanguages) {
  // First pass: look for exact match in preferred order
  for (const lang of preferredLanguages) {
    const track = captionTracks.find(
      (t) => t.languageCode === lang || t.languageCode?.startsWith(lang)
    );
    if (track) {
      return track;
    }
  }

  // Second pass: look for auto-generated captions
  for (const lang of preferredLanguages) {
    const track = captionTracks.find(
      (t) =>
        (t.languageCode === lang || t.languageCode?.startsWith(lang)) &&
        t.kind === "asr"
    );
    if (track) {
      return track;
    }
  }

  // Fallback: return first available track
  return captionTracks[0] || null;
}

/**
 * Fetch transcript from YouTube caption URL.
 * @param {string} url
 * @returns {Promise<Array<{start: number, end: number, text: string}>>}
 */
async function fetchTranscriptFromUrl(url) {
  // Add fmt=json3 to get JSON format
  const jsonUrl = url.includes("fmt=")
    ? url.replace(/fmt=\w+/, "fmt=json3")
    : `${url}&fmt=json3`;

  let response;
  try {
    response = await fetch(jsonUrl);
  } catch (fetchError) {
    throw new Error(
      `无法获取字幕，请启用本地服务并配置系统代理: ${fetchError.message}`
    );
  }

  if (!response.ok) {
    throw new Error(`获取字幕失败: ${response.status}`);
  }

  // 先获取文本，检查是否为空（避免空响应导致 JSON 解析失败）
  const text = await response.text();
  if (!text || text.trim() === "") {
    throw new Error("字幕响应为空，可能需要启用本地服务并配置代理");
  }

  // 安全解析 JSON
  let data;
  try {
    data = JSON.parse(text);
  } catch (parseError) {
    throw new Error(`字幕数据解析失败: ${parseError.message}`);
  }

  return parseJson3Transcript(data);
}

/**
 * Parse YouTube json3 transcript format.
 * @param {Object} data
 * @returns {Array<{start: number, end: number, text: string}>}
 */
function parseJson3Transcript(data) {
  const events = data.events || [];
  const segments = [];

  for (const event of events) {
    // Skip window positioning events
    if (!event.segs || event.segs.length === 0) {
      continue;
    }

    const startMs = event.tStartMs || 0;
    const durationMs = event.dDurationMs || 0;

    // Combine segment text
    const text = event.segs
      .map((seg) => seg.utf8 || "")
      .join("")
      .trim();

    if (!text) {
      continue;
    }

    segments.push({
      start: startMs / 1000,
      end: (startMs + durationMs) / 1000,
      text: text,
    });
  }

  return segments;
}

/**
 * Format transcript segments for display.
 * @param {Array<{start: number, end: number, text: string}>} segments
 * @returns {string}
 */
export function formatTranscriptTimeline(segments) {
  return segments
    .map((seg) => {
      const startTime = formatTimestamp(seg.start);
      const endTime = formatTimestamp(seg.end);
      return `${startTime} - ${endTime} | ${seg.text}`;
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

  if (hrs > 0) {
    return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Check if YouTube video has available captions.
 * @param {string} url
 * @returns {Promise<boolean>}
 */
export async function hasYouTubeCaptions(url) {
  try {
    const videoId = extractYouTubeVideoId(url);
    if (!videoId) return false;

    const pageUrl = `https://www.youtube.com/watch?v=${videoId}`;
    const pageResponse = await fetch(pageUrl);
    if (!pageResponse.ok) return false;

    const pageHtml = await pageResponse.text();
    const playerResponse = extractPlayerResponse(pageHtml);
    if (!playerResponse) return false;

    const captionTracks = playerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
    return captionTracks && captionTracks.length > 0;
  } catch {
    return false;
  }
}

/**
 * Get available caption languages for a YouTube video.
 * @param {string} url
 * @returns {Promise<Array<{code: string, name: string, isAutoGenerated: boolean}>>}
 */
export async function getAvailableCaptionLanguages(url) {
  try {
    const videoId = extractYouTubeVideoId(url);
    if (!videoId) return [];

    const pageUrl = `https://www.youtube.com/watch?v=${videoId}`;
    const pageResponse = await fetch(pageUrl);
    if (!pageResponse.ok) return [];

    const pageHtml = await pageResponse.text();
    const playerResponse = extractPlayerResponse(pageHtml);
    if (!playerResponse) return [];

    const captionTracks = playerResponse?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];

    return captionTracks.map((track) => ({
      code: track.languageCode,
      name: track.name?.simpleText || track.languageCode,
      isAutoGenerated: track.kind === "asr",
    }));
  } catch {
    return [];
  }
}
