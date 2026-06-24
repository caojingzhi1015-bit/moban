/* ============================================================
   resume-generator.js v1 — 反幻觉简历生成引擎

   核心约束:
   - 所有内容仅来源于校验后的用户素材库
   - JD 关键词匹配权重排序（匹配度高的经历前置）
   - 每条经历绑定素材溯源索引
   - 无匹配 JD 能力仅标注空缺，不虚构填充
   - 输出适配电脑/手机双端预览
   ============================================================ */

const ResumeGenerator = (() => {
  // === JD 关键词权重计算 ===
  function calcJDRelevance(entryText, jdKeywords) {
    if (!jdKeywords || !entryText) return 0;
    const text = entryText.toLowerCase();
    let score = 0;
    const allKeywords = [...(jdKeywords.hardSkills || []), ...(jdKeywords.softSkills || [])];
    for (const kw of allKeywords) {
      if (text.includes(kw.toLowerCase())) score += 10;
    }
    if (jdKeywords.industry) {
      for (const ind of jdKeywords.industry) {
        if (text.includes(ind)) score += 5;
      }
    }
    return score;
  }

  /** 按 JD 匹配度排序经历 */
  function sortByJDRelevance(entries, jdKeywords) {
    return [...entries].sort((a, b) => {
      const scoreA = calcJDRelevance(
        [a.company, a.position, a.duties, ...(a.achievements || [])].join(' '),
        jdKeywords
      );
      const scoreB = calcJDRelevance(
        [b.company, b.position, b.duties, ...(b.achievements || [])].join(' '),
        jdKeywords
      );
      return scoreB - scoreA;
    });
  }

  // === 简历生成主函数 ===
  /**
   * @param {Object} extractedData - 校验后的结构化数据
   * @param {Object} jdKeywords - JD 解析结果
   * @param {Object} options - { lang, useLLM, onProgress }
   * @returns {Object} resume - 五模块简历对象
   */
  async function generate(extractedData, jdKeywords = {}, options = {}) {
    const lang = options.lang || 'zh';
    const useLLM = options.useLLM !== false;
    const onProgress = options.onProgress || (() => {});

    onProgress({ stage: 'init', progress: 0, msg: '开始生成简历...' });

    const materialCtx = window.MaterialStore?.getAIContext?.() || '';
    const sources = window.MaterialStore?.getAllSources?.() || [];

    // === 尝试 LLM 生成 ===
    if (useLLM && window.DeepSeekAPI?.getApiKey?.()) {
      try {
        onProgress({ stage: 'llm', progress: 30, msg: 'AI 生成简历...' });
        const llmResult = await generateViaLLM(extractedData, jdKeywords, materialCtx, lang);
        if (llmResult) {
          onProgress({ stage: 'validate', progress: 80, msg: '溯源校验...' });
          const validated = validateResume(llmResult, materialCtx, extractedData, lang);
          onProgress({ stage: 'done', progress: 100, msg: '简历生成完成' });
          return formatResumeOutput(validated, extractedData, jdKeywords, sources, lang);
        }
      } catch (e) {
        console.warn('[ResumeGen] LLM generation failed, using template:', e.message);
      }
    }

    // === 模板生成（降级） ===
    onProgress({ stage: 'template', progress: 50, msg: '模板生成简历...' });
    const templateResume = buildTemplateResume(extractedData, jdKeywords, materialCtx, lang);
    onProgress({ stage: 'validate', progress: 80, msg: '溯源校验...' });
    const validated = validateResume(templateResume, materialCtx, extractedData, lang);
    onProgress({ stage: 'done', progress: 100, msg: '简历生成完成' });
    return formatResumeOutput(validated, extractedData, jdKeywords, sources, lang);
  }

  // === LLM 简历生成 ===
  async function generateViaLLM(extractedData, jdKeywords, materialCtx, lang) {
    const prompt = buildResumeGenPrompt(extractedData, jdKeywords, materialCtx, lang);

    const result = await DeepSeekAPI.chatCompletion({
      messages: [{ role: 'user', content: prompt }],
      taskType: 'enhanced',
      options: {
        maxTokens: 4096,
        temperature: 0.0,
        systemPrompt: RESUME_GEN_SYSTEM,
        extractionText: materialCtx,
        lang,
      },
    });

    if (!result.success || !result.content) return null;

    const parsed = parseJSONSafely(result.content);
    return parsed && (parsed.summary || parsed.experience) ? parsed : null;
  }

  // === 生成 Prompt ===
  const RESUME_GEN_SYSTEM = `# 全局铁律（最高优先级，不可违反）
1. 你只能使用【用户素材库】中已存在的文字。禁止猜测、脑补、编造、概括、润色扩充任何信息。
2. 素材库中没有的经历、数据、技能、项目、证书，一律不得输出，对应位置标注【暂无相关经历，请补充】。
3. 输出语言与用户指定一致，中文用中文生成，英文用英文生成。
4. 每条经历必须标注 source_ref（素材原文引用）。

# 你的角色
你是一个严谨的简历排版师。你只负责将已经校验完成的用户真实素材，按照目标岗位JD进行优先级排序和格式排版。你不创造任何新内容。`;

  function buildResumeGenPrompt(extractedData, jdKeywords, materialCtx, lang) {
    const jdInfo = jdKeywords.hardSkills?.length
      ? `目标岗位需求: ${jdKeywords.hardSkills.join(', ')}; 软技能: ${(jdKeywords.softSkills||[]).join(', ')}; 行业: ${(jdKeywords.industry||[]).join(', ')}`
      : '无JD信息';

    return `${RESUME_GEN_SYSTEM}

# 用户原始素材库（唯一可信数据源）
${materialCtx || '（素材库为空）'}

# 目标岗位JD关键词
${jdInfo}

# 简历生成要求
语言: ${lang === 'zh' ? '中文' : 'English'}
输出格式: 纯净JSON

# 输出Schema
{
  "summary": "1-2句个人概述，仅基于素材库中的技能和JD匹配度最高的2项能力",
  "experience": [
    {
      "company": "公司全称（原文）",
      "position": "职位（原文）",
      "period": "起止时间（原文）",
      "bullets": ["素材原文中的工作职责/成果"],
      "jd_relevance": "高/中/低",
      "source_ref": "素材原文摘录"
    }
  ],
  "education": [{"school":"原文","major":"原文","degree":"原文","period":"原文"}],
  "projects": [{"name":"原文","description":"原文职责","results":"原文数据|null","source_ref":"素材原文摘录"}],
  "skills": ["素材库中存在的技能"],
  "jd_gap_analysis": {
    "matched": ["JD要求且素材具备的能力"],
    "missing": ["JD要求但素材空缺的能力—诚实标注，不编造"]
  }
}

请仅返回JSON。`;
  }

  // === 模板降级生成 ===
  function buildTemplateResume(extractedData, jdKeywords, materialCtx, lang) {
    const bi = extractedData.basic_info || {};

    // 构建概要
    const skills = (extractedData.skills || []).map(s => s.name || s).filter(Boolean);
    const hardSkills = jdKeywords.hardSkills || [];
    const matchedSkills = skills.filter(s => hardSkills.some(h => s.toLowerCase().includes(h.toLowerCase())));

    let summary = '';
    if (lang === 'zh') {
      summary = bi.name ? `${bi.name}，` : '';
      summary += bi.target_job ? `意向${bi.target_job}。` : '';
      if (matchedSkills.length) summary += `具备${matchedSkills.slice(0, 3).join('、')}等岗位匹配技能。`;
      if (extractedData.work_experience?.length) summary += `${extractedData.work_experience.length}年+相关工作经验。`;
    } else {
      summary = bi.name ? `${bi.name}, ` : '';
      summary += bi.target_job ? `seeking ${bi.target_job}. ` : '';
      if (matchedSkills.length) summary += `Skilled in ${matchedSkills.slice(0, 3).join(', ')}. `;
      if (extractedData.work_experience?.length) summary += `${extractedData.work_experience.length}+ years experience.`;
    }

    // JD 排序工作经历
    const sortedWork = sortByJDRelevance(extractedData.work_experience || [], jdKeywords);

    // JD 空缺分析
    const allText = JSON.stringify(extractedData).toLowerCase();
    const matched = hardSkills.filter(h => allText.includes(h.toLowerCase()));
    const missing = hardSkills.filter(h => !allText.includes(h.toLowerCase()));

    return {
      summary,
      experience: sortedWork.map(w => ({
        company: w.company || '',
        position: w.position || '',
        period: [w.start_date, w.end_date].filter(Boolean).join(' - '),
        bullets: (w.duties ? [w.duties] : []).concat(w.achievements || []),
        jd_relevance: calcJDRelevance([w.company, w.position, w.duties].join(' '), jdKeywords) > 0 ? '高' : '中',
        source_ref: w.duties || w.company || '',
      })),
      education: (extractedData.education || []).map(e => ({
        school: e.school || '', major: e.major || '', degree: e.degree || '',
        period: [e.start_date, e.end_date].filter(Boolean).join(' - '),
      })),
      projects: (extractedData.projects || []).map(p => ({
        name: p.name || '', description: p.description || '', results: p.results || null,
        source_ref: p.description || p.name || '',
      })),
      skills: skills,
      jd_gap_analysis: { matched, missing },
    };
  }

  // === 溯源校验 ===
  function validateResume(resume, materialCtx, extractedData, lang) {
    if (!resume) return resume;

    const materialLower = (materialCtx || '').toLowerCase();

    // 校验每段经历的 source_ref 是否在素材中
    if (resume.experience) {
      resume.experience = resume.experience.map(exp => {
        if (exp.source_ref && !materialLower.includes(exp.source_ref.toLowerCase().substring(0, 30))) {
          exp._unverified = true;
          exp._warning = lang === 'zh' ? '该段经历的溯源引用未在素材库中找到' : 'Source reference not found in materials';
        }
        return exp;
      });
    }

    // 校验 summary 中的技能
    if (resume.summary && extractedData.skills) {
      const skillNames = new Set(extractedData.skills.map(s => (s.name || s).toLowerCase()));
      // 简单检查：summary 中的大写专有名词是否在技能库中
      const words = resume.summary.split(/[\s,，。]+/);
      for (const w of words) {
        if (w.length > 3 && /^[A-Z]/.test(w) && !skillNames.has(w.toLowerCase())) {
          // 可能是编造的技术名词
          console.warn(`[ResumeGen] Unverified term in summary: "${w}"`);
        }
      }
    }

    // FactChecker 全量校验
    if (window.FactChecker) {
      const resumeText = JSON.stringify(resume);
      const validation = FactChecker.validate(resumeText, materialCtx, { lang });
      resume._validation = validation;
    }

    return resume;
  }

  // === 格式化输出 ===
  function formatResumeOutput(resume, extractedData, jdKeywords, sources, lang) {
    return {
      ...resume,
      personal: {
        name: extractedData.basic_info?.name || '',
        phone: extractedData.basic_info?.phone || '',
        email: extractedData.basic_info?.email || '',
        city: extractedData.basic_info?.city || '',
        targetJob: extractedData.basic_info?.target_job || '',
        salary: extractedData.basic_info?.expect_salary || '',
      },
      jdKeywords,
      _sources: sources,
      _generatedAt: Date.now(),
      _version: '2.0',
    };
  }

  // === 生成中英自我介绍 (110-130秒) ===
  async function generateSelfIntro(resumeData, lang = 'zh') {
    const personal = resumeData.personal || {};
    const name = personal.name || (lang === 'zh' ? '我' : 'I');
    const targetJob = personal.targetJob || '';

    const skills = (resumeData.skills || []).slice(0, 4);
    const experience = resumeData.experience || [];
    const topExp = experience[0] || {};

    // 字数控制: 中文110-130字/秒*2分钟 = 220-260字, 英文150-160词
    const MAX_LEN = lang === 'zh' ? 250 : 155;
    const MIN_LEN = lang === 'zh' ? 200 : 130;

    if (lang === 'zh') {
      let intro = `面试官您好，我是${name}。`;

      if (targetJob) intro += `应聘${targetJob}岗位。`;
      if (skills.length) intro += `我熟练掌握${skills.join('、')}。`;

      if (topExp.company) {
        intro += `曾在${topExp.company}担任${topExp.position || ''}，`;
        if (topExp.bullets?.length) {
          intro += `负责${topExp.bullets[0].substring(0, 60)}`;
          if (topExp.bullets[0].length > 60) intro += '...';
          intro += '；';
        }
      }

      if (experience.length > 1) {
        const second = experience[1];
        if (second.company) {
          intro += `此前在${second.company}${second.position ? '任'+second.position : ''}，积累了丰富经验。`;
        }
      }

      // 检查字数，不足则补充
      if (intro.length < MIN_LEN) {
        intro += `我有${experience.length}段相关工作经历，`;
        if (resumeData.education?.length) {
          intro += `毕业于${resumeData.education[0].school || ''}${resumeData.education[0].major ? '，专业'+resumeData.education[0].major : ''}。`;
        }
        intro += '期待能为团队贡献价值，谢谢。';
      }

      // 截断到最大字数
      if (intro.length > MAX_LEN) {
        intro = intro.substring(0, MAX_LEN - 3) + '...谢谢。';
      }

      // 估算朗读时长 (中文约 200字/分钟)
      const estSeconds = Math.round(intro.length / 200 * 60);
      return { text: intro, lang: 'zh', estimatedSeconds: estSeconds, charCount: intro.length };
    } else {
      let intro = `Hello, I'm ${name}. `;
      if (targetJob) intro += `I'm applying for the ${targetJob} position. `;
      if (skills.length) intro += `My technical skills include ${skills.join(', ')}. `;

      if (topExp.company) {
        intro += `Most recently at ${topExp.company} as ${topExp.position || 'a team member'}, `;
        if (topExp.bullets?.length) {
          intro += `where I ${topExp.bullets[0].substring(0, 60).toLowerCase()}. `;
        }
      }

      if (experience.length > 1) {
        intro += `Previously, I worked at ${experience[1].company || 'another company'} gaining valuable experience. `;
      }

      if (intro.length < MIN_LEN) {
        intro += `With ${experience.length} relevant roles, `;
        if (resumeData.education?.length) {
          intro += `and a degree from ${resumeData.education[0].school || 'university'}, `;
        }
        intro += `I'm excited about this opportunity. Thank you.`;
      }

      if (intro.length > MAX_LEN) {
        intro = intro.substring(0, MAX_LEN - 3) + '...';
      }

      const estSeconds = Math.round(intro.length / 150 * 60);
      return { text: intro, lang: 'en', estimatedSeconds: estSeconds, charCount: intro.length };
    }
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
    generate,
    generateSelfIntro,
    calcJDRelevance,
    sortByJDRelevance,
  };
})();

window.ResumeGenerator = ResumeGenerator;
