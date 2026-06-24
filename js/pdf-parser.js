/* ============================================================
   pdf-parser.js v1 — PDF/文档解析增强模块

   三级降级: Backend MinerU → Backend Unstructured → pdf.js 增强

   特性:
   - 电子PDF/扫描件自动分流
   - 布局分层、分章节切割（教育/工作/项目/JD职责）
   - 过滤水印、页眉页脚、装饰无关文字
   - 生成分块带索引只读素材库
   - Word文档通过后端 Unstructured 解析
   ============================================================ */

const PDFParser = (() => {
  // === Section classification patterns ===
  const SECTION_PATTERNS = {
    education: /\b(教育经历|教育背景|学历背景|教育|学历|学习经历|Education|EDUCATION)\b/i,
    work: /\b(工作经历|工作经验|实习经历|工作履历|职业经历|从业经历|Work Experience|WORK EXPERIENCE|Employment)\b/i,
    project: /\b(项目经历|项目经验|项目|主要项目|Projects|PROJECTS|Project Experience)\b/i,
    skills: /\b(技能|专业技能|技术栈|技能证书|Skills|SKILLS|Technical Skills)\b/i,
    certificate: /\b(证书|资格证书|证书资质|Certificates|CERTIFICATES|Certifications)\b/i,
    selfIntro: /\b(自我评价|自我介绍|个人评价|自我描述|个人简介|Self-Assessment|Summary|Profile|About Me)\b/i,
    basicInfo: /\b(基本信息|个人信息|个人资料|联系方式|Basic Info|Personal Info)\b/i,
    jobIntent: /\b(求职意向|期望岗位|期望职位|目标岗位|Target|Objective|Career Objective)\b/i,
    jdResponsibilities: /\b(岗位职责|工作职责|主要职责|Responsibilities|Duties|Job Description)\b/i,
    jdRequirements: /\b(任职要求|岗位要求|技能要求|职位要求|Requirements|Qualifications|Skills Required)\b/i,
  };

  // === Watermark / header-footer patterns to filter ===
  const NOISE_PATTERNS = [
    /^[\s\d]+$/,                          // Pure whitespace/digits
    /^(?:第\s*\d+\s*页|Page\s*\d+)/i,     // Page numbers
    /^(?:机密|Confidential|内部资料)/i,     // Confidentiality marks
    /^\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}$/, // Bare dates
    /^[\/\-_=]{3,}$/,                      // Separator lines
    /^(?:扫描全能王|CamScanner|Adobe|WPS)/i, // Scanner app watermarks
  ];

  // === Main API: Parse document ===
  /**
   * @param {File} file - PDF/DOCX/DOC file
   * @param {Object} options
   * @param {string} options.lang - 'zh' | 'en'
   * @param {Function} options.onProgress - ({stage, progress}) => void
   * @param {boolean} options.preferLocal - Skip backend
   * @returns {Promise<{success, markdown, sections, rawText, method, structured}>}
   */
  async function parse(file, options = {}) {
    const { lang = 'zh', onProgress = () => {}, preferLocal = false } = options;
    const ext = getExt(file.name);

    // === Level 1: Backend API (MinerU for PDF, Unstructured for DOCX) ===
    if (!preferLocal && window.BackendAPI && window.BackendAPI.isBackendAvailable()) {
      onProgress({ stage: 'backend', progress: 0 });
      try {
        const result = await BackendAPI.parseFile(file, { lang, fallback: false });
        if (result.success && result.markdown) {
          onProgress({ stage: 'classify', progress: 80 });

          // 后处理: 分章节 + 过滤噪音
          const sections = classifySections(result.markdown);
          const cleaned = filterNoise(result.markdown);

          onProgress({ stage: 'done', progress: 100 });
          return {
            success: true,
            markdown: cleaned,
            sections,
            rawText: result.raw_text || cleaned,
            method: result.method || 'backend',
            pageCount: result.layout?.page_count || 1,
          };
        }
      } catch (e) {
        console.warn('[PDFParser] Backend parse failed:', e.message);
        onProgress({ stage: 'backend_failed', progress: 0 });
      }
    }

    // === Level 2: Browser local parsing ===
    return await parseLocal(file, options);
  }

  /** 浏览器本地解析（pdf.js增强） */
  async function parseLocal(file, options = {}) {
    const { lang = 'zh', onProgress = () => {} } = options;
    const ext = getExt(file.name);

    onProgress({ stage: 'local', progress: 0 });

    if (ext === 'pdf') {
      return await parsePDFLocal(file, { lang, onProgress });
    }
    if (ext === 'docx' || ext === 'doc') {
      return await parseDOCXLocal(file, { lang, onProgress });
    }
    if (ext === 'txt') {
      const text = await file.text();
      return buildResult(text, 'plain_text');
    }

    return { success: false, error: `不支持的文件格式: .${ext}` };
  }

  /** pdf.js 增强 PDF 解析 */
  async function parsePDFLocal(file, options = {}) {
    const { onProgress = () => {} } = options;

    if (typeof pdfjsLib === 'undefined') {
      return { success: false, error: 'PDF.js 未加载' };
    }

    try {
      onProgress({ stage: 'pdfjs', progress: 10 });
      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;

      const totalPages = pdf.numPages;
      const pages = [];
      let isScanned = true;  // 检测是否为扫描件

      for (let i = 1; i <= totalPages; i++) {
        onProgress({ stage: 'pdfjs', progress: 10 + Math.round((i / totalPages) * 70) });

        const page = await pdf.getPage(i);
        const textContent = await page.getTextContent();

        // 按 y, x 坐标排序文本项（版面感知）
        const items = textContent.items.map(item => ({
          text: item.str,
          x: item.transform[4],
          y: item.transform[5],
          width: item.width,
          height: item.height,
        }));

        // 按 y 坐标分组（行）
        const tolerance = 5;
        const lines = [];
        let currentLine = [];
        let currentY = null;

        const sorted = [...items].sort((a, b) => b.y - a.y || a.x - b.x);

        for (const item of sorted) {
          if (item.text.trim().length > 0) isScanned = false;  // 有可读文字 = 电子PDF

          if (currentY === null) {
            currentY = item.y;
            currentLine = [item];
          } else if (Math.abs(item.y - currentY) < tolerance) {
            currentLine.push(item);
          } else {
            if (currentLine.length > 0) {
              currentLine.sort((a, b) => a.x - b.x);
              lines.push(currentLine.map(it => it.text).join(' '));
            }
            currentY = item.y;
            currentLine = [item];
          }
        }
        if (currentLine.length > 0) {
          currentLine.sort((a, b) => a.x - b.x);
          lines.push(currentLine.map(it => it.text).join(' '));
        }

        pages.push({
          pageNum: i,
          text: lines.join('\n'),
          isScanned: false,
          lineCount: lines.length,
        });
      }

      onProgress({ stage: 'classify', progress: 85 });

      // 合并所有页面
      const fullText = pages.map(p =>
        `--- 第 ${p.pageNum} 页 ---\n${p.text}`
      ).join('\n\n');

      // 过滤噪音
      const cleaned = filterNoise(fullText);

      // 分章节
      const sections = classifySections(cleaned);

      onProgress({ stage: 'done', progress: 100 });

      return {
        success: true,
        markdown: cleaned,
        sections,
        rawText: fullText,
        method: isScanned ? 'pdfjs-scanned' : 'pdfjs',
        pageCount: totalPages,
        isScanned,
        pages,
      };
    } catch (e) {
      console.error('[PDFParser] pdf.js error:', e);
      return { success: false, error: `PDF解析失败: ${e.message}` };
    }
  }

  /** DOCX 本地解析（改进版） */
  async function parseDOCXLocal(file, options = {}) {
    const { onProgress = () => {} } = options;

    try {
      onProgress({ stage: 'docx', progress: 30 });
      const text = await file.text();

      // 提取 <w:t> XML 标签
      const tRegex = /<w:t[^>]*>(.*?)<\/w:t>/g;
      const tTexts = [];
      let match;
      while ((match = tRegex.exec(text)) !== null) {
        tTexts.push(match[1]);
      }

      // 检测段落分割
      const pRegex = /<\/w:p>/g;
      const paragraphs = [];
      let lastIdx = 0;
      let tIdx = 0;
      while ((match = pRegex.exec(text)) !== null) {
        const segTexts = [];
        while (tIdx < tTexts.length) {
          segTexts.push(tTexts[tIdx]);
          tIdx++;
          // 粗略估算
          if (tIdx >= tTexts.length) break;
        }
        if (segTexts.length > 0) {
          paragraphs.push(segTexts.join(''));
        }
      }

      const fullText = paragraphs.length > 0
        ? paragraphs.join('\n')
        : tTexts.join('');

      onProgress({ stage: 'classify', progress: 80 });
      const cleaned = filterNoise(fullText);
      const sections = classifySections(cleaned);

      onProgress({ stage: 'done', progress: 100 });

      return {
        success: true,
        markdown: cleaned,
        sections,
        rawText: fullText,
        method: 'docx_xml',
        pageCount: 1,
      };
    } catch (e) {
      return { success: false, error: `DOCX解析失败: ${e.message}` };
    }
  }

  // === 分章节分类 ===
  function classifySections(text) {
    const lines = text.split('\n');
    const sections = {};
    let currentSection = 'header';

    for (const line of lines) {
      const stripped = line.trim();
      if (!stripped) continue;

      // 检测章节标题
      let matched = false;
      for (const [secName, pattern] of Object.entries(SECTION_PATTERNS)) {
        if (pattern.test(stripped) && stripped.length < 30) {
          currentSection = secName;
          if (!sections[currentSection]) {
            sections[currentSection] = { title: stripped, content: [] };
          }
          matched = true;
          break;
        }
      }

      if (!matched) {
        if (!sections[currentSection]) {
          sections[currentSection] = { title: '', content: [] };
        }
        sections[currentSection].content.push(stripped);
      }
    }

    return sections;
  }

  // === 过滤噪音（水印、页眉页脚等） ===
  function filterNoise(text) {
    const lines = text.split('\n');
    const filtered = [];

    for (const line of lines) {
      const stripped = line.trim();
      if (!stripped) {
        filtered.push('');
        continue;
      }

      // 检查是否为噪音
      let isNoise = false;
      for (const pattern of NOISE_PATTERNS) {
        if (pattern.test(stripped)) {
          isNoise = true;
          break;
        }
      }

      if (!isNoise) {
        filtered.push(stripped);
      }
    }

    return filtered.join('\n').replace(/\n{3,}/g, '\n\n');
  }

  // === 格式化带行号索引的文本（喂给 DeepSeek 抽取） ===
  function toIndexedText(text) {
    const lines = text.split('\n').filter(l => l.trim());
    return lines.map((line, i) => `[${i}] ${line}`).join('\n');
  }

  // === Utility ===
  function getExt(name) {
    const parts = name.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
  }

  function buildResult(text, method) {
    const cleaned = filterNoise(text);
    return {
      success: true,
      markdown: cleaned,
      sections: classifySections(cleaned),
      rawText: text,
      method,
      pageCount: 1,
    };
  }

  // === Public API ===
  return {
    parse,
    parseLocal,
    classifySections,
    filterNoise,
    toIndexedText,
  };
})();

window.PDFParser = PDFParser;
