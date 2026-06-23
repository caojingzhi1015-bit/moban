/* ============================================================
   deepseek-file-parser.js — DeepSeek-VL 多模态文件解析
   使用 DeepSeek-VL 原生完成 OCR/图文解析
   替代 Tesseract.js + PDF.js 的第三方OCR/PDF解析逻辑
   ============================================================ */

const DeepSeekFileParser = (() => {
  // === Parse Image via DeepSeek-VL (OCR) ===
  async function parseImageViaVL(file, options = {}) {
    const dataURL = await fileToDataURL(file);
    const lang = options.lang || 'zh';

    const prompt = lang === 'zh'
      ? `你是一个精准的OCR识别工具。请严格识别并提取图片中的所有文字内容，保持原文格式和结构。

识别规则：
1. 逐字逐行识别，不遗漏任何文字
2. 保持原文的段落结构、标题层级
3. 如果是简历：提取姓名、联系方式、教育经历、工作经历、项目经历、技能证书、自我评价
4. 如果是JD：完整提取岗位职责、任职要求、技能要求
5. 数字、日期、百分比必须精确识别，不能近似或编造
6. 不要添加任何不属于图片原文的内容
7. 输出纯文本，使用Markdown格式保留结构`
      : `Extract ALL text from this image. Be precise with numbers, dates, and percentages. Do not add or fabricate any content not present in the image.`;

    const result = await DeepSeekAPI.visionRecognition(dataURL, prompt);

    return {
      success: result.success,
      type: 'image',
      fileName: file.name,
      fullText: result.content || '',
      method: 'deepseek-vl',
      usage: result.usage,
      error: result.error ? result.message : null,
    };
  }

  // === Parse PDF via DeepSeek-VL (send as image) ===
  async function parsePDFViaVL(file, options = {}) {
    // Convert PDF first page to image for VL processing
    // For multi-page PDFs, we'd process page-by-page
    // Simplified: convert first page as representative sample
    const dataURL = await pdfFirstPageToImage(file);

    if (!dataURL) {
      // Fallback: try reading PDF as text
      const text = await fileToText(file);
      return {
        success: true,
        type: 'pdf',
        fileName: file.name,
        fullText: extractReadableText(text),
        method: 'text-fallback',
        note: 'PDF转图片失败，使用文本提取；建议检查结果完整性',
      };
    }

    const lang = options.lang || 'zh';
    const prompt = lang === 'zh'
      ? `完整提取这份PDF文档的所有文字内容。按章节、段落还原结构。如果是JD文档，提取岗位职责和任职要求。如果是简历，提取所有个人信息、经历、技能。保持原文内容，不编造不推测。`
      : `Extract ALL text from this PDF document. Preserve structure, sections, and paragraphs. Do not fabricate or infer any content.`;

    const result = await DeepSeekAPI.visionRecognition(dataURL, prompt);

    return {
      success: result.success,
      type: 'pdf',
      fileName: file.name,
      fullText: result.content || '',
      method: 'deepseek-vl-pdf',
      usage: result.usage,
      error: result.error ? result.message : null,
    };
  }

  // === Unified File Parse (routes to VL for images, VL-pdf for PDFs) ===
  async function parseFile(file, options = {}) {
    const ext = getExt(file.name);

    // Images → DeepSeek-VL
    if (['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif'].includes(ext) || file.type.startsWith('image/')) {
      return await parseImageViaVL(file, options);
    }

    // PDF → DeepSeek-VL (as image conversion)
    if (ext === 'pdf' || file.type === 'application/pdf') {
      return await parsePDFViaVL(file, options);
    }

    // TXT → direct read (no VL needed)
    if (ext === 'txt' || file.type === 'text/plain') {
      const text = await fileToText(file);
      return {
        success: true,
        type: 'txt',
        fileName: file.name,
        fullText: text.trim(),
        method: 'direct-read',
      };
    }

    // DOCX → text extraction
    if (ext === 'docx' || file.type.includes('wordprocessingml')) {
      const text = await fileToText(file);
      const extracted = extractDOCXSimple(text);
      return {
        success: true,
        type: 'docx',
        fileName: file.name,
        fullText: extracted,
        method: 'xml-extraction',
      };
    }

    // Fallback: read as text
    const text = await fileToText(file);
    return {
      success: true,
      type: ext,
      fileName: file.name,
      fullText: text.trim(),
      method: 'text-fallback',
    };
  }

  // === Structured Extraction from Parsed Text ===
  // After VL extracts raw text, this structures it for MaterialStore
  function extractStructuredData(fullText, fileType) {
    return {
      rawText: fullText,
      name: extractField(fullText, /姓\s*名[：:]\s*([^\n]{2,10})/) || extractField(fullText, /([^\n]{2,4})\s*(?:同学|先生|女士)/),
      phone: extractField(fullText, /(?:电话|手机|联系方式|Tel|Phone)[：:\s]*([\d\-+\s]{6,18})/i),
      email: extractField(fullText, /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/),
      city: extractField(fullText, /(?:城市|所在地|Base|Location)[：:\s]*([^\n]{2,10})/i),
      targetJob: extractField(fullText, /(?:岗位|职位|应聘|求职意向|意向岗位|Target)[：:\s]*([^\n]{2,30})/i),
      salary: extractField(fullText, /(?:薪资|期望薪资|薪酬|Salary)[：:\s]*([^\n]{2,20})/i),
      education: extractSectionItems(fullText, ['教育经历', '教育背景', '学历', 'Education']),
      workExperience: extractSectionItems(fullText, ['工作经历', '工作经验', '实习经历', 'Work Experience', 'Employment']),
      projects: extractSectionItems(fullText, ['项目经历', '项目经验', 'Projects']),
      skills: extractListSection(fullText, ['技能', '证书', '技术栈', '专业技能', 'Skills', 'Technologies']),
      selfIntro: extractSection(fullText, ['自我评价', '自我介绍', '个人简介', '个人评价', 'Summary', 'About Me', 'Profile']),
      keywords: fileType === 'jd' ? extractJDKeywords(fullText) : null,
    };
  }

  // === Helper Functions ===
  function getExt(name) {
    const parts = name.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
  }

  function fileToDataURL(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = e => resolve(e.target.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function fileToText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = e => resolve(e.target.result);
      reader.onerror = reject;
      reader.readAsText(file, 'UTF-8');
    });
  }

  // Convert PDF first page to image using canvas
  // (uses PDF.js if available, otherwise returns null)
  async function pdfFirstPageToImage(file) {
    try {
      if (typeof window.pdfjsLib === 'undefined') return null;

      const arrayBuffer = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = e => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsArrayBuffer(file);
      });

      const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
      const page = await pdf.getPage(1);
      const viewport = page.getViewport({ scale: 1.5 });

      const canvas = document.createElement('canvas');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const ctx = canvas.getContext('2d');

      await page.render({ canvasContext: ctx, viewport }).promise;
      return canvas.toDataURL('image/png');
    } catch (e) {
      console.warn('[DeepSeekFileParser] PDF-to-image failed:', e.message);
      return null;
    }
  }

  function extractReadableText(raw) {
    return raw.replace(/[^\x20-\x7E一-鿿　-〿＀-￯\n\r\t]/g, ' ').replace(/\s{3,}/g, '\n').trim();
  }

  function extractDOCXSimple(text) {
    const tMatches = text.match(/<w:t[^>]*>([^<]*)<\/w:t>/g);
    if (tMatches) return tMatches.map(t => t.replace(/<w:t[^>]*>/, '').replace(/<\/w:t>/, '')).join('');
    return text.replace(/<[^>]+>/g, ' ').replace(/\s{3,}/g, '\n').trim();
  }

  function extractField(text, pattern) {
    const m = text.match(pattern);
    return m ? m[1]?.trim() || m[0]?.trim() : null;
  }

  function extractSection(text, labels) {
    for (const label of labels) {
      const patterns = [
        new RegExp(`${label}[：:\\s]*\\n([\\s\\S]*?)(?=\\n(?:${labels.join('|')})[：:]|\\n\\n\\n|$)`, 'i'),
        new RegExp(`【${label}】[：:\\s]*([\\s\\S]*?)(?=【|$)`, 'i'),
      ];
      for (const p of patterns) {
        const m = text.match(p);
        if (m?.[1]?.trim()?.length > 3) return m[1].trim();
      }
    }
    return null;
  }

  function extractSectionItems(text, labels) {
    const section = extractSection(text, labels);
    if (!section) return [];
    return section.split(/\n\s*\n/).filter(e => e.trim().length > 5).map(e => ({ raw: e.trim() }));
  }

  function extractListSection(text, labels) {
    const section = extractSection(text, labels);
    if (!section) return [];
    return section.split(/[,，、\n]/).map(s => s.trim()).filter(Boolean);
  }

  function extractJDKeywords(text) {
    const patterns = [
      /python/i, /java\b/i, /javascript/i, /typescript/i, /react/i, /vue/i, /angular/i,
      /node\.?js/i, /golang/i, /rust/i, /sql/i, /mysql/i, /docker/i, /kubernetes/i, /aws/i,
      /tensorflow/i, /pytorch/i, /llm/i, /nlp/i, /excel/i, /tableau/i,
      /短视频/i, /抖音/i, /小红书/i, /微信/i, /seo/i, /sem/i, /直播/i,
      /项目管理/i, /敏捷/i, /scrum/i,
    ];
    const hardSkills = patterns.filter(p => p.test(text)).map(p => {
      const m = text.match(p);
      return m ? m[0] : '';
    }).filter(Boolean);
    return { hardSkills: [...new Set(hardSkills)], softSkills: [], industry: [] };
  }

  return {
    parseFile,
    parseImageViaVL,
    parsePDFViaVL,
    extractStructuredData,
  };
})();

window.DeepSeekFileParser = DeepSeekFileParser;
