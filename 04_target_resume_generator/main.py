"""
04_target_resume_generator/main.py — JD 对标精准简历生成模块（可独立运行）

输入: 01_jd_parser JD + 02_resume_parser 简历 + 03_info_enquiry 补充信息
输出: 五模块结构化简历 + 2分钟中英自我介绍 + Word/PDF导出数据

核心规则:
  1. 仅重组改写用户已有素材，不虚构任何经历/项目/KPI
  2. 按 JD 关键词匹配度排序经历，匹配度高的前置
  3. 同步输出中英文双版简历 + 口语自我介绍
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.language_switch import LanguageSwitch
from common.module_loader import load_attr
export_resume = load_attr("04_target_resume_generator.word_pdf_exporter.export_resume")


class TargetResumeGenerator:
    """JD 对标简历生成器 —— 不编造、只重组"""

    # ──────────── 主入口 ────────────

    @staticmethod
    def generate(
        jd_data: dict,
        resume_data: dict,
        extra_info: dict | None = None,
        lang: str = "zh",
    ) -> dict:
        """
        根据 JD 对标生成简历

        Args:
            jd_data: JD 解析结果（来自 01_jd_parser）
            resume_data: 简历解析结果（来自 02_resume_parser）
            extra_info: 追问补充信息（来自 03_info_enquiry_agent）
            lang: 语言代码

        Returns:
            { resume, self_intro, export_data }
        """
        # 合并补充信息到简历素材中
        merged_resume = dict(resume_data)
        if extra_info:
            merged_resume = TargetResumeGenerator._merge_extra(resume_data, extra_info)

        # JD 权重排序
        sorted_work = TargetResumeGenerator._by_jd_relevance(
            merged_resume.get("work_experience") or [], jd_data
        )
        sorted_projects = TargetResumeGenerator._by_jd_relevance(
            merged_resume.get("projects") or [], jd_data
        )

        # 生成五模块简历
        resume = {
            "personal": TargetResumeGenerator._build_personal_section(
                merged_resume.get("basic_info")
            ),
            "summary": TargetResumeGenerator._build_summary(merged_resume, jd_data, lang),
            "experience": TargetResumeGenerator._build_experience_section(sorted_work, jd_data),
            "education": TargetResumeGenerator._build_education_section(
                merged_resume.get("education") or []
            ),
            "skills": TargetResumeGenerator._build_skills_section(
                merged_resume.get("skills") or [],
                merged_resume.get("certificates") or [],
                merged_resume.get("languages") or [],
                jd_data,
            ),
            "jd_gap": TargetResumeGenerator._build_jd_analysis(jd_data, merged_resume, lang),
        }

        # 生成中英自我介绍
        self_intro = {
            "zh": TargetResumeGenerator.build_self_intro(resume, "zh"),
            "en": TargetResumeGenerator.build_self_intro(resume, "en"),
        }

        # 构建导出数据
        export_data = TargetResumeGenerator._build_export_data(resume, self_intro)

        return {
            "resume": resume,
            "self_intro": self_intro,
            "export_data": export_data,
        }

    # ──────────── JD 权重排序 ────────────

    @staticmethod
    def _by_jd_relevance(entries: list[dict], jd_data: dict) -> list[dict]:
        """根据 JD 关键词对经历进行权重排序：匹配度高的在前"""
        keywords = (jd_data.get("hard_skills") or []) + (jd_data.get("soft_skills") or [])
        if not keywords:
            return list(entries)
        return sorted(
            entries,
            key=lambda e: sum(
                1 for k in keywords
                if k.lower() in json.dumps(e, ensure_ascii=False, default=str).lower()
            ),
            reverse=True,
        )

    # ──────────── 五模块构建 ────────────

    @staticmethod
    def _build_personal_section(bi: dict | None) -> dict:
        bi = bi or {}
        return {
            "name": bi.get("name") or "",
            "phone": bi.get("phone") or "",
            "email": bi.get("email") or "",
            "city": bi.get("city") or "",
            "target_job": bi.get("target_job") or "",
            "salary": bi.get("expect_salary") or "",
        }

    @staticmethod
    def _build_summary(data: dict, jd: dict, lang: str) -> str:
        """生成个人概述 —— 技能匹配 JD 摘要"""
        skills = [
            s.get("name") if isinstance(s, dict) else str(s)
            for s in (data.get("skills") or [])
        ]
        skills = [s for s in skills if s]
        matched = [
            h for h in (jd.get("hard_skills") or [])
            if any(h.lower() in s.lower() for s in skills)
        ]
        exp_count = len(data.get("work_experience") or [])
        name = (data.get("basic_info") or {}).get("name") or (
            "求职者" if lang == "zh" else "Candidate"
        )
        if lang == "zh":
            return f"{name}，{exp_count}+年经验，{'、'.join(matched[:3])}等技能匹配JD要求。"
        return f"{name}, {exp_count}+ years, skilled in {', '.join(matched[:3])}."

    @staticmethod
    def _build_experience_section(work: list[dict], jd: dict) -> list[dict]:
        """构建工作经历 section，标注 JD 匹配度"""
        jd_skills = jd.get("hard_skills") or []
        result = []
        for w in work:
            duties = str(w.get("duties") or "")
            relevance = (
                "高" if any(k.lower() in duties.lower() for k in jd_skills) else "中"
            )
            result.append({
                "company": w.get("company") or "",
                "position": w.get("position") or "",
                "period": " - ".join(
                    filter(None, [w.get("start_date"), w.get("end_date")])
                ),
                "bullets": [w.get("duties")] if w.get("duties") else [],
                "jd_relevance": relevance,
                "source_index": w.get("source_index") or [],
            })
        return result

    @staticmethod
    def _build_education_section(edu: list[dict]) -> list[dict]:
        return [
            {
                "school": e.get("school") or "",
                "major": e.get("major") or "",
                "degree": e.get("degree") or "",
                "period": " - ".join(
                    filter(None, [e.get("start_date"), e.get("end_date")])
                ),
            }
            for e in edu
        ]

    @staticmethod
    def _build_skills_section(
        skills: list[dict], certs: list[dict], langs: list[dict], jd: dict
    ) -> dict:
        """构建技能 section，标注 JD 匹配 / 缺失"""
        skill_names = [
            s.get("name") if isinstance(s, dict) else str(s)
            for s in skills
        ]
        skill_names = [s for s in skill_names if s]
        skip_set = {"英语", "English", "中文", "CET-4", "CET-6", "IELTS", "TOEFL"}
        jd_hard = jd.get("hard_skills") or []

        return {
            "technical": [s for s in skill_names if s not in skip_set],
            "languages": [
                l.get("name") if isinstance(l, dict) else str(l)
                for l in langs
            ],
            "certificates": [
                c.get("name") if isinstance(c, dict) else str(c)
                for c in certs
            ],
            "jd_matched": [
                h for h in jd_hard
                if any(h.lower() in s.lower() for s in skill_names)
            ],
            "jd_missing": [
                h for h in jd_hard
                if not any(h.lower() in s.lower() for s in skill_names)
            ],
        }

    @staticmethod
    def _build_jd_analysis(jd: dict, data: dict, lang: str) -> dict:
        """JD 缺口分析"""
        all_text = json.dumps(data, ensure_ascii=False, default=str).lower()
        jd_hard = jd.get("hard_skills") or []
        matched = [s for s in jd_hard if s.lower() in all_text]
        missing = [s for s in jd_hard if s.lower() not in all_text]
        return {
            "matched": matched or (
                ["无匹配技能"] if lang == "zh" else ["No matching skills"]
            ),
            "missing": missing or (
                ["无缺失"] if lang == "zh" else ["None"]
            ),
        }

    # ──────────── 自我介绍（中文约 350 字，110-130 秒）────────────

    @staticmethod
    def build_self_intro(resume: dict, lang: str = "zh") -> dict:
        """生成 2 分钟口语版自我介绍"""
        p = resume.get("personal") or {}
        top_exp = (resume.get("experience") or [{}])[0] if resume.get("experience") else {}
        skills_list = resume.get("skills", {}).get("technical") or []
        skills_str = "、".join(skills_list[:4]) if lang == "zh" else ", ".join(skills_list[:4])
        max_chars = 250 if lang == "zh" else 155

        if lang == "zh":
            intro = (
                f"面试官您好，我是{p.get('name') or '求职者'}。"
                + (f"应聘{p.get('target_job')}岗位。" if p.get("target_job") else "")
                + f"我熟练掌握{skills_str}。"
                + (
                    f"曾在{top_exp.get('company')}担任{top_exp.get('position') or ''}，"
                    f"{(top_exp.get('bullets') or [''])[0][:60]}。"
                    if top_exp.get("company")
                    else ""
                )
                + "期待能为团队贡献价值，谢谢。"
            )
        else:
            intro = (
                f"Hello, I'm {p.get('name') or 'a candidate'}. "
                + (f"Applying for {p.get('target_job')}. " if p.get("target_job") else "")
                + f"My skills include {skills_str}. "
                + (
                    f"Most recently at {top_exp.get('company')} "
                    f"as {top_exp.get('position') or 'a team member'}. "
                    if top_exp.get("company")
                    else ""
                )
                + "I'm excited about this opportunity. Thank you."
            )

        if len(intro) > max_chars:
            intro = intro[:max_chars - 3] + "..."

        rate = 200 if lang == "zh" else 150  # 字/分钟朗读速率
        est_seconds = round(len(intro) / rate * 60)
        return {"text": intro, "estimated_seconds": est_seconds, "char_count": len(intro)}

    # ──────────── 导出数据 ────────────

    @staticmethod
    def _build_export_data(resume: dict, self_intro: dict) -> dict:
        return {
            "sections": [
                {"title": "基本信息", "content": resume.get("personal")},
                {"title": "个人概述", "content": resume.get("summary")},
                {"title": "教育经历", "content": resume.get("education")},
                {"title": "工作经历", "content": resume.get("experience")},
                {"title": "技能证书", "content": resume.get("skills")},
            ],
            "self_intro": self_intro,
            "jd_analysis": resume.get("jd_gap"),
        }

    # ──────────── 合并补充信息 ────────────

    @staticmethod
    def _merge_extra(resume_data: dict, extra_info: dict) -> dict:
        """
        将追问补充信息合并到简历素材中。
        支持两种格式：
          1. 问答条目 qa_entries: [{"question": {...}, "answer": "..."}]
          2. 直接数据 new_skills / new_projects
        """
        result = dict(resume_data)

        # ── 处理问答条目（来自 InfoEnquiryAgent 追问）──
        qa_entries = extra_info.get("qa_entries") or []
        new_skills = []
        new_projects = []
        quant_answers = []
        exp_answers = []

        for qa in qa_entries:
            question = qa.get("question", {})
            answer = (qa.get("answer") or "").strip()
            if not answer or len(answer) < 5:
                continue

            category = question.get("category", "")
            keyword = question.get("keyword", "")

            if category in ("skill_gap", "skill_detail") and keyword:
                new_skills.append({
                    "name": keyword,
                    "category": "追问补充",
                    "source": "enquiry",
                })

            elif category == "project_detail":
                # 尝试从回答中提取项目名
                lines = [l.strip("①②③④⑤⑥⑦⑧⑨⑩- ") for l in answer.split("\n") if l.strip()]
                proj_name = lines[0][:60] if lines else "补充项目经历"
                new_projects.append({
                    "name": proj_name,
                    "description": answer[:500],
                    "results": "",
                    "source_index": [],
                })

            elif category == "quant_data":
                quant_answers.append(answer)

            elif category == "experience_gap":
                exp_answers.append(answer)

            elif category == "job_target":
                # 提取求职意向
                bi = result.setdefault("basic_info", {})
                if not bi.get("target_job") and keyword:
                    bi["target_job"] = keyword
                elif not bi.get("target_job"):
                    bi["target_job"] = answer[:60]

        # ── 合并到结果 ──
        if new_skills:
            result["skills"] = (result.get("skills") or []) + new_skills

        if new_projects:
            result["projects"] = (result.get("projects") or []) + new_projects

        # 量化数据 → 注入到工作经历的 duties 中
        if quant_answers:
            work_list = result.get("work_experience") or []
            for i, ans in enumerate(quant_answers):
                if i < len(work_list):
                    duties = work_list[i].get("duties") or ""
                    work_list[i]["duties"] = f"{duties}。补充量化成果：{ans[:200]}"
                else:
                    break

        # 经历补充 → 追加为额外的 work entry
        for ans in exp_answers:
            result.setdefault("work_experience", []).append({
                "company": "（追问补充）",
                "position": "",
                "start_date": "",
                "end_date": "",
                "duties": ans[:300],
                "source_index": [],
            })

        # ── 兼容旧格式：直接数据 ──
        if extra_info.get("new_skills"):
            result["skills"] = (result.get("skills") or []) + extra_info["new_skills"]
        if extra_info.get("new_projects"):
            result["projects"] = (result.get("projects") or []) + extra_info["new_projects"]

        return result


# ═══════════════════════════════════════════════════════════════
# 独立运行入口
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="04_target_resume_generator — 简历生成")
    parser.add_argument("--jd", required=True, help="JD JSON 文件路径")
    parser.add_argument("--resume", required=True, help="简历 JSON 文件路径")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"])
    parser.add_argument("--export", action="store_true", help="导出 Word + PDF")
    parser.add_argument("--output", default="output", help="输出目录")
    args = parser.parse_args()

    LanguageSwitch.set_lang(args.lang)

    with open(args.jd, encoding="utf-8") as f:
        jd_data = json.load(f)
    with open(args.resume, encoding="utf-8") as f:
        resume_data = json.load(f)

    result = TargetResumeGenerator.generate(jd_data, resume_data, lang=args.lang)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    si = result["self_intro"]
    print(f"\n[OK] 简历生成完成")
    print(f"  中文自我介绍: {si['zh']['estimated_seconds']}秒 ({si['zh']['char_count']}字)")
    print(f"  英文自我介绍: {si['en']['estimated_seconds']}秒 ({si['en']['char_count']}字)")

    if args.export:
        paths = export_resume(result, args.output)
        print(f"\n[导出] Word: {paths['word']}")
        print(f"[导出] PDF:  {paths['pdf']}")


if __name__ == "__main__":
    main()
