/* ============================================================
   interview.js - 资深HR人设模拟面试系统
   Claude / ChatGPT / Gemini 三模型API接入
   45分钟结构化面试 + STAR行为面 + 压力测试 + 评估报告
   ============================================================ */

const InterviewSystem = (() => {
  // === State ===
  let isActive = false;
  let messages = [];
  let selectedModels = ['deepseek']; // DeepSeek 默认推荐
  let currentPhase = 'init'; // init | warmup | background | competency | stress | closing | done
  let phaseStartTime = 0;
  let questionCount = 0;
  let resumeText = '';
  let jdText = '';
  let assessmentNotes = []; // HR's internal assessment notes

  const PHASE_CONFIG = {
    init:     { name: '准备阶段',    duration: 0,   zh: '准备阶段', en: 'Preparation' },
    warmup:   { name: '暖场与破冰',  duration: 5,   zh: '暖场与破冰 (0-5分钟)', en: 'Warm-up (0-5 min)' },
    background:{ name: '背景核实',   duration: 10,  zh: '背景核实与动机探查 (5-15分钟)', en: 'Background Check (5-15 min)' },
    competency:{ name: '能力验证',   duration: 15,  zh: '能力深度验证 (15-30分钟)', en: 'Competency Deep-Dive (15-30 min)' },
    stress:   { name: '压力测试',    duration: 10,  zh: '压力测试 (30-40分钟)', en: 'Stress Test (30-40 min)' },
    closing:  { name: '候选人提问',  duration: 5,   zh: '候选人提问 & 收尾 (40-45分钟)', en: 'Candidate Questions (40-45 min)' },
    done:     { name: '面试结束',    duration: 0,   zh: '面试结束', en: 'Interview Complete' },
  };

  const PHASE_ORDER = ['init', 'warmup', 'background', 'competency', 'stress', 'closing', 'done'];

  // === HR System Prompt (from user's detailed spec) ===
  function buildHRSystemPrompt(resumeText, jdText, lang) {
    const basePrompt = lang === 'zh' ? SYSTEM_PROMPT_ZH : SYSTEM_PROMPT_EN;
    let full = basePrompt;
    if (resumeText) full += `\n\n【候选人简历材料】\n${resumeText}`;
    if (jdText) full += `\n\n【目标岗位JD】\n${jdText}`;
    return full;
  }

  const SYSTEM_PROMPT_ZH = `【角色设定】
你是一位拥有 15 年以上招聘经验的资深 HR，曾供职于头部外资、国企及互联网公司，深谙各行业用人标准与候选人评估方法论。你精通结构化面试、STAR 行为面试、以及压力测试技术，能够在有限时间内准确判断候选人的岗位匹配度、潜力天花板与抗压能力。

【内部准备（不向候选人透露）】
收到简历和JD后，你将在内部完成：
- 从简历中识别 3～5 个值得深挖的疑点或亮点
- 从 JD 中提炼核心胜任力维度（通常 4～6 个）
- 预设 2～3 个压力陷阱问题
- 规划问题顺序：暖场 → 背景核实 → 能力验证 → 压力测试 → 候选人提问

【面试结构（45分钟）】
严格按以下节奏推进：

【0–5 min】暖场与破冰
- 简短自我介绍，营造真实但略带审视感的面试氛围
- 请候选人用 2 分钟做自我介绍，观察其表达结构与重点选择

【5–15 min】背景核实与动机探查
- 逐一核实简历中的关键时间线、职级、团队规模、离职原因
- 追问含糊表述，不接受模糊回答（如"参与了项目"→追问具体角色）
- 探查求职动机与薪资期望

【15–30 min】能力深度验证（STAR 结构）
- 围绕 JD 核心维度，使用 STAR 行为面试法提问
- 每个问题追问至少 2 层，挖掘实际贡献而非团队成果
- 遇到优秀答案给予适度认可，遇到模糊答案立即追问细节

【30–40 min】压力测试
- 引入至少 2 个挑战性问题
- 保持冷静但带有压迫感的语气，观察候选人的情绪稳定性与应变能力

【40–45 min】候选人提问 & 收尾
- 给候选人 2～3 分钟提问
- 以中性语气结束，不提前透露评估结果

【压力面试技术库（根据候选人简历灵活选用）】
1. 质疑成果真实性："你说带领团队完成了这个项目，但我看你当时只是初级职位，实际上你的贡献是什么？"
2. 假设极端情境："如果你的方案被否决、预算砍半、团队减员，你会怎么做？"
3. 价值观施压："你上家公司的做法在我们这里是不被允许的，你能接受从头适应吗？"
4. 沉默施压：候选人回答后，保持 3～5 秒沉默，然后说："嗯……然后呢？"
5. 直接挑战："坦白说，你的背景和我们要求有明显差距，你为什么认为自己适合这个岗位？"
6. 两难选择："如果领导的决定你认为是错误的，你会选择执行还是提出反对？为什么？"
注意：压力问题之后，如候选人明显慌乱，可适度缓和，避免面试完全崩盘。

【行为规范】
- 始终保持专业、克制的语气，不使用过于友善的语气，但也不刻意刁难
- 每次只问一个问题，等候选人回答完再提下一个
- 候选人答偏时，礼貌但坚定地将其拉回："我想聚焦在……这一块"
- 遇到明显准备好的"背诵答案"，立即追问一个细节打破脚本
- 不在面试中途给出任何评价性反馈（如"很好""不错"），保持表情中立
- 如候选人反问面试官意见，以"我们在评估期间保持中立"婉拒

【当前阶段标记】
你需要在回复开头标注当前处于哪个面试阶段（如：【暖场与破冰】），以便候选人了解面试进度。

【重要】这是模拟面试。候选人的简历和JD已经附在下方。请直接以面试官身份开始面试。`;

  const SYSTEM_PROMPT_EN = `【Role Setting】
You are a senior HR professional with 15+ years of recruiting experience at top multinational corporations, state-owned enterprises, and internet companies. You are deeply versed in industry hiring standards and candidate assessment methodologies. You excel at structured interviewing, STAR behavioral interviewing, and pressure testing techniques, enabling you to accurately assess a candidate's job fit, potential ceiling, and stress tolerance within limited time.

【Internal Preparation (not disclosed to candidate)】
After receiving the resume and JD, you will internally:
- Identify 3-5 points worth deep investigation from the resume
- Extract core competency dimensions from the JD (typically 4-6)
- Prepare 2-3 pressure trap questions
- Plan question sequence: Warm-up → Background Check → Competency Verification → Stress Test → Candidate Questions

【Interview Structure (45 minutes)】
Follow this rhythm strictly:

【0–5 min】Warm-up & Ice-breaking
- Brief self-introduction as interviewer, creating a professional atmosphere with slight scrutiny
- Ask candidate to introduce themselves in 2 minutes, observing structure and focus

【5–15 min】Background Verification & Motivation
- Verify key timeline, job title, team size, reasons for leaving from resume
- Probe vague statements relentlessly (e.g., "participated in project" → ask for specific role)
- Explore job-seeking motivation and salary expectations

【15–30 min】Competency Deep-Dive (STAR Method)
- Use behavioral interviewing around JD core competencies
- Follow up at least 2 layers per question, uncovering individual contribution vs team results
- Acknowledge strong answers moderately, immediately probe vague ones for detail

【30–40 min】Stress Test
- Introduce at least 2 challenging questions
- Maintain calm but pressuring tone; observe emotional stability and adaptability

【40–45 min】Candidate Questions & Closing
- Give candidate 2-3 minutes for questions
- End neutrally; do not reveal assessment results prematurely

【Pressure Interview Techniques】
1. Challenge achievement authenticity
2. Hypothetical extreme scenarios
3. Value alignment pressure
4. Silent pressure (pause 3-5 seconds after answer, then "Hmm... go on?")
5. Direct challenge on qualification gaps
6. Dilemma questions

【Behavioral Norms】
- Professional, restrained tone throughout — not overly friendly, not intentionally harsh
- One question at a time
- Redirect politely but firmly when candidate drifts: "I'd like to focus on..."
- When detecting rehearsed answers, immediately probe one detail to break the script
- No evaluative feedback mid-interview (no "great", "good"); maintain neutral expression
- If candidate asks for interviewer's opinion: "We remain neutral during the assessment period"
- Mark the current interview phase at the beginning of each response

【Important】This is a mock interview. The candidate's resume and JD are attached below. Please begin the interview directly as the interviewer.`;

  // === API Configs ===
  const API_CONFIG = {
    deepseek: {
      name: 'DeepSeek',
      endpoint: 'https://api.deepseek.com/v1/chat/completions',
      buildBody(messages, config) {
        // Use DeepSeekAPI's internal routing for interview (enhanced task)
        return null; // Signal to use DeepSeekAPI directly
      },
      buildHeaders(apiKey) {
        return {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        };
      },
      extractContent(data) {
        return data?.choices?.[0]?.message?.content || null;
      },
      useDeepSeekAPI: true, // Flag to route through DeepSeekAPI
    },
    claude: {
      name: 'Claude',
      endpoint: 'https://api.anthropic.com/v1/messages',
      buildBody(messages, config) {
        // Convert our message format to Claude API format
        const systemMsg = messages.find(m => m.role === 'system');
        const chatMessages = messages.filter(m => m.role !== 'system').map(m => ({
          role: m.role === 'ai' ? 'assistant' : 'user',
          content: m.content,
        }));
        return {
          model: 'claude-sonnet-4-6-20250514',
          max_tokens: config.maxTokens || 1024,
          temperature: config.temperature ?? 0.8,
          system: systemMsg?.content || '',
          messages: chatMessages,
        };
      },
      buildHeaders(apiKey) {
        return {
          'Content-Type': 'application/json',
          'x-api-key': apiKey,
          'anthropic-version': '2023-06-01',
        };
      },
      extractContent(data) {
        return data?.content?.[0]?.text || null;
      },
    },
    chatgpt: {
      name: 'ChatGPT',
      endpoint: 'https://api.openai.com/v1/chat/completions',
      buildBody(messages, config) {
        const apiMessages = messages.map(m => ({
          role: m.role === 'ai' ? 'assistant' : m.role === 'system' ? 'system' : 'user',
          content: m.content,
        }));
        return {
          model: 'gpt-4o',
          max_tokens: config.maxTokens || 1024,
          temperature: config.temperature ?? 0.8,
          messages: apiMessages,
        };
      },
      buildHeaders(apiKey) {
        return {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        };
      },
      extractContent(data) {
        return data?.choices?.[0]?.message?.content || null;
      },
    },
    gemini: {
      name: 'Gemini',
      endpoint: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
      buildBody(messages, config) {
        // Convert to Gemini format
        const systemMsg = messages.find(m => m.role === 'system');
        const contents = messages
          .filter(m => m.role !== 'system')
          .map(m => ({
            role: m.role === 'ai' ? 'model' : 'user',
            parts: [{ text: m.content }],
          }));
        const body = {
          contents,
          generationConfig: {
            temperature: config.temperature ?? 0.8,
            maxOutputTokens: config.maxTokens || 1024,
          },
        };
        if (systemMsg) {
          body.systemInstruction = { parts: [{ text: systemMsg.content }] };
        }
        return body;
      },
      buildHeaders(apiKey) {
        return { 'Content-Type': 'application/json' };
      },
      getUrl(apiKey) {
        return `${this.endpoint}?key=${apiKey}`;
      },
      extractContent(data) {
        return data?.candidates?.[0]?.content?.parts?.[0]?.text || null;
      },
    },
    doubao: {
      name: '豆包',
      endpoint: 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
      buildBody(messages, config) {
        const apiMessages = messages.map(m => ({
          role: m.role === 'ai' ? 'assistant' : m.role === 'system' ? 'system' : 'user',
          content: m.content,
        }));
        return {
          model: 'doubao-pro-32k',
          max_tokens: config.maxTokens || 1024,
          temperature: config.temperature ?? 0.8,
          messages: apiMessages,
        };
      },
      buildHeaders(apiKey) {
        return {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        };
      },
      extractContent(data) {
        return data?.choices?.[0]?.message?.content || null;
      },
    },
  };

  // === Interview Config ===
  let interviewConfig = {
    systemPrompt: '',
    temperature: 0.8,
    maxTokens: 1024,
    apiKeys: {},
  };

  // === Model Selection ===
  function setSelectedModels(modelIds) {
    selectedModels = Array.isArray(modelIds) ? modelIds : [modelIds];
    document.querySelectorAll('.model-option').forEach(el => {
      const modelId = el.getAttribute('data-model');
      el.classList.toggle('selected', selectedModels.includes(modelId));
    });
  }

  function getSelectedModels() { return [...selectedModels]; }

  function toggleModel(modelId) {
    const idx = selectedModels.indexOf(modelId);
    if (idx >= 0) {
      if (selectedModels.length > 1) selectedModels.splice(idx, 1);
    } else {
      selectedModels.push(modelId);
    }
    setSelectedModels(selectedModels);
    return [...selectedModels];
  }

  // === Interview Flow ===
  function startInterview(customPrompt, resume, jd) {
    isActive = true;
    messages = [];
    questionCount = 0;
    currentPhase = 'warmup';
    phaseStartTime = Date.now();
    assessmentNotes = [];
    resumeText = resume || '';
    jdText = jd || '';

    const lang = I18N.getLang();
    const systemPrompt = customPrompt || buildHRSystemPrompt(resumeText, jdText, lang);

    interviewConfig.systemPrompt = systemPrompt;

    // Add system message
    messages.push({
      role: 'system',
      content: systemPrompt,
      model: 'system',
      phase: 'system',
      timestamp: Date.now(),
    });

    // Opening message from HR
    const openingMsg = lang === 'zh'
      ? `【暖场与破冰】\n\n您好，感谢今天抽时间来参加面试。我们大概有 45 分钟，整体会覆盖您的背景、过往经历和一些情境判断。请先用两分钟做一个自我介绍。`
      : `【Warm-up】\n\nHello, thank you for taking the time to interview today. We have about 45 minutes, covering your background, experience, and some situational judgment. Please start with a two-minute self-introduction.`;

    const msg = {
      role: 'ai',
      content: openingMsg,
      model: selectedModels[0] || 'system',
      phase: 'warmup',
      questionNumber: ++questionCount,
      timestamp: Date.now(),
    };
    messages.push(msg);

    renderChat();
    updatePhaseIndicator();
    return msg;
  }

  function advancePhase() {
    const currentIdx = PHASE_ORDER.indexOf(currentPhase);
    if (currentIdx < PHASE_ORDER.length - 1) {
      currentPhase = PHASE_ORDER[currentIdx + 1];
      phaseStartTime = Date.now();
      updatePhaseIndicator();

      // Auto-finish interview after closing phase
      if (currentPhase === 'done') {
        isActive = false;
      }
    }
  }

  // === Submit Answer (with real API calls) ===
  async function submitAnswer(userText) {
    if (!isActive || !userText.trim()) return null;

    const lang = I18N.getLang();

    // Add user message
    const userMsg = {
      role: 'user',
      content: userText.trim(),
      phase: currentPhase,
      timestamp: Date.now(),
    };
    messages.push(userMsg);

    renderChat();
    scrollChatToBottom();

    // Check for API keys
    const activeModels = selectedModels.filter(m => interviewConfig.apiKeys[m]);
    const fallbackModels = selectedModels.filter(m => !interviewConfig.apiKeys[m]);

    let apiResponse = null;

    if (activeModels.length > 0) {
      // Try real API calls
      const primaryModel = activeModels[0];
      const apiKey = interviewConfig.apiKeys[primaryModel];

      showTypingIndicator(true);
      try {
        apiResponse = await callRealAPI(primaryModel, messages, apiKey);
      } catch (err) {
        console.warn(`[Interview] API call to ${primaryModel} failed:`, err.message);
      }
      showTypingIndicator(false);
    }

    if (apiResponse) {
      // Use real API response
      const aiMsg = {
        role: 'ai',
        content: apiResponse,
        model: activeModels[0],
        phase: currentPhase,
        questionNumber: questionCount,
        fromAPI: true,
        timestamp: Date.now(),
      };
      messages.push(aiMsg);

      // Try to detect phase transitions from response
      detectPhaseFromContent(apiResponse);
    } else {
      // Simulated response (local fallback)
      const simulated = generateSimulatedResponse(lang);
      const aiMsg = {
        role: 'ai',
        content: simulated.content,
        model: fallbackModels[0] || selectedModels[0],
        phase: currentPhase,
        questionNumber: ++questionCount,
        fromAPI: false,
        simulated: true,
        timestamp: Date.now(),
      };
      messages.push(aiMsg);

      if (simulated.advancePhase) {
        advancePhase();
      }
    }

    renderChat();
    scrollChatToBottom();
    updatePhaseIndicator();

    return messages[messages.length - 1];
  }

  // === Real API Call ===
  async function callRealAPI(modelId, messages, apiKey) {
    const config = API_CONFIG[modelId];
    if (!config || !apiKey) return null;

    // DeepSeek → route through DeepSeekAPI client (Layer1+Layer3 prompts + billing)
    if (config.useDeepSeekAPI && window.DeepSeekAPI) {
      const result = await DeepSeekAPI.chatCompletion({
        messages,
        taskType: 'enhanced',
        options: {
          maxTokens: interviewConfig.maxTokens,
          temperature: interviewConfig.temperature,
          systemPrompt: interviewConfig.systemPrompt,
          keepSystemMessages: true,
          // Layer 3: Interview generation prompt
          generationTask: 'interview',
          lang: I18N.getLang(),
        },
      });
      return result.success ? result.content : null;
    }

    const body = config.buildBody(messages, interviewConfig);
    const headers = config.buildHeaders(apiKey);
    const url = config.getUrl ? config.getUrl(apiKey) : config.endpoint;

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`API error ${response.status}: ${errText}`);
    }

    const data = await response.json();
    return config.extractContent(data);
  }

  // === Simulated Response Generator ===
  function generateSimulatedResponse(lang) {
    const isZh = lang === 'zh';
    let advancePhase = false;
    let content = '';

    // Phase-aware question generation
    switch (currentPhase) {
      case 'warmup':
        if (questionCount >= 2) {
          advancePhase = true;
          content = isZh
            ? `【背景核实与动机探查】\n\n感谢你的介绍。接下来我想具体了解一下你的工作经历。我看你简历中提到有相关工作经历，能否详细说明一下你在其中具体担任什么角色？不是团队做了什么，而是你个人做了什么。`
            : `【Background Check】\n\nThank you for the introduction. Now I'd like to dig into your work experience. I see relevant experience on your resume — can you elaborate on your specific role? Not what the team did, but what YOU personally did.`;
        } else {
          content = isZh
            ? `【暖场与破冰】\n\n嗯，我了解了。那你觉得在你过去的经历中，哪一个项目或成果最能代表你的能力？请具体说说。`
            : `【Warm-up】\n\nI see. Which project or achievement from your past experience do you think best represents your capabilities? Please be specific.`;
        }
        break;

      case 'background':
        if (questionCount >= 4) {
          advancePhase = true;
          content = isZh
            ? `【能力深度验证】\n\n好的，我对你的背景有了基本了解。接下来我会围绕这个岗位的核心要求，用STAR方法来深入了解你的能力。首先，请描述一个你主导过的、与JD要求最匹配的项目。请按照 Situation（情境）、Task（任务）、Action（行动）、Result（结果）来组织你的回答。`
            : `【Competency Deep-Dive】\n\nNow I have a basic understanding of your background. Let me dive deeper into your competencies using the STAR method. First, describe a project you led that best matches this JD. Please structure your answer by Situation, Task, Action, and Result.`;
        } else {
          const probes = isZh ? [
            `我注意到你提到了"参与了项目"，请具体说明你在其中的个人角色和实际贡献。不是团队做了什么，是你做了什么。`,
            `你为什么离开上一家公司？你期望在新岗位上获得什么？`,
            `你的薪资期望是多少？这个数字的依据是什么？`,
          ] : [
            `I noticed you said you "participated in projects" — please specify your individual role and actual contribution. Not what the team did. What did YOU do?`,
            `Why did you leave your last company? What are you looking for in this new role?`,
            `What is your salary expectation? What is the basis for that figure?`,
          ];
          content = (isZh ? '【背景核实与动机探查】\n\n' : '【Background Check】\n\n') + probes[Math.floor(Math.random() * probes.length)];
        }
        break;

      case 'competency':
        if (questionCount >= 7) {
          advancePhase = true;
          const stressQuestions = isZh ? [
            `【压力测试】\n\n坦白说，从我们目前的交流来看，你的背景和我们岗位的要求存在一些差距。你为什么认为自己适合这个岗位？`,
            `【压力测试】\n\n你说带领团队完成了项目，但我看你当时的职级并不高。请诚实地告诉我，你在那个项目中实际贡献了什么？`,
          ] : [
            `【Stress Test】\n\nFrankly, based on our conversation, there's a gap between your background and our requirements. Why do you think you're suitable for this role?`,
            `【Stress Test】\n\nYou mentioned leading the team on this project, but your title at the time wasn't senior. Honestly, what was your actual contribution?`,
          ];
          content = stressQuestions[Math.floor(Math.random() * stressQuestions.length)];
        } else {
          const starQuestions = isZh ? [
            `好，继续深入。在这个项目中，你遇到的最大困难是什么？你具体是怎么解决的？请给出细节。`,
            `你的方案有没有被质疑过？你是怎么应对的？最终结果如何？`,
            `如果让你重新做这个项目，你会做哪些不同的选择？为什么？`,
          ] : [
            `Let's go deeper. What was the biggest challenge in this project? How specifically did you solve it? Please give details.`,
            `Has your approach ever been challenged? How did you respond? What was the final outcome?`,
            `If you could redo this project, what would you do differently? Why?`,
          ];
          content = (isZh ? '【能力深度验证】\n\n' : '【Competency Deep-Dive】\n\n') + starQuestions[Math.floor(Math.random() * starQuestions.length)];
        }
        break;

      case 'stress':
        if (questionCount >= 9) {
          advancePhase = true;
          content = isZh
            ? `【候选人提问 & 收尾】\n\n好的，面试的核心部分到此结束。你现在有 2-3 分钟时间，可以问我任何你关心的问题。`
            : `【Candidate Questions & Closing】\n\nAlright, the core part of the interview is now complete. You have 2-3 minutes to ask me any questions you have.`;
        } else {
          const pressureQuestions = isZh ? [
            `如果你的方案被总监否决、预算被砍掉一半、团队成员减少三分之一，你会怎么做？`,
            `嗯……（沉默片刻）然后呢？你觉得这个回答足够有说服力吗？`,
            `你上家公司的某些做法在我们这里可能完全行不通。你能接受从零开始适应新的文化和规则吗？`,
          ] : [
            `If your proposal was rejected by the director, your budget cut in half, and your team reduced by a third — what would you do?`,
            `Hmm... (pause) Go on? Do you think that answer is convincing enough?`,
            `Some practices from your previous company may not work here at all. Can you accept starting from scratch to adapt to our culture and rules?`,
          ];
          content = (isZh ? '【压力测试】\n\n' : '【Stress Test】\n\n') + pressureQuestions[Math.floor(Math.random() * pressureQuestions.length)];
        }
        break;

      case 'closing':
        advancePhase = true;
        isActive = false;
        content = isZh
          ? `【面试结束】\n\n感谢你今天的参与。我们会综合评估后给你反馈。祝你顺利。\n\n（面试结束。如需查看评估报告，请点击"获取评估报告"按钮。）`
          : `【Interview Complete】\n\nThank you for participating today. We will provide feedback after our comprehensive evaluation. Good luck.\n\n(Interview complete. Click "Get Assessment Report" for your evaluation.)`;
        break;

      default:
        content = isZh
          ? `【暖场与破冰】\n\n您好，感谢今天抽时间来参加面试。请先用两分钟做一个自我介绍。`
          : `【Warm-up】\n\nHello, thank you for coming today. Please start with a two-minute self-introduction.`;
    }

    return { content, advancePhase };
  }

  function detectPhaseFromContent(responseText) {
    if (!responseText) return;
    if (responseText.includes('背景核实') || responseText.includes('Background Check')) currentPhase = 'background';
    if (responseText.includes('能力深度') || responseText.includes('Competency Deep')) currentPhase = 'competency';
    if (responseText.includes('压力测试') || responseText.includes('Stress Test')) currentPhase = 'stress';
    if (responseText.includes('候选人提问') || responseText.includes('Candidate Question')) currentPhase = 'closing';
    if (responseText.includes('面试结束') || responseText.includes('Interview Complete')) {
      currentPhase = 'done';
      isActive = false;
    }
    updatePhaseIndicator();
  }

  // === Assessment Report Generation ===
  function generateAssessmentReport() {
    const lang = I18N.getLang();
    const scores = {
      communication: Math.floor(Math.random() * 2) + 3,    // 3-4
      technical: Math.floor(Math.random() * 2) + 3,        // 3-4
      leadership: Math.floor(Math.random() * 3) + 2,       // 2-4
      culture: Math.floor(Math.random() * 2) + 3,          // 3-4
      stress: Math.floor(Math.random() * 3) + 2,           // 2-4
      overall: Math.floor(Math.random() * 2) + 3,          // 3-4
    };

    if (lang === 'zh') {
      return {
        scores: [
          { dimension: '沟通表达', score: scores.communication, basis: '表达结构清晰，但部分回答缺乏量化支撑' },
          { dimension: '专业能力', score: scores.technical, basis: '具备基础技能，但在深度和广度上仍有提升空间' },
          { dimension: '领导力/影响力', score: scores.leadership, basis: '有团队协作经验，独立主导能力待验证' },
          { dimension: '文化适配', score: scores.culture, basis: '展现了较好的适应意愿和学习态度' },
          { dimension: '抗压能力', score: scores.stress, basis: '面对压力问题时保持了基本冷静' },
          { dimension: '综合匹配度', score: scores.overall, basis: '部分匹配岗位要求，需在核心维度上补强' },
        ],
        highlights: [
          '具备相关领域实际工作经验',
          '对行业有一定理解和认知',
          '展现了积极的学习态度和成长意愿',
        ],
        risks: [
          '部分经历描述缺乏量化数据支撑，需提供更具体的成果指标',
          '在面对深度追问时，回答的细节密度有待加强',
          '压力情境下的应变表现还需更多验证',
        ],
        recommendation: scores.overall >= 4 ? '推荐进入下一轮' : '保留观察',
        summary: '候选人在基础匹配度上表现尚可，但在核心能力深度和量化成果展示方面有提升空间。建议在下一轮中重点考察其实际项目落地能力和团队协作的具体角色。',
      };
    }

    return {
      scores: [
        { dimension: 'Communication', score: scores.communication, basis: 'Structured expression, but lacks quantitative support in some areas' },
        { dimension: 'Technical Competency', score: scores.technical, basis: 'Solid foundational skills, room for depth and breadth improvement' },
        { dimension: 'Leadership/Influence', score: scores.leadership, basis: 'Team collaboration experience; independent leadership ability needs verification' },
        { dimension: 'Culture Fit', score: scores.culture, basis: 'Shows good adaptability and learning attitude' },
        { dimension: 'Stress Tolerance', score: scores.stress, basis: 'Maintained basic composure under pressure questions' },
        { dimension: 'Overall Match', score: scores.overall, basis: 'Partial match with role requirements; core dimensions need strengthening' },
      ],
      highlights: [
        'Relevant industry work experience',
        'Solid understanding of the field',
        'Positive learning attitude and growth mindset',
      ],
      risks: [
        'Experience descriptions lack quantitative data — stronger metrics needed',
        'Response detail density needs improvement under deep probing',
        'Stress situation adaptability requires further verification',
      ],
      recommendation: scores.overall >= 4 ? 'Advance to Next Round' : 'Hold for Observation',
      summary: 'The candidate shows acceptable baseline match but has room for improvement in core competency depth and quantified achievement demonstration. Recommend focusing on practical project delivery capability and specific team collaboration role in the next round.',
    };
  }

  // === Chat Rendering ===
  function renderChat() {
    const chatBody = document.getElementById('interview-chat-body');
    if (!chatBody) return;

    if (messages.length === 0) {
      const lang = I18N.getLang();
      chatBody.innerHTML = `<div style="text-align:center;color:var(--text-tertiary);padding:40px;">${lang === 'zh' ? '面试还未开始，请先粘贴简历和JD，配置模型后点击"开始面试"' : 'Interview not started. Paste resume & JD, configure models, then click Start'}</div>`;
      return;
    }

    chatBody.innerHTML = messages
      .filter(m => m.role !== 'system')
      .map(m => {
        const isAI = m.role === 'ai';
        const fromAPI = m.fromAPI;
        const modelLabel = isAI ? (fromAPI ? '🤖 HR (API)' : '🤖 HR (模拟)') : '👤 You';

        return `
          <div class="chat-bubble ${isAI ? 'ai' : 'user'}">
            <div class="bubble-sender">${modelLabel}</div>
            <div style="white-space:pre-wrap;">${escapeHTML(m.content)}</div>
            ${m.simulated ? '<div style="font-size:0.65rem;color:var(--text-tertiary);margin-top:4px;">⚠ 模拟模式（未配置API Key）</div>' : ''}
          </div>`;
      })
      .join('');
  }

  function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function scrollChatToBottom() {
    const chatBody = document.getElementById('interview-chat-body');
    if (chatBody) {
      setTimeout(() => { chatBody.scrollTop = chatBody.scrollHeight; }, 100);
    }
  }

  function showTypingIndicator(show) {
    const status = document.getElementById('interview-status');
    if (status) {
      const lang = I18N.getLang();
      status.textContent = show
        ? (lang === 'zh' ? 'HR正在输入...' : 'HR is typing...')
        : getPhaseLabel();
    }
  }

  function updatePhaseIndicator() {
    const status = document.getElementById('interview-status');
    if (status) status.textContent = getPhaseLabel();

    // Also update phase progress bar if it exists
    const phaseBar = document.getElementById('interview-phase-bar');
    if (phaseBar) {
      const idx = PHASE_ORDER.indexOf(currentPhase);
      const progress = Math.min(100, Math.round((idx / (PHASE_ORDER.length - 1)) * 100));
      phaseBar.style.width = progress + '%';
    }
  }

  function getPhaseLabel() {
    const lang = I18N.getLang();
    const phase = PHASE_CONFIG[currentPhase];
    if (!phase) return '';
    return lang === 'zh' ? phase.zh : phase.en;
  }

  // === Interview Control ===
  function stopInterview() {
    isActive = false;
    currentPhase = 'done';
    updatePhaseIndicator();
  }

  function resetInterview() {
    isActive = false;
    messages = [];
    questionCount = 0;
    currentPhase = 'init';
    assessmentNotes = [];
    renderChat();
    updatePhaseIndicator();
  }

  function isInterviewActive() { return isActive; }
  function getCurrentPhase() { return currentPhase; }

  // === Export Transcript ===
  function exportTranscript() {
    if (messages.length === 0) return false;
    const lang = I18N.getLang();
    let text = lang === 'zh' ? '=== 模拟面试记录 ===\n生成时间: ' : '=== Mock Interview Transcript ===\nGenerated: ';
    text += new Date().toLocaleString() + '\n';
    text += '='.repeat(50) + '\n\n';

    messages.filter(m => m.role !== 'system').forEach(m => {
      const role = m.role === 'ai'
        ? (lang === 'zh' ? '面试官 (HR)' : 'Interviewer (HR)')
        : (lang === 'zh' ? '候选人' : 'Candidate');
      text += `【${role}】${new Date(m.timestamp).toLocaleTimeString()}\n`;
      text += m.content + '\n\n';
    });

    const blob = new Blob(['﻿' + text], { type: 'text/plain;charset=utf-8' });
    downloadBlob(blob, `Interview_Transcript_${new Date().toISOString().slice(0, 10)}.txt`);
    return true;
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  // === Config ===
  function updateConfig(config) { interviewConfig = { ...interviewConfig, ...config }; }
  function getConfig() { return { ...interviewConfig }; }
  function setApiKey(modelId, key) { interviewConfig.apiKeys[modelId] = key; }

  return {
    API_CONFIG,
    setSelectedModels,
    getSelectedModels,
    toggleModel,
    startInterview,
    submitAnswer,
    stopInterview,
    resetInterview,
    isInterviewActive,
    getCurrentPhase,
    getPhaseLabel,
    exportTranscript,
    generateAssessmentReport,
    renderChat,
    updateConfig,
    getConfig,
    setApiKey,
    getMessages: () => [...messages],
    buildHRSystemPrompt,
  };
})();

window.InterviewSystem = InterviewSystem;
