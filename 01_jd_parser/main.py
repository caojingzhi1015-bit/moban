"""
01_jd_parser/main.py — 岗位 JD 解析模块（可独立运行）

输入: 本地图片/PDF 文件，或纯文本字符串
输出: 结构化 JD JSON（岗位名/公司/薪资/职责/技能/行业等）

执行流水线:
  1. 调 common/ocr_pdf_processor 解析文件 → 分章节带索引原文素材库
  2. 正则预提取硬字段（技能关键词/年限/学历/薪资/公司/岗位）
  3. 调 multi_model_gateway AI 结构化抽取（temperature=0）
  4. 合并结果（AI 优先，正则兜底）
  5. 调 fact_check_validator 双层校验（格式+溯源）
"""

import sys
import json
import re
import asyncio
from pathlib import Path

# 将项目根目录加入 sys.path，确保 common 可导入
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.ocr_pdf_processor import OcrPdfProcessor
from common.fact_check_validator import FactCheckValidator
from common.multi_model_gateway import MultiModelGateway, safe_parse_json
from common.language_switch import LanguageSwitch

# ──────────── 硬技能正则预提取模式（扩展版）────────────

HARD_SKILL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in [
    # 编程语言
    r"Python", r"Java\b", r"JavaScript", r"TypeScript", r"Go(lang)?",
    r"Rust", r"C\+\+", r"C#", r"PHP", r"Ruby", r"Swift", r"Kotlin",
    r"Scala", r"MATLAB", r"R\b(?!\w)", r"Shell", r"Bash",
    # 前端
    r"React", r"Vue", r"Angular", r"Svelte", r"Next\.?js", r"Nuxt\.?js",
    r"jQuery", r"HTML5?", r"CSS3?", r"SASS?", r"Less",
    # 后端
    r"Node\.?js", r"Express", r"Django", r"Flask", r"FastAPI",
    r"Spring\s*(Boot|Cloud)?", r"\.NET", r"Laravel", r"Rails",
    # 数据库
    r"SQL", r"MySQL", r"PostgreSQL", r"MongoDB", r"Redis",
    r"Elasticsearch", r"Oracle", r"Hive", r"ClickHouse",
    # 云 & DevOps
    r"Docker", r"Kubernetes", r"K8s", r"AWS", r"Azure", r"GCP",
    r"Jenkins", r"GitLab\s*CI", r"GitHub\s*Actions", r"Terraform",
    r"Ansible", r"Nginx", r"Linux", r"Unix",
    # 大数据 & AI
    r"Spark", r"Hadoop", r"Flink", r"Kafka", r"RabbitMQ",
    r"TensorFlow", r"PyTorch", r"LLM", r"LangChain", r"RAG",
    r"Scikit[- ]?learn", r"Pandas", r"NumPy", r"OpenCV",
    # 工具
    r"Git", r"SVN", r"Figma", r"Photoshop", r"Excel", r"Tableau",
    r"Power\s*BI", r"JIRA", r"Confluence", r"Notion",
]]
# ──────────── 学历预提取模式 ────────────
EDUCATION_PATTERNS = re.compile(
    r"(博士|硕士|本科|大专|MBA|EMBA|高中|中专|不限|学历不限)",
    re.IGNORECASE,
)

# ──────────── 薪资预提取模式 ────────────
SALARY_PATTERNS = re.compile(
    r"(\d{1,2}[kK]-?\d{1,2}[kK]|\d+千[-\s~至到]*\d+千"
    r"|\d+万[-\s~至到]*\d+万"
    r"|\d+[kK][-\s~至到]*\d+[kK])",
)

# ──────────── 年限提取模式 ────────────
YEARS_PATTERNS = re.compile(
    r"(\d+)[\s-]*(年|years?)(?!\s*(以|之))",
    re.IGNORECASE,
)


