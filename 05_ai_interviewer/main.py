"""
05_ai_interviewer/main.py — AI 模拟面试官对话系统（可独立运行）

输入: 01_jd_parser JD + 02_resume_parser 简历
角色: HR常规面 / 技术压力面 / 英文外企面试
对话: 4阶段结构化面试 (开场→背景/实习/项目深挖→核心能力匹配→动机/反问收尾)
约束: 严格基于简历已有经历+JD提问，不编造不存在的内容
铁律: 全程口语化、一轮一问、禁止敷衍短句、继续自动推进
"""

import sys
import json
import asyncio
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.multi_model_gateway import MultiModelGateway
from common.language_switch import LanguageSwitch


# ═══════════════════════════════════════════════════════════════
# 4 阶段面试流程定义
# ═══════════════════════════════════════════════════════════════

@dataclass
class InterviewPhase:
    order: int
    max_rounds: int   # 该阶段最大轮次（含追问）
    zh: str
    en: str


PHASES: dict[str, InterviewPhase] = {
    "opening": InterviewPhase(
        0, 1,
        "阶段1：开场寒暄 + 自我介绍引导",
        "Phase 1: Opening & Self-Introduction",
    ),
    "background": InterviewPhase(
        1, 5,
        "阶段2：教育背景、实习经历、项目细节深挖",
        "Phase 2: Education, Internship & Project Deep-Dive",
    ),
    "competency": InterviewPhase(
        2, 3,
        "阶段3：岗位核心能力匹配、技术难点与量化成果",
        "Phase 3: Core Competency, Technical Challenges & Results",
    ),
    "closing": InterviewPhase(
        3, 2,
        "阶段4：求职动机、职业规划 + 候选人反问",
        "Phase 4: Motivation, Career Plan & Candidate Questions",
    ),
}

# 阶段推进顺序
PHASE_ORDER = ["opening", "background", "competency", "closing"]


# ═══════════════════════════════════════════════════════════════
# 面试官人设（含完整铁律）
# ═══════════════════════════════════════════════════════════════

PERSONAS: dict[str, dict] = {
    "hr": {
        "role": "资深 HR 面试官",
        "background": (
            "你拥有 15 年以上招聘经验，曾供职于头部外资（Google、Microsoft）、"
            "国企（中石油、中国移动）、及互联网大厂（阿里、腾讯、字节跳动），"
            "深谙各行业用人标准与候选人评估方法论。"
            "你精通结构化面试、STAR 行为面试、以及压力测试技术，"
            "能通过精准追问识别候选人简历中的水分与真实能力。"
            "你面试过 5000+ 候选人，从应届生到 VP 级别。"
        ),
        "style": (
            "专业亲和开场但追问犀利，全程口语化自然对话，不使用'请继续''接着说'等敷衍短句；"
            "不接受笼统回答（如'我们团队一起做的'），遇到模糊表述立即打断追问个人贡献；"
            "面试有温度的压迫感——候选人感到被尊重但无法糊弄；"
            "语气正式但柔和，符合真实线下面试节奏，不机械、不生硬，不连续重复话术。"
        ),
        "temperature": 0.7,
    },
    "tech": {
        "role": "技术面试官（资深架构师）",
        "background": (
            "你拥有 12 年以上一线研发经验，曾在头部互联网公司担任技术总监/架构师，"
            "主导过日均亿级流量的系统设计。你深挖技术细节、系统设计权衡、代码思维，"
            "能一眼看出候选人是真正深入做过还是只在简历上写过。"
        ),
        "style": (
            "直接切入技术核心，从项目经历深挖到系统设计原理；"
            "追问具体的技术选型理由、性能数据、遇到的关键 bug 及修复过程；"
            "给出极端场景让候选人现场设计，观察思维过程而非最终答案；"
            "全程口语化，一轮一问，不机械重复话术。"
        ),
        "temperature": 0.5,
    },
    "stress": {
        "role": "压力面试官",
        "background": (
            "你专门执行高压力面试，目标是测试候选人在极端环境下的"
            "情绪管理、逻辑思维和抗压能力。你擅长质疑成果真实性、"
            "沉默施压、给出不可能完成的任务情境。"
        ),
        "style": (
            "质疑一切：'这个项目真的是你主导的吗？请说出具体架构细节。'"
            "沉默施压：候选人回答后保持 3-5 秒沉默，观察反应。"
            "极端情境：'如果明天上线但系统崩了你怎么办？团队成员全离职了？'"
            "所有质疑必须有指向性，而非无意义攻击；全程口语化，一轮一问。"
        ),
        "temperature": 0.8,
    },
    "english": {
        "role": "English Interviewer (Foreign Hiring Manager)",
        "background": (
            "You are a senior hiring manager with 15+ years at multinational "
            "companies. You conduct behavioral interviews using STAR method, "
            "evaluate cultural fit, and assess English communication skills. "
            "You've worked across US, Europe, and APAC regions."
        ),
        "style": (
            "Full English only, behavioral questions with STAR framework, "
            "cultural fit probing, cross-cultural communication assessment. "
            "Polite but thorough — you won't accept vague answers. "
            "One question per turn, never use 'go on' or 'continue' as standalone replies."
        ),
        "temperature": 0.7,
    },
}


