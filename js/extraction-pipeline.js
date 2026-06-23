/* ============================================================
   extraction-pipeline.js v3 — 深度简历信息提取流水线
   Skill 1: MinerU-style PDF 布局解析 (分章节+坐标索引)
   Skill 2: DeepSeek-VL OCR 图像增强识别
   Skill 3: SmartResume 7模块结构化抽取 (阿里开源schema)
   Skill 4: Schema Lock + 事实溯源双校验
   Skill 5: 标准简历模板约束 (防格式错漏)
   ============================================================ */

const ExtractionPipeline = (() => {
  const SMART_RESUME_SCHEMA = {
    basic_info: { name: null, phone: null, email: null, city: null, target_job: null, salary: null, onboard_time: null, source_index: [] },
    education: [], work_experience: [], projects: [], skills: [], certificates: [], self_assessment: null,
  };

  // ================================================================
  // MinerU PDF (unchanged, already robust)
  // ================================================================
  const MinerUPDFSkill = { /* ... keep existing ... */ };

  // ================================================================
  // PyResParser v3 — 超强中文简历正则提取引擎
  // ================================================================
  const PyResParser = {
    extract(text) {
      const clean = normalizeText(text);
      return {
        name: this.extractName(clean),
        phone: this.extractPhone(clean),
        email: this.extractEmail(clean),
        city: this.extractCity(clean),
        targetJob: this.extractTargetJob(clean),
        salary: this.extractSalary(clean),
        birth: this.extractBirth(clean),
        age: this.extractAge(clean),
        gender: this.extractGender(clean),
        education: this.extractEducation(clean),
        workExperience: this.extractWorkExperience(clean),
        projects: this.extractProjects(clean),
        skills: this.extractSkills(clean),
        certificates: this.extractCertificates(clean),
        languages: this.extractLanguages(clean),
        selfAssessment: this.extractSelfAssessment(clean),
      };
    },

    // --- 姓名 ---
    extractName(text) {
      const patterns = [
        /姓\s*名[：:\s]*([^\n,，。.\d\s]{2,6})/,
        /名字[：:\s]*([^\n,，。.\d\s]{2,6})/,
        /^([^\n,，。.\d\s]{2,4})\s*\n\s*(?:电话|手机|1[3-9])/m,
        /^([^\n,，。.\d\s]{2,4})\s*\n\s*(?:邮箱|[a-zA-Z0-9._%+-]+@)/m,
        /【姓名】[：:\s]*([^\n]{2,6})/,
        /姓名[：:\s]*([^\n,，。.\d\s]{2,6})/,
      ];
      for (const p of patterns) { const m = text.match(p); if (m?.[1]?.trim().length >= 2) return m[1].trim(); }
      return null;
    },

    // --- 手机号 ---
    extractPhone(text) {
      const patterns = [
        /(?:电话|手机|Tel|Phone|联系方式|联系电话|手机号码|MOBILE|Mobile)[：:\s]*(\+?86[\s-]?)?(\d[\d\-+\s]{6,18})/i,
        /(1[3-9]\d)[\s\-]?(\d{4})[\s\-]?(\d{4})/,
        /(\+86[\s-]?1[3-9]\d[\s-]?\d{4}[\s-]?\d{4})/,
        /(1[3-9]\d{9})/,
      ];
      for (const p of patterns) {
        const m = text.match(p);
        if (m) {
          const phone = (m[2] ? (m[1]||'') + m[2] : m[1] || m[0]).replace(/[\s\-]/g, '');
          if (/^(\+?86)?1[3-9]\d{9}$/.test(phone)) return phone;
          if (phone.length >= 7) return phone;
        }
      }
      return null;
    },

    // --- 邮箱 ---
    extractEmail(text) {
      const patterns = [
        /(?:邮箱|邮件|Email|E-mail|电子邮箱|EMAIL)[：:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i,
        /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/,
      ];
      for (const p of patterns) { const m = text.match(p); if (m?.[1]) return m[1].trim(); }
      return null;
    },

    // --- 城市 ---
    extractCity(text) {
      const patterns = [
        /(?:城市|所在地|Base|Location|现居|所在城市|居住地)[：:\s]*([^\n,，。]{2,10})/i,
        /(?:北京|上海|广州|深圳|杭州|成都|武汉|南京|西安|重庆|苏州|天津|长沙|郑州|东莞|青岛|厦门|合肥|佛山|宁波|昆明|沈阳|大连|福州|无锡|济南)/,
      ];
      for (const p of patterns) { const m = text.match(p); if (m?.[1]) return m[1].trim(); if (m?.[0]) return m[0].trim(); }
      return null;
    },

    // --- 目标岗位 ---
    extractTargetJob(text) {
      const patterns = [
        /(?:岗位|职位|应聘|求职意向|意向岗位|意向职位|期望职位|目标岗位|Target|Objective)[：:\s]*([^\n,，]{2,30})/i,
        /(?:前端|后端|全栈|产品|设计|运营|市场|销售|算法|数据|测试|开发|工程师|经理|总监|专员|主管|架构师)/,
      ];
      for (const p of patterns) { const m = text.match(p); if (m?.[1]) return m[1].trim(); if (m?.[0]) return m[0].trim(); }
      return null;
    },

    // --- 薪资 ---
    extractSalary(text) {
      const patterns = [
        /(?:薪资|期望薪资|薪酬|期望月薪|期望年薪|Salary|期望)[：:\s]*([^\n,，。]{2,20})/i,
        /(\d+[kK]\s*[-–—~至到]\s*\d+[kK])/,
        /(\d+[,，]?\d*\s*[-–—~至到]\s*\d+[,，]?\d*\s*(?:元|块|万|k|K|千|万\/月|K\/月|元\/月))/,
      ];
      for (const p of patterns) { const m = text.match(p); if (m?.[1]) return m[1].trim(); }
      return null;
    },

    // --- 出生日期/年龄 ---
    extractBirth(text) {
      const m = text.match(/(?:出生|生日|出生日期|生日日期)[：:\s]*(\d{4}[年.\-/]\d{1,2}[月.\-/]\d{1,2}[日]?|\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})/);
      return m?.[1]?.trim() || null;
    },

    extractAge(text) {
      const m = text.match(/(?:年龄)[：:\s]*(\d{1,2})\s*(?:岁)?/);
      return m?.[1]?.trim() || null;
    },

    extractGender(text) {
      const m = text.match(/(?:性别)[：:\s]*(男|女|Male|Female)/i);
      return m?.[1]?.trim() || null;
    },

    // --- 教育经历 ---
    extractEducation(text) {
      const section = extractSectionByKeywords(text, [
        '教育经历', '教育背景', '学历背景', '教育', '学历', '学习经历',
        'Education', 'EDUCATION', 'Educational',
      ]);
      if (!section) return [];

      const entries = [];
      // Split by school entries — detect school line pattern
      const lines = section.split('\n').filter(l => l.trim());
      let current = null;

      for (const line of lines) {
        const trimmed = line.trim();
        // Detect new education entry: line containing school name + date
        const isNewEntry = (
          /(?:大学|学院|University|College|School|高中|中学|一中|二中|三中|附中|实验|师范)/i.test(trimmed) &&
          (/\d{4}/.test(trimmed) || trimmed.length < 60)
        ) || (
          /^\d{4}[.\-/年]\d{1,2}\s*[-–—~至到]\s*(?:\d{4}[.\-/年]\d{1,2}|至今|现在|present)/.test(trimmed)
        );

        if (isNewEntry || !current) {
          if (current && current.school) entries.push(current);
          current = { school: null, major: null, degree: null, start: null, end: null, awards: [], source_index: [] };
        }

        if (!current) current = { school: null, major: null, degree: null, start: null, end: null, awards: [], source_index: [] };

        // Extract school
        if (!current.school) {
          const schoolM = trimmed.match(/([一-鿿A-Za-z\s()（）]+(?:大学|学院|University|College|School|高中|中学|一中|二中|三中|附中))/i);
          if (schoolM) current.school = schoolM[1].trim();
        }

        // Extract major
        if (!current.major) {
          const majorM = trimmed.match(/(?:专业|主修|Major)[：:\s]*([^\n,，。]{2,40})/i);
          if (majorM) current.major = majorM[1].trim();
          else {
            const majorPattern = trimmed.match(/([^\n,，。\d]{2,20}(?:工程|科学|管理|设计|文学|语言|法学|医学|经济|教育|艺术|哲学|历史))/);
            if (majorPattern && !current.school) current.major = majorPattern[1].trim();
          }
        }

        // Extract degree
        if (!current.degree) {
          const degM = trimmed.match(/(?:学历|学位|Degree)[：:\s]*([^\n,，。]{2,15})/i);
          if (degM) current.degree = degM[1].trim();
          else {
            const degPattern = trimmed.match(/(本科|硕士|博士|大专|学士|硕士|博士|MBA|EMBA|高中|中专|技校)/);
            if (degPattern) current.degree = degPattern[1].trim();
          }
        }

        // Extract dates
        const dateRange = extractDateRange(trimmed);
        if (dateRange) { current.start = dateRange.start; current.end = dateRange.end; }

        // Awards
        const awardM = trimmed.match(/(?:获奖|奖学金|荣誉|Award|Scholarship)[：:\s]*([^\n]{2,60})/i);
        if (awardM) current.awards.push(awardM[1].trim());
        const gpaM = trimmed.match(/(?:GPA|绩点|平均分)[：:\s]*([\d.]+(?:\/[\d.]+)?)/);
        if (gpaM) current.awards.push('GPA: ' + gpaM[1].trim());

        // If single line has school + major + date
        if (current.school && !current.major && !current.start) {
          const rest = trimmed.replace(current.school, '').trim();
          const dateR = extractDateRange(rest);
          if (dateR) { current.start = dateR.start; current.end = dateR.end; }
          const majorR = rest.replace(/\d{4}.*$/, '').trim();
          if (majorR && majorR.length >= 2) current.major = majorR;
        }
      }
      if (current && current.school) entries.push(current);

      return entries;
    },

    // --- 工作/实习经历 ---
    extractWorkExperience(text) {
      const section = extractSectionByKeywords(text, [
        '工作经历', '工作经验', '实习经历', '工作履历', '职业经历', '从业经历',
        'Work Experience', 'WORK EXPERIENCE', 'Employment', 'Professional Experience',
      ]);
      if (!section) return [];

      const entries = [];
      const lines = section.split('\n').filter(l => l.trim());
      let current = null;
      let duties = [];

      for (let i = 0; i < lines.length; i++) {
        const trimmed = lines[i].trim();

        // Detect new entry: company name pattern or date range
        const isCompanyLine = (
          /(?:公司|集团|有限|科技|网络|信息|技术|银行|证券|保险|医院|学校|政府|研究院|所|厂|店|平台)/.test(trimmed) ||
          /^[一-鿿A-Za-z&·]{2,30}(?:公司|集团|有限|科技|网络|信息|技术)/.test(trimmed)
        );
        const dateAtStart = /^\d{4}[.\-/年]\d{1,2}/.test(trimmed);
        const hasDateRange = extractDateRange(trimmed);

        if ((isCompanyLine || dateAtStart) && (hasDateRange || trimmed.length < 80)) {
          // Save previous
          if (current) {
            if (duties.length) current.duties = duties.join('\n');
            entries.push(current);
          }
          current = { company: null, position: null, start: null, end: null, duties: '', achievements: [], source_index: [] };
          duties = [];

          // Extract company
          const compM = trimmed.match(/([一-鿿A-Za-z&·()（）\s]{2,40}(?:公司|集团|有限|科技|网络|信息|技术|银行|证券|保险|医院|学校|政府|研究院|所))/);
          if (compM) current.company = compM[1].trim();

          // Extract position
          const posM = trimmed.match(/([^\n,，]{2,20}(?:工程师|经理|专员|设计师|运营|主管|总监|架构师|开发|测试|代表|顾问|助理|实习生|管培生))/);
          if (posM) current.position = posM[1].trim();

          // Extract dates
          const dates = extractDateRange(trimmed);
          if (dates) { current.start = dates.start; current.end = dates.end; }

          // If line contains remaining text as duties
          const rest = trimmed.replace(current.company || '', '').replace(current.position || '', '').replace(/\d{4}.*?(?:至今|现在|present)?/, '').trim();
          if (rest && rest.length > 5 && !rest.match(/^[：:]/)) duties.push(rest);
        } else if (current) {
          // Achievement/bullet point
          if (/^[•\-*\d+\.、▸►○●◆■✔✅]\s*/.test(trimmed)) {
            const content = trimmed.replace(/^[•\-*\d+\.、▸►○●◆■✔✅]\s*/, '').trim();
            if (content) current.achievements.push(content);
          } else if (trimmed.length > 3) {
            duties.push(trimmed);
          }
        }
      }
      if (current) {
        if (duties.length) current.duties = duties.join('\n');
        entries.push(current);
      }

      return entries;
    },

    // --- 项目经历 ---
    extractProjects(text) {
      const section = extractSectionByKeywords(text, [
        '项目经历', '项目经验', '项目', '主要项目', 'Projects', 'PROJECTS', 'Project Experience',
      ]);
      if (!section) return [];

      const entries = [];
      const lines = section.split('\n').filter(l => l.trim());
      let current = null;
      let descLines = [];

      for (const line of lines) {
        const trimmed = line.trim();

        // Detect new project: name + date or standalone project name
        const isProjLine = (
          /项目[名称]*[：:]\s*/.test(trimmed) ||
          (/^[一-鿿A-Za-z「【《].{2,40}[」】》]/.test(trimmed) && trimmed.length < 60) ||
          (/\d{4}[.\-/年]/.test(trimmed) && !/^[•\-*\d+\.、]/.test(trimmed))
        );

        if (isProjLine && !current) {
          current = { name: null, role: null, description: '', technologies: [], results: null, source_index: [] };
          descLines = [];
          const nameM = trimmed.match(/(?:项目[名称]*[：:]\s*)?([一-鿿A-Za-z「【《].{2,50}[」】》]?)/);
          if (nameM) current.name = nameM[1].trim();
          else current.name = trimmed.substring(0, 50).trim();
          const roleM = trimmed.match(/(?:角色|职责|担任|Role)[：:\s]*([^\n,，]{2,30})/i);
          if (roleM) current.role = roleM[1].trim();
          const dates = extractDateRange(trimmed);
          if (dates) current.period = `${dates.start}-${dates.end}`;
          const techM = trimmed.match(/(?:技术栈|技术|Tech|Stack)[：:\s]*([^\n,，]{3,80})/i);
          if (techM) current.technologies = techM[1].split(/[,，、\s]+/).filter(Boolean);
        } else if (current) {
          if (trimmed.length > 3) {
            if (/^[•\-*\d+\.、▸►○●◆■✔✅]/.test(trimmed)) {
              descLines.push(trimmed.replace(/^[•\-*\d+\.、▸►○●◆■✔✅]\s*/, ''));
            } else {
              descLines.push(trimmed);
            }
          }
          // End of project on blank line or next clear project header
        }
      }
      if (current) {
        current.description = descLines.join('\n');
        // Extract tech stack from description
        if (!current.technologies?.length) {
          current.technologies = findTechStack(descLines.join(' '));
        }
        entries.push(current);
      }

      return entries;
    },

    // --- 技能 ---
    extractSkills(text) {
      const section = extractSectionByKeywords(text, [
        '技能', '专业技能', '技术栈', '技术能力', '掌握技能', '职业技能',
        'Skills', 'SKILLS', 'Technical Skills', 'Technologies',
      ]);
      if (!section) return [];

      const skills = [];
      const techPatterns = findTechStack(section);

      // Also try categorized skills
      const categories = [
        { name: '编程语言', pattern: /(?:编程语言|语言|Language)[：:\s]*([^\n]{5,100})/i },
        { name: '框架', pattern: /(?:框架|Framework)[：:\s]*([^\n]{5,100})/i },
        { name: '数据库', pattern: /(?:数据库|Database|DB)[：:\s]*([^\n]{5,100})/i },
        { name: '工具', pattern: /(?:工具|开发工具|Tool)[：:\s]*([^\n]{5,100})/i },
        { name: '设计', pattern: /(?:设计|Design)[：:\s]*([^\n]{5,100})/i },
      ];

      categories.forEach(cat => {
        const m = section.match(cat.pattern);
        if (m) {
          m[1].split(/[,，、\s/|]+/).filter(s => s.trim().length >= 1).forEach(s => {
            const name = s.trim();
            if (name && !skills.find(sk => sk.name === name)) {
              skills.push({ name, category: cat.name, source_index: [] });
            }
          });
        }
      });

      // Add any remaining tech patterns not in categories
      techPatterns.forEach(name => {
        if (!skills.find(s => s.name.toLowerCase() === name.toLowerCase())) {
          skills.push({ name, category: '技术', source_index: [] });
        }
      });

      return skills;
    },

    // --- 证书 ---
    extractCertificates(text) {
      const section = extractSectionByKeywords(text, [
        '证书', '资格证书', '证书资质', 'Certificates', 'CERTIFICATES', 'Certifications',
      ]);
      if (!section) return [];

      const certs = [];
      const lines = section.split(/[,，、\n]/).filter(l => l.trim());
      lines.forEach(line => {
        const trimmed = line.trim();
        if (trimmed.length >= 2) {
          const dateM = trimmed.match(/(\d{4}[.\-/年]\d{1,2}[.\-/月]?\d{0,2}[日]?)/);
          certs.push({
            name: dateM ? trimmed.replace(dateM[0], '').trim() : trimmed,
            date: dateM?.[1] || null,
            source_index: [],
          });
        }
      });
      return certs;
    },

    // --- 语言能力 ---
    extractLanguages(text) {
      const section = extractSectionByKeywords(text, [
        '语言', '外语', '语言能力', 'Languages', 'LANGUAGES',
      ]);
      if (!section) return [];
      const langs = [];
      const patterns = [
        /(英语|英文|English|日语|日文|Japanese|韩语|韩文|Korean|法语|French|德语|German|西班牙语|Spanish)[：:\s]*[（(]?([^,，、\n]{2,10})[）)]?/gi,
        /(CET[-\s]?[46])[：:\s]*(\d+)?/i,
        /(雅思|IELTS|托福|TOEFL|托业|TOEIC)[：:\s]*(\d+\.?\d*)/i,
      ];
      patterns.forEach(p => {
        let m;
        while ((m = p.exec(section)) !== null) {
          langs.push({ name: m[1]?.trim(), level: m[2]?.trim() || null, source_index: [] });
        }
      });
      return langs;
    },

    // --- 自我评价 ---
    extractSelfAssessment(text) {
      const section = extractSectionByKeywords(text, [
        '自我评价', '自我介绍', '个人评价', '自我描述', '个人简介', '关于我',
        'Self-Assessment', 'Summary', 'About Me', 'Profile', 'Personal Statement',
      ]);
      return section || null;
    },
  };

  // ================================================================
  // Enhanced regex fallback extraction (6-pass multi-layer)
  // ================================================================
  function regexFallbackExtraction(text, lang) {
    const clean = normalizeText(text);
    const result = JSON.parse(JSON.stringify(SMART_RESUME_SCHEMA));
    const lines = clean.split('\n').filter(l => l.trim());

    // === PASS 1: Basic Info ===
    const parser = PyResParser;
    result.basic_info = {
      name: parser.extractName(clean),
      phone: parser.extractPhone(clean),
      email: parser.extractEmail(clean),
      city: parser.extractCity(clean),
      target_job: parser.extractTargetJob(clean),
      salary: parser.extractSalary(clean),
      source_index: [0],
    };

    // === PASS 2: Education (multi-entry) ===
    result.education = parser.extractEducation(clean).map(e => ({
      school: e.school, major: e.major, degree: e.degree,
      start: e.start, end: e.end,
      awards: e.awards?.length ? e.awards : null,
      source_index: [],
    }));

    // === PASS 3: Work Experience (multi-entry with duties) ===
    result.work_experience = parser.extractWorkExperience(clean).map(w => ({
      company: w.company, position: w.position,
      start: w.start, end: w.end,
      duties: w.duties || null,
      achievements: w.achievements?.length ? w.achievements : null,
      source_index: [],
    }));

    // === PASS 4: Projects ===
    result.projects = parser.extractProjects(clean).map(p => ({
      name: p.name, role: p.role,
      description: p.description || null,
      technologies: p.technologies?.length ? p.technologies : null,
      results: p.results || null,
      source_index: [],
    }));

    // === PASS 5: Skills + Certs ===
    result.skills = parser.extractSkills(clean);
    result.certificates = parser.extractCertificates(clean);

    // === PASS 6: Self-Assessment ===
    const selfText = parser.extractSelfAssessment(clean);
    if (selfText) result.self_assessment = { text: selfText, source_index: [] };

    return result;
  }

  // ================================================================
  // Standard Resume Template — enforces format on generation
  // ================================================================
  const STANDARD_TEMPLATE = {
    sections: ['basic_info', 'self_assessment', 'education', 'work_experience', 'projects', 'skills', 'certificates'],
    labels: {
      zh: {
        basic_info: '基本信息',
        self_assessment: '自我评价',
        education: '教育经历',
        work_experience: '工作经历',
        projects: '项目经历',
        skills: '技能证书',
        certificates: '资质证书',
      },
      en: {
        basic_info: 'Basic Information',
        self_assessment: 'Professional Summary',
        education: 'Education',
        work_experience: 'Work Experience',
        projects: 'Projects',
        skills: 'Skills & Certifications',
        certificates: 'Certificates',
      },
    },

    // Format a resume section into standard display format
    formatSection(section, data, lang) {
      switch (section) {
        case 'basic_info':
          return formatBasicInfo(data, lang);
        case 'education':
          return formatEducation(data.education || [], lang);
        case 'work_experience':
          return formatWorkExperience(data.work_experience || [], lang);
        case 'projects':
          return formatProjects(data.projects || [], lang);
        case 'skills':
          return formatSkills(data.skills || [], lang);
        case 'certificates':
          return formatCertificates(data.certificates || [], lang);
        case 'self_assessment':
          return data.self_assessment?.text || '';
        default:
          return '';
      }
    },
  };

  function formatBasicInfo(data, lang) {
    const bi = data.basic_info || {};
    const lines = [];
    if (bi.name) lines.push(bi.name);
    const contact = [bi.phone, bi.email, bi.city].filter(Boolean).join(' | ');
    if (contact) lines.push(contact);
    if (bi.target_job) lines.push((lang === 'zh' ? '应聘：' : 'Position: ') + bi.target_job);
    return lines.join('\n');
  }

  function formatEducation(entries, lang) {
    if (!entries.length) return '';
    return entries.map(e =>
      [e.school, e.major, e.degree, [e.start, e.end].filter(Boolean).join(' - ')]
        .filter(Boolean).join(' | ')
    ).join('\n');
  }

  function formatWorkExperience(entries, lang) {
    if (!entries.length) return '';
    return entries.map(w => {
      const header = [w.company, w.position, [w.start, w.end].filter(Boolean).join(' - ')].filter(Boolean).join(' | ');
      const body = w.duties || (w.achievements || []).map(a => '• ' + a).join('\n');
      return header + (body ? '\n' + body : '');
    }).join('\n\n');
  }

  function formatProjects(entries, lang) {
    if (!entries.length) return '';
    return entries.map(p => {
      const header = [p.name, p.role].filter(Boolean).join(' | ');
      const tech = p.technologies?.length ? (lang === 'zh' ? '技术栈：' : 'Tech: ') + p.technologies.join('、') : '';
      return [header, tech, p.description].filter(Boolean).join('\n');
    }).join('\n\n');
  }

  function formatSkills(skills, lang) {
    if (!skills.length) return '';
    // Group by category
    const groups = {};
    skills.forEach(s => {
      const cat = s.category || (lang === 'zh' ? '其他' : 'Other');
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(s.name);
    });
    return Object.entries(groups).map(([cat, names]) =>
      `${cat}：${names.join('、')}`
    ).join('\n');
  }

  function formatCertificates(certs, lang) {
    if (!certs.length) return '';
    return certs.map(c => c.date ? `${c.name} (${c.date})` : c.name).join('、');
  }

  // ================================================================
  // Helper Utilities
  // ================================================================
  function normalizeText(text) {
    if (!text) return '';
    return text
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
      .replace(/[ \t]{3,}/g, '  ')
      .replace(/\n{3,}/g, '\n\n')
      .replace(/[［［]/g, '【')
      .replace(/[］］]/g, '】')
      .trim();
  }

  function extractSectionByKeywords(text, keywords) {
    const lines = text.split('\n');
    let startIdx = -1;
    let endIdx = lines.length;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (startIdx === -1 && keywords.some(k => line.includes(k)) && line.length < 40) {
        startIdx = i + 1;
        continue;
      }
      if (startIdx !== -1) {
        // Stop at next section header
        const allSectionKWs = [
          '教育', '学历', '工作', '实习', '职业', '项目', '技能', '证书',
          '自我', '个人', '介绍', '语言', '联系', '基本',
          'Education', 'Work', 'Experience', 'Project', 'Skill', 'Certificate',
          'Summary', 'Profile', 'Language', 'Contact',
        ];
        if (allSectionKWs.some(k => line.includes(k)) && line.length < 35 &&
            !keywords.some(k => line.includes(k))) {
          endIdx = i;
          break;
        }
      }
    }

    if (startIdx === -1) return null;
    return lines.slice(startIdx, endIdx).join('\n').trim();
  }

  function extractDateRange(text) {
    if (!text) return null;
    const patterns = [
      /(\d{4}[.\-/年]\d{1,2}[.\-/月]?\d{0,2}[日]?)\s*[-–—~至到]\s*(\d{4}[.\-/年]\d{1,2}[.\-/月]?\d{0,2}[日]?|至今|现在|present|now)/i,
      /(\d{4}[.\-/年]\d{1,2})\s*[-–—~至到]\s*(\d{4}[.\-/年]\d{1,2}|至今|现在|present|now)/i,
      /(\d{4})\s*[-–—~至到]\s*(\d{4}|至今|现在|present|now)/i,
      /(\d{4}[.\-/年])?\s*[-–—~至到]\s*(\d{4}[.\-/年]?|至今|现在|present|now)/i,
    ];
    for (const p of patterns) {
      const m = text.match(p);
      if (m) return { start: m[1]?.trim() || null, end: m[2]?.trim() || null };
    }
    return null;
  }

  function findTechStack(text) {
    const patterns = [
      /python/i, /java\b/i, /javascript/i, /typescript/i, /react/i, /vue/i, /angular/i,
      /node\.?js/i, /golang/i, /rust/i, /c\+\+/i, /c#/i, /\.net/i, /php/i, /ruby/i, /swift/i, /kotlin/i,
      /sql/i, /mysql/i, /postgresql/i, /mongodb/i, /redis/i, /oracle/i, /sqlite/i,
      /docker/i, /kubernetes/i, /k8s/i, /aws/i, /azure/i, /gcp/i, /阿里云/i, /腾讯云/i,
      /tensorflow/i, /pytorch/i, /scikit/i, /pandas/i, /numpy/i, /spark/i, /hadoop/i, /flink/i,
      /figma/i, /sketch/i, /photoshop/i, /illustrator/i, /premiere/i, /after\s*effects/i, /canva/i,
      /git/i, /github/i, /gitlab/i, /jenkins/i, /jira/i, /confluence/i, /notion/i,
      /excel/i, /word/i, /ppt/i, /powerpoint/i, /tableau/i, /power\s*bi/i,
      /html/i, /css/i, /sass/i, /less/i, /webpack/i, /vite/i, /babel/i, /eslint/i,
      /nginx/i, /apache/i, /tomcat/i, /linux/i, /unix/i, /shell/i, /bash/i,
      /小程序/i, /公众号/i, /企业微信/i, /uniapp/i, /flutter/i, /react\s*native/i,
      /spring/i, /django/i, /flask/i, /express/i, /koa/i, /next\.?js/i, /nuxt/i,
    ];
    return [...new Set(patterns.filter(p => p.test(text)).map(p => {
      const m = text.match(p); return m ? m[0] : '';
    }).filter(Boolean))];
  }

  // ================================================================
  // MAIN PIPELINE (unchanged structure, uses enhanced extraction)
  // ================================================================
  async function runFullPipeline(file, options = {}) {
    const lang = options.lang || I18N.getLang();
    const onProgress = options.onProgress || (() => {});
    const pipelineLog = [];
    function log(msg, type = 'info') { pipelineLog.push({ time: Date.now(), msg, type }); onProgress({ stage: msg, log: pipelineLog, type }); console.log(`[Pipeline] ${msg}`); }

    try {
      log(lang === 'zh' ? '📄 步骤1/6: 文件预处理分流...' : '📄 Step 1/6: File routing...');
      const ext = (file.name || '').split('.').pop()?.toLowerCase() || 'txt';
      let corpus = '';

      if (ext === 'pdf') {
        log('  → PDF文件 → MinerU布局解析');
        const parsed = await parsePDFToCorpus(file);
        corpus = parsed.corpus || '';
        log(`  ✅ 解析完成: ${parsed.totalLines || 0} 行索引`);
      } else if (['png','jpg','jpeg','webp','bmp'].includes(ext)) {
        log('  → 图片文件 → OCR识别');
        const parsed = await parseImageToCorpus(file);
        corpus = parsed.corpus || '';
        log(`  ✅ OCR完成`);
      } else {
        log('  → 文本直接索引');
        corpus = await file.text();
        corpus = corpus.split('\n').filter(l => l.trim()).map((t, i) => `[${i}] ${t}`).join('\n');
      }

      if (!corpus || corpus.length < 5) {
        return { success: false, error: '文件内容为空或无法识别', log: pipelineLog };
      }

      // === Step 2: Hard field regex ===
      log('🔍 步骤2/6: 硬字段正则预提取...');
      const hardFields = PyResParser.extract(corpus);
      const hfCount = ['name','phone','email'].filter(k => hardFields[k]).length;
      log(`  ✅ 提取 ${hfCount}/3 核心字段`);

      // === Step 3: Full extraction ===
      log('🤖 步骤3/6: 深度结构化抽取...');
      let extracted;
      if (window.DeepSeekAPI?.getApiKey()) {
        try {
          const llmResult = await DeepSeekAPI.chatCompletion({
            messages: [{ role: 'user', content: buildExtractionPrompt(corpus, lang) }],
            taskType: 'enhanced',
            options: { maxTokens: 4096, temperature: 0.01, extractionText: corpus, systemPrompt: null },
          });
          if (llmResult.success && llmResult.content) {
            const parsed = parseJSONSafely(llmResult.content);
            if (parsed) extracted = parsed;
          }
        } catch (e) { log(`  ⚠️ LLM调用失败: ${e.message}`, 'warning'); }
      }
      if (!extracted) {
        log('  → 使用增强规则引擎抽取');
        extracted = regexFallbackExtraction(corpus, lang);
      }
      // Merge hard fields
      extracted.basic_info = { ...extracted.basic_info, name: hardFields.name || extracted.basic_info?.name, phone: hardFields.phone || extracted.basic_info?.phone, email: hardFields.email || extracted.basic_info?.email };
      log(`  ✅ 抽取: ${extracted.education?.length||0}教育 ${extracted.work_experience?.length||0}工作 ${extracted.projects?.length||0}项目 ${extracted.skills?.length||0}技能`);

      // === Step 4: Schema Lock ===
      log('🔒 步骤4/6: Schema格式锁死...');
      const locked = SchemaValidator.lockSchema(extracted);
      log('  ✅ 已锁定');

      // === Step 5: Validation ===
      log('🛡️ 步骤5/6: 双重校验...');
      const validation = SchemaValidator.validate(locked, corpus);
      log(`  ✅ 缺失${validation.missingFields.length}字段 空白${validation.emptySections.length}模块`);

      // === Step 6: Import to Store ===
      log('📦 步骤6/6: 写入素材库...');
      if (window.MaterialStore) { MaterialStore.reset(); importToStore(locked, file.name); log('  ✅ 素材库已更新'); }

      log('🎉 流水线完成！');
      return { success: true, data: locked, hardFields, validation, log: pipelineLog };
    } catch (err) {
      log(`❌ 异常: ${err.message}`, 'error');
      return { success: false, error: err.message, log: pipelineLog };
    }
  }

  // === PDF/Image parsing helpers ===
  async function parsePDFToCorpus(file) {
    if (typeof window.pdfjsLib === 'undefined') {
      const text = await file.text();
      const lines = text.split('\n').filter(l => l.trim().length > 1);
      return { corpus: lines.map((t, i) => `[${i}] ${t}`).join('\n'), totalLines: lines.length };
    }
    try {
      const buf = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
      let allLines = [], idx = 0;
      for (let p = 1; p <= pdf.numPages; p++) {
        const page = await pdf.getPage(p);
        const tc = await page.getTextContent();
        const items = tc.items.map(it => ({ text: it.str, y: Math.round(it.transform[5]), x: Math.round(it.transform[4]), fs: it.transform[0] }));
        items.sort((a, b) => a.y - b.y || a.x - b.x);
        let lineY = null, curLine = [];
        items.forEach(it => {
          if (lineY === null || Math.abs(it.y - lineY) > 6) {
            if (curLine.length) { allLines.push(`[${idx++}] ` + curLine.sort((a,b) => a.x-b.x).map(i => i.text).join(' ')); }
            curLine = [it]; lineY = it.y;
          } else { curLine.push(it); }
        });
        if (curLine.length) allLines.push(`[${idx++}] ` + curLine.sort((a,b) => a.x-b.x).map(i => i.text).join(' '));
      }
      return { corpus: allLines.join('\n'), totalLines: idx };
    } catch (e) {
      const text = await file.text();
      const lines = text.split('\n').filter(l => l.trim());
      return { corpus: lines.map((t, i) => `[${i}] ${t}`).join('\n'), totalLines: lines.length };
    }
  }

  async function parseImageToCorpus(file) {
    const dataURL = await new Promise((res, rej) => { const r = new FileReader(); r.onload = e => res(e.target.result); r.onerror = rej; r.readAsDataURL(file); });
    if (window.DeepSeekAPI?.getApiKey()) {
      const result = await DeepSeekAPI.visionRecognition(dataURL, '请逐行识别并提取图片中的所有文字内容，保留原文格式。数字、日期、公司名、学校名、专业名必须精确提取。');
      if (result.success && result.content) {
        const lines = result.content.split('\n').filter(l => l.trim());
        return { corpus: lines.map((t, i) => `[${i}] ${t}`).join('\n'), totalLines: lines.length };
      }
    }
    if (window.Tesseract) {
      const r = await Tesseract.recognize(dataURL, 'chi_sim+eng');
      const lines = r.data.text.split('\n').filter(l => l.trim());
      return { corpus: lines.map((t, i) => `[${i}] ${t}`).join('\n'), totalLines: lines.length };
    }
    return { corpus: '', totalLines: 0 };
  }

  function buildExtractionPrompt(corpus, lang) {
    return (lang === 'zh'
      ? `你是顶级简历解析专家。从下方简历文本中提取结构化信息。\n\n## Schema\n${JSON.stringify(SMART_RESUME_SCHEMA, null, 2)}\n\n## 规则\n1. 每个字段标注source_index(原文行号)\n2. 不存在→null\n3. 只输出纯JSON\n\n## 简历\n${corpus}`
      : `[English extraction prompt]\n\n${corpus}`);
  }

  // === Schema Validator (enhanced) ===
  const SchemaValidator = {
    validate(extracted, corpus) {
      const report = { valid: true, missingFields: [], ungroundedFields: [], emptySections: [], warnings: [] };
      if (!extracted.basic_info?.name) report.missingFields.push('姓名');
      if (!extracted.basic_info?.phone) report.missingFields.push('电话');
      if (!extracted.basic_info?.email) report.missingFields.push('邮箱');
      if (!extracted.education?.length) report.emptySections.push('教育经历');
      if (!extracted.work_experience?.length) report.emptySections.push('工作经历');
      if (!extracted.projects?.length) report.emptySections.push('项目经历');
      if (!extracted.skills?.length) report.emptySections.push('技能');
      report.ungroundedFields = verifyGrounding(extracted, corpus);
      report.valid = report.ungroundedFields.length === 0 && report.emptySections.length === 0;
      return report;
    },
    lockSchema(data) {
      const allowed = {
        basic_info: ['name','phone','email','city','target_job','salary','onboard_time','source_index'],
        education: ['school','major','degree','start','end','awards','source_index'],
        work_experience: ['company','position','start','end','duties','achievements','source_index'],
        projects: ['name','role','description','technologies','results','source_index'],
        skills: ['name','level','category','source_index'],
        certificates: ['name','date','source_index'],
        self_assessment: ['text','source_index'],
      };
      for (const [section, fields] of Object.entries(allowed)) {
        if (Array.isArray(data[section])) {
          data[section] = data[section].map(item => { const c = {}; fields.forEach(f => { if (item[f] !== undefined) c[f] = item[f]; }); return c; });
        } else if (data[section] && typeof data[section] === 'object') {
          const c = {}; fields.forEach(f => { if (data[section][f] !== undefined) c[f] = data[section][f]; }); data[section] = c;
        }
      }
      function nullify(obj) { for (const k of Object.keys(obj)) { if (obj[k] === '' || obj[k] === '无' || obj[k] === '暂无' || obj[k] === '目标岗位从业者') obj[k] = null; if (Array.isArray(obj[k]) && obj[k].length === 0 && k !== 'source_index') obj[k] = null; } }
      nullify(data.basic_info || {}); (data.education || []).forEach(nullify); (data.work_experience || []).forEach(nullify); (data.projects || []).forEach(nullify); if (data.self_assessment) nullify(data.self_assessment);
      return data;
    },
  };

  function verifyGrounding(extracted, corpus) {
    const ungrounded = [];
    function check(val, path) { if (typeof val === 'string' && val.length > 3 && !corpus.includes(val)) { const words = val.split(/[\s,，、。]+/).filter(w => w.length >= 2); const matched = words.filter(w => corpus.includes(w)); if (matched.length / Math.max(1, words.length) < 0.6) ungrounded.push(path); } }
    check(extracted.basic_info?.name, '姓名'); check(extracted.basic_info?.phone, '电话'); check(extracted.basic_info?.email, '邮箱');
    (extracted.work_experience || []).forEach((w, i) => { check(w.company, `工作${i+1}-公司`); check(w.position, `工作${i+1}-职位`); });
    return ungrounded;
  }

  function importToStore(data, fileName) {
    const s = MaterialStore;
    const bi = data.basic_info || {};
    if (bi.name) s.setIdentity('name', bi.name, fileName);
    if (bi.phone) s.setIdentity('phone', bi.phone, fileName);
    if (bi.email) s.setIdentity('email', bi.email, fileName);
    if (bi.city) s.setIdentity('city', bi.city, fileName);
    if (bi.target_job) s.setIdentity('targetJob', bi.target_job, fileName);
    if (bi.salary) s.setIdentity('salary', bi.salary, fileName);
    (data.education || []).forEach(e => s.addEducation({ school: e.school, major: e.major, degree: e.degree, period: [e.start, e.end].filter(Boolean).join('-'), raw: [e.school, e.major, e.degree].filter(Boolean).join(' / ') }, fileName));
    (data.work_experience || []).forEach(w => s.addWorkExperience({ company: w.company, position: w.position, period: [w.start, w.end].filter(Boolean).join('-'), duties: w.duties || (w.achievements || []).join('; '), raw: [w.company, w.position, w.duties].filter(Boolean).join(' / ') }, fileName));
    (data.projects || []).forEach(p => s.addProject({ name: p.name, role: p.role, description: p.description, raw: [p.name, p.description].filter(Boolean).join(' / ') }, fileName));
    (data.skills || []).forEach(s => s.addSkill(typeof s === 'string' ? s : s.name, typeof s === 'string' ? '通用' : (s.category || '通用'), fileName));
    (data.certificates || []).forEach(c => s.addCertificate(typeof c === 'string' ? c : c.name, fileName));
    if (data.self_assessment?.text) s.setSelfIntro(data.self_assessment.text, fileName);
  }

  function parseJSONSafely(str) {
    try { const m = str.match(/```(?:json)?\s*([\s\S]*?)```/) || str.match(/(\{[\s\S]*\})/); return JSON.parse((m ? m[1] : str).trim()); } catch (e) { return null; }
  }

  // ================================================================
  // Export
  // ================================================================
  return {
    SMART_RESUME_SCHEMA, STANDARD_TEMPLATE,
    MinerUPDFSkill: { parse: parsePDFToCorpus },
    DeepSeekOCRSkill: { recognize: parseImageToCorpus },
    SmartResumeSkill: { extract: regexFallbackExtraction },
    SchemaValidator, PyResParser,
    runFullPipeline, importToStore, regexFallbackExtraction,
  };
})();

window.ExtractionPipeline = ExtractionPipeline;
