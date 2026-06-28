"""
模块4 —— JD对标精准简历生成器
核心功能：根据JD要求对简历进行重组优化，生成5模块结构化简历+自我介绍
核心技术：JD权重排序 + 五模块构建 + 自我介绍生成
"""

import re
import json


class TargetResumeGenerator:
    """JD对标简历生成器 - 不编造、只重组"""

    @staticmethod
    def generate(jd_data: dict, resume_data: dict, extra_info: dict = None) -> dict:
        """核心方法：根据JD对标生成简历 + 自我介绍"""
        merged = resume_data.copy()
        if extra_info:
            merged = TargetResumeGenerator._merge_extra(resume_data, extra_info)

        # JD权重排序
        sorted_work = TargetResumeGenerator._by_jd_relevance(
            merged.get("work_experience") or [], jd_data)
        sorted_projects = TargetResumeGenerator._by_jd_relevance(
            merged.get("projects") or [], jd_data)

        # 五模块简历
        resume = {
            "personal": TargetResumeGenerator._build_personal(merged.get("basic_info")),
            "summary": TargetResumeGenerator._build_summary(merged, jd_data),
            "experience": TargetResumeGenerator._build_experience(sorted_work, jd_data),
            "education": TargetResumeGenerator._build_education(merged.get("education") or []),
            "skills": TargetResumeGenerator._build_skills(
                merged.get("skills") or [], jd_data),
        }

        # 自我介绍
        self_intro = {
            "zh": TargetResumeGenerator.build_self_intro(resume, "zh"),
            "en": TargetResumeGenerator.build_self_intro(resume, "en"),
        }
        return {"resume": resume, "self_intro": self_intro}

    @staticmethod
    def _by_jd_relevance(entries: list, jd: dict) -> list:
        """JD权重排序：关键词匹配度高的在前"""
        keywords = (jd.get("hard_skills") or []) + (jd.get("soft_skills") or [])
        if not keywords:
            return list(entries)
        return sorted(entries, key=lambda e: sum(
            1 for k in keywords if k.lower() in json.dumps(e, ensure_ascii=False, default=str).lower()
        ), reverse=True)

    @staticmethod
    def _build_personal(bi: dict | None) -> dict:
        bi = bi or {}
        return {"name": bi.get("name") or "", "phone": bi.get("phone") or "",
                "email": bi.get("email") or "", "city": bi.get("city") or "",
                "target_job": bi.get("target_job") or "",
                "salary": bi.get("expect_salary") or ""}

    @staticmethod
    def _build_summary(data: dict, jd: dict) -> str:
        skills = [s.get("name") if isinstance(s, dict) else str(s) for s in (data.get("skills") or [])]
        skills = [s for s in skills if s]
        matched = [h for h in (jd.get("hard_skills") or []) if any(h.lower() in s.lower() for s in skills)]
        exp_count = len(data.get("work_experience") or [])
        name = (data.get("basic_info") or {}).get("name") or "求职者"
        return f"{name}，{exp_count}+年经验，{'、'.join(matched[:3])}等技能匹配JD要求。"

    @staticmethod
    def _build_experience(work: list, jd: dict) -> list:
        jd_skills = jd.get("hard_skills") or []
        result = []
        for w in work:
            duties = str(w.get("duties") or "")
            relevance = "高" if any(k.lower() in duties.lower() for k in jd_skills) else "中"
            result.append({
                "company": w.get("company") or "", "position": w.get("position") or "",
                "period": " - ".join(filter(None, [w.get("start_date"), w.get("end_date")])),
                "bullets": [w.get("duties")] if w.get("duties") else [],
                "jd_relevance": relevance})
        return result

    @staticmethod
    def _build_education(edu: list) -> list:
        return [{"school": e.get("school") or "", "major": e.get("major") or "",
                 "degree": e.get("degree") or "",
                 "period": " - ".join(filter(None, [e.get("start_date"), e.get("end_date")]))}
                for e in edu]

    @staticmethod
    def _build_skills(skills: list, jd: dict) -> dict:
        skill_names = [s.get("name") if isinstance(s, dict) else str(s) for s in skills]
        skill_names = [s for s in skill_names if s]
        jd_hard = jd.get("hard_skills") or []
        return {
            "technical": [s for s in skill_names if s not in {"英语", "中文", "CET-4", "CET-6"}],
            "jd_matched": [h for h in jd_hard if any(h.lower() in s.lower() for s in skill_names)],
            "jd_missing": [h for h in jd_hard if not any(h.lower() in s.lower() for s in skill_names)],
        }

    @staticmethod
    def build_self_intro(resume: dict, lang: str = "zh") -> dict:
        """生成2分钟口语版自我介绍"""
        p = resume.get("personal") or {}
        top_exp = (resume.get("experience") or [{}])[0] if resume.get("experience") else {}
        skills_list = resume.get("skills", {}).get("technical") or []
        skills_str = "、".join(skills_list[:4]) if lang == "zh" else ", ".join(skills_list[:4])
        max_chars = 250 if lang == "zh" else 155

        if lang == "zh":
            intro = f"面试官您好，我是{p.get('name') or '求职者'}。" + (
                f"应聘{p.get('target_job')}岗位。" if p.get('target_job') else "") + (
                f"我熟练掌握{skills_str}。" + (
                    f"曾在{top_exp.get('company')}担任{top_exp.get('position') or ''}，"
                    f"{(top_exp.get('bullets') or [''])[0][:60]}。" if top_exp.get('company') else "")
                ) + "期待能为团队贡献价值，谢谢。"
        else:
            intro = f"Hello, I'm {p.get('name') or 'a candidate'}." + (
                f" Applying for {p.get('target_job')}." if p.get('target_job') else "") + (
                f" My skills include {skills_str}." + (
                    f" Most recently at {top_exp.get('company')} as {top_exp.get('position') or 'a team member'}."
                    if top_exp.get('company') else "")
                ) + " I'm excited about this opportunity. Thank you."
        if len(intro) > max_chars:
            intro = intro[:max_chars-3] + "..."
        rate = 200 if lang == "zh" else 150
        est_seconds = round(len(intro) / rate * 60)
        return {"text": intro, "estimated_seconds": est_seconds, "char_count": len(intro)}

    @staticmethod
    def _merge_extra(resume_data: dict, extra_info: dict) -> dict:
        """追加追问补充信息到简历"""
        result = dict(resume_data)
        qa_entries = extra_info.get("qa_entries") or []
        new_skills = [{"name": qa.get("question", {}).get("keyword"), "category": "追问补充",
                       "source": "enquiry"} for qa in qa_entries if qa.get("question", {}).get("category") in ("skill_gap", "skill_detail") and qa.get("question", {}).get("keyword")]
        if new_skills:
            result["skills"] = (result.get("skills") or []) + new_skills
        return result


