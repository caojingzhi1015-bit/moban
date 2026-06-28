"""
模块5 —— AI模拟面试官系统
核心功能：4阶段结构化面试（开场→背景深挖→能力匹配→收尾），支持多种面试官人格
核心技术：阶段状态机 + 本地规则面试引擎 + 面试报告生成
"""

import json


# 4阶段面试流程定义
PHASES = {
    "opening": {"order": 0, "max_rounds": 1, "name": "开场寒暄+自我介绍引导"},
    "background": {"order": 1, "max_rounds": 5, "name": "教育背景/实习/项目细节深挖"},
    "competency": {"order": 2, "max_rounds": 3, "name": "岗位核心能力匹配/技术难点与量化成果"},
    "closing": {"order": 3, "max_rounds": 2, "name": "求职动机/职业规划+候选人反问"},
}
PHASE_ORDER = ["opening", "background", "competency", "closing"]

# 4种面试官人格
PERSONAS = {
    "hr": {
        "role": "资深HR面试官",
        "background": "拥有15年以上招聘经验，曾供职于头部外企、国企及互联网大厂，深谙各行业用人标准与候选人评估方法论。",
        "style": "专业亲和开场但追问犀利，全程口语化自然对话，不接受笼统回答，遇到模糊表述立即打断追问个人贡献。"},
    "tech": {
        "role": "技术面试官（资深架构师）",
        "background": "拥有12年以上一线研发经验，曾在头部互联网公司担任技术总监/架构师，主导过日均亿级流量的系统设计。",
        "style": "直接切入技术核心，从项目经历深挖到系统设计原理，追问具体的技术选型理由、性能数据、关键bug及修复过程。"},
    "stress": {
        "role": "压力面试官",
        "background": "专门执行高压力面试，目标是测试候选人在极端环境下的情绪管理、逻辑思维和抗压能力。擅长质疑成果真实性、沉默施压。",
        "style": "质疑一切：'这个项目真的是你主导的吗？请说出具体架构细节。'沉默施压：回答后保持3-5秒沉默。极端情境考验。"},
    "english": {
        "role": "English Interviewer",
        "background": "Senior hiring manager with 15+ years at multinational companies. Conducts behavioral interviews using STAR method.",
        "style": "Full English only, behavioral questions with STAR framework, cultural fit probing. Polite but thorough."},
}


