/* ============================================================
   backend-api.js — 统一后端 API 调用封装
   替代浏览器端 LLM 调用、PDF 解析、Tesseract OCR
   所有 API key 保留在服务端，浏览器不可见
   ============================================================ */

const BackendAPI = (() => {
  // === Configuration ===
  const CONFIG = {
    // 自动检测：同源用相对路径，开发环境用 localhost
    baseURL: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'http://localhost:8000'
      : '/api',
    timeout: 120000,  // 2 minutes max
  };

  let sessionId = null;
  let isConnected = false;

  // === Health Check ===
  async function checkHealth() {
    try {
      const resp = await fetch(`${CONFIG.baseURL}/api/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      const data = await resp.json();
      isConnected = data.status === 'ok';
      return data;
    } catch (e) {
      isConnected = false;
      console.warn('[BackendAPI] Backend not reachable, falling back to local processing');
      return { status: 'unreachable', services: {} };
    }
  }

  function isBackendAvailable() {
    return isConnected;
  }

  // === Document Parsing ===
  async function parseFile(file, options = {}) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('lang', options.lang || I18N?.getLang?.() || 'zh');

    try {
      const resp = await fetch(`${CONFIG.baseURL}/api/parse`, {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(CONFIG.timeout),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: resp.statusText }));
        throw new Error(err.error || err.detail || '文档解析失败');
      }

      const data = await resp.json();
      sessionId = data.session_id;
      return data;
    } catch (e) {
      console.error('[BackendAPI] Parse failed:', e.message);
      // 降级到本地解析
      if (options.fallback !== false) {
        console.log('[BackendAPI] Falling back to local FileParser...');
        return await FileParser.parseFile(file, options);
      }
      throw e;
    }
  }

  // === Resume Extraction ===
  async function extractResume(text, options = {}) {
    try {
      const resp = await fetch(`${CONFIG.baseURL}/api/extract/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text,
          method: options.method || 'auto',
          session_id: sessionId || options.session_id,
          lang: options.lang || I18N?.getLang?.() || 'zh',
        }),
        signal: AbortSignal.timeout(CONFIG.timeout),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: resp.statusText }));
        throw new Error(err.error || err.detail || '简历提取失败');
      }

      const data = await resp.json();
      return data;
    } catch (e) {
      console.error('[BackendAPI] Extract resume failed:', e.message);
      // 降级到本地 regex 提取
      if (options.fallback !== false && window.ExtractionPipeline) {
        console.log('[BackendAPI] Falling back to local ExtractionPipeline...');
        return ExtractionPipeline.regexFallbackExtraction(text, options.lang || 'zh');
      }
      throw e;
    }
  }

  // === JD Extraction ===
  async function extractJD(text, options = {}) {
    try {
      const resp = await fetch(`${CONFIG.baseURL}/api/extract/jd`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text,
          method: options.method || 'auto',
          lang: options.lang || I18N?.getLang?.() || 'zh',
        }),
        signal: AbortSignal.timeout(30000),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: resp.statusText }));
        throw new Error(err.error || 'JD 解析失败');
      }

      return await resp.json();
    } catch (e) {
      console.error('[BackendAPI] Extract JD failed:', e.message);
      // 降级：使用 ResumeEngine.parseJD
      if (window.ResumeEngine && window.ResumeEngine.parseJD) {
        console.log('[BackendAPI] Falling back to local JD parser...');
        return window.ResumeEngine.parseJD(text);
      }
      throw e;
    }
  }

  // === LLM Chat Proxy (替换 deepseek-api.js 的直接调用) ===
  async function llmChat(params = {}) {
    if (!isConnected) {
      // 如果后端不可用，回退到直接 API 调用
      if (window.DeepSeekAPI) {
        return DeepSeekAPI.chatCompletion(params);
      }
      throw new Error('Backend and DeepSeekAPI both unavailable');
    }

    try {
      const resp = await fetch(`${CONFIG.baseURL}/api/llm/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: params.model || 'deepseek',
          messages: params.messages || [],
          temperature: params.temperature || 0.7,
          max_tokens: params.max_tokens || 2000,
          system_prompt: params.system_prompt,
          lang: params.lang || I18N?.getLang?.() || 'zh',
        }),
        signal: AbortSignal.timeout(CONFIG.timeout),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: resp.statusText }));
        throw new Error(err.error || 'LLM 调用失败');
      }

      const data = await resp.json();
      return {
        success: true,
        content: data.content,
        model: data.model,
        usage: data.usage,
        finish_reason: data.finish_reason,
      };
    } catch (e) {
      console.error('[BackendAPI] LLM chat failed:', e.message);
      // 回退到本地 API 调用
      if (window.DeepSeekAPI) {
        console.log('[BackendAPI] Falling back to direct DeepSeekAPI call...');
        return DeepSeekAPI.chatCompletion(params);
      }
      throw e;
    }
  }

  // === Interview Chat (自动注入 HR 系统提示词) ===
  async function interviewChat(messages, options = {}) {
    try {
      const resp = await fetch(`${CONFIG.baseURL}/api/interview/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: options.model || 'deepseek',
          messages: messages,
          temperature: options.temperature || 0.7,
          max_tokens: options.max_tokens || 2000,
          lang: options.lang || I18N?.getLang?.() || 'zh',
        }),
        signal: AbortSignal.timeout(CONFIG.timeout),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: resp.statusText }));
        throw new Error(err.error || '面试对话失败');
      }

      return await resp.json();
    } catch (e) {
      console.error('[BackendAPI] Interview chat failed:', e.message);
      // 回退
      if (window.InterviewSystem?.callRealAPI) {
        return InterviewSystem.callRealAPI(messages, options);
      }
      throw e;
    }
  }

  // === Generate Interview Assessment ===
  async function generateAssessment(messages, jdText = '', resumeText = '') {
    try {
      const resp = await fetch(`${CONFIG.baseURL}/api/interview/assessment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messages,
          jd_text: jdText,
          resume_text: resumeText,
        }),
        signal: AbortSignal.timeout(CONFIG.timeout),
      });

      if (!resp.ok) throw new Error('评估生成失败');
      return await resp.json();
    } catch (e) {
      console.error('[BackendAPI] Assessment failed:', e.message);
      throw e;
    }
  }

  // === Model Availability ===
  async function getAvailableModels() {
    try {
      const resp = await fetch(`${CONFIG.baseURL}/api/llm/models`);
      return await resp.json();
    } catch (e) {
      return { models: {} };
    }
  }

  // === Billing ===
  async function getBilling() {
    try {
      const resp = await fetch(`${CONFIG.baseURL}/api/llm/billing`);
      return await resp.json();
    } catch (e) {
      return null;
    }
  }

  // === Init: auto-check backend ===
  async function init() {
    const health = await checkHealth();
    console.log(
      `[BackendAPI] Backend ${health.status === 'ok' ? '✅ connected' : '❌ unavailable'}`
    );
    if (health.services) {
      const available = Object.entries(health.services)
        .filter(([, v]) => v === 'available')
        .map(([k]) => k);
      if (available.length > 0) {
        console.log(`[BackendAPI] Available services: ${available.join(', ')}`);
      }
    }
    return health;
  }

  // === Public API ===
  return {
    CONFIG,
    init,
    checkHealth,
    isBackendAvailable,
    parseFile,
    extractResume,
    extractJD,
    llmChat,
    interviewChat,
    generateAssessment,
    getAvailableModels,
    getBilling,
    getSessionId: () => sessionId,
  };
})();

// Auto-init on load
window.BackendAPI = BackendAPI;
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => BackendAPI.init(), 500);
});
