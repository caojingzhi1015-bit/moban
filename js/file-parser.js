/* ============================================================
   file-parser.js — 统一文件解析引擎
   集成 PDF.js (PDF文本提取) + Tesseract.js (OCR图片识别)
   输出结构化文本，供MaterialStore和FactChecker使用
   ============================================================ */

const FileParser = (() => {
  // === Config ===
  let pdfjsLib = null;
  let Tesseract = null;
  let initialized = false;

  function init() {
    if (initialized) return true;
    try {
      if (typeof window.pdfjsLib !== 'undefined') {
        pdfjsLib = window.pdfjsLib;
        // Set worker path
        if (pdfjsLib.GlobalWorkerOptions) {
          pdfjsLib.GlobalWorkerOptions.workerSrc =
            'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        }
      }
      if (typeof window.Tesseract !== 'undefined') {
        Tesseract = window.Tesseract;
      }
      initialized = true;
      return true;
    } catch (e) {
      console.warn('[FileParser] Library init failed:', e.message);
      return false;
    }
  }

  // === Main entry: parse any file type ===
  async function parseFile(file, options = {}) {
    init();

    const ext = getExt(file.name);
    const fileType = file.type;

    // Route to correct parser
    if (ext === 'pdf' || fileType === 'application/pdf') {
      return await parsePDF(file, options);
    }
    if (['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif'].includes(ext) ||
        fileType.startsWith('image/')) {
      return await parseImage(file, options);
    }
    if (ext === 'txt' || fileType === 'text/plain') {
      return await parseTXT(file);
    }
    if (ext === 'docx' || fileType.includes('wordprocessingml')) {
      return await parseDOCX(file);
    }
    if (ext === 'doc' || fileType === 'application/msword') {
      return await parseDOC(file);
    }

    // Fallback: try reading as text
    return await parseTXT(file);
  }

  // === PDF Parsing (uses PDF.js) ===
  async function parsePDF(file, options = {}) {
    if (!pdfjsLib) {
      // Fallback to basic text extraction
      return await parsePDFFallback(file);
    }

    return new Promise(async (resolve) => {
      try {
        const arrayBuffer = await readFileAsArrayBuffer(file);
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;

        let fullText = '';
        const pages = [];
        const structuredData = {
          sections: [],  // Chapter-structured text
          rawLines: [],
          metadata: {},
        };

        // Extract each page
        for (let i = 1; i <= pdf.numPages; i++) {
          const page = await pdf.getPage(i);
          const textContent = await page.getTextContent();

          // Group text items by their Y position (lines)
          const lines = groupTextByLines(textContent.items);
          const pageText = lines.join('\n');
          fullText += pageText + '\n\n';
          pages.push({ pageNum: i, text: pageText, lines });
        }

        // Try to identify sections/chapters
        structuredData.sections = identifySections(fullText);
        structuredData.rawLines = fullText.split('\n').filter(l => l.trim());
        structuredData.metadata = {
          pageCount: pdf.numPages,
          fileName: file.name,
          totalChars: fullText.length,
        };

        resolve({
          success: true,
          type: 'pdf',
          fileName: file.name,
          fullText: fullText.trim(),
          pages,
          structured: structuredData,
          method: 'pdf.js',
        });
      } catch (err) {
        console.warn('[FileParser] PDF.js failed, using fallback:', err.message);
        const fallbackResult = await parsePDFFallback(file);
        resolve(fallbackResult);
      }
    });
  }

  // Fallback PDF parser (when PDF.js unavailable)
  async function parsePDFFallback(file) {
    const text = await readFileAsText(file);
    let extracted = '';

    // Extract text from BT/ET blocks
    const btBlocks = text.match(/BT[\s\S]*?ET/g);
    if (btBlocks) {
      btBlocks.forEach(block => {
        // Tj operator: (text) Tj
        const tjMatches = block.match(/\(([^)]*)\)\s*Tj/g);
        if (tjMatches) {
          tjMatches.forEach(tj => {
            const m = tj.match(/\(([^)]*)\)/);
            if (m) extracted += decodePDFString(m[1]) + ' ';
          });
        }
        // TJ array: [(text) num (text)] TJ
        const tjArrays = block.match(/\[([^\]]*)\]\s*TJ/g);
        if (tjArrays) {
          tjArrays.forEach(arr => {
            const texts = arr.match(/\(([^)]*)\)/g);
            if (texts) texts.forEach(t => extracted += decodePDFString(t.replace(/[()]/g, '')) + ' ');
          });
        }
      });
    }

    // Fallback: clean raw text
    if (!extracted.trim()) {
      extracted = text.replace(/[^\x20-\x7E一-鿿　-〿＀-￯\n\r\t]/g, ' ')
        .replace(/\s{3,}/g, '\n').trim();
    }

    return {
      success: true,
      type: 'pdf',
      fileName: file.name,
      fullText: extracted.trim() || text.trim(),
      method: 'fallback',
      note: 'PDF.js不可用，使用基础文本提取；建议检查提取结果准确性',
    };
  }

  // === Image OCR (uses Tesseract.js) ===
  async function parseImage(file, options = {}) {
    const lang = options.lang || 'chi_sim+eng'; // Chinese Simplified + English

    if (!Tesseract) {
      return {
        success: false,
        type: 'image',
        fileName: file.name,
        fullText: '',
        error: 'Tesseract.js 未加载，无法进行OCR识别。请检查网络连接后刷新页面。',
        method: 'none',
      };
    }

    return new Promise(async (resolve) => {
      try {
        const imageUrl = await readFileAsDataURL(file);

        // Show progress callback if provided
        const progressCb = options.onProgress || (() => {});

        const result = await Tesseract.recognize(imageUrl, lang, {
          logger: (m) => {
            if (m.status === 'recognizing text') {
              progressCb({
                status: 'ocr_progress',
                progress: Math.round(m.progress * 100),
                text: m.status,
              });
            }
          },
        });

        resolve({
          success: true,
          type: 'image',
          fileName: file.name,
          fullText: result.data.text.trim(),
          confidence: result.data.confidence,
          words: result.data.words,
          method: 'tesseract.js',
          lang: lang,
        });
      } catch (err) {
        resolve({
          success: false,
          type: 'image',
          fileName: file.name,
          fullText: '',
          error: `OCR识别失败: ${err.message}`,
          method: 'tesseract_error',
        });
      }
    });
  }

  // === TXT Parser ===
  async function parseTXT(file) {
    const text = await readFileAsText(file);
    return {
      success: true,
      type: 'txt',
      fileName: file.name,
      fullText: text.trim(),
      method: 'direct_read',
    };
  }

  // === DOCX Parser (ZIP-based, reads document.xml) ===
  async function parseDOCX(file) {
    return new Promise(async (resolve) => {
      try {
        const text = await readFileAsText(file);

        // Extract text from w:t tags in document.xml
        const tMatches = text.match(/<w:t[^>]*>([^<]*)<\/w:t>/g);
        let extracted = '';
        if (tMatches) {
          extracted = tMatches
            .map(t => t.replace(/<w:t[^>]*>/, '').replace(/<\/w:t>/, ''))
            .join('');
        }

        // Try to identify paragraph boundaries
        const pMatches = text.match(/<w:p[ >][\s\S]*?<\/w:p>/g);
        if (pMatches) {
          extracted = pMatches.map(p => {
            const tms = p.match(/<w:t[^>]*>([^<]*)<\/w:t>/g);
            return tms ? tms.map(t => t.replace(/<w:t[^>]*>/, '').replace(/<\/w:t>/, '')).join('') : '';
          }).filter(l => l.trim()).join('\n');
        }

        if (!extracted.trim()) {
          // Fallback: strip XML
          extracted = text.replace(/<[^>]+>/g, ' ')
            .replace(/&amp;/g, '&').replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>').replace(/&quot;/g, '"')
            .replace(/\s{3,}/g, '\n').trim();
        }

        resolve({
          success: true,
          type: 'docx',
          fileName: file.name,
          fullText: extracted.trim(),
          method: 'xml_extraction',
        });
      } catch (err) {
        resolve({
          success: false,
          type: 'docx',
          fileName: file.name,
          fullText: '',
          error: `DOCX解析失败: ${err.message}`,
        });
      }
    });
  }

  // === DOC Parser (old format, best effort) ===
  async function parseDOC(file) {
    const text = await readFileAsText(file);
    // Strip non-printable, try to extract readable text
    const cleaned = text
      .replace(/[^\x20-\x7E一-鿿　-〿＀-￯\n\r\t]/g, ' ')
      .replace(/\s{3,}/g, '\n')
      .trim();

    return {
      success: true,
      type: 'doc',
      fileName: file.name,
      fullText: cleaned,
      method: 'text_extraction',
      note: '旧版DOC格式，文本提取可能不完整，建议检查结果',
    };
  }

  // === Bulk parse (multiple files) ===
  async function parseFiles(files, options = {}) {
    const results = [];
    for (const file of files) {
      const result = await parseFile(file, options);
      results.push(result);
    }
    return results;
  }

  // === Structured Data Extraction from Parsed Text ===
  // After parsing, this extracts structured fields for MaterialStore
  function extractStructuredData(fullText, type) {
    const data = { rawText: fullText };

    if (type === 'jd') {
      // Extract JD-specific structure
      data.keywords = extractJDKeywords(fullText);
      data.requirements = extractJDRequirements(fullText);
    } else {
      // Extract resume-specific structure
      data.name = extractField(fullText, /姓\s*名[：:]\s*([^\n]{2,10})/);
      data.phone = extractField(fullText, /(?:电话|手机|联系方式)[：:]\s*(\d[\d\-+\s]{6,15})/);
      data.email = extractField(fullText, /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
      data.city = extractField(fullText, /(?:城市|所在地|base)[：:]\s*([^\n]{2,10})/);
      data.targetJob = extractField(fullText, /(?:岗位|职位|应聘|求职意向)[：:]\s*([^\n]{2,30})/);
      data.salary = extractField(fullText, /(?:薪资|期望薪资|薪酬)[：:]\s*([^\n]{2,20})/);

      // Education
      data.education = extractSectionItems(fullText, ['教育经历', '教育背景', '学历', 'Education'], [
        { key: 'school', pattern: /([一-鿿]+大学|[一-鿿]+学院|[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\sUniversity)/ },
        { key: 'major', pattern: /专业[：:]\s*([^\n,，]+)/ },
        { key: 'degree', pattern: /(本科|硕士|博士|大专|MBA|学士|硕士|博士)/ },
        { key: 'period', pattern: /(\d{4}[.\-/年]\d{1,2}\s*[-–—至到]\s*(?:\d{4}[.\-/年]\d{1,2}|至今|现在|present))/ },
      ]);

      // Work experience
      data.workExperience = extractSectionItems(fullText, ['工作经历', '工作经验', '实习经历', 'Work Experience'], [
        { key: 'company', pattern: /([一-鿿A-Za-z]{2,}(?:科技|集团|公司|有限|股份|技术|网络|信息))/ },
        { key: 'position', pattern: /(?:职位|岗位|担任)[：:]\s*([^\n,，]+)/ },
        { key: 'period', pattern: /(\d{4}[.\-/年]\d{1,2}\s*[-–—至到]\s*(?:\d{4}[.\-/年]\d{1,2}|至今|现在|present))/ },
      ]);

      // Projects
      data.projects = extractSectionItems(fullText, ['项目经历', '项目经验', 'Projects'], [
        { key: 'name', pattern: /项目[名称]*[：:]\s*([^\n,，]+)/ },
        { key: 'role', pattern: /(?:角色|职责|担任)[：:]\s*([^\n,，]+)/ },
      ]);

      // Skills
      const skillSection = extractSection(fullText, ['技能', '证书', '技术栈', '专业技能', 'Skills']);
      if (skillSection) {
        data.skills = skillSection.split(/[,，、\n]/).map(s => s.trim()).filter(Boolean);
      }

      // Self intro
      data.selfIntro = extractSection(fullText, ['自我评价', '自我介绍', '个人简介', 'Summary', 'About Me']);
    }

    return data;
  }

  // === Helper Functions ===

  function getExt(filename) {
    const parts = filename.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
  }

  function readFileAsText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = () => reject(new Error('File read failed'));
      reader.readAsText(file, 'UTF-8');
    });
  }

  function readFileAsArrayBuffer(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = () => reject(new Error('File read failed'));
      reader.readAsArrayBuffer(file);
    });
  }

  function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = () => reject(new Error('File read failed'));
      reader.readAsDataURL(file);
    });
  }

  function groupTextByLines(items) {
    if (!items || items.length === 0) return [];
    const sorted = [...items].sort((a, b) => b.transform[5] - a.transform[5] || a.transform[4] - b.transform[4]);
    const lines = [];
    let currentLine = [];
    let currentY = null;

    sorted.forEach(item => {
      const y = Math.round(item.transform[5]);
      if (currentY === null) currentY = y;
      if (Math.abs(y - currentY) > 5) {
        if (currentLine.length) {
          lines.push(currentLine.sort((a, b) => a.transform[4] - b.transform[4]).map(i => i.str).join(' '));
        }
        currentLine = [];
        currentY = y;
      }
      currentLine.push(item);
    });
    if (currentLine.length) {
      lines.push(currentLine.sort((a, b) => a.transform[4] - b.transform[4]).map(i => i.str).join(' '));
    }
    return lines;
  }

  function identifySections(text) {
    const sections = [];
    const sectionPatterns = [
      /(?:教育经历|教育背景|学历|Education)/,
      /(?:工作经历|工作经验|实习经历|Work\s*Experience|Employment)/,
      /(?:项目经历|项目经验|Projects?)/,
      /(?:技能|证书|技术栈|Skills?|Certifications?)/,
      /(?:自我评价|自我介绍|Summary|About\s*Me)/,
      /(?:岗位职责|工作职责|任职要求|Responsibilities|Requirements|Qualifications)/,
    ];

    const paragraphs = text.split(/\n\n+/);
    paragraphs.forEach(para => {
      for (const pattern of sectionPatterns) {
        if (pattern.test(para)) {
          sections.push({ title: para.split('\n')[0].trim(), content: para });
          break;
        }
      }
    });

    return sections;
  }

  function decodePDFString(str) {
    return str
      .replace(/\\n/g, '\n').replace(/\\r/g, '')
      .replace(/\\t/g, '\t').replace(/\\\(/g, '(')
      .replace(/\\\)/g, ')').replace(/\\\\/g, '\\')
      .replace(/\\\d{3}/g, (m) => String.fromCharCode(parseInt(m.slice(1), 8)));
  }

  function extractField(text, pattern) {
    const match = text.match(pattern);
    return match ? match[1].trim() : null;
  }

  function extractSection(text, labels) {
    for (const label of labels) {
      const patterns = [
        new RegExp(`${label}[：:\\s]*\\n([\\s\\S]*?)(?=\\n(?:${labels.join('|')})[：:]|\\n\\n\\n|$)`, 'i'),
        new RegExp(`【${label}】[：:\\s]*([\\s\\S]*?)(?=【|$)`, 'i'),
        new RegExp(`${label}\\s*\\n([\\s\\S]*?)(?=\\n\\n[A-Z]|$)`, 'i'),
      ];
      for (const p of patterns) {
        const match = text.match(p);
        if (match && match[1] && match[1].trim().length > 5) {
          return match[1].trim();
        }
      }
    }
    return null;
  }

  function extractSectionItems(fullText, sectionLabels, fieldPatterns) {
    const sectionText = extractSection(fullText, sectionLabels);
    if (!sectionText) return [];

    // Split section into individual entries (by company/project)
    const entries = sectionText.split(/\n\s*\n/).filter(e => e.trim().length > 5);
    const result = [];

    entries.forEach(entry => {
      const item = { raw: entry.trim() };
      fieldPatterns.forEach(({ key, pattern }) => {
        const match = entry.match(pattern);
        if (match) item[key] = match[1] ? match[1].trim() : match[0].trim();
      });
      if (Object.keys(item).length > 1) result.push(item); // Has at least one extracted field
    });

    // If no entries found, return the whole section as one entry
    if (result.length === 0 && sectionText.trim()) {
      result.push({ raw: sectionText.trim() });
    }

    return result;
  }

  function extractJDKeywords(text) {
    const hardPatterns = [
      /python/i, /java\b/i, /javascript/i, /typescript/i, /react/i, /vue/i, /angular/i,
      /node\.?js/i, /golang/i, /rust/i, /c\+\+/i, /sql/i, /mysql/i, /postgresql/i,
      /mongodb/i, /redis/i, /docker/i, /kubernetes/i, /k8s/i, /aws/i, /azure/i,
      /tensorflow/i, /pytorch/i, /machine\s*learning/i, /deep\s*learning/i, /nlp/i, /llm/i,
      /excel/i, /tableau/i, /power\s*bi/i, /spark/i, /hadoop/i, /flink/i,
      /figma/i, /sketch/i, /photoshop/i, /canva/i, /premiere/i,
      /短视频/i, /抖音/i, /快手/i, /小红书/i, /b站/i, /tiktok/i, /youtube/i,
      /微信/i, /微博/i, /公众号/i, /社群/i, /私域/i, /直播/i, /带货/i,
      /seo/i, /sem/i, /信息流/i, /广告投放/i, /数据分析/i, /用户增长/i,
      /项目管理/i, /敏捷/i, /scrum/i, /jira/i,
    ];
    const softPatterns = [
      /沟通/i, /协作/i, /团队合作/i, /领导力/i, /执行力/i, /抗压/i,
      /解决问题/i, /逻辑思维/i, /创新/i, /学习能力/i, /自驱/i, /责任心/i,
      /跨部门/i, /推动/i, /影响力/i,
    ];
    const industryPatterns = [
      { p: /互联网/i, l: '互联网/IT' }, { p: /金融/i, l: '金融' },
      { p: /教育/i, l: '教育' }, { p: /医疗/i, l: '医疗健康' },
      { p: /电商/i, l: '电商/零售' }, { p: /游戏/i, l: '游戏' },
      { p: /广告/i, l: '媒体/广告' }, { p: /saas/i, l: 'SaaS/企业服务' },
      { p: /ai|人工智能|大模型/i, l: 'AI/人工智能' },
    ];

    return {
      hardSkills: [...new Set(hardPatterns.filter(p => p.test(text)).map(p => {
        const m = text.match(p); return m ? m[0] : '';
      }).filter(Boolean))],
      softSkills: [...new Set(softPatterns.filter(p => p.test(text)).map(p => {
        const m = text.match(p); return m ? m[0] : '';
      }).filter(Boolean))],
      industry: [...new Set(industryPatterns.filter(({p}) => p.test(text)).map(({l}) => l))],
    };
  }

  function extractJDRequirements(text) {
    const reqs = [];
    // Look for bullet points / numbered requirements
    const bulletPattern = /(?:[•\-\*\d+\.、]\s*|\d+[\.、])\s*([^\n]{10,200})/g;
    let match;
    while ((match = bulletPattern.exec(text)) !== null) {
      reqs.push({ value: match[1].trim(), type: 'requirement' });
    }
    return reqs;
  }

  return {
    init,
    parseFile,
    parseFiles,
    parsePDF,
    parseImage,
    parseTXT,
    parseDOCX,
    parseDOC,
    extractStructuredData,
  };
})();

window.FileParser = FileParser;