class AIInterviewer:
    """AI模拟面试官 - 4阶段结构化面试"""

    def __init__(self):
        self.messages = []
        self.current_phase = "opening"
        self.question_count = 0
        self.phase_rounds = {p: 0 for p in PHASE_ORDER}
        self.jd_data = {}
        self.resume_data = {}
        self.asked_topics = set()

    def init_session(self, jd_data: dict, resume_data: dict, persona: str = "hr") -> dict:
        """初始化面试会话，绑定JD+简历素材"""
        self.jd_data = jd_data or {}
        self.resume_data = resume_data or {}
        self.messages = []
        self.current_phase = "opening"
        self.question_count = 0
        self.phase_rounds = {p: 0 for p in PHASE_ORDER}
        self.asked_topics = set()
        return PERSONAS.get(persona, PERSONAS["hr"])

    def get_opening(self, persona: str = "hr", lang: str = "zh") -> str:
        """获取面试开场白"""
        openings = {
            "hr": "你好，我是今天的面试官。请用2分钟左右做一下自我介绍吧。",
            "tech": "你好，我是今天的技术面试官。请先做1分钟自我介绍，重点说你的核心技术栈和最有挑战的项目。",
            "stress": "请坐。今天这场面试会比较直接，我会针对你简历里的每一项追问具体细节。先自我介绍吧。",
            "english": "Welcome. This entire interview will be conducted in English. Please introduce yourself in about 2 minutes.",
        }
        return openings.get(persona, openings["hr"])

    def chat(self, user_answer: str, persona: str = "hr", lang: str = "zh") -> dict:
        """
        处理一轮面试对话
        规则引擎驱动的本地面试模式（无需API）
        """
        self.messages.append({"role": "user", "content": user_answer})
        self.question_count += 1

        # 检测"继续/下一题"跳过信号
        text = user_answer.strip().lower()
        skip_triggers_zh = ["继续", "下一题", "下一个", "往后", "接着来"]
        skip_triggers_en = ["continue", "next", "next question", "go on", "proceed"]
        triggers = skip_triggers_zh if lang == "zh" else skip_triggers_en
        skip_triggered = len(text) <= 10 and any(text == t or text.startswith(t) for t in triggers)

        if skip_triggered and self.question_count > 0:
            self._force_next_phase()

        # 阶段推进
        phase = self._advance_phase()

        # 使用本地规则引擎生成回复
        reply = self._build_local_reply(lang)

        self.messages.append({"role": "assistant", "content": reply})
        self.phase_rounds[self.current_phase] += 1

        return {"reply": reply, "phase": phase, "question_count": self.question_count}

    def _build_local_reply(self, lang: str) -> str:
        """
        核心方法：基于候选人简历数据+当前阶段，模板化生成针对性追问
        不依赖任何外部API，保证面试永远可用
        """
        resume = self.resume_data
        jd = self.jd_data
        bi = resume.get("basic_info", {}) or {}
        name = bi.get("name", "") or "候选人"
        target_job = bi.get("target_job", "") or jd.get("position", "") or "该岗位"
        edu_list = resume.get("education", []) or []
        work_list = resume.get("work_experience", []) or []
        proj_list = resume.get("projects", []) or []
        skills_list = resume.get("skills", []) or []
        jd_skills = jd.get("hard_skills", []) or []
        q = self.question_count

        def topic_key(prefix, topic):
            return f"{prefix}:{str(topic).lower().strip()[:40]}"

        if lang == "zh":
            # 阶段1: 开场
            if self.current_phase == "opening":
                return f"感谢{name}的自我介绍。我了解到您应聘{target_job}岗位。能具体说说您为什么对这个岗位感兴趣吗？"

            # 阶段2: 背景深挖
            if self.current_phase == "background":
                # 从教育经历开始
                for edu in edu_list:
                    tk = topic_key("edu", edu.get("school", ""))
                    if tk not in self.asked_topics:
                        self.asked_topics.add(tk)
                        major = edu.get("major", "")
                        if major:
                            return f"您就读于{edu.get('school', '')}{edu.get('major', '')}专业。在校期间有没有让您印象最深刻的项目或课程？"
                        return f"在{edu.get('school', '')}就读期间，您最大的收获是什么？"
                for work in work_list:
                    tk = topic_key("work", work.get("company", ""))
                    if tk not in self.asked_topics:
                        self.asked_topics.add(tk)
                        return f"您在{work.get('company', '')}担任{work.get('position', '')}期间，具体负责什么工作？遇到过最大的挑战是什么？"
                for proj in proj_list:
                    tk = topic_key("proj", proj.get("name", ""))
                    if tk not in self.asked_topics:
                        self.asked_topics.add(tk)
                        return f"关于{proj.get('name', '该项目')}，您的具体角色和个人贡献是什么？"
                return "我们来谈谈您的技术能力吧。哪些技能是您在实际工作中最常用的？"

            # 阶段3: 能力匹配
            if self.current_phase == "competency":
                for sk in jd_skills:
                    tk = topic_key("jd_skill", sk)
                    if tk not in self.asked_topics:
                        self.asked_topics.add(tk)
                        return f"JD要求{sk}。您在哪个项目里实际用到过这项技术？到什么深度？"
                if q <= 8:
                    return f"您如何看待自己与{target_job}岗位的匹配度？请具体说明。"
                return "除了技术能力，您认为自己的核心竞争力是什么？"

            # 阶段4: 收尾
            if self.current_phase == "closing":
                if q <= 10:
                    return f"您为什么想离开现在的公司？对{target_job}岗位最看重什么？"
                if q <= 11:
                    return "未来2-3年您的职业规划是什么？想往哪个方向发展？"
                return "我的问题问完了。您有什么想问我的吗？"

            # 兜底
            for work in work_list:
                tk = topic_key("work_fallback", work.get("company", ""))
                if tk not in self.asked_topics:
                    self.asked_topics.add(tk)
                    return f"在{work.get('company', '')}期间，您最有成就感的一件事是什么？"
            return f"对于{target_job}岗位，您觉得自己相比其他候选人的优势是什么？"

        else:
            # English mode
            if self.current_phase == "opening":
                return f"Thank you, {name}. You're applying for {target_job}. What interests you about this role?"
            if self.current_phase == "background":
                for edu in edu_list:
                    tk = topic_key("edu", edu.get("school", ""))
                    if tk not in self.asked_topics:
                        self.asked_topics.add(tk)
                        return f"You studied at {edu.get('school', 'school')}. What skills from that program do you apply in your work?"
                for work in work_list:
                    tk = topic_key("work", work.get("company", ""))
                    if tk not in self.asked_topics:
                        self.asked_topics.add(tk)
                        return f"At {work.get('company', '')} as {work.get('position', '')}, what was your biggest challenge?"
                return "Let's talk about your skills. Which ones do you use most in practice?"
            if self.current_phase == "competency":
                for sk in jd_skills:
                    tk = topic_key("jd_skill", sk)
                    if tk not in self.asked_topics:
                        self.asked_topics.add(tk)
                        return f"{sk} is required for this role. Where have you used this, and at what depth?"
                return f"What sets you apart from other candidates for this {target_job} role?"
            if self.current_phase == "closing":
                if q <= 10:
                    return "Where do you see yourself in 2-3 years?"
                return "That's all my questions. Do you have any for me?"
            return f"For the {target_job} role, what's your greatest strength?"

    def _advance_phase(self):
        """推进面试阶段"""
        rounds = self.phase_rounds.get(self.current_phase, 0)
        max_r = PHASES[self.current_phase]["max_rounds"]
        if rounds >= max_r:
            idx = PHASE_ORDER.index(self.current_phase)
            next_idx = min(idx + 1, len(PHASE_ORDER) - 1)
            if next_idx != idx:
                self.current_phase = PHASE_ORDER[next_idx]
                self.phase_rounds[self.current_phase] = 0
        return PHASES[self.current_phase]

    def _force_next_phase(self):
        """强制跳转下一阶段"""
        idx = PHASE_ORDER.index(self.current_phase) if self.current_phase in PHASE_ORDER else 0
        next_idx = min(idx + 1, len(PHASE_ORDER) - 1)
        if next_idx != idx:
            self.current_phase = PHASE_ORDER[next_idx]
            self.phase_rounds[self.current_phase] = 0

    def generate_report(self) -> dict:
        """生成面试评估报告（模板版本）"""
        dialog = "\n".join(f"{'HR' if m['role'] == 'assistant' else '候选'}: {m['content'][:200]}" for m in self.messages)
        skills = [s.get("name") if isinstance(s, dict) else str(s) for s in (self.resume_data.get("skills") or [])]
        jd_hard = self.jd_data.get("hard_skills") or []
        matched = [s for s in jd_hard if any(s.lower() in sk.lower() for sk in skills)]
        return {
            "report": f"""【面试评估报告】
━━━━━━━━━━━━━━━━━━━━━━━━━━
1.【岗位匹配度】 候选人所具备技能与JD匹配：{', '.join(matched) if matched else '较少'}

2.【STAR回答质量】 基于面试对话，候选人在经历描述上具体程度：{len(self.messages) > 4 and '较好' or '一般'}

3.【表达与逻辑】 已完成{self.question_count}轮对话

4.【诚信度评估】 建议对照简历细节核实

5.【综合推荐】 建议进入下一轮面试

面试对话摘要：
{dialog[:500]}""",
            "question_count": self.question_count,
            "phases": list(PHASES.keys()),
        }

    def reset(self):
        self.messages = []
        self.current_phase = "opening"
        self.question_count = 0
        self.phase_rounds = {p: 0 for p in PHASE_ORDER}
        self.asked_topics = set()


