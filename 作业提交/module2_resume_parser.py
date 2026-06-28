"""
模块2 —— 个人简历解析器
核心功能：输入简历文本，提取结构化个人信息
核心技术：正则表达式提取姓名/电话/邮箱/学校/公司/技能等硬字段
"""

import re
import json


class ResumeParser:
    """简历解析器 - 核心：正则提取硬字段 + AI结构化提取 + 合并"""

    @staticmethod
    def extract_hard_fields(text: str) -> dict:
        """
        正则提取硬字段：姓名/电话/邮箱/城市/学校/专业/公司/时间/技能
        这些是强格式字段，正则比AI更可靠、更稳定
        """
        result = {
            "name": None, "phone": None, "email": None, "city": None,
            "schools": [], "majors": [], "companies": [],
            "degrees": [], "dates": [], "skills_detected": [],
        }

        # 姓名
        m = re.search(r"姓\s*名[：:\s]*([^\n,，。\d\s]{2,6})", text)
        if m:
            result["name"] = m.group(1).strip()
        else:
            m = re.search(r"^([\u4e00-\u9fff]{2,4})\s*\n\s*(?:电话|手机|Tel|Phone|1[3-9]\d)", text, re.MULTILINE)
            if m:
                result["name"] = m.group(1).strip()

        # 手机号
        phone_m = re.search(r"(1[3-9]\d{9})", text)
        if phone_m:
            result["phone"] = phone_m.group(1)

        # 邮箱
        email_m = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text)
        if email_m:
            result["email"] = email_m.group(1)

        # 城市
        city_m = re.search(
            r"(北京|上海|广州|深圳|杭州|成都|武汉|南京|西安|重庆|苏州|天津|长沙"
            r"|郑州|东莞|青岛|厦门|合肥|大连|沈阳|福州|济南|宁波|昆明)", text)
        if city_m:
            result["city"] = city_m.group(1)

        # 学校名称
        school_pat = re.compile(r"((?:[\u4e00-\u9fff]{2,8})(?:大学|学院|College|University|Institute|School))", re.IGNORECASE)
        seen = set()
        for m in school_pat.finditer(text):
            s = m.group(1).strip()
            if s not in seen and len(s) >= 4:
                seen.add(s)
                result["schools"].append(s)

        # 专业名称
        major_patterns = [
            r"(?:专业|Major)[：:\s]*([^\n,，。]{2,20})",
            r"(?:计算机|软件|数据|人工智能|电子|通信|机械|土木|金融|会计"
            r"|市场|设计|法学|医学|英语|中文)(?:科学|工程|技术|学|管理)?",
        ]
        for pat in major_patterns:
            for m in re.finditer(pat, text):
                val = (m.group(1) if m.lastindex else m.group(0)).strip()
                if val not in result["majors"]:
                    result["majors"].append(val)

        # 学历
        degree_m = re.search(r"(博士|硕士|本科|大专|MBA|EMBA|Bachelor|Master|Doctor|PhD)", text, re.IGNORECASE)
        if degree_m:
            result["degrees"].append(degree_m.group(1))

        # 公司名称
        company_pats = [
            r"((?:[\u4e00-\u9fff]{2,15})(?:有限公司|股份公司|集团|科技|网络|信息|互联|数据|软件|通信|技术))",
            r"((?:[\u4e00-\u9fffA-Za-z]{2,20})(?:Inc|Ltd|Corp|LLC|Co\.?)(?:\.|$|\s))",
        ]
        seen_c = set()
        for pat in company_pats:
            for m in re.finditer(pat, text, re.IGNORECASE):
                c = m.group(1).strip()
                if c not in seen_c:
                    seen_c.add(c)
                    result["companies"].append(c)

        # 时间范围
        date_pat = re.compile(
            r"((?:19|20)\d{2}[.年-]\d{1,2}(?:[.月-]\d{1,2}[日号]?)?"
            r"\s*[-～至到]\s*"
            r"(?:至今|现在|present|(?:19|20)\d{2}[.年-]\d{1,2}))", re.IGNORECASE)
        for m in date_pat.finditer(text):
            result["dates"].append(m.group(1))

        # 技能关键词
        skill_kw = re.findall(
            r"(Python|Java|Go|Rust|C\+\+|JavaScript|TypeScript|React|Vue|Angular"
            r"|Node\.?js|Docker|Kubernetes|SQL|MySQL|PostgreSQL|MongoDB|Redis"
            r"|AWS|Azure|GCP|Linux|Git|TensorFlow|PyTorch|Spark|Hadoop"
            r"|Figma|Photoshop|Excel|PPT|PowerPoint|Tableau)", text, re.IGNORECASE)
        result["skills_detected"] = list(set(s[0] if isinstance(s, tuple) else s for s in skill_kw))[:20]

        return result

    @staticmethod
    def merge_results(ai_result: dict | None, hard_fields: dict) -> dict:
        """合并AI和正则结果：硬字段兜底AI遗漏"""
        base = (ai_result or {}).get("basic_info") or {}
        return {
            "basic_info": {
                "name": base.get("name") or hard_fields.get("name"),
                "phone": base.get("phone") or hard_fields.get("phone"),
                "email": base.get("email") or hard_fields.get("email"),
                "city": base.get("target_city") or hard_fields.get("city"),
                "target_job": base.get("target_position") or "",
                "expect_salary": base.get("expected_salary") or "",
            },
            "education": [
                {"school": e.get("school_name"), "major": e.get("major"),
                 "degree": e.get("degree"), "period": " - ".join(filter(None, [e.get("start_date"), e.get("end_date")]))}
                for e in ((ai_result or {}).get("education_list") or [])
            ],
            "work_experience": [
                {"company": w.get("company"), "position": w.get("position"),
                 "period": " - ".join(filter(None, [w.get("start_date"), w.get("end_date")])),
                 "duties": w.get("job_duty")}
                for w in ((ai_result or {}).get("work_experience_list") or [])
            ],
            "skills": [{"name": s} for s in hard_fields.get("skills_detected", [])],
        }

    @staticmethod
    def to_material_json(parsed: dict) -> dict:
        """导出为标准素材库JSON"""
        bi = parsed.get("basic_info") or {}
        return {
            "identity": {
                "name": bi.get("name"), "phone": bi.get("phone"),
                "email": bi.get("email"), "city": bi.get("city"),
                "target_job": bi.get("target_job"),
            },
            "education": parsed.get("education") or [],
            "work_experience": parsed.get("work_experience") or [],
            "skills": parsed.get("skills") or [],
        }