class JDParser:
    """岗位 JD 解析器 —— 文件→原文→正则预提取→AI抽取→校验→结构化JSON"""

    @classmethod
    async def parse(
        cls,
        input_data: str | Path,
        gateway: MultiModelGateway | None = None,
        lang: str = "zh",
    ) -> dict:
        """
        主入口：解析 JD

        Args:
            input_data: 文件路径（图片/PDF/文本），或纯文本字符串
            gateway: 多模型网关实例（为 None 时跳过 AI 抽取，仅用正则）
            lang: 语言代码 zh/en

        Returns:
            标准化 JD JSON，含 _validation 和 _raw_text 元数据
        """
        # Step 0: 文件预处理 → 拿到分章节素材
        raw_text = ""
        sectioned_text = ""
        file_path = (
            Path(input_data)
            if isinstance(input_data, (str, Path)) and Path(input_data).exists()
            else None
        )

        if file_path:
            result = OcrPdfProcessor.process_file(file_path, lang=lang)
            if not result.success:
                raise RuntimeError(f"JD 文件解析失败: {result.error}")
            raw_text = result.raw_text
            sectioned_text = result.sectioned_text or ""
        else:
            raw_text = str(input_data)
            # Build sections for pasted text
            try:
                from common.ocr_pdf_processor import _classify_sections, _format_sectioned_text
                sections = _classify_sections(raw_text, lang)
                if sections:
                    sectioned_text = _format_sectioned_text(sections, raw_text, lang)
            except Exception:
                pass

        # Step 1: 正则预提取硬字段
        regex_result = cls._extract_jd_patterns(raw_text)

        # Step 2: AI 结构化抽取（使用分章节素材，temperature=0）
        llm_result = None
        if gateway:
            ai_input = sectioned_text if sectioned_text else raw_text
            llm_result = await cls._call_ai_extraction(ai_input, lang, gateway)

        # Step 3: 合并（AI 优先，正则兜底）
        merged = cls._merge_results(llm_result or {}, regex_result)

        # Step 4: 双层校验
        validation = FactCheckValidator.validate_all(merged, raw_text)

        return {
            "success": True,
            **merged,
            "_validation": validation,
            "_raw_text": raw_text,
        }

    # ──────────── 正则预提取（增强版）────────────

    @staticmethod
    def _extract_jd_patterns(text: str) -> dict:
        """正则预提取 JD 中的硬字段，AI 失败时的兜底方案"""
        # 技能关键词
        skills: list[str] = []
        for pat in HARD_SKILL_PATTERNS:
            for m in pat.finditer(text):
                s = m.group(0)
                if s not in skills:
                    skills.append(s)

        # 学历
        edu_matches = EDUCATION_PATTERNS.findall(text)
        education = edu_matches[0] if edu_matches else None

        # 薪资
        salary_m = SALARY_PATTERNS.search(text)
        salary = salary_m.group(0) if salary_m else None

        # 年限要求
        years_list = []
        for m in YEARS_PATTERNS.finditer(text):
            yr = int(m.group(1))
            if 1 <= yr <= 30:
                years_list.append(yr)
        years_required = f"{max(years_list)}年" if years_list else None

        # 岗位名称猜测（基于常见职位关键词）
        position_keywords = re.findall(
            r"((?:高级|资深|实习|助理|初级|中级|主管|经理|总监|架构师|工程师|设计师|分析师"
            r"|程序员|运营|产品经理|项目经理|HR|开发|测试|运维|前端|后端|全栈"
            r"|数据[分析工科]|算法|AI|机器学习|深度学习|NLP|CV|推荐系统"
            r"|Senior|Junior|Lead|Staff|Principal|Manager|Director|Engineer|Developer|Analyst"
            r"|Architect|Designer|Consultant|Intern)(?:\s*[（(]\s*\w+\s*[）)])?)",
            text, re.IGNORECASE,
        )
        guessed_position = position_keywords[0] if position_keywords else None

        # 公司名称猜测
        company_match = re.search(
            r"((?:[一-鿿A-Za-z]{2,20})(?:有限公司|股份公司|集团|科技|网络|信息"
            r"|互联|数据|软件|通信|技术|金融|银行|保险|证券|基金"
            r"|Inc\.?|Ltd\.?|Corp\.?|LLC|Co\.?,?\s*Ltd\.?))",
            text, re.IGNORECASE,
        )
        guessed_company = company_match.group(1) if company_match else None

        # 城市/地点
        location_match = re.search(
            r"(北京|上海|广州|深圳|杭州|成都|武汉|南京|西安|重庆"
            r"|苏州|天津|长沙|郑州|东莞|青岛|厦门|合肥|大连|沈阳"
            r"|福州|济南|宁波|昆明|无锡|佛山|珠海|中山|惠州|远程|Remote)",
            text,
        )
        location = location_match.group(1) if location_match else None

        return {
            "hard_skills": skills,
            "years_required": years_required,
            "education_required": education,
            "salary_range": salary,
            "guessed_position": guessed_position,
            "guessed_company": guessed_company,
            "location": location,
        }

    # ──────────── AI 抽取 ────────────

    @classmethod
    async def _call_ai_extraction(
        cls, text: str, lang: str, gateway: MultiModelGateway
    ) -> dict | None:
        """调用 AI 网关执行结构化字段抽取，使用分章节素材 + temperature=0"""
        prompt_text = cls._load_prompt()

        # If text is already section-formatted, use it directly
        if "【" in text and "】" in text and "─" in text:
            indexed_input = text
        else:
            indexed_input = OcrPdfProcessor.text_to_indexed_lines(text)

        full_prompt = f"""{prompt_text}

# 输入素材 (带行索引)
{indexed_input}

# 输出要求
- 严格按以下 JSON Schema 输出，temperature=0，只摘抄原文，禁止编造
- 每个字段若原文不存在，填 null 或空数组 []
- 所有文字内容必须与原文一字不差
- 每条职责/要求必须绑定 source_index 行号

# 输出 Schema (严格纯 JSON，不输出任何其他内容)
{{
  "position": "岗位名称|null",
  "company": "公司名称|null",
  "location": "工作地点|null",
  "salary_range": "薪资范围|null",
  "years_required": "年限要求|null",
  "education_required": "学历要求|null",
  "responsibilities": [{{"text": "职责原文", "source_index": [行号]}}],
  "requirements": [{{"text": "要求原文", "type": "hard_skill|soft_skill|education|experience|other", "source_index": [行号]}}],
  "hard_skills": ["技术关键词"],
  "soft_skills": ["软技能"],
  "industry": ["行业标签"],
  "job_type": "全职|实习|兼职|远程|null"
}}"""

        result = await gateway.chat_completion(
            messages=[{"role": "user", "content": full_prompt}],
            task_type="jd_parse",
            options={"max_tokens": 2048, "temperature": 0.0, "lang": lang},
        )

        if not result.success or not result.content:
            print(f"[JDParser] AI 抽取失败: {result.error} - {result.message}")
            return None

        return safe_parse_json(result.content)

    # ──────────── 合并 ────────────

    @staticmethod
    def _merge_results(ai: dict, regex: dict) -> dict:
        """合并 AI 和正则结果 —— AI 优先，正则兜底"""
        return {
            "position": ai.get("position") or regex.get("guessed_position"),
            "company": ai.get("company") or regex.get("guessed_company"),
            "location": ai.get("location") or regex.get("location"),
            "salary_range": ai.get("salary_range") or regex.get("salary_range"),
            "years_required": ai.get("years_required") or regex.get("years_required"),
            "education_required": ai.get("education_required") or regex.get("education_required"),
            "responsibilities": ai.get("responsibilities") or [],
            "requirements": ai.get("requirements") or [],
            "hard_skills": list(
                set(
                    (ai.get("hard_skills") or []) + (regex.get("hard_skills") or [])
                )
            ),
            "soft_skills": ai.get("soft_skills") or [],
            "industry": ai.get("industry") or [],
            "job_type": ai.get("job_type"),
            "_regex_fallback": {
                "skills_count": len(regex.get("hard_skills", [])),
                "guessed_position": regex.get("guessed_position"),
                "guessed_company": regex.get("guessed_company"),
                "location": regex.get("location"),
            },
        }

    # ──────────── 对外接口 ────────────

    @staticmethod
    def get_jd_match_keywords(data: dict) -> dict:
        """
        提取 JD 匹配关键词，供 04 简历生成模块、05 面试模块读取
        """
        return {
            "hard_skills": data.get("hard_skills") or [],
            "soft_skills": data.get("soft_skills") or [],
            "industry": data.get("industry") or [],
            "years": data.get("years_required"),
            "education": data.get("education_required"),
            "position": data.get("position"),
            "company": data.get("company"),
        }

    @staticmethod
    def _load_prompt() -> str:
        """加载本模块专属提示词"""
        prompt_path = Path(__file__).parent / "prompt.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""


