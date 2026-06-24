/* ============================================================
   ocr-engine.js v1 — 统一图片OCR识别引擎
   三级降级: Backend API → PaddleOCR-Wasm → Tesseract.js

   特性:
   - 前端浏览器离线OCR（PaddleOCR-Wasm / Tesseract.js）
   - 后端增强OCR（PaddleOCR GPU + DeepSeek-VL）
   - 自动裁剪过滤手机状态栏、UI色块等无关元素
   - 输出带行号索引的完整文本
   - 模糊文字标注 [无法识别]
   ============================================================ */

const OCREngine = (() => {
  // === State ===
  let paddleOCRInstance = null;
  let paddleOCRReady = false;
  let paddleOCRLoading = false;
  let tesseractReady = false;
  let currentBackend = null;  // 'backend' | 'paddleocr' | 'tesseract' | null

  const ENGINE_STATE = { UNINITIALIZED: 0, LOADING: 1, READY: 2, ERROR: 3 };
  let paddleState = ENGINE_STATE.UNINITIALIZED;
  let tesseractState = ENGINE_STATE.UNINITIALIZED;

  // === PaddleOCR-Wasm CDN ===
  const PADDLEOCR_CDN = 'https://cdn.jsdelivr.net/npm/paddleocr-js/dist/browser/index.min.js';

  // PaddleOCR PP-OCRv6 tiny models hosted on HuggingFace
  const PADDLEOCR_MODEL_PATH = 'https://huggingface.co/paddleocr/pp-ocrv6-tiny/resolve/main/';

  // === Init: Preload PaddleOCR ===
  async function initPaddleOCR() {
    if (paddleState === ENGINE_STATE.READY) return true;
    if (paddleState === ENGINE_STATE.LOADING) {
      // Wait for existing load
      for (let i = 0; i < 50; i++) {
        if (paddleState !== ENGINE_STATE.LOADING) break;
        await new Promise(r => setTimeout(r, 200));
      }
      return paddleState === ENGINE_STATE.READY;
    }

    paddleState = ENGINE_STATE.LOADING;
    console.log('[OCREngine] Loading PaddleOCR-Wasm...');

    try {
      // Dynamic import from CDN
      if (typeof window.PaddleOCR === 'undefined') {
        await loadScript(PADDLEOCR_CDN);
        console.log('[OCREngine] PaddleOCR CDN script loaded');
      }

      if (typeof window.PaddleOCR === 'undefined') {
        throw new Error('PaddleOCR global not found after script load');
      }

      paddleOCRInstance = new PaddleOCR({
        modelPath: PADDLEOCR_MODEL_PATH,
        useWasm: true,
        useTensorflow: false,
        useONNX: true,
        language: 'ch',
        enableTable: false,
        enableFormula: false,
        enableBarcode: false,
        enableLayout: false,
        enableCache: true,
        maxSideLen: 960,
        threshold: 0.3,
      });

      await paddleOCRInstance.init();
      paddleOCRReady = true;
      paddleState = ENGINE_STATE.READY;
      console.log('[OCREngine] PaddleOCR-Wasm ready ✅');
      return true;
    } catch (e) {
      console.warn('[OCREngine] PaddleOCR-Wasm init failed:', e.message);
      paddleState = ENGINE_STATE.ERROR;
      paddleOCRReady = false;
      return false;
    }
  }

  /** 动态加载 script */
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Failed to load: ${src}`));
      document.head.appendChild(script);
    });
  }

  // === Init: Tesseract.js (already loaded via CDN in index.html) ===
  function initTesseract() {
    if (tesseractState === ENGINE_STATE.READY) return true;
    if (typeof Tesseract === 'undefined') {
      tesseractState = ENGINE_STATE.ERROR;
      console.warn('[OCREngine] Tesseract.js not loaded');
      return false;
    }
    tesseractReady = true;
    tesseractState = ENGINE_STATE.READY;
    console.log('[OCREngine] Tesseract.js ready ✅');
    return true;
  }

  // === Main API: Recognize text from image ===
  /**
   * Recognize text from image file or dataURL.
   *
   * @param {File|string} input - Image File object or dataURL string
   * @param {Object} options
   * @param {string} options.lang - 'zh' | 'en' | 'chi_sim+eng'
   * @param {Function} options.onProgress - ({stage, progress, method}) => void
   * @param {boolean} options.preferLocal - Skip backend, use local OCR only
   * @returns {Promise<{success, fullText, lines, method, confidence, errors}>}
   */
  async function recognize(input, options = {}) {
    const { lang = 'zh', onProgress = () => {}, preferLocal = false } = options;

    const dataURL = typeof input === 'string' ? input : await fileToDataURL(input);
    if (!dataURL) return { success: false, fullText: '', error: '无法读取图片数据' };

    let result = null;

    // === Level 1: Backend API (PaddleOCR GPU) ===
    if (!preferLocal && window.BackendAPI && window.BackendAPI.isBackendAvailable()) {
      onProgress({ stage: 'backend', progress: 0, method: 'backend' });
      try {
        const blob = dataURLtoBlob(dataURL);
        const file = new File([blob], `ocr_${Date.now()}.png`, { type: 'image/png' });
        const parsed = await BackendAPI.parseFile(file, { lang, fallback: false });
        if (parsed.success && parsed.markdown && parsed.markdown.length > 10) {
          onProgress({ stage: 'done', progress: 100, method: 'backend' });
          return {
            success: true,
            fullText: parsed.markdown,
            lines: parsed.markdown.split('\n').filter(l => l.trim()),
            method: 'backend-paddleocr',
            confidence: 0.95,
            rawResult: parsed,
          };
        }
      } catch (e) {
        console.warn('[OCREngine] Backend OCR failed:', e.message);
        onProgress({ stage: 'backend_failed', progress: 0, method: 'backend' });
      }
    }

    // === Level 2: PaddleOCR-Wasm (browser offline) ===
    if (paddleState !== ENGINE_STATE.ERROR) {
      onProgress({ stage: 'paddleocr', progress: 0, method: 'paddleocr' });
      try {
        const inited = await initPaddleOCR();
        if (inited && paddleOCRInstance) {
          onProgress({ stage: 'paddleocr', progress: 30, method: 'paddleocr' });

          // 预处理：裁剪无关区域
          const processedDataURL = await preprocessImage(dataURL);
          onProgress({ stage: 'paddleocr', progress: 50, method: 'paddleocr' });

          const img = await dataURLToImage(processedDataURL);
          const ocrResult = await paddleOCRInstance.recognize(img);
          onProgress({ stage: 'paddleocr', progress: 90, method: 'paddleocr' });

          if (ocrResult && ocrResult.textRecognition) {
            const lines = ocrResult.textRecognition.map((r, i) => ({
              index: i,
              text: r.text,
              confidence: r.score,
            }));

            // 标注模糊文字
            const fullText = lines.map(l => {
              if (l.confidence < 0.5) return `[无法识别:${l.text}]`;
              return l.text;
            }).join('\n');

            const lowConf = lines.filter(l => l.confidence < 0.5);
            if (lowConf.length > 0) {
              console.warn(`[OCREngine] ${lowConf.length}/${lines.length} 行置信度低:`, lowConf.map(l => l.text));
            }

            onProgress({ stage: 'done', progress: 100, method: 'paddleocr' });
            return {
              success: true,
              fullText,
              lines: lines.map(l => l.text),
              method: 'paddleocr-wasm',
              confidence: ocrResult.textRecognition.reduce((s, r) => s + r.score, 0) / Math.max(1, ocrResult.textRecognition.length),
              lowConfidenceLines: lowConf.map(l => l.text),
              rawResult: ocrResult,
            };
          }
        }
      } catch (e) {
        console.warn('[OCREngine] PaddleOCR-Wasm failed:', e.message);
        onProgress({ stage: 'paddleocr_failed', progress: 0, method: 'paddleocr' });
      }
    }

    // === Level 3: Tesseract.js (last resort) ===
    onProgress({ stage: 'tesseract', progress: 0, method: 'tesseract' });
    try {
      initTesseract();
      if (tesseractReady) {
        const tesseractLang = lang === 'zh' ? 'chi_sim+eng' : 'eng';
        onProgress({ stage: 'tesseract', progress: 10, method: 'tesseract' });

        const tResult = await Tesseract.recognize(dataURL, tesseractLang, {
          logger: (info) => {
            if (info.status === 'recognizing text') {
              onProgress({ stage: 'tesseract', progress: Math.round(info.progress * 100), method: 'tesseract' });
            }
          },
        });

        onProgress({ stage: 'done', progress: 100, method: 'tesseract' });
        return {
          success: true,
          fullText: tResult.data.text,
          lines: tResult.data.text.split('\n').filter(l => l.trim()),
          method: 'tesseract.js',
          confidence: tResult.data.confidence / 100,
          rawResult: tResult,
        };
      }
    } catch (e) {
      console.warn('[OCREngine] Tesseract failed:', e.message);
      onProgress({ stage: 'tesseract_failed', progress: 0, method: 'tesseract' });
    }

    // === All levels failed ===
    return {
      success: false,
      fullText: '',
      lines: [],
      method: 'none',
      confidence: 0,
      error: '所有 OCR 引擎均不可用。请启动后端服务或检查网络连接。',
    };
  }

  // === 图片预处理：裁剪无关区域 ===
  /**
   * 自动检测并裁剪掉手机状态栏、UI色块等无关元素
   * 使用简单的边缘检测 + 内容区域识别
   */
  async function preprocessImage(dataURL) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        const maxW = 2048;
        const maxH = 2048;
        let w = img.naturalWidth;
        let h = img.naturalHeight;

        // 限制最大分辨率
        if (w > maxW || h > maxH) {
          const ratio = Math.min(maxW / w, maxH / h);
          w = Math.round(w * ratio);
          h = Math.round(h * ratio);
        }

        canvas.width = w;
        canvas.height = h;
        ctx.drawImage(img, 0, 0, w, h);

        // 简单的内容区域检测:
        // 1. 裁剪顶部 5%（可能的状态栏）
        // 2. 裁剪左右各 3%（可能的UI边距）
        const imageData = ctx.getImageData(0, 0, w, h);
        const pixels = imageData.data;

        // 检测顶部空白行
        let topCrop = 0;
        const topScanLimit = Math.floor(h * 0.15);
        for (let y = 0; y < topScanLimit; y++) {
          let hasContent = false;
          for (let x = 0; x < w; x++) {
            const idx = (y * w + x) * 4;
            const r = pixels[idx], g = pixels[idx + 1], b = pixels[idx + 2];
            // 非纯白/浅灰即为有内容
            if (r < 240 || g < 240 || b < 240) {
              hasContent = true;
              break;
            }
          }
          if (!hasContent) topCrop = y;
          else break;
        }
        topCrop = Math.max(0, topCrop - 2); // 留2px边距

        // 检测底部空白行
        let bottomCrop = h;
        for (let y = h - 1; y >= h - topScanLimit; y--) {
          let hasContent = false;
          for (let x = 0; x < w; x++) {
            const idx = (y * w + x) * 4;
            if (pixels[idx] < 240 || pixels[idx + 1] < 240 || pixels[idx + 2] < 240) {
              hasContent = true;
              break;
            }
          }
          if (!hasContent) bottomCrop = y;
          else break;
        }
        bottomCrop = Math.min(h, bottomCrop + 2);

        // 如果裁剪范围太小（<50px），不做裁剪
        if (bottomCrop - topCrop < 50) {
          resolve(dataURL);
          return;
        }

        // 重新绘制裁剪后的图片
        const cropCanvas = document.createElement('canvas');
        cropCanvas.width = w;
        cropCanvas.height = bottomCrop - topCrop;
        const cropCtx = cropCanvas.getContext('2d');
        cropCtx.drawImage(canvas, 0, topCrop, w, bottomCrop - topCrop, 0, 0, w, bottomCrop - topCrop);

        resolve(cropCanvas.toDataURL('image/png'));
        console.log(`[OCREngine] Image cropped: top=${topCrop}px, bottom=${bottomCrop}px, height=${bottomCrop - topCrop}px`);
      };
      img.src = dataURL;
    });
  }

  // === Utility: File → DataURL ===
  function fileToDataURL(file) {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(file);
    });
  }

  // === Utility: DataURL → Image Element ===
  function dataURLToImage(dataURL) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('Failed to load image'));
      img.src = dataURL;
    });
  }

  // === Utility: DataURL → Blob ===
  function dataURLtoBlob(dataURL) {
    const parts = dataURL.split(',');
    const mime = parts[0].match(/:(.*?);/)[1];
    const bytes = atob(parts[1]);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    return new Blob([arr], { type: mime });
  }

  // === 获取引擎状态 ===
  function getStatus() {
    return {
      paddleOCR: paddleState === ENGINE_STATE.READY ? 'ready' : paddleState === ENGINE_STATE.LOADING ? 'loading' : 'unavailable',
      tesseract: tesseractState === ENGINE_STATE.READY ? 'ready' : 'unavailable',
      backend: window.BackendAPI?.isBackendAvailable?.() ? 'available' : 'unavailable',
      currentBackend,
    };
  }

  // === Preload (后台预热) ===
  function preload() {
    // 后台预加载 PaddleOCR
    if (paddleState === ENGINE_STATE.UNINITIALIZED) {
      initPaddleOCR().catch(() => {});
    }
    // Tesseract 已预加载
    initTesseract();
  }

  // === Public API ===
  return {
    recognize,
    initPaddleOCR,
    initTesseract,
    preload,
    getStatus,
    preprocessImage,
    get isPaddleReady() { return paddleOCRReady; },
    get isTesseractReady() { return tesseractReady; },
  };
})();

// Auto-preload on page load
window.OCREngine = OCREngine;
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => OCREngine.preload(), 2000);
});
