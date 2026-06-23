/* ============================================================
   i18n.js - 中英文双语切换系统
   Internationalization: Chinese (zh) & English (en)
   ============================================================ */

const I18N = (() => {
  // Current language
  let currentLang = localStorage.getItem('careerai_lang') || 'zh';

  // All translatable strings
  const strings = {
    // === Navigation ===
    'nav.brand': { zh: 'CareerAI', en: 'CareerAI' },
    'nav.tagline': { zh: 'AI求职助手', en: 'AI Job Assistant' },
    'nav.lang': { zh: 'EN', en: '中文' },

    // === Hero ===
    'hero.badge': { zh: 'AI 驱动 · 智能求职', en: 'AI-Powered · Smart Job Search' },
    'hero.title': { zh: '一键生成岗位对标简历<br>多模型AI模拟面试', en: 'One-Click Job-Matched Resume<br>Multi-Model AI Mock Interview' },
    'hero.desc': { zh: '上传JD即可自动生成精准匹配简历，支持中英文双语导出。多智能体联动模拟面试，助你拿下心仪Offer。', en: 'Upload a JD to auto-generate a precisely matched resume with bilingual export. Multi-agent mock interviews help you land your dream offer.' },
    'hero.cta.resume': { zh: '开始生成简历', en: 'Generate Resume' },
    'hero.cta.interview': { zh: '模拟面试', en: 'Mock Interview' },

    // === Section Headers ===
    'section.resume': { zh: 'AI精准简历生成', en: 'AI Resume Generator' },
    'section.resume.sub': { zh: 'JD定向解析 + 增信问卷 + 双语导出', en: 'JD Analysis + Credibility QA + Bilingual Export' },
    'section.interview': { zh: '多智能体模拟面试', en: 'Multi-Agent Mock Interview' },
    'section.interview.sub': { zh: '4款AI模型联动 · 中英文双语面试 · 实时点评打分', en: '4 AI Models · Bilingual Interview · Real-time Feedback' },

    // === Form Labels (Module 1-1) ===
    'form.jd.title': { zh: '岗位JD信息', en: 'Job Description' },
    'form.jd.placeholder': { zh: '在此粘贴完整的招聘JD内容，或输入岗位关键要求...', en: 'Paste the full job description here, or enter key requirements...' },
    'form.jd.parse': { zh: 'AI解析JD', en: 'AI Parse JD' },
    'form.jd.parsing': { zh: '解析中...', en: 'Parsing...' },
    'form.personal.title': { zh: '个人信息', en: 'Personal Information' },
    'form.name': { zh: '姓名', en: 'Full Name' },
    'form.name.ph': { zh: '请输入姓名', en: 'Enter your full name' },
    'form.phone': { zh: '电话', en: 'Phone' },
    'form.phone.ph': { zh: '请输入联系电话', en: 'Enter your phone number' },
    'form.email': { zh: '邮箱', en: 'Email' },
    'form.email.ph': { zh: '请输入邮箱地址', en: 'Enter your email' },
    'form.city': { zh: '意向城市', en: 'Target City' },
    'form.city.ph': { zh: '期望工作城市', en: 'Preferred work city' },
    'form.salary': { zh: '期望薪资', en: 'Expected Salary' },
    'form.salary.ph': { zh: '如：15K-25K', en: 'e.g. $80K-$120K' },
    'form.start': { zh: '到岗时间', en: 'Start Date' },
    'form.start.ph': { zh: '如：随时到岗 / 一个月内', en: 'e.g. Immediately / Within 1 month' },
    'form.job_title': { zh: '目标岗位', en: 'Target Position' },
    'form.job_title.ph': { zh: '如：高级前端工程师', en: 'e.g. Senior Frontend Engineer' },
    'form.industry': { zh: '行业', en: 'Industry' },
    'form.industry.placeholder': { zh: '选择行业', en: 'Select industry' },
    'form.experience': { zh: '工作年限', en: 'Years of Experience' },
    'form.experience.placeholder': { zh: '选择年限', en: 'Select years' },
    'form.education': { zh: '教育经历', en: 'Education' },
    'form.education.ph': { zh: '学校名称 / 专业 / 学历 / 起止时间', en: 'School / Major / Degree / Period' },
    'form.work': { zh: '实习/工作经历', en: 'Work Experience' },
    'form.work.ph': { zh: '公司名称 / 职位 / 工作内容 / 起止时间', en: 'Company / Position / Responsibilities / Period' },
    'form.project': { zh: '项目经历', en: 'Project Experience' },
    'form.project.ph': { zh: '项目名称 / 职责 / 成果 / 时间', en: 'Project Name / Role / Results / Period' },
    'form.skills': { zh: '证书技能', en: 'Certificates & Skills' },
    'form.skills.ph': { zh: '证书、技能、语言能力等', en: 'Certificates, skills, languages, etc.' },
    'form.self_intro': { zh: '自我评价', en: 'Self-Assessment' },
    'form.self_intro.ph': { zh: '简短描述个人优势与职业目标', en: 'Briefly describe your strengths and career goals' },

    // === Industries ===
    'industry.internet': { zh: '互联网/IT', en: 'Internet/IT' },
    'industry.finance': { zh: '金融', en: 'Finance' },
    'industry.education': { zh: '教育', en: 'Education' },
    'industry.healthcare': { zh: '医疗健康', en: 'Healthcare' },
    'industry.ecommerce': { zh: '电商/零售', en: 'E-commerce/Retail' },
    'industry.manufacturing': { zh: '制造业', en: 'Manufacturing' },
    'industry.media': { zh: '媒体/广告', en: 'Media/Advertising' },
    'industry.consulting': { zh: '咨询', en: 'Consulting' },
    'industry.other': { zh: '其他', en: 'Other' },

    // === Experience Levels ===
    'exp.fresh': { zh: '应届生', en: 'Fresh Graduate' },
    'exp.1-3': { zh: '1-3年', en: '1-3 Years' },
    'exp.3-5': { zh: '3-5年', en: '3-5 Years' },
    'exp.5-10': { zh: '5-10年', en: '5-10 Years' },
    'exp.10plus': { zh: '10年以上', en: '10+ Years' },

    // === Questionnaire (Module 1-2) ===
    'questionnaire.title': { zh: '增信补充问卷', en: 'Credibility Questionnaire' },
    'questionnaire.sub': { zh: '以下问题将帮助你丰富简历细节，提升可信度', en: 'These questions help enrich your resume with concrete details' },
    'questionnaire.skip': { zh: '跳过', en: 'Skip' },
    'questionnaire.skip_all': { zh: '全部跳过', en: 'Skip All' },
    'questionnaire.next': { zh: '下一题', en: 'Next' },
    'questionnaire.submit': { zh: '完成', en: 'Done' },
    'questionnaire.generated': { zh: 'AI根据你的JD和经历自动生成的问题', en: 'AI-generated questions based on your JD and experience' },

    // Default questions
    'q.data_metrics': { zh: '请提供你主导的项目中可量化的数据成果（如曝光量、转化率、用户增长等）？', en: 'Please provide quantifiable results from projects you led (e.g., impressions, conversion rate, user growth)?' },
    'q.tools': { zh: '你在工作中使用过哪些专业工具或技术栈？请具体列出。', en: 'What professional tools or tech stacks have you used? Please list specifically.' },
    'q.challenge': { zh: '请描述一个你遇到过的最大挑战以及你是如何解决的？', en: 'Describe the biggest challenge you faced and how you overcame it?' },
    'q.teamwork': { zh: '请举例说明你在团队协作中扮演的角色和贡献？', en: 'Please give an example of your role and contribution in team collaboration?' },
    'q.achievement': { zh: '你最引以为豪的一项工作成果是什么？为什么？', en: 'What work achievement are you most proud of? Why?' },
    'q.growth': { zh: '你如何保持专业技能的学习和成长？', en: 'How do you stay current with professional skills and growth?' },

    // === Resume Generation (Module 1-3) ===
    'resume.generate': { zh: '一键生成简历', en: 'Generate Resume' },
    'resume.generating': { zh: 'AI正在为你生成简历...', en: 'AI is crafting your resume...' },
    'resume.regenerate': { zh: '重新生成', en: 'Regenerate' },
    'resume.preview.desktop': { zh: '电脑端预览', en: 'Desktop Preview' },
    'resume.preview.mobile': { zh: '手机端预览', en: 'Mobile Preview' },
    'resume.export.word': { zh: '导出 Word', en: 'Export Word' },
    'resume.export.pdf': { zh: '导出 PDF', en: 'Export PDF' },
    'resume.empty': { zh: '请先填写JD和个人信息，然后点击生成简历', en: 'Please fill in JD and personal info, then generate resume' },
    'resume.section.education': { zh: '教育经历', en: 'Education' },
    'resume.section.experience': { zh: '工作经历', en: 'Work Experience' },
    'resume.section.projects': { zh: '项目经历', en: 'Projects' },
    'resume.section.skills': { zh: '技能证书', en: 'Skills & Certificates' },
    'resume.section.self_intro': { zh: '自我评价', en: 'Self-Assessment' },

    // === Self Introduction (Module 1-4) ===
    'intro.title': { zh: '2分钟HR自我介绍', en: '2-Minute Self-Introduction' },
    'intro.sub': { zh: '基于简历核心经历，生成口语化自我介绍', en: 'A conversational self-introduction based on your resume highlights' },
    'intro.generate': { zh: '生成自我介绍', en: 'Generate Introduction' },
    'intro.copy': { zh: '复制文本', en: 'Copy Text' },
    'intro.copied': { zh: '已复制！', en: 'Copied!' },
    'intro.duration': { zh: '约2分钟朗读', en: '~2 min read' },
    'intro.cn_version': { zh: '中文版本', en: 'Chinese Version' },
    'intro.en_version': { zh: '英文版本', en: 'English Version' },

    // === Interview (Module 2) ===
    'interview.model_config': { zh: '模型配置', en: 'Model Config' },
    'interview.api_key': { zh: 'API Key', en: 'API Key' },
    'interview.api_key.ph': { zh: '输入API密钥（可选，用于真实调用）', en: 'Enter API key (optional, for real calls)' },
    'interview.temperature': { zh: '回答温度', en: 'Temperature' },
    'interview.max_tokens': { zh: '最大长度', en: 'Max Tokens' },
    'interview.system_prompt': { zh: '面试指令', en: 'Interview Prompt' },
    'interview.system_prompt.ph': { zh: '自定义面试官行为指令...', en: 'Custom interviewer behavior prompt...' },
    'interview.start': { zh: '开始面试', en: 'Start Interview' },
    'interview.stop': { zh: '结束面试', en: 'End Interview' },
    'interview.placeholder': { zh: '输入你的回答...', en: 'Type your answer...' },
    'interview.send': { zh: '发送', en: 'Send' },
    'interview.typing': { zh: '正在输入...', en: 'Typing...' },
    'interview.empty': { zh: '面试还未开始，请配置模型并点击开始面试', en: 'Interview not started. Configure models and click Start' },
    'interview.export': { zh: '导出面试记录', en: 'Export Transcript' },
    'interview.score': { zh: '评分', en: 'Score' },
    'interview.suggestion': { zh: '优化建议', en: 'Suggestion' },

    // === Model Names ===
    'model.doubao': { zh: '豆包 (字节)', en: 'Doubao (ByteDance)' },
    'model.gemini': { zh: 'Gemini (Google)', en: 'Gemini (Google)' },
    'model.claude': { zh: 'Claude (Anthropic)', en: 'Claude (Anthropic)' },
    'model.chatgpt': { zh: 'ChatGPT (OpenAI)', en: 'ChatGPT (OpenAI)' },

    // === Toast Messages ===
    'toast.resume_generated': { zh: '简历已生成！', en: 'Resume generated!' },
    'toast.resume_exported': { zh: '简历导出成功！', en: 'Resume exported!' },
    'toast.intro_copied': { zh: '自我介绍已复制到剪贴板', en: 'Self-intro copied to clipboard' },
    'toast.draft_saved': { zh: '草稿已自动保存', en: 'Draft auto-saved' },
    'toast.interview_started': { zh: '面试已开始，AI将向你提问', en: 'Interview started. AI will ask you questions.' },
    'toast.lang_changed': { zh: '语言已切换为中文', en: 'Language switched to English' },
    'toast.form_incomplete': { zh: '请填写必要信息', en: 'Please fill in required fields' },

    // === Misc ===
    'common.loading': { zh: '加载中...', en: 'Loading...' },
    'common.confirm': { zh: '确认', en: 'Confirm' },
    'common.cancel': { zh: '取消', en: 'Cancel' },
    'common.close': { zh: '关闭', en: 'Close' },
    'common.save': { zh: '保存', en: 'Save' },
    'common.delete': { zh: '删除', en: 'Delete' },

    // === Footer ===
    'footer.text': { zh: 'CareerAI · AI求职助手 · 本地运行 · 数据不上传', en: 'CareerAI · AI Job Assistant · Local Only · No Data Upload' },
  };

  // Dynamic question templates - filled based on JD keywords
  const questionTemplates = {
    zh: [
      '根据JD中对「{keyword}」的要求，请描述你在该领域的具体经验和成果？',
      '你在「{keyword}」方面有哪些量化的成绩可以分享？',
      '请举例说明你运用「{keyword}」解决过的实际问题？',
      'JD强调了「{keyword}」能力，你能提供相关项目案例吗？',
    ],
    en: [
      'Based on the JD requirement for "{keyword}", please describe your specific experience and results in this area?',
      'What quantifiable achievements can you share regarding "{keyword}"?',
      'Please give an example of a real problem you solved using "{keyword}"?',
      'The JD emphasizes "{keyword}" skills - can you provide relevant project examples?',
    ]
  };

  function t(key) {
    const entry = strings[key];
    if (!entry) {
      console.warn(`[i18n] Missing translation key: ${key}`);
      return key;
    }
    return entry[currentLang] || entry['zh'] || key;
  }

  function getLang() {
    return currentLang;
  }

  function setLang(lang) {
    if (lang !== 'zh' && lang !== 'en') return;
    currentLang = lang;
    localStorage.setItem('careerai_lang', lang);
    // Dispatch event for all components to re-render
    document.documentElement.lang = lang;
    window.dispatchEvent(new CustomEvent('langchange', { detail: { lang } }));
  }

  function toggleLang() {
    setLang(currentLang === 'zh' ? 'en' : 'zh');
  }

  function getQuestionTemplate(index) {
    const templates = questionTemplates[currentLang];
    return templates[index % templates.length];
  }

  // Generate dynamic questions based on JD keywords
  function generateQuestions(jdKeywords, count = 5) {
    if (!jdKeywords || jdKeywords.length === 0) {
      // Fallback to default questions
      const defaultKeys = ['data_metrics', 'tools', 'challenge', 'teamwork', 'achievement', 'growth'];
      return defaultKeys.slice(0, count).map(k => ({
        key: k,
        text: t(`q.${k}`),
      }));
    }
    const questions = [];
    for (let i = 0; i < Math.min(count, jdKeywords.length * 2); i++) {
      const keyword = jdKeywords[i % jdKeywords.length];
      const template = getQuestionTemplate(i);
      questions.push({
        key: `dynamic_${i}`,
        text: template.replace('{keyword}', keyword),
        keyword,
      });
    }
    return questions;
  }

  // Update all DOM elements with data-i18n attributes
  function refreshDOM() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const translated = t(key);
      if (translated && translated !== key) {
        // Handle HTML content (for hero title with <br>)
        if (translated.includes('<br>')) {
          el.innerHTML = translated;
        } else {
          el.textContent = translated;
        }
      }
    });

    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      const translated = t(key);
      if (translated && translated !== key) {
        el.setAttribute('placeholder', translated);
      }
    });

    // Update select options
    document.querySelectorAll('[data-i18n-options]').forEach(el => {
      const prefix = el.getAttribute('data-i18n-options');
      el.querySelectorAll('option').forEach(opt => {
        const val = opt.value;
        if (!val) return;
        const key = `${prefix}.${val}`;
        const translated = t(key);
        if (translated && translated !== key) {
          opt.textContent = translated;
        }
      });
    });
  }

  // Listen for language change to refresh DOM
  window.addEventListener('langchange', () => {
    refreshDOM();
  });

  // Initial DOM refresh on load
  document.addEventListener('DOMContentLoaded', () => {
    document.documentElement.lang = currentLang;
    refreshDOM();
  });

  return {
    t,
    getLang,
    setLang,
    toggleLang,
    generateQuestions,
    refreshDOM,
  };
})();

// Global shorthand
window.I18N = I18N;
window.t = (key) => I18N.t(key);
