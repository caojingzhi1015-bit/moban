"""
02_resume_parser/main.py — 个人简历解析模块（可独立运行）

输入: 图片简历/PDF扫描件/Word文档/手动文本
输出: 标准化简历 JSON（基本信息/教育/工作/项目/技能/证书/语言），每条绑定 source_index

执行流水线:
  1. 调 ocr_pdf_processor 解析文件 → 分章节带索引原文素材库
  2. 正则预提取姓名/电话/邮箱/院校/时间等硬字段
  3. 调 multi_model_gateway AI 按 Schema 提取结构化信息（temperature=0）
  4. 合并（硬字段兜底 AI 遗漏）
  5. 调 fact_check_validator 双层校验
"""

import sys
import json
import re
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.ocr_pdf_processor import OcrPdfProcessor
from common.fact_check_validator import FactCheckValidator
from common.multi_model_gateway import MultiModelGateway, safe_parse_json
from common.language_switch import LanguageSwitch


class ResumeParser:
    """个人简历解析器 —— 文件→章节拆分→硬字段预提取→AI抽取→校验→结构化JSON"""

    @classmethod
    async def parse(
        cls,
        input_data: str | Path,
        gateway: MultiModelGateway | None = None,
        lang: str = "zh",
    ) -> dict:
        """
        主入口：解析简历

        Args:
            input_data: 文件路径（图片/PDF/DOCX/文本），或纯文本字符串
            gateway: 多模型网关实例
            lang: 语言代码

        Returns:
            标准化简历 JSON
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
                raise RuntimeError(f"简历文件解析失败: {result.error}")
            raw_text = result.raw_text
            sectioned_text = result.sectioned_text or ""
        else:
            raw_text = str(input_data)
            # Build sectioned text manually for pasted text
            sections = OcrPdfProcessor._classify_sections(raw_text, lang) if hasattr(OcrPdfProcessor, "_classify_sections") else {}
            if sections:
                from common.ocr_pdf_processor import _format_sectioned_text
                sectioned_text = _format_sectioned_text(sections, raw_text, lang)

        # Step 1: 正则预提取硬字段（姓名/电话/邮箱/院校/时间）
        hard_fields = cls.extract_hard_fields(raw_text)

        # Step 2: AI 结构化抽取（使用分章节素材，temperature=0）
        ai_result = None
        if gateway:
            # Prefer sectioned text for LLM; fall back to indexed raw text
            ai_input = sectioned_text if sectioned_text else raw_text
            ai_result = await cls._call_ai_extraction(ai_input, lang, gateway)

        # Step 3: 合并（硬字段覆盖 AI 遗漏）
        merged = cls._merge_results(ai_result or {}, hard_fields)

        # Step 4: 双层校验
        validation = FactCheckValidator.validate_all(merged, raw_text)

        return {
            "success": True,
            **merged,
            "_validation": validation,
            "_raw_text": raw_text,
        }

    # ──────────── 正则预提取硬字段（增强版）────────────

    @staticmethod
    def extract_hard_fields(text: str) -> dict:
        """
        正则提取姓名/电话/邮箱/城市/院校/专业/公司/时间 —— AI 遗漏时的兜底方案。
        这些是强格式字段，正则比 AI 更可靠、更稳定。
        """
        result: dict = {
            "name": None, "phone": None, "email": None, "city": None,
            "schools": [], "majors": [], "companies": [],
            "degrees": [], "dates": [],
        }

        # ── 姓名 ──
        # Pattern 1: "姓名: xxx" / "姓名：xxx"
        m = re.search(r"姓\s*名[：:\s]*([^\n,，。.\d\s]{2,6})", text)
        if m:
            result["name"] = m.group(1).strip()
        else:
            # Pattern 2: First line is Chinese name, followed by phone
            m = re.search(
                r"^([一-鿿·]{2,4})\s*\n\s*(?:电话|手机|Tel|Phone|1[3-9]\d)",
                text, re.MULTILINE,
            )
            if m:
                result["name"] = m.group(1).strip()

        # ── 手机号 ──
        phone_m = re.search(r"(1[3-9]\d{9})", text)
        if phone_m:
            result["phone"] = phone_m.group(1)

        # ── 邮箱 ──
        email_m = re.search(
            r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text
        )
        if email_m:
            result["email"] = email_m.group(1)

        # ── 城市 ──
        city_m = re.search(
            r"(北京|上海|广州|深圳|杭州|成都|武汉|南京|西安|重庆"
            r"|苏州|天津|长沙|郑州|东莞|青岛|厦门|合肥|大连|沈阳"
            r"|福州|济南|宁波|昆明|无锡|佛山|珠海|中山|惠州)",
            text,
        )
        if city_m:
            result["city"] = city_m.group(1)

        # ── 院校名称 ──
        # Match common Chinese university patterns
        school_pattern = re.compile(
            r"((?:[一-鿿]{2,8})(?:大学|学院|College|University|Institute|School))",
            re.IGNORECASE,
        )
        seen_schools = set()
        for m in school_pattern.finditer(text):
            s = m.group(1).strip()
            if s not in seen_schools and len(s) >= 4:
                seen_schools.add(s)
                result["schools"].append(s)

        # ── 专业名称 ──
        major_patterns = [
            r"(?:专业|Major)[：:\s]*([^\n,，。.]{2,20})",
            r"(?:计算机|软件|数据|人工智能|电子|通信|机械|土木|金融|会计|市场|设计|法学|医学|英语|中文)(?:科学|工程|技术|学|管理)?",
        ]
        for pat in major_patterns:
            for m in re.finditer(pat, text):
                val = (m.group(1) if m.lastindex else m.group(0)).strip()
                if val not in result["majors"]:
                    result["majors"].append(val)

        # ── 学历 ──
        degree_m = re.search(
            r"(博士|硕士|本科|大专|MBA|EMBA|Bachelor|Master|Doctor|PhD|MD)",
            text, re.IGNORECASE,
        )
        if degree_m:
            result["degrees"].append(degree_m.group(1))

        # ── 公司名称 ──
        company_patterns = [
            r"((?:[一-鿿]{2,15})(?:有限公司|股份公司|集团|科技|网络|信息|互联|数据|软件|通信|技术))",
            r"((?:[一-鿿A-Za-z]{2,20})(?:Inc|Ltd|Corp|LLC|Co\.?)(?:\.|$|\s))",
        ]
        seen_companies = set()
        for pat in company_patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                c = m.group(1).strip()
                if c not in seen_companies:
                    seen_companies.add(c)
                    result["companies"].append(c)

        # ── 时间范围 ──
        date_pattern = re.compile(
            r"((?:19|20)\d{2}[.年/-]\d{1,2}(?:[.月/-]\d{1,2}[日号]?)?"
            r"\s*[-–—至到~]\s*"
            r"(?:至今|现在|present|(?:19|20)\d{2}[.年/-]\d{1,2}))",
            re.IGNORECASE,
        )
        for m in date_pattern.finditer(text):
            result["dates"].append(m.group(1))

        # ── 技能关键词 ──
        skill_keywords = re.findall(
            r"(Python|Java|Go(lang)?|Rust|C\+\+|JavaScript|TypeScript|React|Vue|Angular"
            r"|Node\.?js|Docker|Kubernetes|SQL|MySQL|PostgreSQL|MongoDB|Redis"
            r"|AWS|Azure|GCP|Linux|Git|TensorFlow|PyTorch|Spark|Hadoop"
            r"|Figma|Photoshop|Excel|PPT|PowerPoint|Tableau)",
            text, re.IGNORECASE,
        )
        result["skills_detected"] = list(set(
            s[0] if isinstance(s, tuple) else s for s in skill_keywords
        ))[:20]

        # Clean empty lists
        for k in ("schools", "majors", "companies", "degrees", "dates",
                   "skills_detected"):
            if not result[k]:
                result[k] = []

        return result

    # ──────────── AI 抽取 ────────────

    @classmethod
    async def _call_ai_extraction(
        cls, text: str, lang: str, gateway: MultiModelGateway
    ) -> dict | None:
        """调用 AI 网关执行结构化抽取，使用分章节素材 + temperature=0"""
        prompt_text = cls._load_prompt()

        # If text is already section-formatted, use it directly;
        # otherwise build indexed text
        if "【" in text and "】" in text and "─" in text:
            # Already sectioned — use as-is
            indexed_input = text
        else:
            indexed_input = OcrPdfProcessor.text_to_indexed_lines(text)

        # Load Schema
        schema = cls._load_schema()

        full_prompt = f"""{prompt_text}