def run():
    print("="*60)
    print("  模块4：JD对标简历生成器")
    print("  功能：根据JD要求重组简历 + 生成自我介绍")
    print("="*60)

    jd = {"position": "高级Python后端开发工程师", "company": "字节跳动",
          "hard_skills": ["Python", "Django", "MySQL", "Redis", "Kafka", "Docker"]}
    resume = {
        "basic_info": {"name": "张三", "city": "北京", "target_job": "Python后端开发"},
        "education": [{"school": "北京大学", "major": "计算机科学与技术", "degree": "本科", "start_date": "2018", "end_date": "2022"}],
        "work_experience": [{"company": "某科技公司", "position": "后端开发", "start_date": "2022", "end_date": "至今",
                             "duties": "负责高并发API服务开发，使用Python/Django/MySQL/Redis技术栈"}],
        "skills": [{"name": "Python"}, {"name": "Django"}, {"name": "MySQL"}, {"name": "Redis"}, {"name": "Linux"}],
    }

    result = TargetResumeGenerator.generate(jd, resume)
    print("\n[生成简历]")
    print(json.dumps(result["resume"], ensure_ascii=False, indent=2))
    print("\n[自我介绍（中文）]")
    print(result["self_intro"]["zh"]["text"])
    print(f"  朗读时长约{result['self_intro']['zh']['estimated_seconds']}秒")
    print("\n[核心代码说明]")
    print("  · _by_jd_relevance(): JD关键词权重排序算法")
    print("  · 五模块构建: personal/summary/experience/education/skills")
    print("  · build_self_intro(): 中英文自我介绍文本生成（估算朗读时长）")


if __name__ == "__main__":
    run()
