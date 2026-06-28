"""
模块1 —— JD职位解析器
核心功能：输入招聘JD文本，输出结构化职位信息
核心技术：正则表达式模式匹配 + AI提取 + 合并校验
"""

import re
import json


class JDKeywordMatcher:
    """JD职位解析器 - 核心：正则提取硬字段 + 关键词匹配"""

    # 技能关键词正则库（编程语言/前端/后端/数据库/云DevOps/大数据AI/工具）
    HARD_SKILL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
        r"Python", r"Java\b", r"JavaScript", r"TypeScript", r"Go(lang)?",
        r"Rust", r"C\+\+", r"C#", r"PHP", r"Ruby", r"Swift", r"Kotlin",
        r"React", r"Vue", r"Angular", r"Svelte", r"Next\.?js",
        r"Node\.?js", r"Express", r"Django", r"Flask", r"FastAPI",
        r"Spring\s*(Boot|Cloud)?", r"\.NET", r"Laravel",
        r"SQL", r"MySQL", r"PostgreSQL", r"MongoDB", r"Redis",
        r"Docker", r"Kubernetes", r"K8s", r"AWS", r"Azure", r"GCP",
        r"Jenkins", r"GitLab\s*CI", r"Terraform", r"Nginx", r"Linux",
        r"Spark", r"Hadoop", r"Flink", r"Kafka",
        r"TensorFlow", r"PyTorch", r"LLM", r"LangChain", r"RAG",
        r"Scikit[- ]?learn", r"Pandas", r"NumPy", r"OpenCV",
        r"Git", r"Figma", r"Photoshop", r"Tableau", r"Power\s*BI",
    ]]

    EDUCATION_PATTERNS = re.compile(
        r"(博士|硕士|本科|大专|MBA|EMBA|高中|中专|不限|学历不限)", re.IGNORECASE)

    SALARY_PATTERNS = re.compile(
        r"(\d{1,2}[kK]-?\s*~?\s*\d{1,2}[kK]"
        r"|\d+千-\s*~?\s*\d+千"
        r"|\d+万-\s*~?\s*\d+万"
        r"|\d+[kK][-\s~]*\d+[kK])")

    YEARS_PATTERNS = re.compile(r"(\d+)[\s-]*(年|years?)", re.IGNORECASE)

    @classmethod
    def extract_jd(cls, text: str) -> dict:
        """核心方法：从JD文本中提取结构化信息 - 正则匹配 + 关键词扫描"""
        skills = []
        for pat in cls.HARD_SKILL_PATTERNS:
            for m in pat.finditer(text):
                s = m.group(0)
                if s not in skills:
                    skills.append(s)

        edu_m = cls.EDUCATION_PATTERNS.findall(text)
        education = edu_m[0] if edu_m else None

        salary_m = cls.SALARY_PATTERNS.search(text)
        salary = salary_m.group(0) if salary_m else None

        years_list = []
        for m in cls.YEARS_PATTERNS.finditer(text):
            yr = int(m.group(1))
            if 1 <= yr <= 30:
                years_list.append(yr)
        years_required = f"{max(years_list)}年" if years_list else None

        position_match = re.search(
            r"((?:高级|资深|实习|助理|初级|中级|主管|经理|总监|架构师"
            r"|工程师|设计师|分析师|程序员|运营|产品经理|项目经理"
            r"|HR|开发|测试|运维|前端|后端|全栈"
            r"|数据[分析科]|算法|AI|机器学习|深度学习|NLP|CV"
            r"|Senior|Junior|Lead|Manager|Engineer|Developer|Analyst"
            r"|Architect|Designer|Consultant|Intern)"
            r"(?:\s*[（(]\s*\w+\s*[）)])?)",
            text, re.IGNORECASE)
        position = position_match.group(0) if position_match else None

        company_match = re.search(
            r"((?:[\u4e00-\u9fffA-Za-z]{2,20})"
            r"(?:有限公司|股份公司|集团|科技|网络|信息|互联|数据"
            r"|软件|通信|技术|金融|银行|保险|证券|基金"
            r"|Inc\.?|Ltd\.?|Corp\.?|LLC|Co\.?,?\s*Ltd\.?))",
            text, re.IGNORECASE)
        company = company_match.group(1) if company_match else None

        location_match = re.search(
            r"(北京|上海|广州|深圳|杭州|成都|武汉|南京|西安|重庆"
            r"|苏州|天津|长沙|郑州|东莞|青岛|厦门|合肥|大连|沈阳"
            r"|福州|济南|宁波|昆明|无锡|佛山|珠海|中山|惠州|远程|Remote)",
            text)
        location = location_match.group(1) if location_match else None

        return {
            "position": position, "company": company, "location": location,
            "salary_range": salary, "years_required": years_required,
            "education_required": education, "hard_skills": skills,
            "skills_count": len(skills),
        }

    @classmethod
    def merge_results(cls, ai_result: dict | None, regex_result: dict) -> dict:
        """合并AI和正则结果：AI优先，正则兜底，技能去重"""
        ai = ai_result or {}
        return {
            "position": ai.get("position") or regex_result.get("position"),
            "company": ai.get("company") or regex_result.get("company"),
            "location": ai.get("location") or regex_result.get("location"),
            "salary_range": ai.get("salary_range") or regex_result.get("salary_range"),
            "years_required": ai.get("years_required") or regex_result.get("years_required"),
            "education_required": ai.get("education_required") or regex_result.get("education_required"),
            "hard_skills": list(set(
                (ai.get("hard_skills") or []) + (regex_result.get("hard_skills") or [])
            )),
            "soft_skills": ai.get("soft_skills") or [],
            "industry": ai.get("industry") or [],
            "job_type": ai.get("job_type") or "全职",
        }


def run():
    sample = """岗位名称：高级Python后端开发工程师
公司：北京字节跳动科技有限公司
工作地点：北京
薪资范围：30k-50k
岗位要求：
1. 精通Python，5年以上Python开发经验
2. 熟悉Django、FastAPI等后端框架
3. 熟悉MySQL、Redis、Kafka等中间件
4. 了解Docker、Kubernetes等容器技术
5. 本科以上学历，计算机相关专业优先
6. 有高并发系统设计经验者优先"""
    print("="*60)
    print("  模块1：JD职位解析器")
    print("  功能：输入招聘JD文本，提取结构化职位信息")
    print("="*60)
    print("\n[示例JD文本]\n" + "-"*40 + "\n" + sample + "\n" + "-"*40)
    result = JDKeywordMatcher.extract_jd(sample)
    print("\n[提取结果]")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n[核心代码说明]")
    print("  · HARD_SKILL_PATTERNS: 覆盖30+技能类别的正则表达式库")
    print("  · merge_results(): AI优先、正则兜底的融合策略")
    print("  · 正则提取引擎: 基于关键词扫描的教育/薪资/年限/地点提取")
    custom = input("\n是否输入自定义JD文本？(y/n): ").strip()
    if custom.lower() == 'y':
        print("请输入JD文本（输入END结束）：")
        lines = []
        while True:
            line = input()
            if line == 'END':
                break
            lines.append(line)
        if lines:
            r2 = JDKeywordMatcher.extract_jd('\n'.join(lines))
            print("\n[结果]\n" + json.dumps(r2, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
