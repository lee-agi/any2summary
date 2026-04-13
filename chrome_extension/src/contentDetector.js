/**
 * Content type detection module.
 * Ported from cli.py _smart_detect_content_type() function.
 *
 * Detects whether a URL points to video, audio, or article content.
 */

// Media host suffixes (from cli.py _MEDIA_HOST_SUFFIXES)
const MEDIA_HOST_SUFFIXES = [
  "youtu.be",
  "youtube.com",
  "bilibili.com",
  "soundcloud.com",
  "music.apple.com",
  "podcasts.apple.com",
  "podcast.apple.com",
  "spotify.com",
  "open.spotify.com",
  "podcasters.spotify.com",
];

// Forced audio host suffixes (from cli.py _FORCED_AUDIO_HOST_SUFFIXES)
const FORCED_AUDIO_HOST_SUFFIXES = [
  "podcasts.apple.com",
  "podcast.apple.com",
];

// Video file extensions
const VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"];

// Audio file extensions
const AUDIO_EXTENSIONS = [".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"];

// Video platform indicators: [hostname suffix, path patterns]
const VIDEO_PLATFORM_INDICATORS = [
  // Short video platforms
  ["tiktok.com", ["/video/", "/@"]],
  ["douyin.com", ["/video/"]],
  // Instagram
  ["instagram.com", ["/reel/", "/tv/", "/p/"]],
  // Xiaohongshu (Little Red Book)
  ["xiaohongshu.com", ["/explore/", "/video/"]],
  ["xhslink.com", ["/"]],
  // Other platforms
  ["vimeo.com", ["/"]],
  ["dailymotion.com", ["/video/"]],
  ["twitch.tv", ["/"]],
  ["kick.com", ["/"]],
];

// Article path indicators: [hostname suffix, path patterns that indicate article]
const ARTICLE_PATH_INDICATORS = [
  ["bilibili.com", ["/read/"]], // Bilibili articles
];

// Cache for content type detection
const contentTypeCache = new Map();

/**
 * Check if hostname matches a suffix (handles www. prefix).
 * @param {string} hostname
 * @param {string} suffix
 * @returns {boolean}
 */
function matchesHostSuffix(hostname, suffix) {
  if (hostname === suffix) return true;
  if (hostname.endsWith("." + suffix)) return true;
  return false;
}

/**
 * Check if URL is a YouTube URL.
 * @param {string} url
 * @returns {boolean}
 */
export function isYouTubeUrl(url) {
  try {
    const parsed = new URL(url);
    const hostname = (parsed.hostname || "").toLowerCase();
    return matchesHostSuffix(hostname, "youtube.com") ||
           matchesHostSuffix(hostname, "youtu.be");
  } catch {
    return false;
  }
}

/**
 * Extract YouTube video ID from URL.
 * @param {string} url
 * @returns {string|null}
 */
