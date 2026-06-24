/* ============================================================
   material-store.js — 用户原始素材库（只读结构化存储）
   所有AI输出必须绑定此库中的原文索引，禁止编造
   ============================================================ */

const MaterialStore = (() => {
  // Internal structured storage
  let store = {
    // Personal identity info
    identity: {
      name: null,           // { value, sources: [] }
      phone: null,
      email: null,
      city: null,
      targetJob: null,
      salary: null,
    },
    // Education entries
    education: [],          // [{ school, major, degree, period, raw, source }]
    // Work experience entries
    workExperience: [],     // [{ company, position, duties, period, raw, source }]
    // Project entries
    projects: [],           // [{ name, role, description, results, period, raw, source }]
    // Skills
    skills: [],             // [{ name, category, source }]
    // Certificates
    certificates: [],       // [{ name, source }]
    // Self-assessment
    selfIntro: null,        // { value, source }
    // JD structured data
    jd: {
      rawText: null,
      keywords: { hardSkills: [], softSkills: [], industry: [] },
      requirements: [],     // [{ type, value, source }]
      responsibilities: [], // [{ value, source }]
    },
    // Questionnaire answers (增信问卷，作为合法原始数据)
    qaEntries: [],          // [{ question, answer, source: 'questionnaire' }]
    // All raw source files metadata
    sourceFiles: [],        // [{ name, type, extractedAt, text }]
    // Source index for cross-referencing
    _sourceIndex: 0,
  };

  // Lock flag — once material is extracted, AI cannot modify it
  let materialLocked = false;

  // === Source reference generator ===
  function nextSourceRef(fileName, section) {
    store._sourceIndex++;
    return {
      id: `src-${store._sourceIndex}`,
      file: fileName || '用户输入',
      section: section || '通用',
      timestamp: Date.now(),
    };
  }

  // === Identity ===
  function setIdentity(field, value, fileName) {
    if (materialLocked) return false;
    const ref = nextSourceRef(fileName, `个人信息/${field}`);
    store.identity[field] = { value: String(value).trim(), sources: [ref] };
    return true;
  }

  function getIdentity(field) {
    return store.identity[field]?.value || null;
  }

  // === Education ===
  function addEducation(entry, fileName) {
    if (materialLocked) return false;
    const ref = nextSourceRef(fileName, '教育经历');
    store.education.push({ ...entry, source: ref, raw: entry.raw || entry.school || '' });
    return true;
  }

  function getEducation() { return [...store.education]; }

  // === Work Experience ===
  function addWorkExperience(entry, fileName) {
    if (materialLocked) return false;
    const ref = nextSourceRef(fileName, '工作经历');
    store.workExperience.push({ ...entry, source: ref, raw: entry.raw || entry.company || '' });
    return true;
  }

  function getWorkExperience() { return [...store.workExperience]; }

  // === Projects ===
  function addProject(entry, fileName) {
    if (materialLocked) return false;
    const ref = nextSourceRef(fileName, '项目经历');
    store.projects.push({ ...entry, source: ref, raw: entry.raw || entry.name || '' });
    return true;
  }

  function getProjects() { return [...store.projects]; }

  // === Skills ===
  function addSkill(name, category, fileName) {
    if (materialLocked) return false;
    const ref = nextSourceRef(fileName, '技能证书');
    store.skills.push({ name: String(name).trim(), category: category || '通用', source: ref });
    return true;
  }

  function getSkills() { return [...store.skills]; }
  function getSkillNames() { return store.skills.map(s => s.name); }

  // === Certificates ===
  function addCertificate(name, fileName) {
    if (materialLocked) return false;
    const ref = nextSourceRef(fileName, '证书');
    store.certificates.push({ name: String(name).trim(), source: ref });
    return true;
  }

  function getCertificates() { return [...store.certificates]; }
  function getCertificateNames() { return store.certificates.map(c => c.name); }

  // === Self Intro ===
  function setSelfIntro(value, fileName) {
    if (materialLocked) return false;
    const ref = nextSourceRef(fileName, '自我评价');
    store.selfIntro = { value: String(value).trim(), source: ref };
    return true;
  }

  function getSelfIntro() { return store.selfIntro?.value || null; }

  // === JD ===
  function setJDRawText(text, fileName) {
    if (materialLocked) return false;
    store.jd.rawText = String(text).trim();
    store.jd._source = nextSourceRef(fileName, 'JD原文');
  }

  function setJDKeywords(keywords, fileName) {
    if (materialLocked) return false;
    store.jd.keywords = {
      hardSkills: keywords.hardSkills || [],
      softSkills: keywords.softSkills || [],
      industry: keywords.industry || [],
    };
    store.jd._kwSource = nextSourceRef(fileName, 'JD关键词');
  }

  function addJDRequirement(type, value, fileName) {
    if (materialLocked) return false;
    const ref = nextSourceRef(fileName, 'JD要求');
    store.jd.responsibilities.push({ type, value, source: ref });
  }

  function getJD() { return { ...store.jd }; }
  function getJDRawText() { return store.jd.rawText || ''; }
  function getJDKeywords() { return { ...store.jd.keywords }; }

  // === QA Entries (增信问卷 — 合法原始数据) ===
  function addQAEntry(question, answer) {
    const ref = nextSourceRef('增信问卷', question);
    store.qaEntries.push({ question, answer: String(answer).trim(), source: ref });
    return true;
  }

  function getQAEntries() { return [...store.qaEntries]; }

  // === Source Files ===
  function addSourceFile(name, type, text) {
    store.sourceFiles.push({
      name,
      type,
      extractedAt: Date.now(),
      text: String(text || '').trim(),
    });
  }

  function getSourceFiles() { return [...store.sourceFiles]; }

  // === Bulk Import from Parsed Data ===
  function importParsedData(parsed, fileName) {
    if (materialLocked) return { success: false, reason: '素材库已锁定' };

    const imported = { identity: 0, education: 0, work: 0, projects: 0, skills: 0 };

    if (parsed.name) { setIdentity('name', parsed.name, fileName); imported.identity++; }
    if (parsed.phone) { setIdentity('phone', parsed.phone, fileName); imported.identity++; }
    if (parsed.email) { setIdentity('email', parsed.email, fileName); imported.identity++; }
    if (parsed.city) { setIdentity('city', parsed.city, fileName); imported.identity++; }
    if (parsed.targetJob) { setIdentity('targetJob', parsed.targetJob, fileName); imported.identity++; }
    if (parsed.salary) { setIdentity('salary', parsed.salary, fileName); imported.identity++; }

    if (parsed.education && Array.isArray(parsed.education)) {
      parsed.education.forEach(e => { addEducation(e, fileName); imported.education++; });
    }
    if (parsed.workExperience && Array.isArray(parsed.workExperience)) {
      parsed.workExperience.forEach(w => { addWorkExperience(w, fileName); imported.work++; });
    }
    if (parsed.projects && Array.isArray(parsed.projects)) {
      parsed.projects.forEach(p => { addProject(p, fileName); imported.projects++; });
    }
    if (parsed.skills && Array.isArray(parsed.skills)) {
      parsed.skills.forEach(s => addSkill(typeof s === 'string' ? s : s.name, typeof s === 'string' ? '通用' : s.category, fileName));
      imported.skills += parsed.skills.length;
    }
    if (parsed.certificates && Array.isArray(parsed.certificates)) {
      parsed.certificates.forEach(c => addCertificate(typeof c === 'string' ? c : c.name, fileName));
    }
    if (parsed.selfIntro) { setSelfIntro(parsed.selfIntro, fileName); }

    // Add to source files record
    if (parsed.rawText) {
      addSourceFile(fileName, 'document', parsed.rawText);
    }

    return { success: true, imported };
  }

  // === Import JD parsed data ===
  function importJDParsedData(parsed, fileName) {
    if (materialLocked) return { success: false, reason: '素材库已锁定' };
    if (parsed.rawText) setJDRawText(parsed.rawText, fileName);
    if (parsed.keywords) setJDKeywords(parsed.keywords, fileName);
    if (parsed.requirements) {
      parsed.requirements.forEach(r => addJDRequirement(r.type || '要求', r.value, fileName));
    }
    return { success: true };
  }

  // === Lock / Unlock ===
  function lock() { materialLocked = true; }
  function unlock() { materialLocked = false; }
  function isLocked() { return materialLocked; }

  // === Get all material as flat text for AI context ===
  function getAIContext() {
    const parts = [];

    const id = store.identity;
    const idParts = [];
    if (id.name?.value) idParts.push(`姓名: ${id.name.value}`);
    if (id.phone?.value) idParts.push(`电话: ${id.phone.value}`);
    if (id.email?.value) idParts.push(`邮箱: ${id.email.value}`);
    if (id.city?.value) idParts.push(`城市: ${id.city.value}`);
    if (id.targetJob?.value) idParts.push(`目标岗位: ${id.targetJob.value}`);
    if (id.salary?.value) idParts.push(`期望薪资: ${id.salary.value}`);
    if (idParts.length) parts.push('【个人信息】\n' + idParts.join('\n'));

    if (store.education.length) {
      parts.push('【教育经历】\n' + store.education.map(e =>
        `${e.school || ''} / ${e.major || ''} / ${e.degree || ''} / ${e.period || ''} [来源: ${e.source?.file || '未知'}]`
      ).join('\n'));
    }

    if (store.workExperience.length) {
      parts.push('【工作经历】\n' + store.workExperience.map(w =>
        `${w.company || ''} / ${w.position || ''} / ${w.period || ''}\n  职责: ${w.duties || w.raw || ''} [来源: ${w.source?.file || '未知'}]`
      ).join('\n'));
    }

    if (store.projects.length) {
      parts.push('【项目经历】\n' + store.projects.map(p =>
        `${p.name || ''} / ${p.role || ''} / ${p.period || ''}\n  描述: ${p.description || p.raw || ''} [来源: ${p.source?.file || '未知'}]`
      ).join('\n'));
    }

    if (store.skills.length) {
      parts.push('【技能证书】\n' + store.skills.map(s => s.name).join('、'));
    }

    if (store.selfIntro?.value) {
      parts.push(`【自我评价】\n${store.selfIntro.value}`);
    }

    if (store.jd.rawText) {
      parts.push('【JD原文】\n' + store.jd.rawText);
    }

    if (store.qaEntries.length) {
      parts.push('【增信问卷】\n' + store.qaEntries.map(q =>
        `Q: ${q.question}\nA: ${q.answer}`
      ).join('\n'));
    }

    return parts.join('\n\n---\n\n');
  }

  // === Get all source references ===
  function getAllSources() {
    const sources = [];
    const addSource = (s) => { if (s && !sources.find(x => x.id === s.id)) sources.push(s); };

    Object.values(store.identity).forEach(v => { if (v?.sources) v.sources.forEach(addSource); });
    store.education.forEach(e => addSource(e.source));
    store.workExperience.forEach(w => addSource(w.source));
    store.projects.forEach(p => addSource(p.source));
    store.skills.forEach(s => addSource(s.source));
    store.certificates.forEach(c => addSource(c.source));
    if (store.selfIntro?.source) addSource(store.selfIntro.source);
    if (store.jd._source) addSource(store.jd._source);
    store.qaEntries.forEach(q => addSource(q.source));

    return sources;
  }

  // === Reset ===
  function reset() {
    store = {
      identity: { name: null, phone: null, email: null, city: null, targetJob: null, salary: null },
      education: [], workExperience: [], projects: [], skills: [], certificates: [],
      selfIntro: null,
      jd: { rawText: null, keywords: { hardSkills: [], softSkills: [], industry: [] }, requirements: [], responsibilities: [] },
      qaEntries: [], sourceFiles: [], _sourceIndex: 0,
    };
    materialLocked = false;
  }

  // === Export for debugging ===
  function dump() { return JSON.parse(JSON.stringify(store)); }

  // === 从提取结果批量导入 ===
  function loadFromExtraction(extractedData, fileName) {
    if (materialLocked) return false;
    return importParsedData(extractedData, fileName);
  }

  // === 获取素材锁定状态 ===
  function isMaterialLocked() { return materialLocked; }

  // === 获取溯源映射（字段 → 原文行） ===
  function getSourceMap() {
    const map = {};
    const addEntry = (key, entry) => {
      if (!entry) return;
      const src = entry.source || (entry.sources && entry.sources[0]);
      if (src) {
        if (!map[key]) map[key] = [];
        map[key].push({ id: src.id, file: src.file, section: src.section, snippet: src.text_snippet || '' });
      }
    };

    addEntry('name', store.identity.name);
    addEntry('phone', store.identity.phone);
    addEntry('email', store.identity.email);
    addEntry('city', store.identity.city);
    addEntry('target_job', store.identity.targetJob);

    store.education.forEach((e, i) => addEntry(`education_${i}`, e));
    store.workExperience.forEach((w, i) => addEntry(`work_${i}`, w));
    store.projects.forEach((p, i) => addEntry(`project_${i}`, p));
    store.skills.forEach((s, i) => addEntry(`skill_${i}`, s));
    store.certificates.forEach((c, i) => addEntry(`cert_${i}`, c));

    return map;
  }

  return {
    // Identity
    setIdentity, getIdentity,
    // Education
    addEducation, getEducation,
    // Work
    addWorkExperience, getWorkExperience,
    // Projects
    addProject, getProjects,
    // Skills
    addSkill, getSkills, getSkillNames,
    // Certificates
    addCertificate, getCertificates, getCertificateNames,
    // Self Intro
    setSelfIntro, getSelfIntro,
    // JD
    setJDRawText, setJDKeywords, addJDRequirement, getJD, getJDRawText, getJDKeywords,
    // QA
    addQAEntry, getQAEntries,
    // Source files
    addSourceFile, getSourceFiles,
    // Bulk import
    importParsedData, importJDParsedData, loadFromExtraction,
    // Lock
    lock, unlock, isLocked, isMaterialLocked,
    // Context & Sources
    getAIContext, getAllSources, getSourceMap,
    // Lifecycle
    reset, dump,
  };
})();

window.MaterialStore = MaterialStore;