# ═══════════════════════════════════════════════════════════════
# 开场白
# ═══════════════════════════════════════════════════════════════

OPENINGS: dict[str, dict[str, str]] = {
    "hr": {
        "zh": (
            "你好，我是今天的面试官，我做了十几年招聘，面过各种类型的候选人。"
            "今天我们围绕你的真实经历来聊——你具体做了什么、怎么做的、结果怎样。"
            "我会问得比较细，希望用具体的事例来回答。"
            "先请你用2分钟左右做一下自我介绍吧。"
        ),
        "en": (
            "Hello, I'm your interviewer today. I've been recruiting for over 15 years "
            "across multinational corporations, state-owned enterprises, and tech companies. "
            "Today I'll focus on your real experience — what you did, how you did it, and the results. "
            "I'll ask detailed follow-ups, so please answer with specific examples. "
            "Let's start — please introduce yourself in about 2 minutes."
        ),
    },
    "tech": {
        "zh": (
            "你好，我是今天的技术面试官，做了12年架构师。"
            "今天主要深挖你的技术深度——你选了什么方案、为什么这么选、踩过什么坑、怎么解决的。"
            "请先做一个2分钟自我介绍，重点说你的核心技术栈和最有挑战的项目。"
        ),
        "en": (
            "Hi, I'm your technical interviewer, a principal architect with 12 years in the industry. "
            "Today we'll go deep on your technical decisions — what you chose, why, "
            "what went wrong, and how you fixed it. "
            "Please introduce yourself in 2 minutes, focusing on your core tech stack and most challenging project."
        ),
    },
    "stress": {
        "zh": (
            "请坐。先说明一下，今天这场面试会比较直接——"
            "我会针对你简历里的每一项追问具体细节，不清楚的地方我会打断追问。"
            "我希望看到真实的能力，不是漂亮的话术。先自我介绍吧。"
        ),
        "en": (
            "Have a seat. To be upfront — this will be a direct conversation. "
            "I'll push for details on everything in your resume, "
            "and I'll interrupt if something isn't clear. "
            "I'm looking for real capability, not polished talking points. Start with your introduction."
        ),
    },
    "english": {
        "zh": (
            "Welcome. This entire interview will be conducted in English. "
            "I'll be assessing both your professional experience and your English communication skills. "
            "Please introduce yourself in about 2 minutes."
        ),
        "en": (
            "Welcome. This entire interview will be conducted in English. "
            "I'll be assessing both your professional experience and your English communication skills. "
            "Please introduce yourself in about 2 minutes."
        ),
    },
}


# ═══════════════════════════════════════════════════════════════
# "继续" 触发词（自动推进到下一阶段）
# ═══════════════════════════════════════════════════════════════

SKIP_TRIGGERS_ZH = ["继续", "下一题", "下一个", "往下", "接着来"]
SKIP_TRIGGERS_EN = ["continue", "next", "next question", "go on", "proceed"]


