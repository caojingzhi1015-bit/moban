/* ============================================================
   deepseek-api.js — DeepSeek API 客户端 + OneAPI 统一调度
   OpenAI兼容接口 | 支持 DeepSeek-Lite / Chat-V2 / VL 多模态
   ============================================================ */

const DeepSeekAPI = (() => {
  // === OneAPI Configuration ===
  // 开发环境 / 生产环境 两套配置（通过 ONEAPI_ENV 切换）
  const CONFIG = {
    // DeepSeek 官方 OneAPI 端点
    baseURL: 'https://api.deepseek.com/v1',

    // 模型映射
    models: {
      lite: {
        id: 'deepseek-chat',           // DeepSeek-Lite (轻量任务)
        maxTokens: 4096,
        contextWindow: 32000,
        costPer1kInput: 0.00014,       // $0.14/1M tokens ≈ $0.00014/1K
        costPer1kOutput: 0.00028,
      },
      chatv2: {
        id: 'deepseek-reasoner',       // DeepSeek-Chat V2 128K (高精度任务)
        maxTokens: 4096,
        contextWindow: 128000,
        costPer1kInput: 0.00055,
        costPer1kOutput: 1.10,
      },
      vl: {
        id: 'deepseek-vl',             // DeepSeek-VL 多模态 (图片/PDF OCR)
        maxTokens: 4096,
        contextWindow: 32000,
        costPer1kInput: 0.00055,
        costPer1kOutput: 1.10,
        multimodal: true,
      },
    },

    // 环境切换
    env: 'development',               // 'development' | 'production'

    // 开发环境限制
    dev: {
      dailyTokenLimit: 100000,        // 每日Token上限
      rpmLimit: 10,                   // 每分钟请求上限
      freeTierTokens: 100000,         // 免费额度
    },

    // 生产环境限制
    prod: {
      dailyTokenLimit: 1000000,
      rpmLimit: 60,
      freeTierTokens: 0,
    },
  };

  // === State ===
  let apiKey = '';
  let isInitialized = false;
  let requestCounters = { minute: 0, daily: 0, minuteStart: 0, dailyStart: 0 };
  let tokenUsage = { total: 0, input: 0, output: 0, byModel: {} };

  // 从 localStorage 恢复
  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem('deepseek_state') || '{}');
      apiKey = saved.apiKey || localStorage.getItem('careerai_deepseek_key') || '';
      tokenUsage = saved.tokenUsage || { total: 0, input: 0, output: 0, byModel: {} };
      CONFIG.env = saved.env || 'development';
      isInitialized = true;
    } catch (e) {
      tokenUsage = { total: 0, input: 0, output: 0, byModel: {} };
    }
  }

  function saveState() {
    try {
      localStorage.setItem('deepseek_state', JSON.stringify({
        apiKey,
        tokenUsage,
        env: CONFIG.env,
      }));
    } catch (e) { /* storage full */ }
  }

  // === Prompt Layers (from PromptsConfig) ===
  // Layer 1 is now managed by PromptsConfig.getGlobalBase()
  // The old ANTI_HALLUCINATION_PROMPT is superseded by the 3-layer system
  // Legacy reference kept for backward compat

  // === Model Router ===
  /**
   * 根据任务类型自动选择模型
   * @param {'lite'|'enhanced'|'vision'} taskType
   */
  function selectModel(taskType) {
    switch (taskType) {
      case 'lite':
        return CONFIG.models.lite;
      case 'enhanced':
        return CONFIG.models.chatv2;
      case 'vision':
        return CONFIG.models.vl;
      default:
        return CONFIG.models.lite;
    }
  }

  // === Core API Call ===
  /**
   * 调用 DeepSeek API (OpenAI 兼容格式)
   * @param {Object} params
   * @param {Array} params.messages - 消息列表
   * @param {'lite'|'enhanced'|'vision'} params.taskType - 任务类型
   * @param {Object} params.options - 额外选项
   */
  async function chatCompletion({ messages, taskType = 'lite', options = {} }) {
    if (!isInitialized) loadState();
    if (!apiKey) {
      return { success: false, error: 'API_KEY_MISSING', message: '请先配置 DeepSeek API Key' };
    }

    // === Rate Limiting Check ===
    const limitCheck = checkRateLimits();
    if (!limitCheck.allowed) {
      return { success: false, error: 'RATE_LIMITED', message: limitCheck.reason };
    }

    // === Select Model ===
    const model = selectModel(taskType);

    // === Build layered system prompts via PromptsConfig ===
    const currentLang = options.lang || I18N.getLang();
    const layerMessages = PromptsConfig.assembleFullPrompt({
      layer2Text: options.extractionText || null,
      layer3Task: options.generationTask || null,
      layer3Data: options.generationData || {},
      lang: currentLang,
    });

    // === Prepare Messages ===
    const apiMessages = [];

    // Layer 1: Global base (FORCED, always present)
    const layer1 = layerMessages.find(m => m.layer === 1);
    if (layer1) apiMessages.push({ role: 'system', content: layer1.content });

    // Layer 2: Extraction (if applicable)
    const layer2 = layerMessages.find(m => m.layer === 2);
    if (layer2) apiMessages.push({ role: 'system', content: layer2.content });

    // Layer 3: Generation task (if applicable)
    const layer3 = layerMessages.find(m => m.layer === 3);
    if (layer3) apiMessages.push({ role: 'system', content: layer3.content });

    // If caller provided additional custom system prompt, append it
    if (options.systemPrompt) {
      apiMessages.push({ role: 'system', content: options.systemPrompt });
    }

    // Add conversation messages
    const convMessages = messages.filter(m => {
      if (m.role === 'system' && !options.keepSystemMessages) return false;
      return true;
    }).map(m => ({
      role: m.role === 'ai' ? 'assistant' : m.role,
      content: m.content,
    }));
    apiMessages.push(...convMessages);

    // === API Call ===
    const body = {
      model: model.id,
      messages: apiMessages,
      max_tokens: options.maxTokens || model.maxTokens,
      temperature: options.temperature ?? 0.7,
      stream: false,
    };

    // 多模态请求（图片）
    if (taskType === 'vision' && options.images) {
      // 构造 vision 消息
      const visionContent = [{ type: 'text', text: apiMessages.filter(m => m.role === 'system').map(m => m.content).join('\n') }];
      options.images.forEach(img => {
        visionContent.push({
          type: 'image_url',
          image_url: { url: img.dataURL || img.url, detail: 'high' },
        });
      });
      // Replace messages with vision format
      body.messages = [{ role: 'user', content: visionContent }];
    }

    try {
      const startTime = Date.now();
      const response = await fetch(`${CONFIG.baseURL}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const errMsg = errData.error?.message || `HTTP ${response.status}`;

        // 余额不足
        if (response.status === 402 || (errData.error?.code === 'insufficient_balance')) {
          return { success: false, error: 'INSUFFICIENT_BALANCE', message: 'DeepSeek 账户余额不足，请充值' };
        }

        return { success: false, error: 'API_ERROR', message: errMsg, status: response.status };
      }

      const data = await response.json();
      const latency = Date.now() - startTime;

      // === Debug Logging (完整Prompt+响应) ===
      const responseContent = data.choices?.[0]?.message?.content || '';
      const debugLog = PromptsConfig.formatPromptForDebug(layerMessages, responseContent);
      console.log(debugLog);
      // Also store in window for inspection
      window.__lastDebugLog = { prompt: layerMessages, response: responseContent, timestamp: Date.now() };

      // === Token Usage Tracking ===
      if (data.usage) {
        trackUsage(data.usage, model.id);
      }

      // Update rate counters
      updateRateCounters();

      return {
        success: true,
        content: data.choices?.[0]?.message?.content || '',
        model: model.id,
        usage: data.usage,
        latency,
      };
    } catch (err) {
      return { success: false, error: 'NETWORK_ERROR', message: err.message };
    }
  }

  // === Vision API (图片/PDF OCR via DeepSeek-VL) ===
  async function visionRecognition(imageDataURLs, prompt) {
    if (!Array.isArray(imageDataURLs)) imageDataURLs = [imageDataURLs];

    const images = imageDataURLs.map(url => ({ dataURL: url }));

    return await chatCompletion({
      messages: [{
        role: 'user',
        content: prompt || '请识别并提取图片中的所有文字内容，保持原文格式和结构。如果是简历，请提取姓名、联系方式、教育经历、工作经历、项目经历、技能等所有信息。如果是JD，请完整提取所有要求和职责。',
      }],
      taskType: 'vision',
      options: { images, maxTokens: 4096 },
    });
  }

  // === Token Usage Tracking ===
  function trackUsage(usage, modelId) {
    tokenUsage.total += (usage.total_tokens || 0);
    tokenUsage.input += (usage.prompt_tokens || 0);
    tokenUsage.output += (usage.completion_tokens || 0);

    if (!tokenUsage.byModel[modelId]) {
      tokenUsage.byModel[modelId] = { input: 0, output: 0, total: 0, calls: 0 };
    }
    tokenUsage.byModel[modelId].input += (usage.prompt_tokens || 0);
    tokenUsage.byModel[modelId].output += (usage.completion_tokens || 0);
    tokenUsage.byModel[modelId].total += (usage.total_tokens || 0);
    tokenUsage.byModel[modelId].calls++;

    saveState();
  }

  // === Billing Calculation ===
  function estimateCost(modelId) {
    const model = Object.values(CONFIG.models).find(m => m.id === modelId);
    if (!model) return 0;
    const usage = tokenUsage.byModel[modelId] || { input: 0, output: 0 };
    return (usage.input / 1000) * model.costPer1kInput + (usage.output / 1000) * model.costPer1kOutput;
  }

  function getTotalCost() {
    return Object.keys(tokenUsage.byModel).reduce((sum, mid) => sum + estimateCost(mid), 0);
  }

  function getBillingReport() {
    const env = CONFIG.env;
    const limits = env === 'production' ? CONFIG.prod : CONFIG.dev;
    const totalCost = getTotalCost();
    const dailyTokens = tokenUsage.total; // simplified

    const modelReports = Object.entries(tokenUsage.byModel).map(([mid, usage]) => ({
      model: mid,
      calls: usage.calls,
      inputTokens: usage.input,
      outputTokens: usage.output,
      cost: estimateCost(mid),
    }));

    return {
      env,
      totalTokens: tokenUsage.total,
      totalCost: totalCost.toFixed(4),
      dailyTokens,
      dailyLimit: limits.dailyTokenLimit,
      dailyPercent: Math.round((dailyTokens / limits.dailyTokenLimit) * 100),
      rpmCurrent: requestCounters.minute,
      rpmLimit: limits.rpmLimit,
      freeTokensRemaining: Math.max(0, limits.freeTierTokens - tokenUsage.total),
      models: modelReports,
      apiConfigured: !!apiKey,
    };
  }

  // === Rate Limiting ===
  function checkRateLimits() {
    const now = Date.now();
    const env = CONFIG.env;
    const limits = env === 'production' ? CONFIG.prod : CONFIG.dev;

    // Reset minute counter
    if (now - requestCounters.minuteStart > 60000) {
      requestCounters.minute = 0;
      requestCounters.minuteStart = now;
    }

    // Reset daily counter
    if (now - requestCounters.dailyStart > 86400000) {
      requestCounters.daily = 0;
      requestCounters.dailyStart = now;
    }

    if (requestCounters.minute >= limits.rpmLimit) {
      return { allowed: false, reason: `每分钟请求次数已达上限 (${limits.rpmLimit})，请稍后重试` };
    }

    if (tokenUsage.total >= limits.dailyTokenLimit) {
      return { allowed: false, reason: `每日Token用量已达上限 (${limits.dailyTokenLimit})，明天自动重置` };
    }

    return { allowed: true };
  }

  function updateRateCounters() {
    const now = Date.now();
    if (now - requestCounters.minuteStart > 60000) {
      requestCounters.minute = 0;
      requestCounters.minuteStart = now;
    }
    if (now - requestCounters.dailyStart > 86400000) {
      requestCounters.daily = 0;
      requestCounters.dailyStart = now;
    }
    requestCounters.minute++;
    requestCounters.daily++;
  }

  // === Configuration ===
  function setApiKey(key) {
    apiKey = key;
    localStorage.setItem('careerai_deepseek_key', key);
    saveState();
  }

  function getApiKey() { return apiKey; }

  function setEnv(env) {
    if (env === 'development' || env === 'production') {
      CONFIG.env = env;
      saveState();
    }
  }

  function getEnv() { return CONFIG.env; }

  // Initialize
  loadState();

  return {
    CONFIG,
    chatCompletion,
    visionRecognition,
    selectModel,
    setApiKey,
    getApiKey,
    setEnv,
    getEnv,
    getBillingReport,
    getTotalCost,
    getTokenUsage: () => ({ ...tokenUsage }),
    estimateCost,
    checkRateLimits,
    ANTI_HALLUCINATION_PROMPT,
  };
})();

window.DeepSeekAPI = DeepSeekAPI;