def run():
    sample = """姓名：张三
电话：13800138000
邮箱：zhangsan@email.com
城市：北京
教育经历
北京大学  计算机科学与技术  本科  2018.09 - 2022.06
工作经历
字节跳动  Python后端开发工程师  2022.07 - 至今
负责高并发API服务开发，使用Python/Django/MySQL/Redis/Kafka
技能：Python, Django, MySQL, Redis, Docker, Git, Linux"""
    print("="*60)
    print("  模块2：个人简历解析器")
    print("  功能：输入简历文本，提取结构化个人信息")
    print("="*60)
    print("\n[示例简历文本]\n" + "-"*40 + "\n" + sample + "\n" + "-"*40)
    result = ResumeParser.extract_hard_fields(sample)
    print("\n[正则提取结果]")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n[核心代码说明]")
    print("  · extract_hard_fields(): 8类硬字段正则提取（姓名/电话/邮箱/城市/学校/专业/公司/技能）")
    print("  · to_material_json(): 标准化素材库导出格式")
    print("  · merge_results(): AI优先、正则兜底的融合策略")
    custom = input("\n是否输入自定义简历？(y/n): ").strip()
    if custom.lower() == 'y':
        print("请输入简历文本（输入END结束）：")
        lines = []
        while True:
            line = input()
            if line == 'END': break
            lines.append(line)
        if lines:
            r2 = ResumeParser.extract_hard_fields('\n'.join(lines))
            print("\n[结果]\n" + json.dumps(r2, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