export function extractYouTubeVideoId(url) {
  try {
    const parsed = new URL(url);
    const hostname = (parsed.hostname || "").toLowerCase();

    // youtu.be/VIDEO_ID
    if (matchesHostSuffix(hostname, "youtu.be")) {
      const pathParts = parsed.pathname.split("/").filter(Boolean);
      if (pathParts.length > 0) {
        return pathParts[0];
      }
    }

    // youtube.com/watch?v=VIDEO_ID
    if (matchesHostSuffix(hostname, "youtube.com")) {
      const videoId = parsed.searchParams.get("v");
      if (videoId) return videoId;

      // youtube.com/embed/VIDEO_ID or youtube.com/v/VIDEO_ID
      const pathMatch = parsed.pathname.match(/^\/(embed|v)\/([^/?]+)/);
      if (pathMatch) {
        return pathMatch[2];
      }
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Check if URL is a media source (video/audio platform).
 * @param {string} url
 * @returns {boolean}
 */
function isMediaSourceUrl(url) {
  try {
    const parsed = new URL(url);
    const hostname = (parsed.hostname || "").toLowerCase();

    // Check media host suffixes
    for (const suffix of MEDIA_HOST_SUFFIXES) {
      if (matchesHostSuffix(hostname, suffix)) {
        return true;
      }
    }

    // Check path extensions
    const pathLower = parsed.pathname.toLowerCase();
    for (const ext of AUDIO_EXTENSIONS) {
      if (pathLower.endsWith(ext)) {
        return true;
      }
    }

    return false;
  } catch {
    return false;
  }
}

/**
 * Check if URL should force Azure audio transcription.
 * @param {string} url
 * @returns {boolean}
 */
export function shouldForceAzureTranscription(url) {
  try {
    const parsed = new URL(url);
    const hostname = (parsed.hostname || "").toLowerCase();

    for (const suffix of FORCED_AUDIO_HOST_SUFFIXES) {
      if (matchesHostSuffix(hostname, suffix)) {
        return true;
      }
    }

    return false;
  } catch {
    return false;
  }
}

/**
 * Intelligently detect content type (video/audio/article) from URL.
 *
 * Detection strategy (in order):
 * 1. Check cache for previous results
 * 2. Check URL file extension (.mp4, .mp3, etc.)
 * 3. Check for embed/player/watch keywords in URL
 * 4. Check known video/social media platforms
 * 5. Send HTTP HEAD request to check Content-Type header (if enabled)
 * 6. Fetch HTML to check meta tags (if enabled)
 * 7. Fallback to existing white list logic
 *
 * @param {string} url - The URL to detect content type for
 * @param {Object} options - Detection options
 * @param {boolean} options.useHttpDetection - Whether to use HTTP requests for detection
 * @param {AbortSignal} [options.signal] - Optional abort signal
 * @returns {Promise<"video"|"audio"|"article">}
 */
export async function detectContentType(url, options = {}) {
  const { useHttpDetection = true, signal } = options;

  // Step 1: Check cache
  if (contentTypeCache.has(url)) {
    return contentTypeCache.get(url);
  }

  const urlLower = url.toLowerCase();

  // Step 2: Check file extension
  for (const ext of VIDEO_EXTENSIONS) {
    if (urlLower.endsWith(ext)) {
      contentTypeCache.set(url, "video");
      return "video";
    }
  }

  for (const ext of AUDIO_EXTENSIONS) {
    if (urlLower.endsWith(ext)) {
      contentTypeCache.set(url, "audio");
      return "audio";
    }
  }

  // Step 3: Check for embed/player/watch keywords
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    contentTypeCache.set(url, "article");
    return "article";
  }

  const pathLower = parsed.pathname.toLowerCase();
  if (["embed", "player", "watch"].some((kw) => pathLower.includes(kw))) {
    contentTypeCache.set(url, "video");
    return "video";
  }

  // Step 4: Check known platforms
  const hostname = (parsed.hostname || "").toLowerCase();

  // First check for article paths that should NOT be treated as video
  let isArticlePath = false;
  for (const [platformHost, articlePatterns] of ARTICLE_PATH_INDICATORS) {
    if (hostname.endsWith(platformHost)) {
      if (articlePatterns.some((pattern) => pathLower.includes(pattern))) {
        isArticlePath = true;
        break;
      }
    }
  }

  // If not an article path, check for video platforms
  if (!isArticlePath) {
    for (const [platformHost, pathPatterns] of VIDEO_PLATFORM_INDICATORS) {
      if (hostname.endsWith(platformHost)) {
        if (
          pathPatterns.length === 0 ||
          pathPatterns.some((pattern) => pathLower.includes(pattern))
        ) {
          contentTypeCache.set(url, "video");
          return "video";
        }
      }
    }
  }

  // Step 5-6: HTTP detection (optional)
  if (useHttpDetection) {
    try {
      const result = await detectContentTypeViaHttp(url, signal);
      if (result) {
        contentTypeCache.set(url, result);
        return result;
      }
    } catch (error) {
      // Re-throw abort errors
      if (error.name === "AbortError") {
        throw error;
      }
      // HTTP detection failed, continue to fallback
    }
  }

  // Step 7: Fallback to existing white list logic
  if (isMediaSourceUrl(url)) {
    contentTypeCache.set(url, "video");
    return "video";
  }

  // Default to article
  contentTypeCache.set(url, "article");
  return "article";
}

/**
 * Detect content type via HTTP requests (HEAD + partial HTML fetch).
 * @param {string} url
 * @param {AbortSignal} [signal] - Optional abort signal
 * @returns {Promise<"video"|"audio"|null>}
 */
async function detectContentTypeViaHttp(url, signal) {
  try {
    // Send HEAD request
    const headResponse = await fetch(url, {
      method: "HEAD",
      redirect: "follow",
      signal,
    });

    const contentType = (headResponse.headers.get("content-type") || "").toLowerCase();

    if (contentType.includes("video/")) {
      return "video";
    }

    if (contentType.includes("audio/")) {
      return "audio";
    }

    // If HTML, fetch partial content to check meta tags
    if (contentType.includes("text/html")) {
      try {
        const htmlResponse = await fetch(url, {
          method: "GET",
          headers: { Range: "bytes=0-2047" },
          redirect: "follow",
          signal,
        });

        const htmlContent = (await htmlResponse.text()).toLowerCase();

        // Check OpenGraph meta tag
        if (
          htmlContent.includes('property="og:type"') &&
          htmlContent.includes('content="video')
        ) {
          return "video";
        }

        // Check Twitter Card meta tag
        if (
          htmlContent.includes('name="twitter:card"') &&
          htmlContent.includes('content="player"')
        ) {
          return "video";
        }

        // Check for <video> or <audio> tags
        if (htmlContent.includes("<video") || htmlContent.includes("<audio")) {
          return "video";
        }
      } catch {
        // Failed to fetch HTML
      }
    }
  } catch {
    // HTTP request failed
  }

  return null;
}

/**
 * Check if URL is probably an article (not video/audio).
 * @param {string} url
 * @param {Object} options
 * @returns {Promise<boolean>}
 */
export async function isProbableArticle(url, options = {}) {
  const contentType = await detectContentType(url, options);
  return contentType === "article";
}

/**
 * Clear content type cache.
 */
export function clearContentTypeCache() {
  contentTypeCache.clear();
}
