/**
 * 配置常量模块
 * 与 cli.py SUMMARY_LENGTH_CONFIGS 保持一致
 */

/**
 * 摘要长度配置（与 cli.py 保持一致）
 */
export const SUMMARY_LENGTH_CONFIGS = {
  brief: {
    max_tokens: 2048,
    description: "简洁 (3-5句话)",
    prompt_modifier: "\n\n【输出要求】请用 3-5 句话简洁总结核心内容，省略次要细节。",
  },
  standard: {
    max_tokens: 8192,
    description: "标准",
    prompt_modifier: "",
  },
  detailed: {
    max_tokens: 16384,
    description: "详细",
    prompt_modifier: "\n\n【输出要求】请详细展开每个要点，提供充分的上下文和解释。",
  },
  full: {
    max_tokens: 32768,
    description: "完整翻译",
    prompt_modifier: "\n\n【输出要求】请完整翻译全部内容，不做任何压缩或省略，保留所有细节。",
  },
};

/**
 * 获取摘要长度配置
 * @param {string} length - 长度名称 (brief/standard/detailed/full)
 * @returns {Object} 配置对象
 */
export function getSummaryLengthConfig(length) {
  return SUMMARY_LENGTH_CONFIGS[length] || SUMMARY_LENGTH_CONFIGS.standard;
}

/**
 * 构建长度相关的 prompt 修饰符
 * @param {string} length - 长度名称
 * @returns {string} prompt 修饰符字符串
 */
export function buildLengthPromptModifier(length) {
  const config = getSummaryLengthConfig(length);
  return config.prompt_modifier || "";
}

/**
 * 进度阶段定义
 */
export const PROGRESS_STAGES = {
  DETECTING: { ratio: 0.1, label: "检测内容类型..." },
  FETCHING: { ratio: 0.3, label: "获取内容..." },
  ANALYZING: { ratio: 0.6, label: "分析中..." },
  SUMMARIZING: { ratio: 0.8, label: "生成摘要..." },
  SAVING: { ratio: 0.95, label: "保存文件..." },
  COMPLETE: { ratio: 1.0, label: "完成" },
};
