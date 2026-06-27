"""
03_info_enquiry_agent/main.py — AI 信息补充追问 Agent（可独立运行）

输入: 01_jd_parser 的 JD 关键词 + 02_resume_parser 的个人简历素材
逻辑: 识别 JD 要求但简历缺失的能力 → API 生成精准追问 → 用户回答回写素材库
约束: 只围绕岗位缺失项提问，不发散无关内容
"""

import sys
import json
import re
import asyncio
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.language_switch import LanguageSwitch
from common.multi_model_gateway import MultiModelGateway


class InfoEnquiryAgent:
    """
    AI 信息追问 Agent
    - 对比 JD 岗位需求 vs 简历已有信息
    - API 精准识别缺口并生成上下文追问
    - 用户回答后回写素材库，体现在最终简历中
    """

    # ──────────── 主入口：生成追问问题列表 ────────────

    @staticmethod
    def generate_questions(
        jd_data: dict,
        resume_data: dict,
        lang: str = "zh",
        gateway: MultiModelGateway | None = None,
    ) -> list[dict]:
        """
        基于 JD 和简历差异，生成精准追问问题列表。

        优先使用 API 生成上下文相关的高质量问题；
        API 不可用时回退到规则引擎。
        """
        # 先用规则引擎生成基础缺口分析
        gaps = InfoEnquiryAgent._analyze_gaps(jd_data, resume_data, lang)

        if not gaps:
            return []

        # 尝试用 API 生成更精准的追问
        if gateway and any(gateway.validate_api_keys().values()):
            try:
                api_questions = asyncio.run(
                    InfoEnquiryAgent._api_generate_questions(
                        gateway, jd_data, resume_data, gaps, lang
                    )
                )
                if api_questions and len(api_questions) >= len(gaps):
                    return api_questions
            except Exception:
                pass

        # 回退：用规则模板生成问题
        return InfoEnquiryAgent._build_template_questions(gaps, lang)

    # ──────────── 缺口分析 ────────────

    @staticmethod
    def _analyze_gaps(jd_data: dict, resume_data: dict, lang: str) -> list[dict]:
        """分析 JD 与简历之间的所有缺口。"""
        gaps: list[dict] = []

        jd_hard = jd_data.get("hard_skills") or []
        jd_soft = jd_data.get("soft_skills") or []
        years_req = jd_data.get("years_required")
        jd_position = jd_data.get("position", "")

        # 简历已有技能
        extracted_skills: set[str] = set()
        for s in resume_data.get("skills") or []:
            name = s.get("name") if isinstance(s, dict) else str(s)
            extracted_skills.add(name.lower())

        work_text = json.dumps(
            resume_data.get("work_experience") or [], ensure_ascii=False
        ).lower()
        proj_text = json.dumps(
            resume_data.get("projects") or [], ensure_ascii=False
        ).lower()
        all_text = work_text + " " + proj_text

        # 1. 技能缺口
        for skill in jd_hard:
            if skill.lower() not in extracted_skills and skill.lower() not in all_text:
                gaps.append({
                    "category": "skill_gap",
                    "keyword": skill,
                    "detail": f"JD 要求 {skill}，简历未体现",
                    "source": "jd",
                })
            elif skill.lower() not in extracted_skills:
                gaps.append({
                    "category": "skill_detail",
                    "keyword": skill,
                    "detail": f"JD 要求 {skill}，简历有提及但未在技能列表中",
                    "source": "jd",
                })

        # 2. 软技能缺口
        for skill in jd_soft:
            if skill.lower() not in all_text:
                gaps.append({
                    "category": "soft_skill_gap",
                    "keyword": skill,
                    "detail": f"JD 要求软技能：{skill}",
                    "source": "jd",
                })

        # 3. 量化数据缺失
        has_quant = False
        for w in resume_data.get("work_experience") or []:
            duties = str(w.get("duties") or "")
            if re.search(r"\d+[%％倍kKwW万]", duties):
                has_quant = True
                break
        if not has_quant and len(resume_data.get("work_experience") or []) > 0:
            gaps.append({
                "category": "quant_data",
                "detail": "工作经历缺少量化成果数据",
                "target_sections": ["work_experience", "projects"],
                "source": "analysis",
            })

        # 4. 项目经历缺失
        if not resume_data.get("projects"):
            gaps.append({
                "category": "project_detail",
                "detail": "简历缺少项目经历章节",
                "source": "analysis",
            })

        # 5. 工作年限缺口
        if years_req:
            y_match = re.match(r"(\d+)", str(years_req))
            y = int(y_match.group(1)) if y_match else 0
            work_count = len(resume_data.get("work_experience") or [])
            if y > 0 and work_count < max(1, y // 2):
                gaps.append({
                    "category": "experience_gap",
                    "detail": f"JD 要求 {years_req} 经验，简历展示 {work_count} 段经历",
                    "source": "jd",
                })

        # 6. 自我介绍缺失
        bi = resume_data.get("basic_info") or {}
        if not bi.get("target_job") and jd_position:
            gaps.append({
                "category": "job_target",
                "detail": f"JD 岗位为 {jd_position}，简历未明确求职意向",
                "source": "analysis",
            })

        return gaps

    # ──────────── API 生成追问 ────────────

    @staticmethod
    async def _api_generate_questions(
        gateway: MultiModelGateway,
        jd_data: dict,
        resume_data: dict,
        gaps: list[dict],
        lang: str,
    ) -> list[dict] | None:
        """使用 AI 根据缺口生成精准追问问题。"""
        jd_summary = json.dumps({
            "position": jd_data.get("position"),
            "company": jd_data.get("company"),
            "hard_skills": jd_data.get("hard_skills", [])[:8],
            "soft_skills": jd_data.get("soft_skills", [])[:5],
            "years": jd_data.get("years_required"),
            "education": jd_data.get("education_required"),
        }, ensure_ascii=False)

        resume_summary = json.dumps({
            "name": (resume_data.get("basic_info") or {}).get("name"),
            "education": [
                {"school": e.get("school"), "major": e.get("major")}
                for e in (resume_data.get("education") or [])[:2]
            ],
            "work": [
                {"company": w.get("company"), "position": w.get("position"), "duties": str(w.get("duties", ""))[:100]}
                for w in (resume_data.get("work_experience") or [])[:3]
            ],
            "skills": [
                s.get("name") if isinstance(s, dict) else str(s)
                for s in (resume_data.get("skills") or [])[:10]
            ],
        }, ensure_ascii=False)

        gaps_json = json.dumps(gaps, ensure_ascii=False)

        prompt = f"""你是资深 HR，需要针对候选人的简历与 JD 之间的缺口，生成精准的追问问题。

# JD 要求
{jd_summary}

# 候选人简历
{resume_summary}

# 已识别的缺口
{gaps_json}

# 任务
为每个缺口生成 1 个追问。要求：
1. 问题要具体、指向明确，不能泛泛而问
2. 每个问题绑定 category/keyword/source 字段
3. 只输出 JSON 数组，格式：[{{"category":"skill_gap","keyword":"React","question":"...","detail":"...","source":"jd"}}]

语言：{'中文' if lang == 'zh' else 'English'}"""

        result = await gateway.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            task_type="enquiry",
            options={"max_tokens": 2048, "temperature": 0.3, "lang": lang},
        )

        if result.success and result.content:
            from common.multi_model_gateway import safe_parse_json
            questions = safe_parse_json(result.content)
            if isinstance(questions, list) and len(questions) > 0:
                return questions
        return None

    # ──────────── 模板问题回退 ────────────

    @staticmethod
    def _build_template_questions(gaps: list[dict], lang: str) -> list[dict]:
        """用规则模板为每个缺口生成问题。"""
        questions = []
        for gap in gaps:
            cat = gap.get("category", "")
            keyword = gap.get("keyword", "")
            detail = gap.get("detail", "")

            if cat == "skill_gap":
                questions.append({
                    "category": cat, "keyword": keyword,
                    "question": (
                        f"【技能缺口】{detail}。请描述您使用 {keyword} 的具体项目经历、"
                        f"掌握程度（入门/熟练/精通），以及在实际工作中用 {keyword} 解决了什么问题？"
                    ) if lang == "zh" else f"Skill gap: {detail}. Describe your experience with {keyword}.",
                    "detail": detail, "source": gap.get("source", "jd"),
                })
            elif cat == "skill_detail":
                questions.append({
                    "category": cat, "keyword": keyword,
                    "question": (
                        f"【技能详情】{detail}。请在下方详细说明您在 {keyword} 方面的"
                        f"实际使用场景、项目案例和掌握深度。"
                    ) if lang == "zh" else f"Detail needed: {detail}. Elaborate on your {keyword} experience.",
                    "detail": detail, "source": gap.get("source", "jd"),
                })
            elif cat == "quant_data":
                questions.append({
                    "category": cat,
                    "question": (
                        "【量化成果】您的简历中工作经历缺少具体数据支撑。请为每段经历补充量化成果，"
                        "例如：性能提升 X%、团队规模 N 人、业务增长 X 倍、QPS 从 A 提升到 B 等。"
                    ) if lang == "zh" else "Please add quantitative results to your work experience.",
                    "detail": detail, "source": gap.get("source", "analysis"),
                })
            elif cat == "project_detail":
                questions.append({
                    "category": cat,
                    "question": (
                        "【项目经历】请补充 1-2 个最能体现您技术能力的项目："
                        "① 项目名称 ② 您的角色和具体职责 ③ 使用的技术栈 ④ 取得的量化成果。"
                    ) if lang == "zh" else "Please add 1-2 key projects with your role, tech stack, and outcomes.",
                    "detail": detail, "source": gap.get("source", "analysis"),
                })
            elif cat == "experience_gap":
                questions.append({
                    "category": cat,
                    "question": (
                        f"【经历补充】{detail}。您是否有更早期的相关工作、实习或项目经历？"
                        f"请补充完整的工作时间线。"
                    ) if lang == "zh" else f"Experience gap: {detail}. Any earlier relevant roles?",
                    "detail": detail, "source": gap.get("source", "jd"),
                })
            elif cat == "soft_skill_gap":
                questions.append({
                    "category": cat, "keyword": keyword,
                    "question": (
                        f"【软技能】JD 要求具备「{keyword}」能力。请举例说明您在过往工作中"
                        f"如何体现这项能力的？"
                    ) if lang == "zh" else f"Soft skill needed: {keyword}. Give an example.",
                    "detail": detail, "source": gap.get("source", "jd"),
                })
            elif cat == "job_target":
                questions.append({
                    "category": cat,
                    "question": (
                        f"【求职意向】{detail}。请确认您的求职意向岗位、期望薪资和可入职时间。"
                    ) if lang == "zh" else f"Job target: {detail}. Confirm your target role and expectations.",
                    "detail": detail, "source": gap.get("source", "analysis"),
                })

        return questions

    # ──────────── 处理用户回答 ────────────

    @staticmethod
    def process_answer(
        question: dict,
        answer: str,
        material_store: Any = None,
    ) -> bool:
        """
        处理用户对追问的回答，回写到素材库

        Args:
            question: 原始追问问题
            answer: 用户的文本回答
            material_store: 素材库对象（需支持 add_skill / add_qa_entry）

        Returns:
            是否成功回写
        """
        if not material_store:
            return False

        # 技能类回答 —— 写入技能列表
        if question.get("category") == "skill_gap" and len(answer.strip()) > 5:
            if hasattr(material_store, "add_skill"):
                material_store.add_skill(
                    {
                        "name": question.get("keyword"),
                        "category": "工具",
                        "source": "增信问卷",
                    },
                    "问卷补充",
                )
            return True

        # 通用回答 —— 写入 QA 记录
        if len(answer.strip()) > 10:
            if hasattr(material_store, "add_qa_entry"):
                material_store.add_qa_entry({
                    "question": question.get("question"),
                    "answer": answer,
                    "source": "questionnaire",
                })
            return True

        return False


# ═══════════════════════════════════════════════════════════════
# 独立运行入口
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="03_info_enquiry_agent — AI 追问")
    parser.add_argument("--jd", required=True, help="JD JSON 文件路径")
    parser.add_argument("--resume", required=True, help="简历 JSON 文件路径")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"])
    args = parser.parse_args()

    LanguageSwitch.set_lang(args.lang)

    with open(args.jd, encoding="utf-8") as f:
        jd_data = json.load(f)
    with open(args.resume, encoding="utf-8") as f:
        resume_data = json.load(f)

    questions = InfoEnquiryAgent.generate_questions(jd_data, resume_data, lang=args.lang)
    print(json.dumps(questions, ensure_ascii=False, indent=2))
    print(f"\n[OK] 共生成 {len(questions)} 个追问")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. [{q['category']}] {q['question'][:80]}...")


if __name__ == "__main__":
    main()
