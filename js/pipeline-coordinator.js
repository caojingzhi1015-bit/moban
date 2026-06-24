/* ============================================================
   pipeline-coordinator.js v1 — 全链路流水线协调器

   完整流程:
   Step 0: 用户上传/粘贴 → 文件离线解析（OCREngine/PDFParser）
   Step 1: 规则预提取（PyResParser 硬字段正则）
   Step 2: DeepSeek 结构化抽取（强Schema + temperature=0）
   Step 3: 后端双层校验（格式正则 + 素材溯源）
   Step 4: 前端表单回填 + 溯源标记
   Step 5: 用户确认后 → 简历生成（ResumeGenerator）
   Step 6: 双端预览 + 导出

   所有步骤打印完整日志。
   ============================================================ */

const PipelineCoordinator = (() => {
  const LOG_PREFIX = '[Pipeline]';

  function log(msg, data) {
    const ts = new Date().toISOString().slice(11, 19);
    console.log(`${LOG_PREFIX} ${ts} ${msg}`, data || '');
  }

  // === 全链路: 文件/文本 → 表单填充 ===
  /**
   * @param {File|string} input - File object 或 text string
   * @param {Object} options
   *   - lang: 'zh'|'en'
   *   - onProgress: ({step, stage, msg, progress}) => void
   *   - preferLocal: bool (skip backend)
   * @returns {Object} { extractedData, validation, logs, method }
   */
  async function runExtractionPipeline(input, options = {}) {
    const lang = options.lang || 'zh';
    const onProgress = options.onProgress || (() => {});
    const logs = [];

    function addLog(msg) { logs.push({ time: Date.now(), msg }); log(msg); }

    let rawText = '';

    onProgress({ step: 0, stage: 'prep', msg: '准备解析...', progress: 0 });

    // === Step 0: 文件离线解析 ===
    if (input instanceof File) {
      addLog(`Step 0: 文件分流 — ${input.name} (${input.type})`);
      const ext = (input.name || '').split('.').pop()?.toLowerCase();

      if (['png','jpg','jpeg','webp','bmp','gif'].includes(ext)) {
        addLog('  → 图片 → OCREngine');
        onProgress({ step: 0, stage: 'ocr', msg: 'OCR 识别中...', progress: 10 });
        const ocrResult = await OCREngine.recognize(input, { lang });
        if (!ocrResult.success) throw new Error('OCR 失败: ' + (ocrResult.error || 'unknown'));
        rawText = ocrResult.fullText;
        addLog(`  ✅ OCR完成: ${ocrResult.method}, ${ocrResult.lines?.length || 0} 行, confidence=${ocrResult.confidence?.toFixed(2)}`);
      } else if (['pdf','docx','doc'].includes(ext)) {
        addLog('  → PDF/DOCX → PDFParser');
        onProgress({ step: 0, stage: 'pdf', msg: '文档解析中...', progress: 10 });
        const pdfResult = await PDFParser.parse(input, { lang });
        if (!pdfResult.success) throw new Error('PDF解析失败: ' + (pdfResult.error || 'unknown'));
        rawText = pdfResult.markdown;
        addLog(`  ✅ 文档解析完成: ${pdfResult.method}, ${pdfResult.pageCount || 1} 页, sections=${Object.keys(pdfResult.sections||{}).length}`);
      } else {
        addLog('  → 文本文件');
        rawText = await input.text();
      }
    } else if (typeof input === 'string') {
      rawText = input;
      addLog(`Step 0: 文本输入, ${rawText.length} 字符`);
    }

    if (!rawText || rawText.length < 5) {
      throw new Error('文件内容为空或无法识别，请检查文件');
    }

    onProgress({ step: 1, stage: 'regex', msg: '正则预提取...', progress: 25 });

    // === Step 1: 规则预提取（硬字段正则兜底） ===
    addLog('Step 1: 正则预提取硬字段...');
    const regexResult = window.ExtractionPipeline?.regexFallbackExtraction?.(rawText, lang) || { basic_info: {} };
    const hardFields = {};
    if (regexResult.basic_info) {
      hardFields.name = regexResult.basic_info.name;
      hardFields.phone = regexResult.basic_info.phone;
      hardFields.email = regexResult.basic_info.email;
    }
    addLog(`  ✅ 预提取: name=${hardFields.name || '?'}, phone=${hardFields.phone ? '***' : '?'}, email=${hardFields.email || '?'}`);

    onProgress({ step: 2, stage: 'llm', msg: 'DeepSeek 结构化抽取...', progress: 35 });

    // === Step 2: DeepSeek 结构化抽取 ===
    let extractedData = null;
    let extractionMethod = 'regex';

    if (window.BackendAPI?.isBackendAvailable?.()) {
      addLog('Step 2: 后端 API 提取 (SmartResume/DeepSeek)');
      try {
        const resp = await BackendAPI.extractResume(rawText, { lang, method: 'auto' });
        if (resp.success && (resp.basic_info?.name || resp.education?.length || resp.work_experience?.length)) {
          extractedData = resp;
          extractionMethod = resp.method || 'backend';
          addLog(`  ✅ 后端提取完成: ${extractionMethod}, confidence=${resp.confidence || '?'}`);
        }
      } catch (e) { addLog(`  ⚠️ 后端提取失败: ${e.message}`); }
    }

    if (!extractedData && window.DeepSeekAPI?.getApiKey?.()) {
      addLog('Step 2: DeepSeek 直接调用 (temperature=0)');
      try {
        const prompt = PromptsConfig.getExtraction(rawText, lang);
        const result = await DeepSeekAPI.chatCompletion({
          messages: [{ role: 'user', content: prompt }],
          taskType: 'enhanced',
          options: { maxTokens: 4096, temperature: 0.0, extractionText: rawText, lang },
        });
        if (result.success && result.content) {
          const parsed = parseJSONSafely(result.content);
          if (parsed && (parsed.base_info || parsed.basic_info)) {
            extractedData = normalizeSchema(parsed);
            extractionMethod = 'deepseek-llm';
            addLog(`  ✅ DeepSeek 提取完成`);
          }
        }
      } catch (e) { addLog(`  ⚠️ DeepSeek 调用失败: ${e.message}`); }
    }

    // 降级: 纯 regex
    if (!extractedData) {
      addLog('Step 2: 降级到纯正则提取');
      extractedData = regexResult;
      extractionMethod = 'regex';
      addLog(`  ✅ 正则提取完成`);
    }

    // 用硬字段覆盖（LLM 可能遗漏基础字段）
    extractedData.basic_info = extractedData.basic_info || {};
    for (const [k, v] of Object.entries(hardFields)) {
      if (!extractedData.basic_info[k] && v) {
        extractedData.basic_info[k] = v;
      }
    }

    onProgress({ step: 3, stage: 'validate', msg: '双层校验...', progress: 70 });

    // === Step 3: 双层校验（格式 + 溯源） ===
    addLog('Step 3: 双层校验...');
    let validation = { severity: 'pass', issues: [], warnings: [] };

    // 格式正则校验
    const formatIssues = validateFormat(extractedData);
    if (formatIssues.length) {
      validation.issues.push(...formatIssues.map(i => ({ ...i, source: 'format' })));
      addLog(`  格式校验: ${formatIssues.length} 问题`);
    }

    // 溯源校验
    if (window.FactChecker) {
      const fcResult = FactChecker.validate(
        JSON.stringify(extractedData),
        rawText,
        extractedData,
        lang
      );
      validation.severity = fcResult.severity;
      validation.issues.push(...fcResult.issues.map(i => ({ ...i, source: 'factcheck' })));
      validation.groundedRatio = fcResult.grounded_ratio;
      validation.missingFields = fcResult.missing_fields || [];
      addLog(`  溯源校验: severity=${fcResult.severity}, grounded=${fcResult.grounded_ratio?.toFixed(2)}, issues=${fcResult.issues?.length || 0}`);
    }

    onProgress({ step: 4, stage: 'fill', msg: '表单回填...', progress: 85 });

    // === Step 4: 表单回填 ===
    addLog('Step 4: 表单回填 + 素材入库...');

    // 导入 MaterialStore
    if (window.MaterialStore) {
      const fileName = input instanceof File ? input.name : '用户输入';
      window.MaterialStore.loadFromExtraction?.(extractedData, fileName);
      window.MaterialStore.lock?.();
      addLog('  ✅ 素材库已锁定');
    }

    onProgress({ step: 5, stage: 'done', msg: '提取完成', progress: 100 });
    addLog('✅ 提取流水线完成');

    return {
      success: true,
      extractedData,
      validation,
      method: extractionMethod,
      rawText,
      logs,
      sessionId: window.BackendAPI?.getSessionId?.() || null,
    };
  }

  // === 完整简历生成流水线 ===
  async function runGenerationPipeline(extractedData, jdKeywords, options = {}) {
    const lang = options.lang || 'zh';
    const onProgress = options.onProgress || (() => {});
    const logs = [];

    function addLog(msg) { logs.push({ time: Date.now(), msg }); log(msg); }

    addLog('=== 简历生成流水线 ===');

    // Step 1: JD 匹配权重排序
    onProgress({ stage: 'sort', msg: 'JD 匹配排序...', progress: 10 });
    addLog('  Step 1: JD 关键词权重排序经历...');
    const sortedWork = ResumeGenerator.sortByJDRelevance(extractedData.work_experience || [], jdKeywords);
    addLog(`    ${sortedWork.length} 条工作经历已按JD匹配度排序`);

    // Step 2: 生成简历
    onProgress({ stage: 'generate', msg: 'AI 生成简历...', progress: 30 });
    addLog('  Step 2: 调用 ResumeGenerator...');
    const resume = await ResumeGenerator.generate(extractedData, jdKeywords, {
      lang,
      useLLM: options.useLLM !== false,
      onProgress: (info) => addLog(`    ${info.msg}`),
    });
    addLog(`  ✅ 简历生成完成, validation: ${resume._validation?.severity || 'N/A'}`);

    // Step 3: 生成自我介绍
    onProgress({ stage: 'intro', msg: '生成自我介绍...', progress: 80 });
    addLog('  Step 3: 生成自我介绍...');
    const selfIntroCN = await ResumeGenerator.generateSelfIntro(resume, 'zh');
    const selfIntroEN = await ResumeGenerator.generateSelfIntro(resume, 'en');
    addLog(`  ✅ 中文: ${selfIntroCN.charCount}字, ~${selfIntroCN.estimatedSeconds}秒`);
    addLog(`  ✅ 英文: ${selfIntroEN.charCount}字, ~${selfIntroEN.estimatedSeconds}秒`);

    onProgress({ stage: 'done', msg: '生成完成', progress: 100 });

    return {
      resume,
      selfIntro: { cn: selfIntroCN.text, en: selfIntroEN.text },
      selfIntroMeta: { cn: selfIntroCN, en: selfIntroEN },
      logs,
    };
  }

  // === 格式校验 ===
  function validateFormat(data) {
    const issues = [];
    const bi = data.basic_info || {};

    // 手机号格式
    if (bi.phone && !/^(\+?86)?1[3-9]\d{9}$/.test(bi.phone.replace(/[\s\-]/g, ''))) {
      issues.push({ type: 'format_phone', severity: 'warning', field: 'phone', message: `手机号格式异常: ${bi.phone}` });
    }

    // 邮箱格式
    if (bi.email && !/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(bi.email)) {
      issues.push({ type: 'format_email', severity: 'warning', field: 'email', message: `邮箱格式异常: ${bi.email}` });
    }

    // 时间逻辑校验
    for (const work of (data.work_experience || [])) {
      if (work.start_date && work.end_date && work.end_date !== '至今') {
        const s = parseInt(work.start_date);
        const e = parseInt(work.end_date);
        if (!isNaN(s) && !isNaN(e) && s > e) {
          issues.push({ type: 'time_conflict', severity: 'block', field: 'work_experience', message: `时间冲突: ${work.company} ${work.start_date}-${work.end_date}` });
        }
      }
    }

    return issues;
  }

  // === Schema 归一化 ===
  function normalizeSchema(data) {
    if (data.basic_info) return data; // 已是内部格式
    const result = {};

    // base_info → basic_info
    const base = data.base_info || {};
    result.basic_info = {
      name: base.name, phone: base.phone, email: base.email,
      city: base.target_city, target_job: base.target_position,
      expect_salary: base.expected_salary, onboard_time: base.available_onboard_time,
    };

    // education_list → education
    result.education = (data.education_list || []).map(e => ({
      school: e.school_name, major: e.major, degree: e.degree,
      start_date: e.start_date, end_date: e.end_date, awards: e.scholarship_awards || [],
    }));

    // work_experience_list → work_experience
    result.work_experience = (data.work_experience_list || []).map(w => ({
      company: w.company, position: w.position, start_date: w.start_date,
      end_date: w.end_date, duties: w.job_duty, achievements: [],
    }));

    // project_list → projects
    result.projects = (data.project_list || []).map(p => ({
      name: p.project_name, description: p.responsibility, results: p.project_data,
    }));

    // skill_certificate → skills
    const sc = data.skill_certificate || {};
    result.skills = [
      ...(sc.software_skill || []).map(s => ({ name: s, category: '工具' })),
      ...(sc.ai_tool_mastered || []).map(s => ({ name: s, category: 'AI工具' })),
    ];
    result.certificates = (sc.other_cert || []).map(c => ({ name: c }));
    result.languages = (sc.language_cert || []).map(l => ({ name: l }));

    return result;
  }

  // === Utility ===
  function parseJSONSafely(text) {
    try { return JSON.parse(text); } catch (e) {
      const m = text.match(/\{[\s\S]*\}/);
      if (m) {
        try { return JSON.parse(m[0]); } catch (e2) { return null; }
      }
      return null;
    }
  }

  // === Public API ===
  return {
    runExtractionPipeline,
    runGenerationPipeline,
    validateFormat,
  };
})();

window.PipelineCoordinator = PipelineCoordinator;