def _is_skip_input(user_input: str, lang: str = "zh") -> bool:
    """检测候选人是否输入了'继续/下一题'等跳过信号。"""
    text = user_input.strip().lower()
    # 长文本不是跳过信号
    if len(text) > 10:
        return False
    triggers = SKIP_TRIGGERS_ZH if lang == "zh" else SKIP_TRIGGERS_EN
    return any(text == t or text.startswith(t) for t in triggers)


# ═══════════════════════════════════════════════════════════════
# AI 面试官主类
# ═══════════════════════════════════════════════════════════════

class AIInterviewer:
    """
    AI 模拟面试官 — 4 阶段结构化面试。
    所有提问严格基于候选人简历真实内容 + JD 岗位要求。

    双模式：
      - API 模式：调用 LLM 生成自然对话（需配置 API Key）
      - 本地模式：基于简历数据模板化生成针对性提问（无需 API，永久可用）
    """

    def __init__(self):
        self._messages: list[dict] = []
        self._current_phase = "opening"
        self._question_count = 0
        self._jd_context = ""
        self._resume_context = ""
        self._jd_data: dict = {}
        self._resume_data: dict = {}
        self._phase_rounds: dict[str, int] = {p: 0 for p in PHASE_ORDER}
        self._last_user_input = ""
        self._asked_topics: set[str] = set()  # 本地模式追踪已问话题

    # ── 初始化 ──────────────────────────────────────────────

    def init_session(
        self,
        jd_data: dict,
        resume_data: dict,
        persona: str = "hr",
    ) -> dict:
        """初始化面试会话，绑定 JD + 简历素材。"""
        self._jd_context = json.dumps(jd_data or {}, ensure_ascii=False)
        self._resume_context = json.dumps(resume_data or {}, ensure_ascii=False)
        self._jd_data = jd_data or {}
        self._resume_data = resume_data or {}
        self._messages = []
        self._current_phase = "opening"
        self._question_count = 0
        self._phase_rounds = {p: 0 for p in PHASE_ORDER}
        self._last_user_input = ""
        self._asked_topics = set()
        return PERSONAS.get(persona, PERSONAS["hr"])

    def get_opening(self, persona: str = "hr", lang: str = "zh") -> str:
        """获取面试开场白。"""
        return OPENINGS.get(persona, OPENINGS["hr"]).get(lang, OPENINGS["hr"]["zh"])

    # ── 对话主循环 ──────────────────────────────────────────

    async def chat(
        self,
        user_answer: str,
        gateway: MultiModelGateway,
        persona: str = "hr",
        lang: str = "zh",
    ) -> dict:
        """
        处理一轮面试对话。

        若候选人输入"继续"/"下一题"：自动推进到下一个阶段，开启新问题。
        否则：针对性追问细节、数据、难点。
        """
        cfg = PERSONAS.get(persona, PERSONAS["hr"])
        self._messages.append({"role": "user", "content": user_answer})
        self._last_user_input = user_answer.strip()

        # ── 检测"继续/下一题"→ 强制推进阶段 ──
        skip_triggered = _is_skip_input(user_answer, lang)
        if skip_triggered and self._question_count > 0:
            self._force_next_phase()

        # ── 正常阶段推进 ──
        phase = self._advance_phase()

        # ── 构建系统提示词（含完整铁律 + JD/简历素材） ──
        system_prompt = self._build_system_prompt(cfg, phase, lang, skip_triggered)

        # ── 调用 AI ──
        result = await gateway.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                *self._messages[-12:],
            ],
            task_type="interview",
            options={
                "max_tokens": 1024,
                "temperature": cfg["temperature"],
                "lang": lang,
            },
        )

        reply = (
            result.content.strip()
            if result.success
            else self._fallback_reply(lang)
        )
        self._messages.append({"role": "assistant", "content": reply})
        self._question_count += 1
        self._phase_rounds[self._current_phase] += 1

        return {
            "reply": reply,
            "phase": {
                "key": self._current_phase,
                "zh": phase.zh,
                "en": phase.en,
                "order": phase.order,
            },
            "question_count": self._question_count,
        }

    def _fallback_reply(self, lang: str) -> str:
        """AI 失败时的兜底提问——使用本地模板引擎生成针对性问题。"""
        return self._build_local_reply(lang)

    # ── 本地模拟面试引擎（无需 API，基于简历数据模板化提问）──

    def _build_local_reply(self, lang: str) -> str:
        """
        基于候选人简历数据 + 当前阶段，模板化生成针对性追问。
        不依赖任何外部 API，保证面试永远可用。
        """
        resume = self._resume_data
        jd = self._jd_data

        # 提取简历关键事实
        bi = resume.get("basic_info", {}) or {}
        name = bi.get("name", "") or "候选人"
        target_job = bi.get("target_job", "") or jd.get("position", "") or "该岗位"
        edu_list = resume.get("education", []) or []
        work_list = resume.get("work_experience", []) or []
        proj_list = resume.get("projects", []) or []
        skills_list = resume.get("skills", []) or []
        skill_names = [s.get("name", s) if isinstance(s, dict) else str(s) for s in skills_list]
        jd_skills = jd.get("hard_skills", []) or []

        # ── 根据阶段生成针对性提问 ──
        phase = self._current_phase
        q_num = self._question_count

        if lang == "zh":
            return self._local_reply_zh(phase, q_num, name, target_job,
                                        edu_list, work_list, proj_list,
                                        skill_names, jd_skills)
        else:
            return self._local_reply_en(phase, q_num, name, target_job,
                                        edu_list, work_list, proj_list,
                                        skill_names, jd_skills)

    def _local_reply_zh(self, phase, q_num, name, target_job,
                         edu_list, work_list, proj_list, skill_names, jd_skills):
        """中文本地面试引擎。"""
        # 辅助函数：生成一个未被问过的topic key
        def topic_key(*parts):
            return "_".join(str(p) for p in parts)

        # ── 阶段1：开场后引导自我介绍 → 过渡 ──
        if phase == "opening":
            if q_num == 0:
                return "请先用2分钟左右做一下自我介绍。"
            return f"好的，了解了。接下来我想详细聊一下你的教育背景——你是{edu_list[0].get('school', '哪个学校') if edu_list else '什么学校'}毕业的？专业方向是什么？"

        # ── 阶段2：教育/实习/项目深挖 ──
        if phase == "background":
            questions = []

            # 教育追问
            for edu in edu_list:
                tk = topic_key("edu", edu.get("school", ""))
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    school = edu.get("school", "学校")
                    major = edu.get("major", "专业")
                    if major:
                        return f"你在{school}读的是{major}，这个专业对你的职业发展有什么具体帮助？"
                    return f"你在{school}的学习经历中，哪门课或者哪个项目对你影响最大？"

            # 项目经历
            for proj in proj_list:
                tk = topic_key("proj", proj.get("name", ""))
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    pname = proj.get("name", "这个项目")
                    desc = proj.get("description", "") or proj.get("results", "") or ""
                    if desc:
                        return f"你提到{pname}，能具体讲讲你在其中负责了哪些部分？不要讲团队做了什么，就讲你个人做的。"
                    return f"关于{pname}，当时遇到的最大技术难点是什么？你是怎么解决的？"

            # 实习/工作经历
            for work in work_list:
                tk = topic_key("bg_work", work.get("company", ""))
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    company = work.get("company", "这家公司")
                    position = work.get("position", "")
                    return f"你在{company}担任{position}，当时为什么选择加入这家公司？"

            # 如果都问过了，过渡
            return "这部分聊得差不多了，接下来我想了解一下你在核心能力方面的匹配情况。你对JD里要求的技能掌握到什么程度？"

        # ── 阶段3：核心能力匹配 ──
        if phase == "competency":
            # 问JD要求的技能
            for sk in jd_skills:
                tk = topic_key("jd_skill", sk)
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    if any(sk.lower() in s.lower() for s in skill_names):
                        return f"JD要求{sk}，你简历里也写了这个技能。在哪个项目里实际用过？用到什么深度？"
                    return f"JD要求{sk}，但你简历里没有明确提到。你对这个技术有了解吗？到什么程度？"

            # 追问量化成果
            for work in work_list:
                tk = topic_key("result", work.get("company", ""))
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    duties = work.get("duties", "") or ""
                    if any(kw in duties for kw in ["提升", "增长", "优化", "降低", "%"]):
                        return f"你提到在{work.get('company', '公司')}有量化成果，这些数据是怎么测算的？你个人的贡献占比大概是多少？"
                    return f"在{work.get('company', '公司')}的工作经历中，你觉得最有成就感的一件事是什么？"

            return "能力方面我了解了。最后我想聊一下你的求职意向——为什么对这个机会感兴趣？"

        # ── 阶段4：动机/规划/反问 ──
        if phase == "closing":
            if q_num <= 9:
                return f"你应聘的是{target_job}，为什么选择投递这个岗位？目前在看哪些其他机会？"
            if q_num <= 10:
                return "未来2-3年你在职业上有什么规划？想往技术深度走还是往管理方向走？"
            if q_num <= 11:
                return "我的问题问完了，你有什么想问我的吗？"
            return "好的，感谢你今天的时间，我们会尽快反馈面试结果。祝你一切顺利！"

        # fallback
        for edu in edu_list:
            tk = topic_key("edu_fallback", edu.get("school", ""))
            if tk not in self._asked_topics:
                self._asked_topics.add(tk)
                return f"回到你的教育经历——在{edu.get('school', '学校')}期间，有没有参加过什么竞赛或者社团活动？"
        return f"感谢你的分享。我想再问一下——对于{target_job}这个方向，你觉得自己最大的优势是什么？"

    def _local_reply_en(self, phase, q_num, name, target_job,
                         edu_list, work_list, proj_list, skill_names, jd_skills):
        """English local interview engine."""
        def topic_key(*parts):
            return "_".join(str(p) for p in parts)

        if phase == "opening":
            if q_num == 0:
                return "Please introduce yourself in about 2 minutes."
            school = edu_list[0].get('school', 'your school') if edu_list else 'your school'
            return f"Great. Let's talk about your education — you studied at {school}. How did that prepare you for this role?"

        if phase == "background":
            for edu in edu_list:
                tk = topic_key("edu", edu.get("school", ""))
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    major = edu.get("major", "")
                    if major:
                        return f"You majored in {major} at {edu.get('school', 'school')}. What specific skills from that program do you apply in your work?"
                    return f"At {edu.get('school', 'school')}, what was the most impactful project or course for you?"

            for proj in proj_list:
                tk = topic_key("proj", proj.get("name", ""))
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    pname = proj.get("name", "that project")
                    return f"Tell me about {pname} — what was YOUR specific role and contribution, not the team's?"

            for work in work_list:
                tk = topic_key("bg_work", work.get("company", ""))
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    return f"You worked at {work.get('company', 'that company')} as {work.get('position', '')}. What made you join them?"

            return "Let's shift gears — I'd like to understand how your skills match our requirements."

        if phase == "competency":
            for sk in jd_skills:
                tk = topic_key("jd_skill", sk)
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    return f"The role requires {sk}. Where have you used this in practice, and at what depth?"

            for work in work_list:
                tk = topic_key("result", work.get("company", ""))
                if tk not in self._asked_topics:
                    self._asked_topics.add(tk)
                    return f"At {work.get('company', 'company')}, what achievement are you most proud of?"

            return "I have a good sense of your capabilities now. Let's talk about your career goals."

        if phase == "closing":
            if q_num <= 9:
                return f"Why are you interested in this {target_job} role? What other opportunities are you exploring?"
            if q_num <= 10:
                return "Where do you see yourself in 2-3 years? Individual contributor track or management?"
            if q_num <= 11:
                return "Those are all my questions. Do you have any questions for me?"
            return "Thank you for your time today. We'll be in touch with next steps. Good luck!"

        for work in work_list:
            tk = topic_key("work_fallback", work.get("company", ""))
            if tk not in self._asked_topics:
                self._asked_topics.add(tk)
                return f"What would you say was the biggest challenge at {work.get('company', 'company')}?"
        return f"For this {target_job} role, what do you think sets you apart from other candidates?"

    # ── 阶段推进逻辑 ────────────────────────────────────────

    def _force_next_phase(self) -> None:
        """强制跳转到下一个面试阶段。"""
        current_idx = PHASE_ORDER.index(self._current_phase) if self._current_phase in PHASE_ORDER else 0
        next_idx = min(current_idx + 1, len(PHASE_ORDER) - 1)
        if next_idx != current_idx:
            self._current_phase = PHASE_ORDER[next_idx]
            self._phase_rounds[self._current_phase] = 0

    def _advance_phase(self) -> InterviewPhase:
        """
        根据当前阶段轮次自动推进面试阶段。

        阶段轮次分布（总约 8-12 轮）：
          阶段1 opening:     第 0 轮（开场后即进入阶段2）
          阶段2 background:  第 1-5 轮（深挖教育/实习/项目，3-5轮追问）
          阶段3 competency:  第 6-8 轮（核心能力匹配，2-3轮追问）
          阶段4 closing:     第 9+ 轮（动机/规划/反问，收尾）
        """
        rounds_in_phase = self._phase_rounds.get(self._current_phase, 0)
        max_rounds = PHASES[self._current_phase].max_rounds

        # 当前阶段轮次用尽 → 推进
        if rounds_in_phase >= max_rounds:
            current_idx = PHASE_ORDER.index(self._current_phase) if self._current_phase in PHASE_ORDER else 0
            next_idx = min(current_idx + 1, len(PHASE_ORDER) - 1)
            if next_idx != current_idx:
                self._current_phase = PHASE_ORDER[next_idx]
                self._phase_rounds[self._current_phase] = 0

        return PHASES[self._current_phase]

    # ── 系统提示词构建（核心 — 注入完整铁律 + 素材）─────────

    def _build_system_prompt(
        self,
        cfg: dict,
        phase: InterviewPhase,
        lang: str,
        skip_triggered: bool = False,
    ) -> str:
        """构建面试官系统提示词，铁律嵌入到每一轮对话。"""

        background = cfg.get("background", "")
        style = cfg.get("style", "")

        # ── 阶段专属追问指南 ──
        phase_guides = {
            "opening": (
                "【开场阶段 — 本轮任务】\n"
                "引导候选人做 2 分钟自我介绍。观察：表达结构是否清晰？是否用数据说话？\n"
                "自我介绍结束后，过渡到下一阶段：'好的，了解了。接下来我想详细聊一下你的教育背景和项目经历。'"
            ),
            "background": (
                "【背景深挖阶段 — 本轮任务】\n"
                "围绕候选人的教育背景、实习经历、项目细节逐条深挖。\n"
                "追问方向：时间线有无断层？项目中你个人做了什么（不是团队）？遇到的最大困难？怎么解决的？\n"
                "不要连续问同一段经历超过 3 轮——每轮换一个项目或经历来问。\n"
                "本阶段结束时自然过渡：'这部分聊得差不多了，接下来我想了解一下你在岗位核心能力方面的匹配情况。'"
            ),
            "competency": (
                "【核心能力匹配阶段 — 本轮任务】\n"
                "对标 JD 要求，逐条追问候选人的匹配度。\n"
                "追问方向：JD 要求的技术/能力你在哪个项目里实际用过？到了什么深度？\n"
                "遇到量化成果立即追问：这个数据怎么来的？你的个人贡献占比多大？\n"
                "本阶段结束时自然过渡：'好的，能力方面我了解了。最后我想聊一下你的求职意向和职业规划。'"
            ),
            "closing": (
                "【收尾阶段 — 本轮任务】\n"
                "① 求职动机：为什么看这个机会？为什么离开现在的公司？\n"
                "② 职业规划：未来 2-3 年的规划？想往哪个方向发展？\n"
                "③ 反问环节：'我的问题问完了，你有什么想问我的吗？'\n"
                "候选人问完后：'好的，感谢今天的时间，我们会尽快反馈面试结果。'\n"
                "中性语气结束，不透露面试结果。"
            ),
        }

        phase_guide = phase_guides.get(self._current_phase, f"当前阶段: {phase.zh}")

        if lang == "zh":
            # ── 中文系统提示词（铁律嵌入） ──
            prompt = f"""# 你的身份
{background}

# 你的面试风格
{style}

# 当前面试阶段
{phase.zh}（第 {self._question_count + 1} 轮提问）

{phase_guide}

# 【候选人完整简历】
{self._resume_context[:2000]}

# 【岗位 JD 要求】
{self._jd_context[:1000]}

# ⚠️ 铁律（任何一条违反都是严重错误）

## 禁止行为
1. ❌ 绝对禁止输出"请继续""接着说""还有呢"等敷衍短句——每次回复必须包含一个具体的、有指向性的追问
2. ❌ 绝对禁止凭空编造问题——所有提问必须100%来自候选人简历或JD原文中存在的经历/技能
3. ❌ 绝对禁止一次性抛出多个问题——每轮只问1个问题，等候选人回答后再追问
4. ❌ 绝对禁止输出面试评语、打分、或'很好''不错'等评价——只输出提问话术，点评留在面试结束后
5. ❌ 绝对禁止连续重复相同话术——每轮必须有新的追问角度

## 必须行为
1. ✅ 全程口语化自然对话，语气正式但柔和，像真实线下面试一样说话
2. ✅ 候选人回答后必须针对性追问：具体数据、遇到困难、协作流程、复盘思考
3. ✅ 遇到模糊/笼统/用'我们'代替'我'的回答，立刻打断追问个人贡献
4. ✅ 每次回复控制在 50-200 字，简洁有力
5. ✅ 语言：中文

## '继续'处理
候选人刚输入了"{'继续' if skip_triggered else '（正常回答）'}"。
{'→ 候选人想跳过当前话题，请直接提出下一阶段的新问题，不要再追问上一轮的内容。' if skip_triggered else '→ 请针对候选人的回答内容进行具体追问。'}
"""
        else:
            # ── 英文系统提示词 ──
            prompt = f"""# Your Identity
{background}

# Your Interview Style
{style}

# Current Phase
{phase.en} (Question #{self._question_count + 1})

{phase_guide}

# Candidate Resume
{self._resume_context[:2000]}

# Job Requirements
{self._jd_context[:1000]}

# ⚠️ Iron Rules (DO NOT BREAK)

## Prohibited
1. ❌ NEVER output "go on", "continue", "tell me more" as standalone replies — every response must contain a specific follow-up question
2. ❌ NEVER invent questions — all questions must be 100% based on the candidate's actual resume or JD
3. ❌ NEVER ask multiple questions at once — ONE question per turn
4. ❌ NEVER output evaluation or judgment during the interview — only questions
5. ❌ NEVER repeat the same question — each turn must have a fresh angle

## Required
1. ✅ Natural conversational tone, professional but warm
2. ✅ Every response must include a specific follow-up: data, challenges, collaboration, lessons learned
3. ✅ For vague answers, immediately push for personal contribution specifics
4. ✅ Keep responses 50-200 words, concise
5. ✅ Language: English only

## Skip Signal
Candidate just said: "{'continue/next' if skip_triggered else '(normal answer)'}"
{'→ Candidate wants to move on. Skip the current topic and ask a new question for the next phase.' if skip_triggered else '→ Follow up specifically on what the candidate just said.'}
"""

        return prompt

    # ── 生成评估报告 ──────────────────────────────────────────

    async def generate_report(
        self,
        gateway: MultiModelGateway,
        lang: str = "zh",
    ) -> dict:
        """
        面试结束后生成 5 维度专业评估报告。
        只在面试全部完成后调用，面试过程中不输出任何评语。
        """
        dialog = "\n".join(
            f"{'HR' if m['role'] == 'assistant' else '候选人'}: {m['content'][:300]}"
            for m in self._messages
        )

        if lang == "zh":
            prompt = f"""你是一位拥有 15 年+ 招聘经验的资深 HR 面试官。
请基于以下面试对话，生成一份专业的面试评估报告。

评估维度（5 维度，每个维度 1-10 分 + 具体说明）：

1. 【岗位匹配度】候选人的技能/经验与 JD 要求的匹配程度（硬技能 + 软技能 + 行业背景）
2. 【STAR 回答质量】候选人是否用具体的事例、数据来回答（S-情景 T-任务 A-行动 R-结果）
3. 【表达与逻辑】语言组织是否清晰、是否有逻辑漏洞、是否回避关键问题
4. 【诚信度评估】简历内容是否与口述一致、有无夸大嫌疑、时间线是否自洽
5. 【综合推荐】是否推荐进入下一轮（推荐录用 / 可进入下一轮 / 暂不推荐 / 不推荐）

每个维度请给出：
- 评分（1-10）
- 关键观察（1-2句话）
- 风险标记（如有）

最后给出总体评价（150 字以内）和明确的录用建议。

面试对话：
{dialog}"""
        else:
            prompt = f"""As a senior HR interviewer with 15+ years of experience,
generate a professional interview evaluation report.

5 dimensions (1-10 each + specific notes):
1. Job Fit — skills/experience match with JD
2. STAR Quality — specific examples, data, behavioral responses
3. Communication & Logic — clarity, logical consistency, evasion
4. Credibility — resume vs verbal consistency, exaggeration
5. Overall Recommendation — hire / next round / hold / reject

For each dimension: score (1-10), key observation (1-2 lines), risk flags (if any).
Final: overall assessment (100 words max) and clear recommendation.

Interview transcript:
{dialog}"""

        result = await gateway.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            task_type="enhanced",
            options={"max_tokens": 3072, "temperature": 0.3, "lang": lang},
        )
        return {
            "report": result.content if result.success else "",
            "messages": list(self._messages),
            "question_count": self._question_count,
            "phases": list(PHASES.keys()),
            "current_phase": self._current_phase,
        }

    # ── 重置 ──────────────────────────────────────────────────

    def reset(self) -> None:
        """重置面试会话。"""
        self._messages = []
        self._current_phase = "opening"
        self._question_count = 0
        self._phase_rounds = {p: 0 for p in PHASE_ORDER}
        self._last_user_input = ""
        self._asked_topics = set()

    # ── 只读属性 ──────────────────────────────────────────────

    @property
    def messages(self) -> list[dict]:
        return list(self._messages)

    @property
    def current_phase(self) -> str:
        return self._current_phase

    @property
    def question_count(self) -> int:
        return self._question_count


