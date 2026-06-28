"""
模块3 —— AI职位匹配追问系统
核心功能：对比JD要求 vs 简历已有信息，识别缺口并生成精准追问
核心技术：规则引擎缺口分析 + 模板问题生成
"""

import re
import json


class InfoEnquiryAgent:
    """AI信息追问Agent - 对比JD vs 简历，识别缺口并生成追问"""

    @staticmethod
    def analyze_gaps(jd_data: dict, resume_data: dict) -> list[dict]:
        """核心方法：分析JD与简历之间的所有缺口"""
        gaps = []
        jd_hard = jd_data.get("hard_skills") or []
        jd_soft = jd_data.get("soft_skills") or []
        years_req = jd_data.get("years_required")

        # 提取简历已有技能
        extracted_skills = set()
        for s in resume_data.get("skills") or []:
            name = s.get("name") if isinstance(s, dict) else str(s)
            extracted_skills.add(name.lower())
        # 从工作经历和项目中扫描技能
        all_text = json.dumps(resume_data.get("work_experience") or [], ensure_ascii=False).lower()
        all_text += " " + json.dumps(resume_data.get("projects") or [], ensure_ascii=False).lower()

        # 1. 技能缺口
        for skill in jd_hard:
            if skill.lower() not in extracted_skills and skill.lower() not in all_text:
                gaps.append({
                    "category": "skill_gap", "keyword": skill,
                    "detail": f"JD要求{skill}，简历未体现", "source": "jd"})

        # 2. 软技能缺口
        for skill in jd_soft:
            if skill.lower() not in all_text:
                gaps.append({
                    "category": "soft_skill_gap", "keyword": skill,
                    "detail": f"JD要求软技能：{skill}", "source": "jd"})

        # 3. 量化数据缺失
        has_quant = False
        for w in resume_data.get("work_experience") or []:
            duties = str(w.get("duties") or "")
            if re.search(r"\d+[%％倍KwW万]", duties):
                has_quant = True; break
        if not has_quant and len(resume_data.get("work_experience") or []) > 0:
            gaps.append({
                "category": "quant_data",
                "detail": "工作经历缺少量化成果数据",
                "source": "analysis"})

        # 4. 项目经历缺失
        if not resume_data.get("projects"):
            gaps.append({
                "category": "project_detail",
                "detail": "简历缺少项目经历章节",
                "source": "analysis"})

        # 5. 工作年限缺口
        if years_req:
            ym = re.match(r"(\d+)", str(years_req))
            y = int(ym.group(1)) if ym else 0
            work_count = len(resume_data.get("work_experience") or [])
            if y > 0 and work_count < max(1, y // 2):
                gaps.append({
                    "category": "experience_gap",
                    "detail": f"JD要求{years_req}经验，简历展示{work_count}段经历",
                    "source": "jd"})

        # 6. 求职意向缺失
        bi = resume_data.get("basic_info") or {}
        jd_pos = jd_data.get("position", "")
        if not bi.get("target_job") and jd_pos:
            gaps.append({
                "category": "job_target",
                "detail": f"JD职位为{jd_pos}，简历未明确求职意向",
                "source": "analysis"})

        return gaps

    @staticmethod
    def build_template_questions(gaps: list[dict]) -> list[dict]:
        """用规则模板为每个缺口生成追问问题"""
        questions = []
        for gap in gaps:
            cat = gap.get("category", "")
            keyword = gap.get("keyword", "")
            detail = gap.get("detail", "")

            if cat == "skill_gap":
                questions.append({
                    "category": cat, "keyword": keyword,
                    "question": f"【技能缺口】{detail}。请描述您使用{keyword}的具体项目经历和掌握程度（入门/熟练/精通）。"})
            elif cat == "soft_skill_gap":
                questions.append({
                    "category": cat, "keyword": keyword,
                    "question": f"【软技能】JD要求具备「{keyword}」能力。请举例说明您在过去工作中如何体现这项能力的？"})
            elif cat == "quant_data":
                questions.append({
                    "category": cat,
                    "question": "【量化成果】您的简历中工作经历缺少具体数据支撑。请为每段经历补充量化成果，例如：性能提升X%、团队规模N人、业务增长X倍。"})
            elif cat == "project_detail":
                questions.append({
                    "category": cat,
                    "question": "【项目经历】请补充1-2个最能体现您技术能力的项目：①项目名称 ②您的角色和具体职责 ③使用的技术栈 ④取得的量化成果。"})
            elif cat == "experience_gap":
                questions.append({
                    "category": cat,
                    "question": f"【经验补充】{detail}。您是否有更早期的相关工作经验、实习或项目经历？请补充完整的工作时间线。"})
            elif cat == "job_target":
                questions.append({
                    "category": cat,
                    "question": f"【求职意向】{detail}。请确认您的求职意向岗位、期望薪资和可入职时间。"})
        return questions

    @staticmethod
    def process_answer(question: dict, answer: str) -> bool:
        """处理用户对追问的回答"""
        if not answer or len(answer.strip()) < 5:
            return False
        return True


def run():
    print("="*60)
    print("  模块3：AI职位匹配追问系统")
    print("  功能：对比JD与简历缺口，生成精准追问问题")
    print("="*60)

    # 示例JD数据
    jd = {
        "position": "高级Python后端开发工程师",
        "company": "字节跳动",
        "hard_skills": ["Python", "Django", "MySQL", "Redis", "Kafka", "Docker"],
        "soft_skills": ["团队协作", "沟通能力", "问题解决"],
        "years_required": "3-5年",
        "education_required": "本科"
    }
    # 示例简历数据
    resume = {
        "basic_info": {"name": "张三", "phone": "13800138000", "email": "zhangsan@email.com", "city": "北京"},
        "education": [{"school": "北京大学", "major": "计算机科学与技术", "degree": "本科", "period": "2018-2022"}],
        "work_experience": [{"company": "某科技公司", "position": "后端开发", "period": "2022-至今",
                             "duties": "负责API服务开发和维护"}],
        "projects": [],
        "skills": [{"name": "Python"}, {"name": "Django"}, {"name": "MySQL"}],
    }

    print("\n[JD要求] " + json.dumps(jd, ensure_ascii=False, indent=2))
    print("\n[简历信息] " + json.dumps(resume, ensure_ascii=False, indent=2))

    gaps = InfoEnquiryAgent.analyze_gaps(jd, resume)
    print(f"\n[识别缺口 {len(gaps)}项]")
    for g in gaps:
        print(f"  · [{g['category']}] {g['detail']}")

    questions = InfoEnquiryAgent.build_template_questions(gaps)
    print(f"\n[生成追问 {len(questions)}条]")
    for i, q in enumerate(questions, 1):
        print(f"  Q{i}. [{q['category']}] {q['question'][:60]}...")

    print("\n[核心代码说明]")
    print("  · analyze_gaps(): 6维度缺口分析（技能/软技能/量化/项目/年限/意向）")
    print("  · build_template_questions(): 规则模板引擎生成追问问题")
    print("  · process_answer(): 用户回答处理与素材回写机制")


if __name__ == "__main__":
    run()
