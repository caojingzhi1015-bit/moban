/* ============================================================
   app.js - 主应用控制器 v2
   新增：图片上传、自由文本解析、HR人设面试、评估报告
   ============================================================ */

const App = (() => {
  const state = {
    jdText: '',
    jdKeywords: null,
    jdImageData: null,
    personalText: '',
    personalImageData: null,
    formData: {},
    questionnaireAnswers: {},
    currentQuestions: [],
    currentQIndex: 0,
    resumeData: null,
    selfIntro: { cn: '', en: '' },
    interviewStarted: false,
    currentJDInputMode: 'text',
    currentPersonalInputMode: 'text',
  };

  // === Init ===
  function init() {
    loadAllDrafts();
    LiquidMetal.init();
    bindAllEvents();
    setInterval(saveAllDrafts, 10000);
    InterviewSystem.renderChat();
    updatePreview();
    console.log('🚀 CareerAI v2 initialized');
  }

  // === Persistence ===
  function saveAllDrafts() {
    try {
      const draft = {
        jdText: state.jdText || document.getElementById('jd-input')?.value || '',
        personalText: state.personalText || document.getElementById('personal-free-text')?.value || '',
        formData: state.formData,
        questionnaireAnswers: state.questionnaireAnswers,
        timestamp: Date.now(),
      };
      localStorage.setItem('careerai_draft_v2', JSON.stringify(draft));
      // Save API keys
      ['claude', 'chatgpt', 'gemini'].forEach(m => {
        const val = document.getElementById(`api-key-${m}`)?.value;
        if (val) localStorage.setItem(`careerai_api_key_${m}`, val);
      });
      showSaveIndicator();
    } catch(e) {}
  }

  function loadAllDrafts() {
    try {
      const raw = localStorage.getItem('careerai_draft_v2');
      if (!raw) return;
      const draft = JSON.parse(raw);
      if (draft.jdText) {
        state.jdText = draft.jdText;
        const jdInput = document.getElementById('jd-input');
        if (jdInput) jdInput.value = draft.jdText;
      }
      if (draft.personalText) {
        state.personalText = draft.personalText;
        const personalInput = document.getElementById('personal-free-text') || document.getElementById('personal-image-text') || document.getElementById('personal-file-text');
        if (personalInput) personalInput.value = draft.personalText;
      }
      state.formData = draft.formData || {};
      state.questionnaireAnswers = draft.questionnaireAnswers || {};
      // Restore extracted fields
      Object.entries(state.formData).forEach(([key, val]) => {
        const el = document.getElementById(`field-${key}`);
        if (el && val) el.value = val;
      });
      if (Object.keys(state.formData).length > 0) {
        showExtractedFields(state.formData);
      }
    } catch(e) {}
  }

  function showSaveIndicator() {
    const el = document.getElementById('save-indicator');
    if (!el) return;
    el.classList.add('visible');
    setTimeout(() => el.classList.remove('visible'), 2000);
  }

  // === Event Binding ===
  function bindAllEvents() {
    bindNavScroll();
    bindLangToggle();
    bindInputModeTabs();
    bindImageUploads();
    bindFileUploads();
    bindJDEvents();
    bindPersonalEvents();
    bindQuestionnaireEvents();
    bindResumeEvents();
    bindSelfIntroEvents();
    bindInterviewEvents();
    bindPreviewControls();
    bindDragEvents();
    bindKeyboardShortcuts();
    bindScrollEffects();
  }

  // === Navigation ===
  function bindNavScroll() {
    document.querySelectorAll('[data-scroll-to]').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const target = document.getElementById(link.getAttribute('data-scroll-to'));
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
    window.addEventListener('scroll', () => {
      const navbar = document.querySelector('.navbar');
      if (navbar) navbar.classList.toggle('scrolled', window.scrollY > 50);
    });
  }

  function bindScrollEffects() {
    window.addEventListener('scroll', () => {
      const hero = document.querySelector('.hero');
      if (hero) {
        const s = window.scrollY;
        hero.style.transform = `translateY(${s * 0.3}px)`;
        hero.style.opacity = Math.max(0, 1 - s / 600);
      }
    });
  }

  // === Language Toggle ===
  function bindLangToggle() {
    document.querySelectorAll('.lang-option').forEach(opt => {
      opt.addEventListener('click', () => {
        const lang = opt.getAttribute('data-lang');
        I18N.setLang(lang);
        document.querySelectorAll('.lang-option').forEach(o => o.classList.remove('active'));
        opt.classList.add('active');
        updatePreview();
        InterviewSystem.renderChat();
        const toggleEl = document.querySelector('.lang-toggle');
        if (toggleEl) {
          const r = toggleEl.getBoundingClientRect();
          LiquidMetal.triggerBurst(r.left + r.width/2, r.top + r.height/2, 15);
        }
      });
    });
  }

  // === Input Mode Tabs (Text / Image / File) ===
  function bindInputModeTabs() {
    // JD tabs
    document.querySelectorAll('#jd-input-mode-tabs .input-mode-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const mode = tab.getAttribute('data-mode');
        state.currentJDInputMode = mode;
        document.querySelectorAll('#jd-input-mode-tabs .input-mode-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('jd-text-mode').classList.toggle('hidden', mode !== 'text');
        document.getElementById('jd-image-mode').classList.toggle('hidden', mode !== 'image');
        document.getElementById('jd-file-mode').classList.toggle('hidden', mode !== 'file');
      });
    });
    // Personal tabs
    document.querySelectorAll('#personal-input-mode-tabs .input-mode-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const mode = tab.getAttribute('data-mode');
        state.currentPersonalInputMode = mode;
        document.querySelectorAll('#personal-input-mode-tabs .input-mode-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('personal-text-mode').classList.toggle('hidden', mode !== 'text');
        document.getElementById('personal-image-mode').classList.toggle('hidden', mode !== 'image');
        document.getElementById('personal-file-mode').classList.toggle('hidden', mode !== 'file');
      });
    });
  }

  // === Image Uploads ===
  function bindImageUploads() {
    setupImageUpload('jd', (data) => {
      state.jdImageData = data;
      // Show preview
      const previewEl = document.getElementById('jd-image-preview');
      previewEl.innerHTML = `<div class="image-preview-container">
        <img src="${data.dataURL}" class="image-preview" alt="JD Image">
        <button class="image-preview-remove" id="jd-preview-remove">✕</button>
      </div>`;
      previewEl.classList.remove('hidden');
      document.getElementById('jd-image-text').classList.remove('hidden');
      document.getElementById('jd-preview-remove').addEventListener('click', () => {
        previewEl.classList.add('hidden');
        document.getElementById('jd-image-text').classList.add('hidden');
        state.jdImageData = null;
      });
      // Simulate OCR
      performImageOCR(data.dataURL, 'jd-image-text', 'JD');
    });

    setupImageUpload('personal', (data) => {
      state.personalImageData = data;
      const previewEl = document.getElementById('personal-image-preview');
      previewEl.innerHTML = `<div class="image-preview-container">
        <img src="${data.dataURL}" class="image-preview" alt="Resume Image">
        <button class="image-preview-remove" id="personal-preview-remove">✕</button>
      </div>`;
      previewEl.classList.remove('hidden');
      document.getElementById('personal-image-text').classList.remove('hidden');
      document.getElementById('personal-preview-remove').addEventListener('click', () => {
        previewEl.classList.add('hidden');
        document.getElementById('personal-image-text').classList.add('hidden');
        state.personalImageData = null;
      });
      performImageOCR(data.dataURL, 'personal-image-text', '简历');
    });
  }

  // === File Uploads (TXT/PDF/DOCX/DOC) ===
  function bindFileUploads() {
    setupFileUpload('jd', (fileInfo) => {
      const previewEl = document.getElementById('jd-file-preview');
      previewEl.innerHTML = `
        <div class="file-preview-card">
          <span class="file-type-icon">${fileInfo.icon}</span>
          <div class="file-info">
            <div class="file-name">${fileInfo.name}</div>
            <div class="file-meta">${formatFileSize(fileInfo.size)} · ${fileInfo.extension.toUpperCase()} · ${fileInfo.method || '解析完成'}</div>
          </div>
          <button class="file-preview-remove" id="jd-file-remove">✕</button>
        </div>`;
      previewEl.classList.remove('hidden');
      const textEl = document.getElementById('jd-file-text');
      textEl.classList.remove('hidden');
      textEl.value = fileInfo.extractedText || '';
      if (!fileInfo.extractedText || fileInfo.extractedText.length < 20) {
        textEl.placeholder = '文件文字提取有限，请手动粘贴或编辑JD内容...';
      }
      document.getElementById('jd-file-remove').addEventListener('click', () => {
        previewEl.classList.add('hidden');
        textEl.classList.add('hidden');
        textEl.value = '';
      });
      // Import into MaterialStore
      if (fileInfo.extractedText) {
        importToMaterialStore(fileInfo, 'jd');
      }
      showToast(`文件 "${fileInfo.name}" 已加载 · 素材已入库`, 'success');
    });

    setupFileUpload('personal', (fileInfo) => {
      const previewEl = document.getElementById('personal-file-preview');
      previewEl.innerHTML = `
        <div class="file-preview-card">
          <span class="file-type-icon">${fileInfo.icon}</span>
          <div class="file-info">
            <div class="file-name">${fileInfo.name}</div>
            <div class="file-meta">${formatFileSize(fileInfo.size)} · ${fileInfo.extension.toUpperCase()} · ${fileInfo.method || '解析完成'}</div>
          </div>
          <button class="file-preview-remove" id="personal-file-remove">✕</button>
        </div>`;
      previewEl.classList.remove('hidden');
      const textEl = document.getElementById('personal-file-text');
      textEl.classList.remove('hidden');
      textEl.value = fileInfo.extractedText || '';
      if (!fileInfo.extractedText || fileInfo.extractedText.length < 20) {
        textEl.placeholder = '文件文字提取有限，请手动粘贴或编辑个人信息...';
      }
      document.getElementById('personal-file-remove').addEventListener('click', () => {
        previewEl.classList.add('hidden');
        textEl.classList.add('hidden');
        textEl.value = '';
      });
      // Import into MaterialStore
      if (fileInfo.extractedText) {
        importToMaterialStore(fileInfo, 'resume');
      }
      showToast(`文件 "${fileInfo.name}" 已加载 · 素材已入库`, 'success');
    });
  }

  function setupFileUpload(prefix, onFileLoaded) {
    const zone = document.getElementById(`${prefix}-file-upload-zone`);
    const input = document.getElementById(`${prefix}-file-input`);
    if (!zone || !input) return;

    zone.addEventListener('click', (e) => {
      if (e.target === input) return;
      input.click();
    });
    input.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) processUploadedFile(file, onFileLoaded);
    });

    // Drag & drop
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) processUploadedFile(file, onFileLoaded);
    });

    // Clipboard paste (Ctrl+V) - support files copied from system/file manager
    zone.addEventListener('paste', (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.kind === 'file') {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) {
            zone.classList.add('drag-over');
            setTimeout(() => zone.classList.remove('drag-over'), 300);
            processUploadedFile(file, onFileLoaded);
            return;
          }
        }
      }
    });

    // Global paste catch for when this zone's tab is active
    document.addEventListener('paste', function fileDocPasteHandler(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (zone.closest('.hidden') || zone.offsetParent === null) return;
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.kind === 'file') {
          e.preventDefault();
          zone.classList.add('drag-over');
          setTimeout(() => zone.classList.remove('drag-over'), 300);
          const file = item.getAsFile();
          if (file) processUploadedFile(file, onFileLoaded);
          return;
        }
      }
    });
  }

  function processUploadedFile(file, callback) {
    showLoading('正在解析文件并提取文字...');

    // 图片文件 → 优先用后端 VL OCR，其次浏览器端 DeepSeek-VL，最后 Tesseract.js
    const isImage = ['png','jpg','jpeg','webp','bmp','gif'].includes(getFileExt(file.name));
    const isPDF = getFileExt(file.name) === 'pdf';

    // 图片文件 + 后端可用 → 用后端 parse 接口（后端内部调 VL OCR）
    if (isImage && window.BackendAPI && window.BackendAPI.isBackendAvailable()) {
      BackendAPI.parseFile(file, { lang: I18N.getLang() }).then(result => {
        hideLoading();
        if (result.success && result.markdown) {
          showToast('✅ 后端 VL OCR 识别完成', 'success');
          callback({
            name: file.name, size: file.size, type: file.type,
            extension: getFileExt(file.name), icon: getFileIconFor(file.name),
            extractedText: result.markdown, method: 'backend-vl-ocr',
          });
        } else {
          // 后端失败 → 降级浏览器端
          _parseFileLocal(file, callback);
        }
      }).catch(() => _parseFileLocal(file, callback));
      return;
    }

    _parseFileLocal(file, callback);
  }

  function _parseFileLocal(file, callback) {
    showLoading('正在本地解析文件 (PDF.js/Tesseract/DeepSeek-VL)...');
    const isImage = ['png','jpg','jpeg','webp','bmp','gif'].includes(getFileExt(file.name));
    const isPDF = getFileExt(file.name) === 'pdf';

    // 图片/PDF + DeepSeek API key → 用 DeepSeek-VL
    const useDeepSeek = DeepSeekAPI.getApiKey() && (isImage || isPDF);
    const parser = useDeepSeek ? DeepSeekFileParser : FileParser;

    parser.parseFile(file, {
      lang: I18N.getLang() === 'zh' ? 'chi_sim+eng' : 'eng',
      onProgress: (info) => {
        if (info.status === 'ocr_progress') {
          const loadingText = document.getElementById('loading-text');
          if (loadingText) loadingText.textContent = `OCR识别中... ${info.progress}%`;
        }
      },
    }).then(result => {
      hideLoading();

      if (!result.success) {
        showToast(result.error || '文件解析失败', 'error');
        callback({ name: file.name, size: file.size, type: file.type, extension: getFileExt(file.name), icon: getFileIconFor(file.name), extractedText: '' });
        return;
      }

      // Show method used
      const methodNote = result.method === 'pdf.js' ? ' (PDF.js解析)' :
        result.method === 'tesseract.js' ? ` (OCR识别, 置信度${Math.round(result.confidence || 0)}%)` :
        result.method === 'xml_extraction' ? ' (DOCX解析)' :
        result.method === 'fallback' ? ' (基础提取，请核对)' : '';

      showToast(`文件解析完成${methodNote}`, 'success');

      callback({
        name: file.name,
        size: file.size,
        type: file.type,
        extension: getFileExt(file.name),
        icon: getFileIconFor(file.name),
        extractedText: result.fullText,
        method: result.method,
        confidence: result.confidence,
        structured: result.structured,
      });
    }).catch(err => {
      hideLoading();
      showToast('文件处理失败: ' + err.message, 'error');
      callback({ name: file.name, size: file.size, type: file.type, extension: getFileExt(file.name), icon: getFileIconFor(file.name), extractedText: '' });
    });
  }

  function getFileExt(name) {
    const parts = name.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
  }

  function getFileIconFor(name) {
    const ext = getFileExt(name);
    const icons = { txt: '📝', pdf: '📕', docx: '📘', doc: '📗', png: '🖼', jpg: '🖼', jpeg: '🖼', webp: '🖼' };
    return icons[ext] || '📎';
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function setupImageUpload(prefix, onImageLoaded) {
    const zone = document.getElementById(`${prefix}-image-upload-zone`);
    const input = document.getElementById(`${prefix}-image-input`);
    if (!zone || !input) return;

    // Click to upload
    zone.addEventListener('click', (e) => {
      if (e.target === input) return;
      input.click();
    });
    input.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) processUploadedImage(file, onImageLoaded);
    });

    // Drag & drop
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) processUploadedImage(file, onImageLoaded);
    });

    // Clipboard paste (Ctrl+V) - support images copied from web/clipboard
    zone.addEventListener('paste', (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          const blob = item.getAsFile();
          if (blob) {
            zone.classList.add('drag-over');
            setTimeout(() => zone.classList.remove('drag-over'), 300);
            processUploadedImage(blob, onImageLoaded);
            return;
          }
        }
      }
    });

    // Also listen for paste on the whole document when this zone is visible
    // to catch paste events when user hasn't focused the zone specifically
    document.addEventListener('paste', function docPasteHandler(e) {
      // Only handle if the target is NOT an input/textarea (those handle text paste)
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      // Only handle if this zone's tab is active
      if (zone.closest('.hidden') || zone.offsetParent === null) return;
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          zone.classList.add('drag-over');
          setTimeout(() => zone.classList.remove('drag-over'), 300);
          const blob = item.getAsFile();
          if (blob) processUploadedImage(blob, onImageLoaded);
          return;
        }
      }
    });
  }

  function processUploadedImage(file, callback) {
    if (!file.type.startsWith('image/')) {
      showToast('请上传图片文件 (PNG/JPG/WebP)', 'warning');
      return;
    }
    ResumeEngine.processImageFile(file).then(callback).catch(err => {
      showToast('图片处理失败: ' + err.message, 'error');
    });
  }

  /**
   * 图片 VL OCR — 将图片 dataURL 发送到多模态模型识别文字，回填到输入框
   *
   * 流程（三级降级）：
   * 1. 后端 API /api/parse（服务端调 VL OCR）
   * 2. 浏览器端 DeepSeek-VL visionRecognition（API key 可配）
   * 3. 提示用户手动输入（无可用 OCR 通道）
   */
  async function performImageOCR(dataURL, textareaId, contentType) {
    const textarea = document.getElementById(textareaId);
    if (!textarea || !dataURL) return;

    showLoading('AI 正在识别图片文字... (VL多模态)');
    let ocrText = null;
    let method = null;

    // === Level 1: 后端 API（服务端 VL OCR） ===
    if (window.BackendAPI && window.BackendAPI.isBackendAvailable()) {
      try {
        const blob = dataURLtoBlob(dataURL);
        const file = new File([blob], `image_${Date.now()}.png`, { type: 'image/png' });
        const result = await BackendAPI.parseFile(file, { lang: I18N.getLang(), fallback: false });
        if (result.success && result.markdown && result.markdown.length > 10) {
          ocrText = result.markdown;
          method = 'backend-vl-ocr';
        }
      } catch (e) { console.warn('[OCR] Backend VL failed:', e.message); }
    }

    // === Level 2: 浏览器端 DeepSeek-VL ===
    if (!ocrText && window.DeepSeekAPI && DeepSeekAPI.getApiKey()) {
      try {
        const prompt = contentType === 'JD'
          ? '你是一个精准的OCR识别工具。请严格识别并提取图片中的所有文字内容，保持原文格式和结构。完整提取岗位职责、任职要求、技能要求。数字、日期、百分比必须精确识别。不要添加任何不属于图片原文的内容。'
          : '你是一个精准的OCR识别工具。请严格识别并提取图片中的所有文字内容，保持原文格式和结构。如果是简历：提取姓名、联系方式、教育经历、工作经历、项目经历、技能证书、自我评价。数字、日期、百分比必须精确识别，不能近似或编造。';
        const result = await DeepSeekAPI.visionRecognition([dataURL], prompt);
        if (result.success && result.content && result.content.length > 10) {
          ocrText = result.content;
          method = 'deepseek-vl';
        }
      } catch (e) { console.warn('[OCR] DeepSeek-VL failed:', e.message); }
    }

    hideLoading();

    // === 回填文本框 ===
    if (ocrText) {
      textarea.value = ocrText;
      textarea.focus();
      showToast(`✅ ${method === 'backend-vl-ocr' ? '后端 VL OCR' : 'DeepSeek-VL'} 识别完成，请核对修改`, 'success');
      // 如果文案里包含 "本地模拟" 则清除
      if (textarea.value.includes('本地模拟')) {
        textarea.value = textarea.value.replace(/.*本地模拟.*\n?/g, '');
      }
    } else {
      // Level 3: 无可用的 OCR 通道
      textarea.placeholder = 'OCR 通道不可用（后端未启动 + DeepSeek API Key 未配置）。\n请手动粘贴图片中的文字内容。\n也可以启动后端以获得自动 OCR 功能。';
      textarea.focus();
      showToast('⚠️ OCR 通道不可用，请手动输入图片文字', 'warning');
    }
  }

  /** data URL 转 Blob */
  function dataURLtoBlob(dataURL) {
    const parts = dataURL.split(',');
    const mime = parts[0].match(/:(.*?);/)[1];
    const bytes = atob(parts[1]);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    return new Blob([arr], { type: mime });
  }

  // === JD Events ===
  function bindJDEvents() {
    const parseBtn = document.getElementById('btn-parse-jd');
    if (!parseBtn) return;

    parseBtn.addEventListener('click', () => {
      // Get JD text from either text mode or image mode
      let jdText = '';
      if (state.currentJDInputMode === 'text') {
        jdText = document.getElementById('jd-input')?.value?.trim() || '';
      } else if (state.currentJDInputMode === 'image') {
        jdText = document.getElementById('jd-image-text')?.value?.trim() || '';
      } else if (state.currentJDInputMode === 'file') {
        jdText = document.getElementById('jd-file-text')?.value?.trim() || '';
      }

      if (!jdText || jdText.length < 10) {
        showToast('请先输入或上传JD内容（至少10个字符）', 'warning');
        return;
      }

      state.jdText = jdText;
      parseBtn.textContent = '⏳ 解析中...';
      parseBtn.disabled = true;

      setTimeout(() => {
        state.jdKeywords = ResumeEngine.parseJD(jdText);
        // Import JD into MaterialStore
        MaterialStore.setJDRawText(jdText, 'JD输入');
        MaterialStore.setJDKeywords(state.jdKeywords, 'JD输入');
        renderJDTags();
        generateQuestionnaire();
        parseBtn.textContent = '🔍 AI解析JD关键词';
        parseBtn.disabled = false;

        const r = parseBtn.getBoundingClientRect();
        LiquidMetal.triggerBurst(r.left + r.width/2, r.top + r.height/2, 20);
        saveAllDrafts();
      }, 600);
    });
  }

  function renderJDTags() {
    const container = document.getElementById('jd-tags-container');
    if (!container) return;
    const kw = state.jdKeywords;
    if (!kw || (kw.hardSkills.length === 0 && kw.softSkills.length === 0)) {
      container.innerHTML = '';
      return;
    }
    let html = '';
    kw.hardSkills.slice(0, 8).forEach(s => html += `<span class="jd-tag hard-skill">🔧 ${s}</span>`);
    kw.softSkills.slice(0, 5).forEach(s => html += `<span class="jd-tag soft-skill">💡 ${s}</span>`);
    kw.industry.slice(0, 3).forEach(s => html += `<span class="jd-tag industry">🏭 ${s}</span>`);
    if (kw.yearsRequired) html += `<span class="jd-tag hard-skill">📅 ${kw.yearsRequired}</span>`;
    if (kw.educationRequired) html += `<span class="jd-tag soft-skill">🎓 ${kw.educationRequired}</span>`;
    container.innerHTML = html;
  }

  // === Personal Info Events ===
  function bindPersonalEvents() {
    const extractBtn = document.getElementById('btn-extract-personal');
    if (!extractBtn) return;

    extractBtn.addEventListener('click', async () => {
      // === Collect input: check file upload first, then text ===
      let fileToProcess = null;
      let textToProcess = '';

      // Check if there's a file in the file/image upload area
      const fileInput = document.getElementById('personal-file-input');
      const imageInput = document.getElementById('personal-image-input');

      if (state.currentPersonalInputMode === 'file' && fileInput?.files?.length > 0) {
        fileToProcess = fileInput.files[0];
      } else if (state.currentPersonalInputMode === 'image' && imageInput?.files?.length > 0) {
        fileToProcess = imageInput.files[0];
      } else if (state.currentPersonalInputMode === 'file') {
        textToProcess = document.getElementById('personal-file-text')?.value?.trim() || '';
      } else if (state.currentPersonalInputMode === 'image') {
        textToProcess = document.getElementById('personal-image-text')?.value?.trim() || '';
      } else {
        textToProcess = document.getElementById('personal-free-text')?.value?.trim() || '';
      }

      // If no file and no text, look for text area fallback
      if (!fileToProcess && !textToProcess) {
        showToast('请先输入文字、粘贴内容或上传文件', 'warning');
        return;
      }

      // === Run extraction pipeline ===
      extractBtn.textContent = '⏳ 提取中...';
      extractBtn.disabled = true;

      // Show progress log area
      const logContainer = document.getElementById('extraction-progress');
      if (logContainer) {
        logContainer.classList.remove('hidden');
        logContainer.innerHTML = '<div class="extraction-progress-title">🔍 正在执行提取流水线...</div>';
      }

      const logProgress = (msg) => {
        if (logContainer) {
          const entry = document.createElement('div');
          entry.className = 'pipeline-log-entry pipeline-log-info';
          entry.textContent = msg;
          logContainer.appendChild(entry);
          logContainer.scrollTop = logContainer.scrollHeight;
        }
        console.log('[Extraction]', msg);
      };

      // === 优先使用后端 API（如果可用） ===
      let pipelineResult;
      if (window.BackendAPI && window.BackendAPI.isBackendAvailable()) {
        try {
          logProgress('🚀 使用后端提取引擎 (SmartResume → LLM → Regex)...');
          const backendFile = fileToProcess || new File([textToProcess], 'input.txt', { type: 'text/plain' });
          const parsed = await BackendAPI.parseFile(backendFile, { lang: I18N.getLang(), fallback: false });
          if (parsed.success && parsed.markdown) {
            const extracted = await BackendAPI.extractResume(parsed.markdown, { lang: I18N.getLang(), fallback: false });
            if (extracted.success || extracted.basic_info) {
              pipelineResult = { ...extracted, log: [] };
              logProgress('✅ 后端提取完成: method=' + (extracted.method || '?') + ', confidence=' + (extracted.confidence || '?'));
            }
          }
        } catch (e) { console.warn('[App] Backend extract failed, falling back:', e.message); }
      }
      if (!pipelineResult) {
        logProgress('🖥️ 使用浏览器端提取引擎...');
        pipelineResult = await ExtractionPipeline.runFullPipeline(
          fileToProcess || new File([textToProcess], 'input.txt', { type: 'text/plain' }),
          {
            lang: I18N.getLang(),
            onProgress: (info) => {
              if (logContainer) {
                const existing = logContainer.querySelector('.pipeline-logs') || document.createElement('div');
                if (!existing.classList.contains('pipeline-logs')) {
                  existing.className = 'pipeline-logs';
                  logContainer.appendChild(existing);
                }
                const entry = document.createElement('div');
                entry.className = `pipeline-log-entry pipeline-log-${info.type || 'info'}`;
                entry.textContent = info.stage;
                existing.appendChild(entry);
                existing.scrollTop = existing.scrollHeight;
              }
            }
          },
      );
    } // end if (!pipelineResult)

      // === Handle Result ===
      if (pipelineResult.success && pipelineResult.data) {
        const data = pipelineResult.data;
        const validation = pipelineResult.validation;

        // Populate form fields from extracted data
        populateFormFromExtracted(data);

        // Show validation summary
        if (validation) {
          const missingCount = (validation.missingFields?.length || 0) + (validation.emptySections?.length || 0);
          if (missingCount > 0) {
            showMissingFieldsIndicator(validation);
          }
        }

        showToast(
          `✅ 提取完成：${data.education?.length || 0}段教育 · ${data.work_experience?.length || 0}段工作 · ${data.projects?.length || 0}个项目 · ${data.skills?.length || 0}项技能`,
          'success'
        );

        // Refresh previews
        collectAllFormData();
        if (state.jdText) handleGenerateResume();
        updatePreview();
      } else {
        showToast('提取失败: ' + (pipelineResult.error || '未知错误'), 'error');
      }

      extractBtn.textContent = '🤖 AI自动提取个人信息';
      extractBtn.disabled = false;

      const r = extractBtn.getBoundingClientRect();
      LiquidMetal.triggerBurst(r.left + r.width / 2, r.top + r.height / 2, 30);
      saveAllDrafts();
    });
  }

  // === Populate all form fields from extracted data ===
  function populateFormFromExtracted(data) {
    const bi = data.basic_info || {};
    // Basic fields
    setFieldValue('field-name', bi.name);
    setFieldValue('field-phone', bi.phone);
    setFieldValue('field-email', bi.email);
    setFieldValue('field-city', bi.city);
    setFieldValue('field-salary', bi.salary);
    setFieldValue('field-jobTitle', bi.target_job);

    // Multi-line fields
    const eduText = (data.education || []).map(e =>
      [e.school, e.major, e.degree, e.start, e.end].filter(Boolean).join(' / ')
    ).join('\n');
    setFieldValue('field-education', eduText);

    const workText = (data.work_experience || []).map(w =>
      [w.company, w.position, w.start, w.end].filter(Boolean).join(' / ') +
      (w.duties ? '\n  ' + w.duties : '')
    ).join('\n\n');
    setFieldValue('field-work', workText);

    const projText = (data.projects || []).map(p =>
      [p.name, p.role, p.description, p.results].filter(Boolean).join(' / ')
    ).join('\n');
    setFieldValue('field-project', projText);

    const skillText = (data.skills || []).map(s => typeof s === 'string' ? s : s.name).join('、');
    setFieldValue('field-skills', skillText);

    if (data.self_assessment?.text) {
      setFieldValue('field-selfIntro', data.self_assessment.text);
    }

    // Show extracted fields
    state.formData = {
      name: bi.name || '',
      phone: bi.phone || '',
      email: bi.email || '',
      city: bi.city || '',
      salary: bi.salary || '',
      jobTitle: bi.target_job || '',
      education: eduText,
      work: workText,
      project: projText,
      skills: skillText,
      selfIntro: data.self_assessment?.text || '',
    };
    showExtractedFields(state.formData);
    document.getElementById('extracted-fields')?.classList.remove('hidden');
    document.getElementById('extracted-detail-fields')?.classList.remove('hidden');
  }

  function setFieldValue(id, value) {
    const el = document.getElementById(id);
    if (el && value) el.value = value;
  }

  // === Missing fields indicator ===
  function showMissingFieldsIndicator(validation) {
    const missing = [...(validation.missingFields || []), ...(validation.emptySections || [])];
    if (missing.length === 0) return;

    const lang = I18N.getLang();
    const banner = document.createElement('div');
    banner.className = 'validation-banner warning';
    banner.innerHTML = `
      <span>⚠️</span>
      <span>${lang === 'zh' ? '以下信息未能提取，请手动补充：' : 'Could not extract:'} ${missing.join('、')}</span>
      <button class="btn btn-sm btn-cta" style="margin-left:auto;font-size:0.72rem;padding:4px 12px;" id="btn-auto-fill-missing">
        🪄 ${lang === 'zh' ? '一键自动补全' : 'Auto-Fill'}
      </button>`;

    const container = document.getElementById('extracted-detail-fields');
    if (container) {
      const existing = container.querySelector('.validation-banner');
      if (existing) existing.remove();
      container.insertBefore(banner, container.firstChild);
    }

    document.getElementById('btn-auto-fill-missing')?.addEventListener('click', () => {
      showToast('请在上方表单中手动补充缺少的信息', 'info');
      document.getElementById('field-education')?.focus();
    });
  }

  function showExtractedFields(data) {
    if (!data || Object.keys(data).filter(k => !k.startsWith('_')).length === 0) {
      document.getElementById('extracted-fields')?.classList.add('hidden');
      document.getElementById('extracted-detail-fields')?.classList.add('hidden');
      return;
    }

    document.getElementById('extracted-fields')?.classList.remove('hidden');
    document.getElementById('extracted-detail-fields')?.classList.remove('hidden');

    const basicFields = ['name', 'phone', 'email', 'city', 'salary', 'jobTitle'];
    basicFields.forEach(f => {
      const el = document.getElementById(`field-${f}`);
      if (el) {
        el.value = data[f] || '';
        el.readOnly = false;
      }
    });

    const detailFields = ['education', 'work', 'project', 'skills', 'selfIntro'];
    detailFields.forEach(f => {
      const el = document.getElementById(`field-${f}`);
      if (el) el.value = data[f] || '';
    });
  }

  // === Questionnaire ===
  function generateQuestionnaire() {
    const keywords = state.jdKeywords?.hardSkills || [];
    state.currentQuestions = I18N.generateQuestions(keywords.length > 0 ? keywords : null, 5);
    state.currentQIndex = 0;
    renderQuestionnaire();
  }

  function renderQuestionnaire() {
    const container = document.getElementById('questionnaire-container');
    if (!container || state.currentQuestions.length === 0) { if (container) container.innerHTML = ''; return; }

    const q = state.currentQuestions[state.currentQIndex];
    const total = state.currentQuestions.length;
    const current = state.currentQIndex + 1;
    const lang = I18N.getLang();

    container.innerHTML = `
      <div class="questionnaire-card">
        <div class="q-number">${current}/${total}</div>
        <div class="q-text">${q.text}</div>
        <input class="q-input" id="q-input-${state.currentQIndex}" placeholder="${lang === 'zh' ? '输入你的回答...' : 'Type your answer...'}" value="${state.questionnaireAnswers[q.key] || ''}">
        <div class="q-actions">
          <button class="q-skip" id="btn-q-skip">跳过 →</button>
          <button class="q-skip" id="btn-q-skip-all">全部跳过</button>
          <button class="btn btn-sm btn-cta" id="btn-q-next" style="margin-left:auto;">${current >= total ? '完成 ✓' : '下一题'}</button>
        </div>
      </div>`;

    document.getElementById('btn-q-next')?.addEventListener('click', () => {
      const input = document.getElementById(`q-input-${state.currentQIndex}`);
      if (input?.value.trim()) state.questionnaireAnswers[q.key] = input.value.trim();
      if (state.currentQIndex < total - 1) { state.currentQIndex++; renderQuestionnaire(); }
      else {
        state.questionnaireAnswers = ResumeEngine.processQAData(state.questionnaireAnswers);
        // Import QA into MaterialStore as legitimate source data
        if (window.MaterialStore) {
          Object.entries(state.questionnaireAnswers).forEach(([q, a]) => {
            if (a && a.trim()) MaterialStore.addQAEntry(q, a);
          });
        }
        container.innerHTML = '<div class="card" style="text-align:center;padding:32px;"><div style="font-size:2rem;margin-bottom:12px;">✅</div><div style="font-weight:600;">问卷完成！你的回答已录入素材库，将用于优化简历</div></div>';
        saveAllDrafts();
      }
    });
    document.getElementById('btn-q-skip')?.addEventListener('click', () => {
      if (state.currentQIndex < total - 1) { state.currentQIndex++; renderQuestionnaire(); }
      else container.innerHTML = '';
    });
    document.getElementById('btn-q-skip-all')?.addEventListener('click', () => { container.innerHTML = ''; state.currentQIndex = total; });
    setTimeout(() => document.getElementById(`q-input-${state.currentQIndex}`)?.focus(), 100);
  }

  function bindQuestionnaireEvents() {}

  // === Resume Events ===
  function bindResumeEvents() {
    document.getElementById('btn-generate-resume')?.addEventListener('click', handleGenerateResume);
    document.getElementById('btn-export-word')?.addEventListener('click', () => handleExport('word'));
    document.getElementById('btn-export-pdf')?.addEventListener('click', () => handleExport('pdf'));
    window.addEventListener('langchange', () => updatePreview());
  }

  function handleGenerateResume() {
    collectAllFormData();
    if (!state.jdText && !state.formData.name && MaterialStore.getAIContext().length < 20) {
      showToast('请先输入JD或上传简历文件', 'warning');
      return;
    }

    // === Lock material store (prevent further modifications during generation) ===
    MaterialStore.lock();

    showLoading('AI正在生成简历...\n校验素材真实性...');
    if (!state.jdKeywords) state.jdKeywords = ResumeEngine.parseJD(state.jdText);

    setTimeout(() => {
      state.resumeData = ResumeEngine.generateResume(state.formData, state.jdKeywords, state.questionnaireAnswers);

      // === Check for blocked (hallucination detected) ===
      if (state.resumeData._blocked) {
        hideLoading();
        showHallucinationAlert(state.resumeData);
        MaterialStore.unlock();
        return;
      }

      // === Check for warnings ===
      const validation = state.resumeData._validation;
      if (validation && validation.severity === 'warning') {
        showValidationBanner(validation);
      }

      state.selfIntro = ResumeEngine.generateSelfIntro(state.resumeData, I18N.getLang());
      updatePreview();
      hideLoading();

      if (validation && validation.stats) {
        const lang = I18N.getLang();
        showToast(
          lang === 'zh'
            ? `简历已生成 ✅${validation.stats.verified}项验证 ⚠️${validation.stats.uncertain}项存疑`
            : `Resume generated ✅${validation.stats.verified} verified ⚠️${validation.stats.uncertain} uncertain`,
          validation.stats.fabricated > 0 ? 'warning' : 'success'
        );
      } else {
        showToast('简历已生成！', 'success');
      }

      const btn = document.getElementById('btn-generate-resume');
      if (btn) { const r = btn.getBoundingClientRect(); LiquidMetal.triggerBurst(r.left + r.width/2, r.top + r.height/2, 30); }
    }, 1000);
  }

  function collectAllFormData() {
    if (state.currentJDInputMode === 'text') {
      state.jdText = document.getElementById('jd-input')?.value?.trim() || state.jdText;
    } else if (state.currentJDInputMode === 'image') {
      state.jdText = document.getElementById('jd-image-text')?.value?.trim() || state.jdText;
    } else if (state.currentJDInputMode === 'file') {
      state.jdText = document.getElementById('jd-file-text')?.value?.trim() || state.jdText;
    }
    const fields = ['name', 'phone', 'email', 'city', 'salary', 'jobTitle', 'education', 'work', 'project', 'skills', 'selfIntro'];
    fields.forEach(f => {
      const el = document.getElementById(`field-${f}`);
      if (el && el.value) state.formData[f] = el.value;
    });
  }

  function updatePreview() {
    ResumeEngine.renderPreview(state.resumeData, 'preview-desktop-body', false);
    ResumeEngine.renderPreview(state.resumeData, 'preview-mobile-body', true);

    // Add source hover tooltips to preview sections
    setTimeout(() => bindSourceHoverTooltips(), 300);

    const introContainer = document.getElementById('self-intro-content');
    if (introContainer && state.selfIntro) {
      const lang = I18N.getLang();
      const text = lang === 'zh' ? state.selfIntro.cn : state.selfIntro.en;
      if (text) introContainer.innerHTML = text.replace(/\n/g, '<br>');
    }
  }

  // === Source Hover Tooltips (素材溯源悬浮) ===
  function bindSourceHoverTooltips() {
    if (!state.resumeData?._sources) return;

    const sourceMap = {};
    state.resumeData._sources.forEach(s => {
      if (s.file) sourceMap[s.file] = s;
    });

    const tooltip = document.getElementById('source-tooltip');
    if (!tooltip) return;

    document.querySelectorAll('.resume-preview-section p').forEach(el => {
      el.addEventListener('mouseenter', (e) => {
        // Find matching source
        const text = el.textContent || '';
        for (const [file, src] of Object.entries(sourceMap)) {
          // Check if any key terms match
          const terms = text.split(/[\s,，、。]+/).filter(t => t.length >= 3);
          const matchCount = terms.filter(t =>
            MaterialStore.getAIContext().includes(t)
          ).length;
          if (matchCount >= 2) {
            tooltip.innerHTML = `
              <div class="src-file">📎 来源: ${file}</div>
              <div class="src-section">章节: ${src.section || '通用'}</div>
              <div style="font-size:0.68rem;color:var(--text-tertiary);margin-top:4px;">✅ 素材库已验证</div>`;
            tooltip.classList.add('visible');
            positionTooltip(tooltip, e);
            el.style.cursor = 'help';
            return;
          }
        }
      });
      el.addEventListener('mouseleave', () => {
        tooltip.classList.remove('visible');
        el.style.cursor = '';
      });
    });
  }

  function positionTooltip(tooltip, e) {
    const x = e.clientX + 12;
    const y = e.clientY - 10;
    tooltip.style.left = Math.min(x, window.innerWidth - 340) + 'px';
    tooltip.style.top = y + 'px';
  }

  function handleExport(format) {
    if (!state.resumeData) { showToast('请先生成简历', 'warning'); return; }
    const lang = I18N.getLang();
    const ok = format === 'word' ? ResumeEngine.exportWord(state.resumeData, lang) : ResumeEngine.exportPDF(state.resumeData, lang);
    if (ok) showToast('导出成功！', 'success');
  }

  // === Self-Intro Events ===
  function bindSelfIntroEvents() {
    document.getElementById('btn-generate-intro')?.addEventListener('click', () => {
      if (!state.resumeData) { handleGenerateResume(); return; }
      state.selfIntro = ResumeEngine.generateSelfIntro(state.resumeData, I18N.getLang());
      updatePreview();
    });
    document.getElementById('btn-copy-intro')?.addEventListener('click', () => {
      const el = document.getElementById('self-intro-content');
      if (!el) return;
      const text = el.textContent || el.innerText;
      navigator.clipboard.writeText(text).then(() => showToast('已复制！', 'success')).catch(() => {
        const ta = document.createElement('textarea'); ta.value = text;
        document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
        showToast('已复制！', 'success');
      });
    });
  }

  // === Interview Events ===
  function bindInterviewEvents() {
    // Model selection
    document.querySelectorAll('.model-option').forEach(el => {
      el.addEventListener('click', () => InterviewSystem.toggleModel(el.getAttribute('data-model')));
    });

    // Start interview
    document.getElementById('btn-start-interview')?.addEventListener('click', () => {
      collectAllFormData();
      const resumeInput = document.getElementById('interview-resume-input');
      const jdInput = document.getElementById('interview-jd-input');

      // Auto-fill from form data
      if (resumeInput && !resumeInput.value.trim() && state.personalText) {
        resumeInput.value = state.personalText;
      }
      if (jdInput && !jdInput.value.trim() && state.jdText) {
        jdInput.value = state.jdText;
      }

      const resume = resumeInput?.value?.trim() || state.personalText || '';
      const jd = jdInput?.value?.trim() || state.jdText || '';

      InterviewSystem.startInterview('', resume, jd);
      state.interviewStarted = true;
      updateInterviewUI();
      showToast('面试开始！HR已就位', 'success');
      setTimeout(() => LiquidMetal.resize(), 200);
    });

    // Stop interview
    document.getElementById('btn-stop-interview')?.addEventListener('click', () => {
      InterviewSystem.stopInterview();
      state.interviewStarted = false;
      updateInterviewUI();
    });

    // Send answer
    const answerInput = document.getElementById('interview-answer-input');
    document.getElementById('btn-send-answer')?.addEventListener('click', () => sendInterviewAnswer(answerInput));
    answerInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendInterviewAnswer(answerInput); }
    });

    // Reset
    document.getElementById('btn-reset-interview')?.addEventListener('click', () => {
      InterviewSystem.resetInterview();
      state.interviewStarted = false;
      updateInterviewUI();
    });

    // Export transcript
    document.getElementById('btn-export-transcript')?.addEventListener('click', () => {
      if (InterviewSystem.exportTranscript()) showToast('面试记录已导出', 'success');
    });

    // Assessment report
    document.getElementById('btn-assessment-report')?.addEventListener('click', showAssessmentReport);

    window.addEventListener('langchange', () => InterviewSystem.renderChat());
  }

  function sendInterviewAnswer(input) {
    if (!input?.value?.trim()) return;
    if (!InterviewSystem.isInterviewActive()) {
      showToast('请先开始面试', 'warning');
      return;
    }
    const text = input.value.trim();
    input.value = '';
    InterviewSystem.submitAnswer(text);
    setTimeout(() => LiquidMetal.resize(), 200);
  }

  function updateInterviewUI() {
    const startBtn = document.getElementById('btn-start-interview');
    const stopBtn = document.getElementById('btn-stop-interview');
    const inputArea = document.getElementById('interview-input-area');
    if (state.interviewStarted) {
      startBtn?.classList.add('hidden');
      stopBtn?.classList.remove('hidden');
      inputArea?.classList.remove('hidden');
    } else {
      startBtn?.classList.remove('hidden');
      stopBtn?.classList.add('hidden');
      inputArea?.classList.add('hidden');
    }
  }

  function showAssessmentReport() {
    const report = InterviewSystem.generateAssessmentReport();
    const container = document.getElementById('assessment-report-container');
    if (!container) return;
    const lang = I18N.getLang();

    container.innerHTML = `
      <div class="assessment-report">
        <h3>📊 ${lang === 'zh' ? '结构化评估报告' : 'Structured Assessment Report'}</h3>
        ${report.scores.map(s => `
          <div class="score-row">
            <span style="font-weight:600;">${s.dimension}</span>
            <div class="score-stars">${'<span class="score-star filled"></span>'.repeat(s.score)}${'<span class="score-star"></span>'.repeat(5 - s.score)}</div>
            <span style="font-size:0.78rem;color:var(--text-tertiary);">${s.score}/5</span>
          </div>
          <div style="font-size:0.72rem;color:var(--text-tertiary);padding:2px 0 8px;">${s.basis}</div>
        `).join('')}
        <div class="report-section">
          <h4>✅ ${lang === 'zh' ? '核心亮点' : 'Key Highlights'}</h4>
          ${report.highlights.map(h => `<span class="report-tag good">${h}</span>`).join('')}
        </div>
        <div class="report-section">
          <h4>⚠️ ${lang === 'zh' ? '主要风险点' : 'Key Risks'}</h4>
          ${report.risks.map(r => `<span class="report-tag risk">${r}</span>`).join('')}
        </div>
        <div class="report-section">
          <h4>📝 ${lang === 'zh' ? '综合评语' : 'Summary'}</h4>
          <p style="font-size:0.84rem;color:var(--text-secondary);line-height:1.7;">${report.summary}</p>
        </div>
        <div class="report-recommendation ${report.recommendation.includes('下一轮') || report.recommendation.includes('Advance') ? 'advance' : 'hold'}">
          ${lang === 'zh' ? '建议：' : 'Recommendation: '}${report.recommendation}
        </div>
      </div>`;
    container.scrollIntoView({ behavior: 'smooth' });
  }

  // === Preview Controls ===
  function bindPreviewControls() {
    document.querySelectorAll('.preview-toggle button').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.preview-toggle button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const view = btn.getAttribute('data-view');
        document.getElementById('preview-desktop')?.classList.toggle('hidden', view === 'mobile');
        document.getElementById('preview-mobile')?.classList.toggle('hidden', view === 'desktop');
      });
    });
  }

  // === Drag Events ===
  function bindDragEvents() {
    document.querySelectorAll('.device-mockup').forEach(device => {
      let dragging = false, sx, sy, sl, st;
      device.addEventListener('mousedown', (e) => {
        if (e.target.closest('.device-body')) return;
        dragging = true; sx = e.clientX; sy = e.clientY;
        const rect = device.getBoundingClientRect();
        sl = rect.left; st = rect.top;
        device.style.transition = 'none';
        e.preventDefault();
      });
      document.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        device.style.left = (sl + e.clientX - sx) + 'px';
        device.style.top = (st + e.clientY - sy) + 'px';
      });
      document.addEventListener('mouseup', () => { if (dragging) { dragging = false; device.style.transition = ''; } });
    });
  }

  // === Keyboard Shortcuts ===
  function bindKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'g') { e.preventDefault(); handleGenerateResume(); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'e') { e.preventDefault(); handleExport('pdf'); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'l') { e.preventDefault(); I18N.toggleLang(); }
    });
  }

  // === Toast ===
  function showToast(msg, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) { container = document.createElement('div'); container.className = 'toast-container'; document.body.appendChild(container); }
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transform = 'translateX(20px)'; toast.style.transition = 'all 0.3s ease-out'; setTimeout(() => toast.remove(), 300); }, 3000);
  }

  // === Loading ===
  function showLoading(msg = '') {
    const overlay = document.getElementById('loading-overlay');
    const text = document.getElementById('loading-text');
    if (text) text.textContent = msg;
    if (overlay) overlay.classList.add('visible');
  }
  function hideLoading() {
    document.getElementById('loading-overlay')?.classList.remove('visible');
  }

  // === Hallucination Alert (幻觉拦截弹窗) ===
  function showHallucinationAlert(resumeData) {
    const lang = I18N.getLang();
    const issues = resumeData._validation?.issues || [];
    const blockIssues = issues.filter(i => i.severity === 'block');

    // Build alert HTML
    const overlay = document.createElement('div');
    overlay.className = 'hallucination-alert-overlay';
    overlay.innerHTML = `
      <div class="hallucination-alert">
        <div class="alert-icon">🚫</div>
        <div class="alert-title">${lang === 'zh' ? '检测到虚构内容 · 生成已拦截' : 'Fabricated Content Detected · Blocked'}</div>
        <div class="alert-desc">${lang === 'zh'
          ? 'AI尝试生成原始素材中不存在的信息。请提供真实数据后重试。'
          : 'AI attempted to generate information not found in source materials. Please provide real data.'}</div>
        <div class="alert-issues">
          ${blockIssues.map(i => `
            <div class="alert-issue-item">
              <span>⚠️</span>
              <div>
                <div style="font-weight:600;margin-bottom:2px;">${i.claim}</div>
                <div style="font-size:0.74rem;color:var(--text-tertiary);">${i.suggestion}</div>
              </div>
            </div>
          `).join('')}
        </div>
        <div class="alert-actions">
          <button class="btn btn-cta" id="btn-hallucination-fix">${lang === 'zh' ? '前往补充真实信息' : 'Add Real Information'}</button>
          <button class="btn btn-ghost" id="btn-hallucination-dismiss">${lang === 'zh' ? '知道了' : 'Dismiss'}</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    requestAnimationFrame(() => overlay.classList.add('visible'));

    overlay.querySelector('#btn-hallucination-dismiss').addEventListener('click', () => {
      overlay.classList.remove('visible');
      setTimeout(() => overlay.remove(), 300);
    });
    overlay.querySelector('#btn-hallucination-fix').addEventListener('click', () => {
      overlay.classList.remove('visible');
      setTimeout(() => overlay.remove(), 300);
      // Scroll to personal info / questionnaire area
      document.getElementById('section-resume')?.scrollIntoView({ behavior: 'smooth' });
      // Open questionnaire
      if (state.currentQuestions.length === 0) generateQuestionnaire();
    });
    // Click outside to dismiss
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 300);
      }
    });
  }

  // === Validation Warning Banner ===
  function showValidationBanner(validation) {
    const lang = I18N.getLang();
    const previewArea = document.getElementById('preview-area');
    if (!previewArea) return;

    // Remove existing banner
    const existingBanner = document.querySelector('.validation-banner');
    if (existingBanner) existingBanner.remove();

    const banner = document.createElement('div');
    banner.className = 'validation-banner warning';
    banner.innerHTML = `
      <span>⚠️</span>
      <span>${validation.summary || (lang === 'zh' ? '部分内容可能与原始素材不完全匹配' : 'Some content may not fully match source materials')}</span>
      <button class="btn btn-sm btn-ghost" style="margin-left:auto;font-size:0.72rem;padding:4px 10px;">
        ${lang === 'zh' ? '查看详情' : 'Details'}
      </button>`;
    previewArea.parentNode.insertBefore(banner, previewArea);

    banner.querySelector('button').addEventListener('click', () => {
      showToast(validation.summary || '', 'warning');
    });
  }

  // === Import extracted data into MaterialStore ===
  function importToMaterialStore(parsedResult, fileType) {
    if (!window.MaterialStore || !parsedResult?.fullText) return;

    // Parse the extracted text into structured data
    const structuredData = FileParser.extractStructuredData(parsedResult.fullText, fileType);

    // Import into MaterialStore
    let importResult;
    if (fileType === 'jd') {
      importResult = MaterialStore.importJDParsedData(structuredData, parsedResult.fileName);
      // Also set JD keywords from parsed data
      state.jdKeywords = structuredData.keywords;
      state.jdText = parsedResult.fullText;
      renderJDTags();
      generateQuestionnaire();
    } else {
      importResult = MaterialStore.importParsedData(structuredData, parsedResult.fileName);
      // Also update form fields with parsed data
      if (structuredData.name) state.formData.name = structuredData.name;
      if (structuredData.phone) state.formData.phone = structuredData.phone;
      if (structuredData.email) state.formData.email = structuredData.email;
      if (structuredData.city) state.formData.city = structuredData.city;
      if (structuredData.targetJob) state.formData.jobTitle = structuredData.targetJob;
      if (structuredData.salary) state.formData.salary = structuredData.salary;
      showExtractedFields(state.formData);
    }

    console.log(`[MaterialStore] Imported from ${parsedResult.fileName}:`, importResult);
    return importResult;
  }

  // === Debug: Log last API prompt+response to console ===
  function debugLastCall() {
    const log = window.__lastDebugLog;
    if (!log) {
      console.log('⚠️ 暂无API调用记录。请先执行一次DeepSeek API操作。');
      return null;
    }
    console.log(`⏱ 调用时间: ${new Date(log.timestamp).toLocaleTimeString()}`);
    console.log(`📊 Prompt层数: ${log.prompt.length}`);
    log.prompt.forEach((p, i) => {
      console.log(`  Layer ${p.layer || '?'} [${p.role}]: ${p.content?.length || 0} chars`);
    });
    console.log(`📤 响应长度: ${log.response?.length || 0} chars`);
    console.log('💡 完整日志已输出到控制台，搜索"DEBUG: Full API Prompt"查看');
    return log;
  }

  // Expose debug globally
  window.debugDeepSeekCall = debugLastCall;

  return { init, getState: () => state, showToast, showLoading, hideLoading, updatePreview, importToMaterialStore, debugLastCall };
})();

document.addEventListener('DOMContentLoaded', () => App.init());
window.App = App;
