/* ============================================================
   fact-checker.js — 事实溯源校验 + 幻觉拦截引擎
   所有AI输出必须通过素材库验证，检测到虚构内容立即拦截
   ============================================================ */

const FactChecker = (() => {
  // === Validation Result Types ===
  const SEVERITY = {
    PASS: 'pass',         // All claims verified
    WARNING: 'warning',   // Minor uncertainty, allows generation with warnings
    BLOCK: 'block',       // Fabricated content detected, generation blocked
  };

  // Patterns that indicate potentially fabricated content
  const FABRICATION_PATTERNS = {
    // Numbers that look fabricated (percentages, large numbers)
    quantifiedClaims: [
      /提升[了]?(\d+[%％])/g,
      /增长[了]?(\d+[%％])/g,
      /降低[了]?(\d+[%％])/g,
      /(\d+[%％])[的]?提升/g,
      /(\d+[万億亿])\+(?:用户|访问|播放|曝光|GMV|营收)/g,
      /(\d+\.?\d*)\s*(万|亿|千万|百万|k|K|w|W)\s*(用户|粉丝|播放|曝光|营收|GMV)/g,
      /ROI\s*[＞>]\s*\d+/g,
      /转化率\s*(\d+[%％])/g,
      /UV\s*(\d+[万億亿])/g,
      /PV\s*(\d+[万億亿])/g,
    ],
    // Fake company names or positions
    fabricatedRoles: [
      /负责[了]?(全[部局]?|整个|所有)/g,
      /主导[了]?((?!.*项目).)*从[0零]到[1一]/g,
      /管理\s*(\d+)\s*人[的]?团队/g,
      /带领[了]?(\d+)\s*人/g,
    ],
    // Unverifiable achievements
    unverifiableAchievements: [
      /荣获[了]?["""].*["»"]/g,
      /被评为[了]?.*(?:最佳|优秀|杰出|TOP|top)/g,
      /获得[了]?.*(?:一等奖|二等奖|金奖|银奖)/g,
    ],
  };

  // === Core Validation: Check if generated text is grounded in source materials ===
  function validate(aiGeneratedText, materialContext, options = {}) {
    const results = {
      severity: SEVERITY.PASS,
      issues: [],
      citations: [],
      stats: { claimsChecked: 0, verified: 0, uncertain: 0, fabricated: 0 },
    };

    if (!aiGeneratedText || !aiGeneratedText.trim()) {
      return results;
    }

    const lang = options.lang || 'zh';

    // --- 1. Check quantified claims against material store ---
    checkQuantifiedClaims(aiGeneratedText, materialContext, results, lang);

    // --- 2. Check for fabricated experiences ---
    checkFabricatedExperiences(aiGeneratedText, materialContext, results, lang);

    // --- 3. Check for fake projects/companies ---
    checkFakeEntities(aiGeneratedText, materialContext, results, lang);

    // --- 4. Source matching: find which claims trace back to material ---
    traceSources(aiGeneratedText, materialContext, results, lang);

    // --- Determine severity ---
    if (results.stats.fabricated > 0) {
      results.severity = SEVERITY.BLOCK;
    } else if (results.stats.uncertain > 3) {
      results.severity = SEVERITY.WARNING;
    }

    return results;
  }

  // === Check quantified number claims ===
  function checkQuantifiedClaims(text, materialCtx, results, lang) {
    // Extract all number/percentage claims from generated text
    const allPatterns = FABRICATION_PATTERNS.quantifiedClaims;
    const foundClaims = [];

    allPatterns.forEach(pattern => {
      let match;
      const regex = new RegExp(pattern.source, pattern.flags);
      while ((match = regex.exec(text)) !== null) {
        foundClaims.push({
          claim: match[0],
          number: match[1] || match[0],
          position: match.index,
        });
      }
    });

    results.stats.claimsChecked += foundClaims.length;

    foundClaims.forEach(fc => {
      // Check if this number appears in the material context
      const numberStr = fc.number.replace(/[%％\s]/g, '');
      if (materialCtx.includes(fc.number) || materialCtx.includes(numberStr)) {
        results.stats.verified++;
        results.citations.push({
          claim: fc.claim,
          status: 'verified',
          source: '素材库匹配',
          match: fc.number,
        });
      } else {
        // Number not found in source material — potential hallucination
        results.stats.fabricated++;
        results.issues.push({
          type: 'fabricated_number',
          claim: fc.claim,
          detail: lang === 'zh'
            ? `检测到量化数据「${fc.claim}」在原始素材中不存在，疑似AI虚构`
            : `Quantified claim "${fc.claim}" not found in source materials — potential hallucination`,
          severity: 'block',
          suggestion: lang === 'zh'
            ? `请提供「${fc.claim}」对应的真实数据来源，或从简历中移除该数据`
            : `Please provide real data source for "${fc.claim}" or remove it from resume`,
          position: fc.position,
        });
      }
    });
  }

  // === Check for fabricated experiences ===
  function checkFabricatedExperiences(text, materialCtx, results, lang) {
    // Check for "responsible for all/the entire" type claims
    const rolePattern = /负责[了]?(全[部局]?|整个|所有|全部)/g;
    let match;
    while ((match = roleRegexp(rolePattern, text)) !== null) {
      results.stats.claimsChecked++;
      // This type of claim is suspicious if the material doesn't mention it
      if (!materialCtx.includes(match[0].substring(0, 6))) {
        results.stats.uncertain++;
        results.issues.push({
          type: 'exaggerated_role',
          claim: match[0],
          detail: lang === 'zh'
            ? `「${match[0]}」类表述在原始素材中无对应，可能存在夸大`
            : `Claim "${match[0]}" not grounded in source materials`,
          severity: 'warning',
          suggestion: lang === 'zh'
            ? '请确认该职责描述是否与实际情况一致'
            : 'Please verify this responsibility description matches reality',
        });
      } else {
        results.stats.verified++;
      }
    }

    // Check team management claims (e.g., "managed X people")
    const teamPattern = /(?:管理|带领)[了]?(\d+)\s*人/g;
    while ((match = teamPattern.exec(text)) !== null) {
      results.stats.claimsChecked++;
      const num = match[1];
      if (!materialCtx.includes(`${num}人`) && !materialCtx.includes(`${num} 人`)) {
        results.stats.fabricated++;
        results.issues.push({
          type: 'fabricated_team_size',
          claim: match[0],
          detail: lang === 'zh'
            ? `管理${num}人团队的描述在素材库中无依据`
            : `Claim of managing ${num} people not found in source materials`,
          severity: 'block',
          suggestion: lang === 'zh'
            ? `请确认实际管理人数，或改为不涉及具体数字的表述`
            : 'Please verify actual team size or rephrase without specific numbers',
        });
      } else {
        results.stats.verified++;
      }
    }
  }

  // === Check for fake companies/projects/proper nouns ===
  function checkFakeEntities(text, materialCtx, results, lang) {
    // Extract proper nouns (Chinese company names, project names)
    const properNounPattern = /([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*|[「【].*?[」】]|[一-鿿]{2,}(?:科技|集团|公司|平台|系统|项目|方案))/g;
    let match;
    const checked = new Set();

    while ((match = properNounPattern.exec(text)) !== null) {
      const entity = match[0];
      if (checked.has(entity) || entity.length < 3) continue;
      checked.add(entity);

      // Skip common words that aren't proper nouns
      if (/^(公司|项目|系统|平台|方案|团队)$/.test(entity)) continue;

      results.stats.claimsChecked++;
      if (!materialCtx.includes(entity)) {
        // This entity name not found in material — potential fabrication
        results.stats.uncertain++;
        results.issues.push({
          type: 'unverified_entity',
          claim: entity,
          detail: lang === 'zh'
            ? `未在素材库中找到「${entity}」的相关信息`
            : `Entity "${entity}" not found in source materials`,
          severity: 'warning',
          suggestion: lang === 'zh'
            ? `请确认「${entity}」是否为真实存在的项目/公司/平台名称`
            : `Please verify "${entity}" is a real project/company/platform name`,
        });
      } else {
        results.stats.verified++;
      }
    }
  }

  // === Trace which parts of text have source backing ===
  function traceSources(text, materialCtx, results, lang) {
    // Split text into sentences
    const sentences = text.split(/[。.!！?\n]+/).filter(s => s.trim().length > 5);

    sentences.forEach(sentence => {
      const trimmed = sentence.trim();
      if (trimmed.length < 10) return;

      // Check if sentence has keywords matching material context
      const words = trimmed.split(/[,，、\s]+/).filter(w => w.length >= 2);
      let matchCount = 0;
      words.forEach(word => {
        if (materialCtx.includes(word)) matchCount++;
      });

      const matchRatio = matchCount / Math.max(1, words.length);

      if (matchRatio >= 0.3) {
        // Good grounding
        results.citations.push({
          claim: trimmed.substring(0, 80) + (trimmed.length > 80 ? '...' : ''),
          status: 'grounded',
          matchRatio: Math.round(matchRatio * 100),
        });
      } else if (matchRatio < 0.1 && trimmed.length > 30) {
        // Poor grounding — potential hallucination
        results.stats.uncertain++;
        results.issues.push({
          type: 'low_grounding',
          claim: trimmed.substring(0, 80) + (trimmed.length > 80 ? '...' : ''),
          detail: lang === 'zh'
            ? `该句内容与素材库匹配度仅${Math.round(matchRatio * 100)}%，可能包含非原始信息`
            : `This sentence has only ${Math.round(matchRatio * 100)}% match with source materials`,
          severity: 'warning',
          matchRatio: Math.round(matchRatio * 100),
        });
      }
    });
  }

  // === Validate a single claim against the material store ===
  function validateClaim(claim, materialCtx) {
    if (!claim || !materialCtx) return { valid: false, reason: 'no_context' };

    // Direct string match
    if (materialCtx.includes(claim)) {
      return { valid: true, method: 'direct_match' };
    }

    // Substring match (80% of claim words appear in material)
    const claimWords = claim.split(/[\s,，、。.!！?]+/).filter(w => w.length >= 2);
    const matchedWords = claimWords.filter(w => materialCtx.includes(w));
    const ratio = matchedWords.length / Math.max(1, claimWords.length);

    if (ratio >= 0.7) {
      return { valid: true, method: 'partial_match', confidence: ratio };
    } else if (ratio >= 0.4) {
      return { valid: true, method: 'weak_match', confidence: ratio, warning: true };
    }

    return { valid: false, method: 'no_match', confidence: ratio, reason: 'insufficient_source_match' };
  }

  // === Generate source-grounded version of text ===
  function annotateWithSources(text, materialCtx, sources) {
    // Add source reference markers [来源: xxx] to text sections
    if (!sources || sources.length === 0) return text;

    const sourceMap = {};
    sources.forEach(s => {
      if (s.file) sourceMap[s.file] = s;
    });

    // Find material-backed segments and annotate
    const paragraphs = text.split('\n');
    const annotated = paragraphs.map(para => {
      if (para.trim().length < 10) return para;
      // Simple heuristic: if paragraph contains info from any source file, mark it
      for (const [file, src] of Object.entries(sourceMap)) {
        // Check if key terms from this source appear in the paragraph
        const keyTerms = para.split(/[\s,，、。]+/).filter(w => w.length >= 3).slice(0, 5);
        const matchCount = keyTerms.filter(t => materialCtx.includes(t)).length;
        if (matchCount >= 2) {
          return `${para} [📎 来源: ${file}]`;
        }
      }
      return para;
    });

    return annotated.join('\n');
  }

  // === Generate hallucination report for display ===
  function generateReport(validationResult, lang) {
    const r = validationResult;
    const isZh = lang === 'zh';

    return {
      passed: r.severity === SEVERITY.PASS,
      blocked: r.severity === SEVERITY.BLOCK,
      warning: r.severity === SEVERITY.WARNING,
      summary: isZh
        ? `校验完成：${r.stats.claimsChecked}项声明，✅验证${r.stats.verified}项，⚠️存疑${r.stats.uncertain}项，🚫虚构${r.stats.fabricated}项`
        : `Validation: ${r.stats.claimsChecked} claims, ✅${r.stats.verified} verified, ⚠️${r.stats.uncertain} uncertain, 🚫${r.stats.fabricated} fabricated`,
      issues: r.issues.map(i => ({
        ...i,
        displayDetail: i.detail,
        displaySuggestion: i.suggestion,
      })),
      citations: r.citations,
      severity: r.severity,
      stats: r.stats,
    };
  }

  // === Helper: create RegExp that won't cause infinite loop ===
  function roleRegexp(pattern, text) {
    const regex = new RegExp(pattern.source, 'g');
    return regex;
  }

  // === Schema Lock: detect AI-generated placeholder junk ===
  function detectAIPlaceholder(text) {
    if (!text) return false;
    const junkPatterns = [
      /目标岗位从业者/, /相关领域从业者/, /专业技能的从业者/,
      /具备.*能力.*能够.*创造价值/, /熟练掌握.*等.*技能/,
      /responsible for various tasks/, /experienced professional/,
      /[a-zA-Z]+ professional with experience in/,
    ];
    return junkPatterns.some(p => p.test(text));
  }

  // === Validate extracted data fit the SmartResume schema ===
  function schemaValidate(data, schemaKeys) {
    const issues = [];
    // Check for junk placeholder text in each field
    if (data.basic_info) {
      Object.entries(data.basic_info).forEach(([k, v]) => {
        if (typeof v === 'string' && detectAIPlaceholder(v)) {
          issues.push({ field: `basic_info.${k}`, value: v, issue: 'ai_placeholder' });
        }
      });
    }
    // Check work experience for fabricated duties
    (data.work_experience || []).forEach((w, i) => {
      if (w.duties && detectAIPlaceholder(w.duties)) {
        issues.push({ field: `work_experience[${i}].duties`, value: w.duties, issue: 'ai_placeholder' });
      }
    });
    return issues;
  }

  return {
    SEVERITY,
    validate,
    validateClaim,
    annotateWithSources,
    generateReport,
    detectAIPlaceholder,
    schemaValidate,
  };
})();

window.FactChecker = FactChecker;