# ═══════════════════════════════════════════════════════════════
# 独立运行入口：python -m 01_jd_parser.main 或 python main.py
# ═══════════════════════════════════════════════════════════════

async def main():
    """模块独立调试入口"""
    import argparse

    parser = argparse.ArgumentParser(description="01_jd_parser — JD 岗位解析")
    parser.add_argument("--input", "-i", required=True, help="JD 文件路径或纯文本")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"], help="语言")
    parser.add_argument("--no-ai", action="store_true", help="跳过 AI 抽取，仅用正则")
    parser.add_argument("--regex-only", action="store_true", help="仅输出正则预提取结果")
    args = parser.parse_args()

    LanguageSwitch.set_lang(args.lang)

    if args.regex_only:
        raw_text = ""
        file_path = Path(args.input) if Path(args.input).exists() else None
        if file_path:
            result = OcrPdfProcessor.process_file(file_path, lang=args.lang)
            if result.success:
                raw_text = result.raw_text
            else:
                print(f"[ERROR] {result.error}")
                return
        else:
            raw_text = args.input
        regex = JDParser._extract_jd_patterns(raw_text)
        print(json.dumps(regex, ensure_ascii=False, indent=2, default=str))
        return

    gateway = None
    if not args.no_ai:
        gateway = MultiModelGateway()
        print(f"[Gateway] 已初始化，默认模型: {gateway.default_model}")

    try:
        result = await JDParser.parse(args.input, gateway=gateway, lang=args.lang)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        print(f"\n[OK] 解析完成 | 技能: {result.get('hard_skills', [])} | 行业: {result.get('industry', [])}")
        v = result.get("_validation", {})
        print(f"[校验] 格式问题: {len(v.get('format', []))}项 | 溯源: {v.get('source', {}).get('severity', '?')}")
    finally:
        if gateway:
            await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
