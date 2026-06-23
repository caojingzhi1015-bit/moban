/* ============================================================
   resume-engine.js - AI简历生成引擎 + Word/PDF导出
   支持：自由文本输入 + 图片上传 + 自动信息提取
   Resume Generation & Bilingual Export (Word/PDF)
   ============================================================ */

const ResumeEngine = (() => {
  let currentResumeData = null;
  let questionnaireAnswers = {};

  // === JD Parsing (supports both text and image-derived text) ===
  function parseJD(jdText) {
    if (!jdText || !jdText.trim()) return { hardSkills: [], softSkills: [], industry: [] };

    const keywords = {
      hardSkills: [],
      softSkills: [],
      industry: [],
    };

    // Hard skill patterns (comprehensive)
    const hardPatterns = [
      /python/i, /java\b/i, /javascript/i, /typescript/i, /react/i, /vue/i, /angular/i,
      /node\.?js/i, /golang/i, /rust/i, /c\+\+/i, /sql/i, /mysql/i, /postgresql/i,
      /mongodb/i, /redis/i, /docker/i, /kubernetes/i, /k8s/i, /aws/i, /azure/i, /gcp/i,
      /tensorflow/i, /pytorch/i, /machine\s*learning/i, /deep\s*learning/i, /nlp/i, /llm/i,
      /excel/i, /tableau/i, /power\s*bi/i, /spark/i, /hadoop/i, /flink/i,
      /figma/i, /sketch/i, /photoshop/i, /illustrator/i, /after\s*effects/i, /canva/i,
      /短视频/i, /抖音/i, /快手/i, /小红书/i, /b站/i, /bilibili/i, /youtube/i, /tiktok/i,
      /微信/i, /微博/i, /公众号/i, /社群/i, /私域/i, /小程序/i, /视频号/i,
      /seo/i, /sem/i, /信息流/i, /竞价/i, /广告投放/i, /千川/i, /巨量/i,
      /直播/i, /带货/i, /电商/i, /天猫/i, /京东/i, /拼多多/i, /shopify/i,
      /数据分析/i, /用户研究/i, /ab\s*test/i, /增长/i, /用户增长/i, /黑客增长/i,
      /项目管理/i, /敏捷/i, /scrum/i, /jira/i, /confluence/i, /notion/i,
      /linux/i, /git/i, /ci\/cd/i, /jenkins/i, /terraform/i, /ansible/i,
      /photoshop/i, /premiere/i, /final\s*cut/i, /达芬奇/i, /剪映/i,
    ];

    const softPatterns = [
      /沟通/i, /协作/i, /团队合作/i, /领导力/i, /管理/i, /执行力/i,
      /抗压/i, /解决问题/i, /逻辑思维/i, /创新/i, /学习能力/i,
      /自驱/i, /责任心/i, /结果导向/i, /用户导向/i, /同理心/i,
      /跨部门/i, /推动/i, /影响力/i, /演讲/i, /汇报/i, /谈判/i,
      /ownership/i, /leadership/i, /communication/i, /team\s*work/i,
    ];

    const industryPatterns = [
      { pattern: /互联网/i, label: '互联网/IT' },
      { pattern: /金融/i, label: '金融' },
      { pattern: /教育/i, label: '教育' },
      { pattern: /医疗/i, label: '医疗健康' },
      { pattern: /电商/i, label: '电商/零售' },
      { pattern: /游戏/i, label: '游戏' },
      { pattern: /广告/i, label: '媒体/广告' },
      { pattern: /saas/i, label: 'SaaS/企业服务' },
      { pattern: /ai|人工智能|大模型/i, label: 'AI/人工智能' },
      { pattern: /汽车/i, label: '汽车/出行' },
      { pattern: /新能源/i, label: '新能源' },
      { pattern: /芯片|半导体/i, label: '芯片/半导体' },
    ];

    hardPatterns.forEach(p => {
      const match = jdText.match(p);
      if (match && !keywords.hardSkills.find(s => s.toLowerCase() === match[0].toLowerCase())) {
        keywords.hardSkills.push(match[0]);
      }
    });

    softPatterns.forEach(p => {
      const match = jdText.match(p);
      if (match && !keywords.softSkills.includes(match[0])) {
        keywords.softSkills.push(match[0]);
      }
    });

    industryPatterns.forEach(({ pattern, label }) => {
      if (pattern.test(jdText) && !keywords.industry.includes(label)) {
        keywords.industry.push(label);
      }
    });

    // Extract years
    const yearMatch = jdText.match(/(\d+)[\s-]*年(以上)?(工作经验|经验|工作年限)/);
    if (yearMatch) keywords.yearsRequired = yearMatch[1] + '年';

    // Extract education
    const eduMatch = jdText.match(/(本科|硕士|博士|大专|MBA|EMBA)(及以上|以上)?(学历)?/);
    if (eduMatch) keywords.educationRequired = eduMatch[0];

    // Extract salary range
    const salaryMatch = jdText.match(/(\d+[kK]-?\d*[kK]|\d+千-\d+千|\d+万-\d+万)/);
    if (salaryMatch) keywords.salaryRange = salaryMatch[0];

    return keywords;
  }

  // === Free-Form Personal Info Parsing ===
  function parseFreeFormPersonalInfo(text) {
    if (!text || !text.trim()) return {};

    const data = {};

    // Name extraction
    const nameMatch = text.match(/(?:姓名|名字|我是|我叫|名字是)[：:\s]*([^\n，。,.\d]{2,4})/);
    if (nameMatch) data.name = nameMatch[1].trim();

    // Phone
    const phoneMatch = text.match(/(?:电话|手机|联系方式|tel|phone)[：:\s]*(\d[\d\-+\s]{6,15})/i);
    if (phoneMatch) data.phone = phoneMatch[1].trim();

    // Email
    const emailMatch = text.match(/(?:邮箱|邮件|email|e-mail)[：:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i);
    if (emailMatch) data.email = emailMatch[1].trim();
    // Fallback: find any email
    if (!data.email) {
      const emailFallback = text.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
      if (emailFallback) data.email = emailFallback[1].trim();
    }

    // City
    const cityMatch = text.match(/(?:城市|地点|base|所在地|意向城市)[：:\s]*([^\n]{2,10})/);
    if (cityMatch) data.city = cityMatch[1].trim();

    // Salary
    const salaryMatch = text.match(/(?:薪资|期望薪资|薪资要求|薪酬)[：:\s]*([^\n]{2,20})/);
    if (salaryMatch) data.salary = salaryMatch[1].trim();

    // Job title
    const jobMatch = text.match(/(?:岗位|职位|应聘|目标岗位|求职意向|期望职位)[：:\s]*([^\n]{2,30})/);
    if (jobMatch) data.jobTitle = jobMatch[1].trim();

    // Experience years
    const expMatch = text.match(/(?:工作年限|经验|工作)[：:\s]*(\d+[\s-]*年)/);
    if (expMatch) data.experience = expMatch[1].trim();

    // Education section
    const eduSection = extractSection(text, ['教育', '教育经历', '学历', 'education']);
    if (eduSection) data.education = eduSection;

    // Work section
    const workSection = extractSection(text, ['工作经历', '工作', '实习', '职业经历', 'work experience', 'experience']);
    if (workSection) data.work = workSection;

    // Project section
    const projSection = extractSection(text, ['项目经历', '项目', 'project']);
    if (projSection) data.project = projSection;

    // Skills section
    const skillSection = extractSection(text, ['技能', '证书', '技术栈', '专业技能', 'skills', '技术能力']);
    if (skillSection) data.skills = skillSection;

    // Self intro
    const introSection = extractSection(text, ['自我评价', '自我介绍', '个人评价', '自我描述', 'about me', 'summary']);
    if (introSection) data.selfIntro = introSection;

    // If no structured sections found, use the entire text as the raw input
    data._raw = text;

    return data;
  }

  function extractSection(text, labels) {
    for (const label of labels) {
      const patterns = [
        new RegExp(`${label}[：:\\s]*\\n([\\s\\S]*?)(?=\\n(?:${labels.join('|')})[：:]|$)`, 'i'),
        new RegExp(`【${label}】[：:\\s]*([\\s\\S]*?)(?=【|$)`, 'i'),
        new RegExp(`##\\s*${label}\\s*\\n([\\s\\S]*?)(?=##|$)`, 'i'),
      ];
      for (const p of patterns) {
        const match = text.match(p);
        if (match && match[1].trim()) {
          return match[1].trim();
        }
      }
    }
    return null;
  }

  // === Document File Processing (TXT/PDF/DOCX/DOC) ===
  function processDocumentFile(file) {
    return new Promise((resolve, reject) => {
      if (!file) { reject(new Error('No file provided')); return; }

      const ext = getFileExtension(file.name);
      const fileInfo = {
        name: file.name,
        size: file.size,
        type: file.type,
        extension: ext,
        icon: getFileTypeIcon(ext),
        extractedText: '',
      };

      // TXT files - direct read
      if (ext === 'txt' || file.type === 'text/plain') {
        const reader = new FileReader();
        reader.onload = (e) => {
          fileInfo.extractedText = e.target.result;
          resolve(fileInfo);
        };
        reader.onerror = () => reject(new Error('Failed to read TXT file'));
        reader.readAsText(file, 'UTF-8');
        return;
      }

      // PDF files - attempt text extraction
      if (ext === 'pdf' || file.type === 'application/pdf') {
        extractPDFText(file).then(text => {
          fileInfo.extractedText = text;
          resolve(fileInfo);
        }).catch(() => {
          // Fallback: try reading as text
          const reader = new FileReader();
          reader.onload = (e) => {
            fileInfo.extractedText = e.target.result || '';
            resolve(fileInfo);
          };
          reader.onerror = () => {
            fileInfo.extractedText = '';
            resolve(fileInfo);
          };
          reader.readAsText(file);
        });
        return;
      }

      // DOCX files - attempt text extraction
      if (ext === 'docx' || file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
        extractDOCXText(file).then(text => {
          fileInfo.extractedText = text;
          resolve(fileInfo);
        }).catch(() => {
          // Fallback: read as text, strip XML tags
          const reader = new FileReader();
          reader.onload = (e) => {
            const raw = e.target.result || '';
            fileInfo.extractedText = stripXMLTags(raw);
            resolve(fileInfo);
          };
          reader.onerror = () => {
            fileInfo.extractedText = '';
            resolve(fileInfo);
          };
          reader.readAsText(file);
        });
        return;
      }

      // DOC (old format) and other files - best effort text read
      const reader = new FileReader();
      reader.onload = (e) => {
        fileInfo.extractedText = e.target.result || '';
        resolve(fileInfo);
      };
      reader.onerror = () => {
        fileInfo.extractedText = '';
        resolve(fileInfo);
      };
      reader.readAsText(file);
    });
  }

  // Minimal PDF text extraction (handles uncompressed text PDFs)
  function extractPDFText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const text = e.target.result;
          // Try to find text in PDF streams (BT...ET blocks)
          let extracted = '';
          // Pattern for text between BT and ET markers
          const btBlocks = text.match(/BT[\s\S]*?ET/g);
          if (btBlocks) {
            btBlocks.forEach(block => {
              // Extract text within parentheses in Tj/TJ operators
              const tjTexts = block.match(/\((.*?)\)\s*Tj/g);
              if (tjTexts) {
                tjTexts.forEach(tj => {
                  const match = tj.match(/\((.*?)\)/);
                  if (match) extracted += match[1] + ' ';
                });
              }
              // Handle TJ arrays
              const tjArrays = block.match(/\[(.*?)\]\s*TJ/gs);
              if (tjArrays) {
                tjArrays.forEach(arr => {
                  const texts = arr.match(/\((.*?)\)/g);
                  if (texts) texts.forEach(t => extracted += t.replace(/[()]/g, '') + ' ');
                });
              }
            });
          }

          if (extracted.trim()) {
            // Decode PDF escape sequences
            extracted = extracted
              .replace(/\\n/g, '\n')
              .replace(/\\r/g, '')
              .replace(/\\t/g, '\t')
              .replace(/\\\(/g, '(')
              .replace(/\\\)/g, ')')
              .replace(/\\\\/g, '\\');
            // Clean up excessive whitespace
            extracted = extracted.replace(/\s{3,}/g, '\n').trim();
            resolve(extracted);
          } else {
            // No BT blocks found - try reading raw text
            const rawText = text.replace(/[^\x20-\x7E一-鿿　-〿＀-￯\n\r\t]/g, ' ');
            const cleaned = rawText.replace(/\s{3,}/g, '\n').trim();
            resolve(cleaned || '');
          }
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = () => reject(new Error('Failed to read PDF'));
      reader.readAsText(file);
    });
  }

  // Minimal DOCX text extraction (DOCX is a ZIP containing document.xml)
  function extractDOCXText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const text = e.target.result;
          // DOCX is ZIP-compressed; when read as text, we look for document.xml content
          // The XML stores text in <w:t> tags
          const textMatches = text.match(/<w:t[^>]*>([^<]*)<\/w:t>/g);
          if (textMatches) {
            let extracted = textMatches
              .map(t => t.replace(/<w:t[^>]*>/, '').replace(/<\/w:t>/, ''))
              .join('');
            // Handle paragraph breaks
            const paraBreaks = text.match(/<w:p[ >]/g);
            if (paraBreaks && paraBreaks.length > 1) {
              // Insert newlines between paragraphs
              let result = '';
              let idx = 0;
              const parts = text.split(/<w:p[ >]/);
              parts.slice(1).forEach(part => {
                const tMatches = part.match(/<w:t[^>]*>([^<]*)<\/w:t>/g);
                if (tMatches) {
                  result += tMatches.map(t => t.replace(/<w:t[^>]*>/, '').replace(/<\/w:t>/, '')).join('') + '\n';
                }
              });
              extracted = result.trim();
            }
            resolve(extracted.trim());
          } else {
            // No w:t tags found, try stripping all XML
            const stripped = stripXMLTags(text);
            resolve(stripped);
          }
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = () => reject(new Error('Failed to read DOCX'));
      reader.readAsText(file);
    });
  }

  function stripXMLTags(text) {
    return text
      .replace(/<[^>]+>/g, ' ')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&apos;/g, "'")
      .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n)))
      .replace(/\s{3,}/g, '\n')
      .trim();
  }

  function getFileExtension(filename) {
    const parts = filename.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
  }

  function getFileTypeIcon(ext) {
    const icons = {
      txt: '📝',
      pdf: '📕',
      docx: '📘',
      doc: '📗',
    };
    return icons[ext] || '📎';
  }

  // === Image "OCR" Simulation ===
  // Since this is frontend-only, we simulate OCR by analyzing image metadata
  // and providing an editable text extraction interface
  function processImageFile(file) {
    return new Promise((resolve, reject) => {
      if (!file || !file.type.startsWith('image/')) {
        reject(new Error('Invalid image file'));
        return;
      }

      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          resolve({
            dataURL: e.target.result,
            width: img.width,
            height: img.height,
            name: file.name,
            size: file.size,
            type: file.type,
            // Placeholder for extracted text (user will fill in)
            extractedText: '',
          });
        };
        img.onerror = () => reject(new Error('Failed to load image'));
        img.src = e.target.result;
      };
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.readAsDataURL(file);
    });
  }

  // === Resume Generation ===
  function generateResume(formData, jdKeywords, questionnaireData = {}, options = {}) {
    const lang = I18N.getLang();

    const enrichedData = { ...formData };
    Object.entries(questionnaireData).forEach(([key, value]) => {
      if (value && value.trim()) {
        enrichedData._qa = enrichedData._qa || {};
        enrichedData._qa[key] = value;
      }
    });

    // === Build resume content from MaterialStore (source-grounded) ===
    const materialCtx = window.MaterialStore ? MaterialStore.getAIContext() : '';
    const sources = window.MaterialStore ? MaterialStore.getAllSources() : [];

    const resume = {
      personal: {
        name: MaterialStore.getIdentity('name') || formData.name || (lang === 'zh' ? '未填写' : 'N/A'),
        phone: MaterialStore.getIdentity('phone') || formData.phone || '',
        email: MaterialStore.getIdentity('email') || formData.email || '',
        city: MaterialStore.getIdentity('city') || formData.city || '',
        salary: MaterialStore.getIdentity('salary') || formData.salary || '',
        startDate: formData.startDate || '',
        targetJob: MaterialStore.getIdentity('targetJob') || formData.jobTitle || '',
      },
      summary: generateSummaryGrounded(formData, jdKeywords, lang, materialCtx),
      education: buildEducationFromStore(lang),
      experience: buildExperienceFromStore(lang),
      projects: buildProjectsFromStore(lang),
      skills: buildSkillsFromStore(formData.skills, jdKeywords, lang),
      selfIntro: MaterialStore.getSelfIntro() || formData.selfIntro || '',
      jdKeywords: jdKeywords,
      qaData: enrichedData._qa || {},
      // Source traceability metadata
      _sources: sources,
      _materialContext: materialCtx,
      _generatedAt: Date.now(),
    };

    // === Anti-Hallucination Validation ===
    if (window.FactChecker && materialCtx) {
      // Build a text representation of the resume for validation
      const resumeText = buildResumeTextForValidation(resume);
      const validation = FactChecker.validate(resumeText, materialCtx, { lang });

      resume._validation = validation;

      if (validation.severity === FactChecker.SEVERITY.BLOCK) {
        // Hallucination detected — return with block status
        resume._blocked = true;
        resume._blockReason = validation.issues
          .filter(i => i.severity === 'block')
          .map(i => i.detail)
          .join('; ');
      }
    }

    currentResumeData = resume;
    return resume;
  }

  // Build flat text from resume for validation
  function buildResumeTextForValidation(resume) {
    const parts = [];
    if (resume.summary) parts.push(resume.summary);
    resume.education.forEach(e => parts.push(e.enhanced || e.content));
    resume.experience.forEach(e => parts.push(e.enhanced || e.content));
    resume.projects.forEach(e => parts.push(e.enhanced || e.content));
    if (resume.selfIntro) parts.push(resume.selfIntro);
    return parts.join('\n');
  }

  // === Source-grounded summary (no fabricated claims) ===
  function generateSummaryGrounded(formData, jdKeywords, lang, materialCtx) {
    const name = formData.name || MaterialStore.getIdentity('name') || (lang === 'zh' ? '求职者' : 'Candidate');
    const job = formData.jobTitle || MaterialStore.getIdentity('targetJob') || (lang === 'zh' ? '目标岗位' : 'Target Position');

    // Only include skills that exist in the material store
    const storeSkills = MaterialStore.getSkillNames();
    const storeSkillCount = storeSkills.length;
    const skillText = storeSkills.slice(0, 4).join('、') || (lang === 'zh' ? '专业技能' : 'professional skills');

    if (lang === 'zh') {
      return `${name}，${job}从业者，掌握${skillText}。${storeSkillCount > 0 ? `具备${storeSkillCount}项可验证的专业技能。` : ''}`;
    }
    return `${name}, experienced in ${job}, skilled in ${skillText}. ${storeSkillCount > 0 ? `Possesses ${storeSkillCount} verifiable professional skills.` : ''}`;
  }

  // === Build education from MaterialStore only (no fabrication) ===
  function buildEducationFromStore(lang) {
    const storeEdu = MaterialStore.getEducation();
    if (storeEdu.length > 0) {
      return storeEdu.map(e => {
        const text = [e.school, e.major, e.degree, e.period].filter(Boolean).join(' / ');
        return { content: text, enhanced: text, source: e.source };
      });
    }
    return [];
  }

  // === Build work experience from MaterialStore only ===
  function buildExperienceFromStore(lang) {
    const storeWork = MaterialStore.getWorkExperience();
    if (storeWork.length > 0) {
      return storeWork.map(w => {
        const header = [w.company, w.position, w.period].filter(Boolean).join(' / ');
        const details = w.duties || w.raw || '';
        // Use ONLY the raw material, do NOT add fabricated "business growth"
        const text = details ? `${header}\n  ${details}` : header;
        return { content: text, enhanced: text, source: w.source };
      });
    }
    return [];
  }

  // === Build projects from MaterialStore only ===
  function buildProjectsFromStore(lang) {
    const storeProjects = MaterialStore.getProjects();
    if (storeProjects.length > 0) {
      return storeProjects.map(p => {
        const text = [p.name, p.role, p.description, p.period].filter(Boolean).join(' / ');
        return { content: text, enhanced: text, source: p.source };
      });
    }
    return [];
  }

  // === Build skills from MaterialStore + user form ===
  function buildSkillsFromStore(formSkills, jdKeywords, lang) {
    const storeSkills = MaterialStore.getSkillNames();
    const userSkills = formSkills ? formSkills.split(/[,，、\n]/).map(s => s.trim()).filter(Boolean) : [];
    const jdSkills = (jdKeywords?.hardSkills || []).map(s => s.trim());
    return [...new Set([...storeSkills, ...userSkills, ...jdSkills])];
  }

  function generateSummary(formData, jdKeywords, lang) {
    return generateSummaryGrounded(formData, jdKeywords, lang, '');
  }

  function parseMultiLineSection(text, lang) {
    if (!text || !text.trim()) return [];
    return text.split('\n').filter(line => line.trim()).map(line => ({
      content: line.trim(),
      enhanced: line.trim(),
    }));
  }

  function enhanceExperience(text, jdKeywords, lang) {
    // NO fabrication: only return what's in the original text
    // Previously added fake "business growth" — now strictly source-grounded
    const items = parseMultiLineSection(text, lang);
    return items.map(item => ({
      content: item.content,
      enhanced: item.content, // exact copy, no additions
    }));
  }

  function parseSkills(text, jdKeywords, lang) {
    const userSkills = text ? text.split(/[,，、\n]/).map(s => s.trim()).filter(Boolean) : [];
    const jdSkills = (jdKeywords?.hardSkills || []).map(s => s.trim());
    const allSkills = [...new Set([...jdSkills, ...userSkills])];
    return allSkills;
  }

  // === Self-Introduction Generation (2分钟·约800字·三部分结构) ===
  function generateSelfIntro(resumeData, lang) {
    if (!resumeData) return { cn: '', en: '' };

    // Pull data from MaterialStore for grounding
    const name = MaterialStore.getIdentity('name') || resumeData.personal?.name || (lang === 'zh' ? '求职者' : 'Candidate');
    const job = MaterialStore.getIdentity('targetJob') || resumeData.personal?.targetJob || (lang === 'zh' ? '贵司岗位' : 'this position');
    const city = MaterialStore.getIdentity('city') || resumeData.personal?.city || '';
    const storeSkills = MaterialStore.getSkillNames();
    const storeCerts = MaterialStore.getCertificateNames();
    const storeEdu = MaterialStore.getEducation();
    const storeWork = MaterialStore.getWorkExperience();
    const storeProjects = MaterialStore.getProjects();
    const storeSelfIntro = MaterialStore.getSelfIntro();
    const jdKeywords = resumeData.jdKeywords || {};
    const jdHardSkills = jdKeywords.hardSkills || [];
    const jdSoftSkills = jdKeywords.softSkills || [];

    // Build Chinese version (~800字, 3 sections)
    const cn = buildChineseIntro(name, job, city, storeSkills, storeCerts, storeWork, storeProjects, storeEdu, storeSelfIntro, jdHardSkills, jdSoftSkills);

    // Build English version (equivalent length)
    const en = buildEnglishIntro(name, job, city, storeSkills, storeCerts, storeWork, storeProjects, storeEdu, storeSelfIntro, jdHardSkills, jdSoftSkills);

    return { cn, en };
  }

  // === Chinese 2-Minute Self-Introduction (~800字) ===
  function buildChineseIntro(name, job, city, skills, certs, workExps, projects, edu, selfIntro, jdHard, jdSoft) {
    // Section 1: 专业技能 (~250字)
    const section1 = buildSkillSectionCN(name, job, skills, certs, jdHard);

    // Section 2: 实习/工作经历 (~300字)
    const section2 = buildExperienceSectionCN(workExps, projects);

    // Section 3: 岗位匹配度 (~250字)
    const section3 = buildFitSectionCN(name, job, jdHard, jdSoft, skills, selfIntro);

    const intro = `面试官您好，我是${name}，非常感谢给我这次面试机会。下面我从专业技能、实习经历和岗位匹配度三个方面做简要介绍。\n\n${section1}\n\n${section2}\n\n${section3}\n\n以上就是我的基本情况。我非常期待能加入贵公司，与团队一起成长，为业务创造实际价值。谢谢！`;

    return intro;
  }

  function buildSkillSectionCN(name, job, skills, certs, jdHard) {
    const parts = [];

    parts.push(`【专业技能】`);
    parts.push(`我毕业于${getEduSummaryCN()}，在校期间系统学习了专业核心课程，打下了扎实的理论基础。`);

    if (skills.length > 0) {
      const topSkills = skills.slice(0, 8);
      parts.push(`在技术/专业技能方面，我熟练掌握${topSkills.slice(0, 4).join('、')}等。`);
      if (topSkills.length > 4) {
        parts.push(`同时对${topSkills.slice(4).join('、')}也有深入的应用经验。`);
      }
    }

    if (jdHard.length > 0) {
      const matchedSkills = jdHard.filter(s => skills.some(sk => sk.toLowerCase().includes(s.toLowerCase()) || s.toLowerCase().includes(sk.toLowerCase())));
      if (matchedSkills.length > 0) {
        parts.push(`其中${matchedSkills.slice(0, 3).join('、')}与贵司JD要求高度匹配。`);
      }
    }

    if (certs.length > 0) {
      parts.push(`此外我还取得了${certs.slice(0, 3).join('、')}等证书/资质。`);
    }

    parts.push(`我始终保持对新技术的学习热情，通过实际项目不断打磨专业能力，能够独立解决工作中遇到的技术难题。`);

    return parts.join('');
  }

  function buildExperienceSectionCN(workExps, projects) {
    const parts = [];

    parts.push(`【实习/工作经历】`);

    if (workExps.length > 0) {
      parts.push(`我共有${workExps.length}段工作/实习经历。`);
      workExps.forEach((w, i) => {
        const company = w.company || (w.raw ? w.raw.split(/[/\n]/)[0] : '某公司');
        const position = w.position || '';
        const duties = w.duties || w.raw || '';
        const period = w.period || '';
        const desc = [company, position, period].filter(Boolean).join('，');
        parts.push(`第${i + 1}段是在${desc}。${duties ? '期间我主要负责' + truncateText(duties, 80) + '。' : ''}`);
      });
    }

    if (projects.length > 0) {
      parts.push(`在项目经历方面，`);
      projects.forEach((p, i) => {
        const pname = p.name || p.raw || '某项目';
        const desc = p.description || p.raw || '';
        parts.push(`我参与/主导了「${pname}」${desc ? '，' + truncateText(desc, 60) : ''}。`);
      });
    }

    if (workExps.length === 0 && projects.length === 0) {
      parts.push(`虽然我的工作经历相对有限，但我在校期间通过课程项目和自主学习积累了一定的实践经验。`);
    }

    parts.push(`通过这些经历，我锻炼了团队协作能力、项目管理意识以及解决问题的执行力。`);

    return parts.join('');
  }

  function buildFitSectionCN(name, job, jdHard, jdSoft, skills, selfIntro) {
    const parts = [];

    parts.push(`【岗位匹配度】`);

    if (jdHard.length > 0 || jdSoft.length > 0) {
      parts.push(`我仔细研究了贵司${job}岗位的JD要求。`);
    }

    // Hard skill match
    if (jdHard.length > 0) {
      const matched = jdHard.filter(j => skills.some(s => s.toLowerCase().includes(j.toLowerCase()) || j.toLowerCase().includes(s.toLowerCase())));
      if (matched.length > 0) {
        parts.push(`在硬性技能方面，我掌握的${matched.slice(0, 3).join('、')}直接对标岗位需求。`);
      }
      const unmatched = jdHard.filter(j => !skills.some(s => s.toLowerCase().includes(j.toLowerCase()) || j.toLowerCase().includes(s.toLowerCase())));
      if (unmatched.length > 0) {
        parts.push(`对于${unmatched.slice(0, 2).join('、')}，我也有基础了解并正在深入学习中。`);
      }
    }

    // Soft skill match
    if (jdSoft.length > 0) {
      parts.push(`在软实力方面，${jdSoft.slice(0, 3).join('、')}等能力要求与我的工作风格高度一致。`);
    }

    // Self-assessment integration
    if (selfIntro && selfIntro.trim().length > 5) {
      parts.push(`关于我个人，${truncateText(selfIntro, 80)}。`);
    } else {
      parts.push(`我具备快速学习和适应新环境的能力，对待工作认真负责、结果导向。`);
    }

    parts.push(`我相信自己的专业背景和实际经验能够胜任${job}岗位，也非常期待能在贵司的平台上持续成长、创造价值。`);

    return parts.join('');
  }

  // === English 2-Minute Self-Introduction ===
  function buildEnglishIntro(name, job, city, skills, certs, workExps, projects, edu, selfIntro, jdHard, jdSoft) {
    const parts = [];

    // Opening
    parts.push(`Hello, I'm ${name}, and I'm excited to interview for the ${job} position. Let me introduce myself from three angles: my professional skills, relevant experience, and how I match this role.`);

    // Skills section
    parts.push(`\n\n【Professional Skills】`);
    if (skills.length > 0) {
      parts.push(`I'm proficient in ${skills.slice(0, 5).join(', ')}.`);
    }
    if (certs.length > 0) {
      parts.push(`I also hold certifications in ${certs.slice(0, 3).join(', ')}.`);
    }
    parts.push(`I actively stay current with industry trends and continuously sharpen my skills through hands-on projects.`);

    // Experience section
    parts.push(`\n\n【Work & Project Experience】`);
    if (workExps.length > 0) {
      workExps.slice(0, 3).forEach((w, i) => {
        const company = w.company || (w.raw ? w.raw.split(/[/\n]/)[0] : 'a company');
        parts.push(`I worked at ${company} as ${w.position || 'a team member'}${w.period ? ' from ' + w.period : ''}.`);
      });
    }
    if (projects.length > 0) {
      projects.slice(0, 2).forEach(p => {
        parts.push(`I led/contributed to the "${p.name || 'key project'}" project${p.description ? ' — ' + truncateText(p.description, 60) : ''}.`);
      });
    }
    parts.push(`These experiences strengthened my teamwork, problem-solving, and project delivery skills.`);

    // Fit section
    parts.push(`\n\n【Role Fit】`);
    if (jdHard.length > 0) {
      parts.push(`After reviewing the JD, I believe my skills in ${jdHard.slice(0, 3).join(', ')} align well with your requirements.`);
    }
    parts.push(`I'm a fast learner, results-driven, and thrive in collaborative environments. I'm confident I can make meaningful contributions to your team.`);

    // Closing
    parts.push(`\n\nThank you for your time — I look forward to the opportunity to grow and deliver value with your team.`);

    return parts.join('');
  }

  function getEduSummaryCN() {
    const edu = MaterialStore.getEducation();
    if (edu.length > 0) {
      const e = edu[0];
      return [e.school, e.major, e.degree].filter(Boolean).join(' ') || '相关院校';
    }
    return '相关院校';
  }

  function truncateText(text, maxLen) {
    if (!text) return '';
    const cleaned = text.replace(/\n/g, ' ').trim();
    if (cleaned.length <= maxLen) return cleaned;
    return cleaned.substring(0, maxLen) + '…';
  }

  // === Export Functions ===
  function exportWord(resumeData, lang) {
    if (!resumeData) return false;
    const html = buildResumeHTML(resumeData, lang);
    const wordHTML = `
      <html xmlns:o="urn:schemas-microsoft-com:office:office"
            xmlns:w="urn:schemas-microsoft-com:office:word"
            xmlns="http://www.w3.org/TR/REC-html40">
      <head><meta charset="utf-8"><meta http-equiv="Content-Type" content="text/html; charset=utf-8">
      <!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View>
      <w:Zoom>100</w:Zoom><w:DoNotOptimizeForBrowser/></w:WordDocument></xml><![endif]-->
      <style>
        @page { size: A4; margin: 2cm; }
        body { font-family: 'Microsoft YaHei', Arial, sans-serif; font-size: 12pt; line-height: 1.8; color: #333; }
        h1 { font-size: 20pt; color: #1a1a2e; border-bottom: 2px solid #f4813a; padding-bottom: 6pt; }
        h2 { font-size: 14pt; color: #1a1a2e; border-bottom: 1px solid #ddd; padding-bottom: 4pt; margin-top: 16pt; }
        .contact { color: #666; font-size: 10pt; margin-bottom: 12pt; }
        ul { margin: 4pt 0; padding-left: 20pt; } li { margin-bottom: 4pt; }
      </style></head>
      <body>${html}</body></html>`;
    downloadBlob('﻿' + wordHTML, `Resume_${resumeData.personal?.name || 'Candidate'}_${lang.toUpperCase()}.doc`, 'application/msword;charset=utf-8');
    return true;
  }

  function exportPDF(resumeData, lang) {
    if (!resumeData) return false;
    const html = buildResumeHTML(resumeData, lang);
    const printWindow = window.open('', '_blank', 'width=800,height=600');
    if (!printWindow) {
      const printDiv = document.createElement('div');
      printDiv.innerHTML = html;
      printDiv.style.cssText = 'font-family:"Microsoft YaHei",Arial,sans-serif;font-size:12pt;line-height:1.8;color:#333;padding:40px;max-width:210mm;margin:0 auto;';
      printDiv.className = 'print-section';
      document.body.appendChild(printDiv);
      window.print();
      setTimeout(() => printDiv.remove(), 1000);
      return true;
    }
    printWindow.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Resume</title>
      <style>@page{size:A4;margin:2cm}body{font-family:'Microsoft YaHei',Arial,sans-serif;font-size:12pt;line-height:1.8;color:#333;padding:0;margin:0}
      h1{font-size:20pt;color:#1a1a2e;border-bottom:2px solid #f4813a;padding-bottom:6pt}
      h2{font-size:14pt;color:#1a1a2e;border-bottom:1px solid #ddd;padding-bottom:4pt;margin-top:16pt}
      .contact{color:#666;font-size:10pt;margin-bottom:12pt}
      @media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style></head>
      <body>${html}</body></html>`);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => printWindow.print(), 500);
    setTimeout(() => printWindow.close(), 2000);
    return true;
  }

  function buildResumeHTML(resumeData, lang) {
    const p = resumeData.personal || {};
    const labels = getResumeLabels(lang);
    const template = window.ExtractionPipeline?.STANDARD_TEMPLATE;

    // Use standard template format if available
    const sections = [];
    sections.push(`<h1>${p.name || ''}</h1>`);
    sections.push(`<div class="contact">${[p.phone, p.email, p.city].filter(Boolean).join(' | ')}${p.targetJob ? ' | ' + labels.targetJob + ': ' + p.targetJob : ''}</div>`);

    if (resumeData.selfIntro) {
      sections.push(`<div class="section"><h2>${labels.selfIntro}</h2><p>${resumeData.selfIntro}</p></div>`);
    }
    sections.push(buildSection(labels.education, resumeData.education));
    sections.push(buildSection(labels.experience, resumeData.experience));
    sections.push(buildSection(labels.projects, resumeData.projects));
    if (resumeData.skills?.length) {
      sections.push(`<div class="section"><h2>${labels.skills}</h2><p>${resumeData.skills.join('、')}</p></div>`);
    }

    return sections.join('');
  }

  function buildSection(title, items) {
    if (!items || items.length === 0) return '';
    return `<div class="section"><h2>${title}</h2><ul>${items.map(item => `<li>${item.enhanced || item.content || item}</li>`).join('')}</ul></div>`;
  }

  function getResumeLabels(lang) {
    return lang === 'zh'
      ? { targetJob: '应聘岗位', summary: '职业概述', education: '教育经历', experience: '工作经历', projects: '项目经历', skills: '技能证书', selfIntro: '自我评价' }
      : { targetJob: 'Target Position', summary: 'Professional Summary', education: 'Education', experience: 'Work Experience', projects: 'Projects', skills: 'Skills & Certificates', selfIntro: 'Self-Assessment' };
  }

  function downloadBlob(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // === Render Preview ===
  function renderPreview(resumeData, containerId, isMobile = false) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const lang = I18N.getLang();

    if (!resumeData) {
      container.innerHTML = `<p style="color:#999;text-align:center;padding:40px;">${lang === 'zh' ? '请先填写信息，然后点击生成简历' : 'Please fill in info, then generate resume'}</p>`;
      return;
    }

    const p = resumeData.personal || {};
    const sf = isMobile ? '0.68rem' : '0.82rem';
    const hf = isMobile ? '0.85rem' : '0.9rem';
    const cf = isMobile ? '0.58rem' : '0.76rem';

    const sections = [];

    // Header
    sections.push(`<div class="resume-preview-name" style="font-size:${isMobile ? '1rem' : '1.6rem'}">${p.name || ''}</div>`);
    const contactParts = [];
    if (p.phone) contactParts.push(`📱 ${p.phone}`);
    if (p.email) contactParts.push(`📧 ${p.email}`);
    if (p.city) contactParts.push(`📍 ${p.city}`);
    if (p.targetJob) contactParts.push(`🎯 ${p.targetJob}`);
    if (contactParts.length) {
      sections.push(`<div class="resume-preview-contact" style="font-size:${cf}">${contactParts.join(' &nbsp;|&nbsp; ')}</div>`);
    }

    // Self-assessment
    if (resumeData.selfIntro) {
      sections.push(`<div class="resume-preview-section"><h3 style="font-size:${hf}">${lang === 'zh' ? '自我评价' : 'Self-Assessment'}</h3><p style="font-size:${sf}">${resumeData.selfIntro.replace(/\n/g, '<br>')}</p></div>`);
    }

    // Education
    if (resumeData.education?.length) {
      const items = resumeData.education.map(e => `<li style="font-size:${sf}">${(e.enhanced || e.content || '').replace(/\n/g, '<br>')}</li>`).join('');
      sections.push(`<div class="resume-preview-section"><h3 style="font-size:${hf}">${lang === 'zh' ? '教育经历' : 'Education'}</h3><ul>${items}</ul></div>`);
    }

    // Work experience
    if (resumeData.experience?.length) {
      const items = resumeData.experience.map(e => {
        const text = (e.enhanced || e.content || '').replace(/\n/g, '<br>');
        const srcTag = e.source ? `<span class="source-tag form" title="${e.source.file}">📎</span>` : '';
        return `<li style="font-size:${sf}">${text} ${srcTag}</li>`;
      }).join('');
      sections.push(`<div class="resume-preview-section"><h3 style="font-size:${hf}">${lang === 'zh' ? '工作经历' : 'Work Experience'}</h3><ul>${items}</ul></div>`);
    }

    // Projects
    if (resumeData.projects?.length) {
      const items = resumeData.projects.map(p => `<li style="font-size:${sf}">${(p.enhanced || p.content || '').replace(/\n/g, '<br>')}</li>`).join('');
      sections.push(`<div class="resume-preview-section"><h3 style="font-size:${hf}">${lang === 'zh' ? '项目经历' : 'Projects'}</h3><ul>${items}</ul></div>`);
    }

    // Skills
    if (resumeData.skills?.length) {
      sections.push(`<div class="resume-preview-section"><h3 style="font-size:${hf}">${lang === 'zh' ? '技能证书' : 'Skills'}</h3><p style="font-size:${sf}">${resumeData.skills.join(' · ')}</p></div>`);
    }

    container.innerHTML = sections.join('');
  }

  function renderPreviewSection(title, items, fontSize) {
    if (!items || items.length === 0) return '';
    return `<div class="resume-preview-section"><h3>${title}</h3>${items.map(item => `<p style="font-size:${fontSize}">• ${item.enhanced || item.content || item}</p>`).join('')}</div>`;
  }

  // === Questionnaire ===
  function processQAData(answers) { questionnaireAnswers = { ...questionnaireAnswers, ...answers }; return questionnaireAnswers; }
  function getQAData() { return { ...questionnaireAnswers }; }
  function clearQAData() { questionnaireAnswers = {}; }

  return {
    parseJD,
    parseFreeFormPersonalInfo,
    processImageFile,
    processDocumentFile,
    generateResume,
    generateSelfIntro,
    exportWord,
    exportPDF,
    renderPreview,
    processQAData,
    getQAData,
    clearQAData,
    getCurrentResume: () => currentResumeData,
  };
})();

window.ResumeEngine = ResumeEngine;