def run():
    print("="*60)
    print("  模块5：AI模拟面试官系统")
    print("  功能：4阶段结构化面试（支持多种人格）")
    print("="*60)

    jd = {"position": "高级Python后端开发工程师", "company": "字节跳动",
          "hard_skills": ["Python", "Django", "MySQL", "Redis", "Kafka", "Docker"]}
    resume = {
        "basic_info": {"name": "张三", "city": "北京", "target_job": "Python后端开发"},
        "education": [{"school": "北京大学", "major": "计算机科学与技术", "degree": "本科"}],
        "work_experience": [{"company": "某科技公司", "position": "后端开发", "duties": "高并发API服务开发"}],
        "skills": [{"name": "Python"}, {"name": "Django"}, {"name": "MySQL"}],
    }

    print("\n选择面试官人格：")
    for k, v in PERSONAS.items():
        print(f"  {k}: {v['role']}")
    persona = input("\n请输入（默认hr）: ").strip() or "hr"

    iv = AIInterviewer()
    cfg = iv.init_session(jd, resume, persona=persona)
    print(f"\n[面试官] {cfg['role']}")
    print(f"[风格] {cfg['style'][:60]}...")
    print(f"\n[开场白] {iv.get_opening(persona)}")

    print("\n=== 面试开始（输入 quit 退出，next 跳下一阶段，report 生成报告）===")
    while True:
        user = input("\n您: ").strip()
        if not user: continue
        if user.lower() == "quit": break
        if user.lower() == "report":
            report = iv.generate_report()
            print(f"\n[面试报告]\n{report['report']}")
            break
        result = iv.chat(user, persona=persona)
        phase = result["phase"]
        print(f"\n面试官 [{phase['name']}] (Q{result['question_count']}): {result['reply']}")

    print("\n[核心代码说明]")
    print("  · 4阶段状态机: opening→background→competency→closing")
    print("  · _build_local_reply(): 纯规则引擎（无需API），基于简历数据模板化生成追问")
    print("  · 4种人格: hr/tech/stress/english，不同提问风格")
    print("  · generate_report(): 面试评估报告自动生成")
    print(f"  · 共完成{iv.question_count}轮面试对话")


if __name__ == "__main__":
    run()