# 输入素材 (【章节名】+ 带行索引原文)
{indexed_input}

# 输出要求
- 严格按以下 JSON Schema 输出，temperature=0，只摘抄原文，禁止编造
- 每个字段若原文不存在，填 null 或空数组 []
- 所有文字内容必须与原文一字不差
- 每条记录必须绑定 source_index 行号数组

# 输出 Schema (纯 JSON，严格按此结构)
{json.dumps(schema, ensure_ascii=False, indent=2)}"""

        result = await gateway.chat_completion(
            messages=[{"role": "user", "content": full_prompt}],
            task_type="resume_parse",
            options={"max_tokens": 4096, "temperature": 0.0, "lang": lang},
        )

        if not result.success or not result.content:
            print(f"[ResumeParser] AI 抽取失败: {result.error}")
            return None

        return safe_parse_json(result.content) or {}

    # ──────────── 合并 ────────────

    @staticmethod
    def _merge_results(ai: dict, hard: dict) -> dict:
        """合并 AI 结果和硬字段 —— 硬字段兜底 AI 遗漏"""
        base = ai.get("base_info") or {}
        sc = ai.get("skill_certificate") or {}

        return {
            "basic_info": {
                "name": base.get("name") or hard.get("name"),
                "phone": base.get("phone") or hard.get("phone"),
                "email": base.get("email") or hard.get("email"),
                "city": base.get("target_city") or hard.get("city"),
                "target_job": base.get("target_position"),
                "expect_salary": base.get("expected_salary"),
                "onboard_time": base.get("available_onboard_time"),
            },
            "education": [
                {
                    "school": e.get("school_name"),
                    "major": e.get("major"),
                    "degree": e.get("degree"),
                    "start_date": e.get("start_date"),
                    "end_date": e.get("end_date"),
                    "awards": e.get("scholarship_awards") or [],
                    "source_index": e.get("source_index"),
                }
                for e in (ai.get("education_list") or [])
            ],
            "work_experience": [
                {
                    "company": w.get("company"),
                    "position": w.get("position"),
                    "start_date": w.get("start_date"),
                    "end_date": w.get("end_date"),
                    "duties": w.get("job_duty"),
                    "achievements": [],
                    "source_index": w.get("source_index"),
                }
                for w in (ai.get("work_experience_list") or [])
            ],
            "projects": [
                {
                    "name": p.get("project_name"),
                    "description": p.get("responsibility"),
                    "results": p.get("project_data"),
                    "source_index": p.get("source_index"),
                }
                for p in (ai.get("project_list") or [])
            ],
            "skills": [
                {"name": s, "category": "工具"}
                for s in (sc.get("software_skill") or [])
            ] + [
                {"name": s, "category": "AI工具"}
                for s in (sc.get("ai_tool_mastered") or [])
            ],
            "certificates": [
                {"name": c} for c in (sc.get("other_cert") or [])
            ],
            "languages": [
                {"name": l} for l in (sc.get("language_cert") or [])
            ],
            "_hard_fields": {
                "name": hard.get("name"),
                "phone": hard.get("phone"),
                "email": hard.get("email"),
                "city": hard.get("city"),
                "schools": hard.get("schools", []),
                "companies": hard.get("companies", []),
                "skills_detected": hard.get("skills_detected", []),
            },
        }

    # ──────────── 对外接口 ────────────

    @staticmethod
    def to_material_json(parsed: dict) -> dict:
        """
        导出为标准化素材库 JSON，供 03 追问 / 04 简历生成 / 05 面试 消费
        """
        bi = parsed.get("basic_info") or {}
        return {
            "identity": {
                "name": bi.get("name"),
                "phone": bi.get("phone"),
                "email": bi.get("email"),
                "city": bi.get("city"),
                "target_job": bi.get("target_job"),
                "salary": bi.get("expect_salary"),
            },
            "education": parsed.get("education") or [],
            "work_experience": parsed.get("work_experience") or [],
            "projects": parsed.get("projects") or [],
            "skills": parsed.get("skills") or [],
            "certificates": parsed.get("certificates") or [],
            "languages": parsed.get("languages") or [],
        }

    @staticmethod
    def _load_prompt() -> str:
        p = Path(__file__).parent / "prompt.txt"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    @staticmethod
    def _load_schema() -> dict:
        p = Path(__file__).parent / "schema.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {}


# ═══════════════════════════════════════════════════════════════
# 独立运行入口
# ═══════════════════════════════════════════════════════════════

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="02_resume_parser — 简历解析")
    parser.add_argument("--input", "-i", required=True, help="简历文件路径或文本")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"])
    parser.add_argument("--no-ai", action="store_true", help="跳过 AI，仅用正则")
    parser.add_argument("--material", action="store_true", help="输出素材库格式")
    parser.add_argument("--hard-only", action="store_true", help="仅输出正则预提取结果")
    args = parser.parse_args()

    LanguageSwitch.set_lang(args.lang)

    if args.hard_only:
        # 仅测试正则预提取
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
        hard = ResumeParser.extract_hard_fields(raw_text)
        print(json.dumps(hard, ensure_ascii=False, indent=2, default=str))
        return

    gateway = None
    if not args.no_ai:
        gateway = MultiModelGateway()

    try:
        result = await ResumeParser.parse(args.input, gateway=gateway, lang=args.lang)
        if args.material:
            result = ResumeParser.to_material_json(result)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        bi = result.get("basic_info", {})
        print(f"\n[OK] {bi.get('name', '?')} | 工作: {len(result.get('work_experience', []))}段 | 项目: {len(result.get('projects', []))}个")
    finally:
        if gateway:
            await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