# ═══════════════════════════════════════════════════════════════
# 独立运行入口 — 命令行交互式面试
# ═══════════════════════════════════════════════════════════════

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="05_ai_interviewer — AI 模拟面试")
    parser.add_argument("--jd", required=True, help="JD JSON 文件")
    parser.add_argument("--resume", required=True, help="简历 JSON 文件")
    parser.add_argument("--persona", default="hr", choices=["hr", "tech", "stress", "english"])
    parser.add_argument("--lang", default="zh", choices=["zh", "en"])
    args = parser.parse_args()

    LanguageSwitch.set_lang(args.lang)

    with open(args.jd, encoding="utf-8") as f:
        jd_data = json.load(f)
    with open(args.resume, encoding="utf-8") as f:
        resume_data = json.load(f)

    interviewer = AIInterviewer()
    cfg = interviewer.init_session(jd_data, resume_data, persona=args.persona)

    print(f"面试官: {cfg['role']}")
    print(f"风格: {cfg['style'][:80]}...")
    print(f"\n开场白: {interviewer.get_opening(args.persona, args.lang)}")

    gateway = MultiModelGateway()
    try:
        print("\n=== 面试开始 (输入 /quit 退出, 输入 继续 跳下一阶段, /report 生成报告) ===\n")
        while True:
            user_input = input("你: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("/quit", "/exit"):
                break
            if user_input.lower() == "/report":
                print("\n[生成评估报告中...]")
                report = await interviewer.generate_report(gateway, lang=args.lang)
                print(report["report"])
                break

            result = await interviewer.chat(
                user_input, gateway=gateway, persona=args.persona, lang=args.lang,
            )
            phase = result["phase"]
            print(f"\n面试官 [{phase['zh']}] (Q{result['question_count']}): {result['reply']}\n")
    finally:
        await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
