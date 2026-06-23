"""结构化提取层 — 三级降级链 (SmartResume → DeepSeek LLM → 增强 Regex)

优先级 P0，替代 PyResParser + extraction-pipeline.js，是核心模块。

Level 1: SmartResume (阿里开源, 93.1% 准确率) — 需要 GPU/vLLM
Level 2: DeepSeek LLM API (85% 准确率) — 需要 API key
Level 3: 增强 Regex 提取 (70%+ 准确率) — 纯本地，无需任何外部依赖
"""
import json
import re
import logging
from typing import Optional

from backend.config import (
    SMARTRESUME_ENABLED, SMARTRESUME_VLLM_URL, SMARTRESUME_MODEL, SMARTRESUME_TIMEOUT,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL_LITE,
)
from backend.models.resume import (
    BasicInfo, EducationEntry, WorkExperienceEntry, ProjectEntry,
    SkillEntry, CertificateEntry, LanguageEntry, ValidationResult,
)
from backend.utils.text_normalizer import (
    normalize_text, extract_section, extract_date_range, extract_city, find_tech_stack,
)
from backend.utils.json_safe import parse_json_safely

logger = logging.getLogger(__name__)


class SmartExtractor:
    """三级降级简历信息提取器"""

    # === LLM Extraction Prompt (Level 2) ===
    EXTRACTION_SYSTEM_PROMPT = """# 全局不可违反铁律（优先级最高）
1. 数据源唯一约束：你仅能使用【带行索引的简历原始素材文本】内存在的文字，绝对禁止猜测、脑补、编造、概括、润色扩充任何不存在的信息；素材无对应内容时，对应字段统一返回null，严禁填充模糊笼统文字（如"目标岗位从业者""掌握相关技能"这类无意义占位描述）。
2. 溯源强制要求：每一条提取结果必须绑定原文行索引source_index数组，记录该信息在原始素材中的行数，无溯源则该字段置空。
3. 格式约束：只输出纯净JSON，不输出Markdown、注释、标题、自然语言解释、分段换行说明，禁止添加任何正文以外内容。
4. 字段约束：严格使用给定Schema内的键名，不新增、不删减、不修改字段名称；时间、电话、邮箱、公司名称、学校名称必须和原文一字不差，识别模糊残缺直接填null，不补全、不猜数字。
5. 内容分割规则：严格按照原文章节拆分多段教育、多份工作、多个项目，不合并、不遗漏素材内所有独立经历。

# 你的角色
仅做客观简历字段提取机器，不做文案优化、不做求职分析、不总结个人情况，只精准提取原始文本内客观存在的结构化信息。"""

    @staticmethod
    async def extract(
        text: str,
        method: str = "auto",
        lang: str = "zh",
        file_name: str = "",
    ) -> dict:
        """主入口：三级降级提取"""
        clean_text = normalize_text(text)

        if method == "regex":
            return SmartExtractor._level3_regex(clean_text, lang)

        if method == "llm":
            return await SmartExtractor._level2_llm(clean_text, lang)

        if method == "smartresume":
            return await SmartExtractor._level1_smartresume(clean_text, lang)

        # Auto: try all levels
        return await SmartExtractor._auto_extract(clean_text, lang)

    @staticmethod
    async def _auto_extract(text: str, lang: str) -> dict:
        """自动模式：按优先级尝试各级别"""
        # Level 1: SmartResume (if GPU available)
        if SMARTRESUME_ENABLED:
            try:
                result = await SmartExtractor._level1_smartresume(text, lang)
                if result.get("basic_info", {}).get("name") or result.get("education") or result.get("work_experience"):
                    result["method"] = "smartresume"
                    result["confidence"] = 0.93
                    return result
                logger.info("SmartResume returned sparse results, falling back to LLM")
            except Exception as e:
                logger.warning(f"SmartResume failed: {e}, falling back to LLM")

        # Level 2: DeepSeek LLM
        if DEEPSEEK_API_KEY:
            try:
                result = await SmartExtractor._level2_llm(text, lang)
                if result.get("basic_info", {}).get("name") or result.get("education") or result.get("work_experience"):
                    result["method"] = "llm"
                    result["confidence"] = 0.85
                    return result
                logger.info("LLM returned sparse results, falling back to regex")
            except Exception as e:
                logger.warning(f"LLM extraction failed: {e}, falling back to regex")

        # Level 3: Enhanced Regex (always available)
        result = SmartExtractor._level3_regex(text, lang)
        result["method"] = "regex"
        result["confidence"] = 0.75
        return result

    # ================================================================
    # Level 1: SmartResume (vLLM)
    # ================================================================
    @staticmethod
    async def _level1_smartresume(text: str, lang: str) -> dict:
        """通过 SmartResume vLLM 服务提取"""
        import httpx

        extraction_prompt = SmartExtractor._build_extraction_prompt(text, lang)

        async with httpx.AsyncClient(timeout=SMARTRESUME_TIMEOUT) as client:
            response = await client.post(
                f"{SMARTRESUME_VLLM_URL}/chat/completions",
                json={
                    "model": SMARTRESUME_MODEL,
                    "messages": [
                        {"role": "system", "content": SmartExtractor.EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": extraction_prompt},
                    ],
                    "temperature": 0.01,
                    "max_tokens": 4096,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return parse_json_safely(content, {})

    # ================================================================
    # Level 2: DeepSeek LLM API
    # ================================================================
    @staticmethod
    async def _level2_llm(text: str, lang: str) -> dict:
        """通过 DeepSeek API 结构化提取"""
        import httpx

        extraction_prompt = SmartExtractor._build_extraction_prompt(text, lang)

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={
                    "model": DEEPSEEK_MODEL_LITE,
                    "messages": [
                        {"role": "system", "content": SmartExtractor.EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": extraction_prompt},
                    ],
                    "temperature": 0.01,
                    "max_tokens": 4096,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return parse_json_safely(content, {})

    # ================================================================
    # Level 3: Enhanced Regex (PyResParser Python 移植 + 大量增强)
    # ================================================================
    @staticmethod
    def _level3_regex(text: str, lang: str) -> dict:
        """纯正则提取，6-pass 流水线"""
        # Pass 1: Basic info
        basic_info = {
            "name": SmartExtractor._extract_name(text),
            "phone": SmartExtractor._extract_phone(text),
            "email": SmartExtractor._extract_email(text),
            "city": extract_city(text),
            "target_job": SmartExtractor._extract_target_job(text),
            "expect_salary": SmartExtractor._extract_salary(text),
            "birth_date": SmartExtractor._extract_birth(text),
            "age": SmartExtractor._extract_age(text),
            "gender": SmartExtractor._extract_gender(text),
            "onboard_time": SmartExtractor._extract_onboard_time(text),
            "source_index": [],
        }

        # Pass 2: Education
        education = SmartExtractor._extract_education(text)

        # Pass 3: Work experience
        work_experience = SmartExtractor._extract_work_experience(text)

        # Pass 4: Projects
        projects = SmartExtractor._extract_projects(text)

        # Pass 5: Skills + Certificates + Languages
        skills = SmartExtractor._extract_skills(text)
        certificates = SmartExtractor._extract_certificates(text)
        languages = SmartExtractor._extract_languages(text)

        # Pass 6: Self-assessment
        self_assessment = SmartExtractor._extract_self_assessment(text)

        return {
            "basic_info": basic_info,
            "education": education,
            "work_experience": work_experience,
            "projects": projects,
            "skills": skills,
            "certificates": certificates,
            "languages": languages,
            "self_assessment": self_assessment,
            "source_index": {},
        }

    @staticmethod
    def _build_extraction_prompt(text: str, lang: str) -> str:
        """用行索引格式化输入文本"""
        lines = text.strip().split('\n')
        indexed_lines = [f"[{i}] {line}" for i, line in enumerate(lines)]
        indexed_text = '\n'.join(indexed_lines)

        return f"""{SmartExtractor.EXTRACTION_SYSTEM_PROMPT}

# 输入原始素材（带行号索引）
{indexed_text}

# 强制输出固定JSON Schema
{{
  "base_info": {{
    "name": "string|null",
    "phone": "string|null",
    "email": "string|null",
    "target_city": "string|null",
    "target_position": "string|null",
    "expected_salary": "string|null",
    "available_onboard_time": "string|null",
    "source_index": "number[]"
  }},
  "education_list": [
    {{
      "school_name": "string|null",
      "major": "string|null",
      "degree": "string|null",
      "start_date": "string|null",
      "end_date": "string|null",
      "scholarship_awards": "string[]|null",
      "source_index": "number[]"
    }}
  ],
  "work_experience_list": [
    {{
      "company": "string|null",
      "position": "string|null",
      "start_date": "string|null",
      "end_date": "string|null",
      "job_duty": "string|null",
      "source_index": "number[]"
    }}
  ],
  "project_list": [
    {{
      "project_name": "string|null",
      "project_time": "string|null",
      "responsibility": "string|null",
      "project_data": "string|null",
      "source_index": "number[]"
    }}
  ],
  "skill_certificate": {{
    "language_cert": "string[]|null",
    "software_skill": "string[]|null",
    "ai_tool_mastered": "string[]|null",
    "other_cert": "string[]|null",
    "source_index": "number[]"
  }}
}}

# 细分抽取执行细则
1. 基础信息：仅提取原文明确写明的姓名、手机号、邮箱、意向城市、目标岗位、期望薪资、到岗时间；原文无则全部null，不自行推断求职意向。
2. 教育经历：逐条拆分每一段就读院校，完整提取学校、专业、学历、起止就读时间、在校奖项；原文无奖项则数组为空，不编造奖学金、竞赛经历。
3. 工作实习经历：区分每一家任职公司，提取公司全称、岗位、入职离职时间、原文完整工作职责；不缩写、不扩充工作内容。
4. 项目经历：拆分每一个独立项目，提取项目名称、项目周期、个人负责内容、原文自带量化数据；无数据则project_data为null，禁止虚构曝光、营收、转化数字。
5. 技能证书：拆分语言证书、设计办公软件、熟练使用的AI工具、其他资格证书，逐条罗列原文存在的全部技能，不新增未提及工具/证书。
6. 杜绝无效概括：禁止生成"掌握专业技能""从事相关行业"这类无原文支撑的笼统描述，没有素材则字段直接为空。

# 输出要求
仅返回标准纯净JSON字符串，无任何额外文字。"""

    # ================================================================
    # 各字段提取方法 (从 PyResParser JS 移植并增强)
    # ================================================================

    @staticmethod
    def _extract_name(text: str) -> Optional[str]:
        patterns = [
            r'姓\s*名[：:\s]*([^\n,，。.\d\s]{2,6})',
            r'名字[：:\s]*([^\n,，。.\d\s]{2,6})',
            r'^([^\n,，。.\d\s]{2,4})\s*\n\s*(?:电话|手机|1[3-9])',
            r'^([^\n,，。.\d\s]{2,4})\s*\n\s*(?:邮箱|[a-zA-Z0-9._%+-]+@)',
            r'【姓名】[：:\s]*([^\n]{2,6})',
            r'姓名[：:\s]*([^\n,，。.\d\s]{2,6})',
            # 增强：中文姓名在文本开头
            r'^([一-鿿]{2,4})\s*(?:\n|$)',
        ]
        for p in patterns:
            m = re.search(p, text, re.MULTILINE)
            if m:
                name = m.group(1).strip()
                if 2 <= len(name) <= 6 and not re.search(r'\d', name):
                    return name
        return None

    @staticmethod
    def _extract_phone(text: str) -> Optional[str]:
        patterns = [
            r'(?:电话|手机|Tel|Phone|联系方式|联系电话|手机号码|MOBILE|Mobile)[：:\s]*(\+?86[\s-]?)?([\d\-+\s]{7,20})',
            r'(1[3-9]\d)[\s\-]?(\d{4})[\s\-]?(\d{4})',
            r'(\+86[\s-]?1[3-9]\d[\s-]?\d{4}[\s-]?\d{4})',
            r'(?<!\d)(1[3-9]\d{9})(?!\d)',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                # 处理不同 group 组合
                if m.lastindex and m.lastindex >= 2 and m.group(2):
                    phone = (m.group(1) or '') + m.group(2)
                else:
                    phone = m.group(1) or m.group(0)
                phone = re.sub(r'[\s\-]', '', phone)
                if re.match(r'^(\+?86)?1[3-9]\d{9}$', phone):
                    return phone
        return None

    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        patterns = [
            r'(?:邮箱|邮件|Email|E-mail|电子邮箱|EMAIL)[：:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip().lower()
        return None

    @staticmethod
    def _extract_target_job(text: str) -> Optional[str]:
        patterns = [
            r'(?:岗位|职位|应聘|求职意向|意向岗位|意向职位|期望职位|目标岗位|Target|Objective)[：:\s]*([^\n,，]{2,30})',
            r'(?:求职意向|应聘岗位|期望岗位)[：:\s]*([^\n]{2,30})',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        # 尝试匹配常见职位名
        job_patterns = [
            r'(前端|后端|全栈|产品|设计|运营|市场|销售|算法|数据|测试|开发|工程师|经理|总监|专员|主管|架构师|分析师)'
        ]
        for jp in job_patterns:
            m = re.search(jp, text)
            if m:
                # 尝试获取更完整的职位名（前后文本）
                start = max(0, m.start() - 10)
                end = min(len(text), m.end() + 10)
                context = text[start:end]
                return context.strip()
        return None

    @staticmethod
    def _extract_salary(text: str) -> Optional[str]:
        patterns = [
            r'(?:薪资|期望薪资|薪酬|期望月薪|期望年薪|Salary|期望)[：:\s]*([^\n,，。]{2,20})',
            r'(\d+[kK]\s*[-–—~至到]\s*\d+[kK])',
            r'(\d+[,，]?\d*\s*[-–—~至到]\s*\d+[,，]?\d*\s*(?:元|块|万|k|K|千|万/月|K/月|元/月))',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    @staticmethod
    def _extract_birth(text: str) -> Optional[str]:
        m = re.search(
            r'(?:出生|生日|出生日期|生日日期)[：:\s]*(\d{4}[年.\-/]\d{1,2}[月.\-/]\d{1,2}[日]?|\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2})',
            text
        )
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_age(text: str) -> Optional[int]:
        m = re.search(r'(?:年龄)[：:\s]*(\d{1,2})\s*(?:岁)?', text)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def _extract_gender(text: str) -> Optional[str]:
        m = re.search(r'(?:性别)[：:\s]*(男|女|Male|Female)', text, re.IGNORECASE)
        if m:
            g = m.group(1)
            return {'Male': '男', 'Female': '女'}.get(g, g)
        return None

    @staticmethod
    def _extract_onboard_time(text: str) -> Optional[str]:
        m = re.search(r'(?:到岗时间|可入职时间|入职时间|到岗)[：:\s]*([^\n,，。]{2,20})', text)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_education(text: str) -> list[dict]:
        section = extract_section(text, [
            '教育经历', '教育背景', '学历背景', '教育', '学历', '学习经历',
            'Education', 'EDUCATION', 'Educational',
        ])
        if not section:
            return []

        entries = []
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        current = None

        for line in lines:
            # 检测新条目
            is_new = (
                re.search(r'(?:大学|学院|University|College|School|高中|中学|一中|二中|三中|附中|实验|师范)', line)
                and (re.search(r'\d{4}', line) or len(line) < 60)
            ) or re.match(r'\d{4}[.\-/年]\d{1,2}\s*[-–—~至到]\s*(?:\d{4}[.\-/年]\d{1,2}|至今|现在|present)', line)

            if is_new or not current:
                if current and current.get('school'):
                    entries.append(current)
                current = {'school': None, 'major': None, 'degree': None, 'start_date': None, 'end_date': None, 'gpa': None, 'awards': [], 'source_index': []}

            if not current:
                current = {'school': None, 'major': None, 'degree': None, 'start_date': None, 'end_date': None, 'gpa': None, 'awards': [], 'source_index': []}

            # 学校名
            if not current['school']:
                sm = re.search(r'([一-鿿A-Za-z\s()（）]+(?:大学|学院|University|College|School|高中|中学|一中|二中|三中|附中))', line)
                if sm:
                    current['school'] = sm.group(1).strip()

            # 专业
            if not current['major']:
                mm = re.search(r'(?:专业|主修|Major)[：:\s]*([^\n,，。]{2,40})', line, re.IGNORECASE)
                if mm:
                    current['major'] = mm.group(1).strip()

            # 学历
            if not current['degree']:
                dm = re.search(r'(?:学历|学位|Degree)[：:\s]*([^\n,，。]{2,15})', line, re.IGNORECASE)
                if dm:
                    current['degree'] = dm.group(1).strip()
                else:
                    dp = re.search(r'(本科|硕士|博士|大专|学士|MBA|EMBA|高中|中专|技校)', line)
                    if dp:
                        current['degree'] = dp.group(1).strip()

            # 日期
            dr = extract_date_range(line)
            if dr:
                current['start_date'] = dr['start']
                current['end_date'] = dr['end']

            # GPA
            gm = re.search(r'(?:GPA|绩点|平均分)[：:\s]*([\d.]+(?:/[\d.]+)?)', line)
            if gm:
                current['gpa'] = gm.group(1).strip()

            # 奖项
            am = re.search(r'(?:获奖|奖学金|荣誉|Award|Scholarship)[：:\s]*([^\n]{2,60})', line, re.IGNORECASE)
            if am:
                current['awards'].append(am.group(1).strip())

        if current and current.get('school'):
            entries.append(current)

        return entries

    @staticmethod
    def _extract_work_experience(text: str) -> list[dict]:
        section = extract_section(text, [
            '工作经历', '工作经验', '实习经历', '工作履历', '职业经历', '从业经历',
            'Work Experience', 'WORK EXPERIENCE', 'Employment', 'Professional Experience',
        ])
        if not section:
            return []

        entries = []
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        current = None
        duties = []
        achievements = []

        # 知名公司名列表（不包含标准后缀的公司）
        KNOWN_COMPANIES = [
            '阿里巴巴', '阿里', '腾讯', '百度', '字节跳动', '美团', '滴滴',
            '京东', '拼多多', '网易', '小米', '华为', '蚂蚁', '快手',
            '哔哩哔哩', 'B站', '小红书', '微博', '知乎', '豆瓣',
            '谷歌', 'Google', '微软', 'Microsoft', '亚马逊', 'Amazon',
            '苹果', 'Apple', 'Meta', 'Facebook', '特斯拉', 'Tesla',
            'Shopee', 'Grab', 'Lazada', 'Tokopedia', 'Gojek',
            'Shopify', 'Stripe', 'Airbnb', 'Uber', 'Lyft',
        ]

        for line in lines:
            # 检测新公司条目
            is_company = (
                re.search(r'(?:公司|集团|有限|科技|网络|信息|技术|银行|证券|保险|医院|学校|政府|研究院|所|厂|店|平台)', line)
                or re.match(r'^[一-鿿A-Za-z&·]{2,30}(?:公司|集团|有限|科技|网络|信息|技术)', line)
                or any(c in line for c in KNOWN_COMPANIES)
            )
            has_date = extract_date_range(line)
            date_at_start = bool(re.match(r'\d{4}[.\-/年]\d{1,2}', line))

            if (is_company or date_at_start) and (has_date or len(line) < 80):
                # 跳过明显的列表项/成就行
                if re.match(r'^[\s]*[-•*\d+\.、▸►○●◆■✔✅]\s', line):
                    if current:
                        # 属于当前条目的成就
                        content = re.sub(r'^[\s]*[-•*\d+\.、▸►○●◆■✔✅]\s*', '', line).strip()
                        if content:
                            current['achievements'].append(content)
                    continue
                # 保存前一条目
                if current:
                    current['duties'] = '\n'.join(duties) if duties else None
                    current['achievements'] = achievements
                    entries.append(current)
                current = {
                    'company': None, 'position': None, 'start_date': None, 'end_date': None,
                    'department': None, 'duties': None, 'achievements': [], 'source_index': [],
                }
                duties = []
                achievements = []

                # 公司名
                cm = re.search(r'([一-鿿A-Za-z&·()（）\s]{2,40}(?:公司|集团|有限|科技|网络|信息|技术|银行|证券|保险|医院|学校|政府|研究院|所))', line)
                if not cm:
                    # 尝试匹配知名公司名（无标准后缀）
                    for known in KNOWN_COMPANIES:
                        if known in line:
                            # 在日期之后的公司名
                            rest_after_date = re.sub(r'\d{4}[.\-/年]\d{1,2}.*?[-–—~至到].*?(?:\d{4}[.\-/年]\d{1,2}|至今|现在|present)\s*', '', line)
                            if known in rest_after_date:
                                current['company'] = known
                            else:
                                current['company'] = known
                            break
                else:
                    current['company'] = cm.group(1).strip()

                # 职位（在公司名之后查找）
                if current['company']:
                    after_company = line.split(current['company'], 1)[-1] if current['company'] in line else line
                    pm = re.search(r'([^\n,，\d]{2,20}(?:工程师|经理|专员|设计师|运营|主管|总监|架构师|开发|测试|代表|顾问|助理|实习生|管培生))', after_company)
                else:
                    # 没有公司名时，从日期之后查找
                    after_date = re.sub(r'\d{4}[.\-/年]\d{1,2}.*?[-–—~至到].*?(?:\d{4}[.\-/年]\d{1,2}|至今|现在|present)\s*', '', line)
                    pm = re.search(r'([^\n,，\d]{2,20}(?:工程师|经理|专员|设计师|运营|主管|总监|架构师|开发|测试|代表|顾问|助理|实习生|管培生))', after_date)
                if pm:
                    current['position'] = pm.group(1).strip()

                # 日期
                if has_date:
                    current['start_date'] = has_date['start']
                    current['end_date'] = has_date['end']

                # 剩余文本作为职责
                rest = line
                for pat in [current['company'], current['position']]:
                    if pat:
                        rest = rest.replace(pat, '', 1)
                rest = re.sub(r'\d{4}.*?(?:至今|现在|present)?', '', rest).strip()
                if rest and len(rest) > 5 and not rest.startswith('：'):
                    duties.append(rest)

            elif current:
                # 列表项
                bullet = re.match(r'^[•\-*\d+\.、▸►○●◆■✔✅]\s*(.+)', line)
                if bullet:
                    achievements.append(bullet.group(1).strip())
                elif len(line) > 3:
                    duties.append(line)

        if current:
            current['duties'] = '\n'.join(duties) if duties else None
            current['achievements'] = achievements
            entries.append(current)

        return entries

    @staticmethod
    def _extract_projects(text: str) -> list[dict]:
        section = extract_section(text, [
            '项目经历', '项目经验', '项目', '主要项目', 'Projects', 'PROJECTS', 'Project Experience',
        ])
        if not section:
            return []

        entries = []
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        current = None
        desc_lines = []

        for line in lines:
            # 检测新项目
            has_date = extract_date_range(line)
            is_proj_name = (
                line.startswith('项目') or
                re.match(r'^[一-鿿A-Za-z].{1,40}(?:系统|平台|项目|方案|工具|App|APP|系统|产品|引擎)', line) or
                (re.match(r'^[一-鿿A-Za-z]{2,30}$', line) and len(line) < 30)
            )

            if (is_proj_name or has_date) and len(line) < 100:
                if current and current.get('name'):
                    current['description'] = '\n'.join(desc_lines) if desc_lines else None
                    entries.append(current)
                current = {
                    'name': None, 'role': None, 'start_date': None, 'end_date': None,
                    'description': None, 'technologies': [], 'results': None, 'source_index': [],
                }
                desc_lines = []

                current['name'] = line[:60].strip()
                if has_date:
                    current['start_date'] = has_date['start']
                    current['end_date'] = has_date['end']

            elif current:
                # 角色
                if not current['role']:
                    rm = re.search(r'(?:角色|Role|担任|负责)[：:\s]*([^\n,，]{2,20})', line)
                    if rm:
                        current['role'] = rm.group(1).strip()

                # 技术栈
                techs = find_tech_stack(line)
                if techs:
                    current['technologies'].extend(t for t in techs if t not in current['technologies'])

                # 成果
                res_m = re.search(r'(?:成果|结果|效果|产出|业绩|Result)[：:\s]*([^\n]{5,80})', line, re.IGNORECASE)
                if res_m:
                    current['results'] = res_m.group(1).strip()
                else:
                    desc_lines.append(line)

        if current and current.get('name'):
            current['description'] = '\n'.join(desc_lines) if desc_lines else None
            entries.append(current)

        return entries

    @staticmethod
    def _extract_skills(text: str) -> list[dict]:
        section = extract_section(text, [
            '技能', '专业技能', '技术栈', '技能证书', 'Skills', 'SKILLS', 'Technical Skills',
        ])
        if not section:
            return SmartExtractor._extract_skills_from_full_text(text)

        skills = []
        # 分割技能项
        items = re.split(r'[,，、；;|/·\n]', section)
        for item in items:
            item = item.strip()
            if not item or len(item) < 1 or len(item) > 40:
                continue
            # 过滤非技能文本
            if re.search(r'[：:]', item):
                continue
            skills.append({'name': item, 'category': SmartExtractor._categorize_skill(item), 'level': None, 'source_index': []})

        # 去重
        seen = set()
        unique_skills = []
        for s in skills:
            if s['name'].lower() not in seen:
                seen.add(s['name'].lower())
                unique_skills.append(s)

        return unique_skills

    @staticmethod
    def _extract_skills_from_full_text(text: str) -> list[dict]:
        """当没有独立技能章节时，从全文匹配技术栈"""
        techs = find_tech_stack(text)
        return [{'name': t, 'category': SmartExtractor._categorize_skill(t), 'level': None, 'source_index': []} for t in techs]

    @staticmethod
    def _categorize_skill(name: str) -> str:
        """技能分类"""
        programming = {'Python', 'Java', 'JavaScript', 'TypeScript', 'Go', 'Golang', 'Rust', 'C++', 'C', 'C#', 'Ruby', 'PHP', 'Swift', 'Kotlin', 'Scala', 'R', 'MATLAB', 'Shell', 'Bash', 'SQL'}
        frameworks = {'React', 'Vue', 'Angular', 'Django', 'Flask', 'FastAPI', 'Spring', 'Express', 'Node.js', 'Next.js', 'Nuxt', 'Svelte', 'jQuery', 'Bootstrap', 'Tailwind', 'PyTorch', 'TensorFlow', 'Keras', 'Pandas', 'NumPy'}
        tools = {'Docker', 'Kubernetes', 'Git', 'Jenkins', 'AWS', 'Azure', 'GCP', 'Linux', 'Nginx', 'Redis', 'MongoDB', 'MySQL', 'PostgreSQL', 'Elasticsearch', 'Kafka', 'RabbitMQ', 'CI/CD', 'Terraform', 'Ansible', 'Figma', 'Sketch'}
        languages = {'英语', 'English', '中文', '日语', '韩语', '法语', '德语', 'CET-4', 'CET-6', 'IELTS', 'TOEFL'}

        nl = name.lower()
        if any(p.lower() in nl for p in programming):
            return '编程语言'
        if any(f.lower() in nl for f in frameworks):
            return '框架'
        if any(t.lower() in nl for t in tools):
            return '工具'
        if any(l in name for l in languages):
            return '语言'
        return '其他'

    @staticmethod
    def _extract_certificates(text: str) -> list[dict]:
        section = extract_section(text, [
            '证书', '资格证书', '证书资质', 'Certificates', 'CERTIFICATES', 'Certifications',
        ])
        if not section:
            # 尝试全文匹配
            section = text

        certs = []
        cert_patterns = [
            r'(?:证书|Certification|Certificate)[：:\s]*([^\n,，。]{2,40})',
            r'([^\n,，。]{2,30}(?:证书|资格证|认证|执照))',
        ]
        for pat in cert_patterns:
            for m in re.finditer(pat, section, re.IGNORECASE):
                name = m.group(1).strip()
                if name not in [c['name'] for c in certs]:
                    certs.append({'name': name, 'date': None, 'issuing_authority': None, 'source_index': []})
        return certs

    @staticmethod
    def _extract_languages(text: str) -> list[dict]:
        section = extract_section(text, [
            '语言', '语言能力', '外语', 'Languages', 'LANGUAGES',
        ])
        if not section:
            return []

        langs = []
        lang_patterns = [
            r'(英语|English|中文|日语|韩语|法语|德语|西班牙语|俄语)[：:\s]*([^\n,，。]{0,15})',
            r'(CET-[46]|IELTS\s*\d[\d.]*|TOEFL\s*\d+|N[1-5])',
        ]
        for pat in lang_patterns:
            for m in re.finditer(pat, section, re.IGNORECASE):
                name = m.group(1)
                level = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else None
                langs.append({'name': name, 'level': level, 'source_index': []})
        return langs

    @staticmethod
    def _extract_self_assessment(text: str) -> Optional[str]:
        section = extract_section(text, [
            '自我评价', '自我介绍', '个人评价', '自我描述', '个人简介',
            'Self-Assessment', 'Self Assessment', 'Summary', 'Profile', 'About Me',
        ])
        if not section:
            return None
        # 移除章节标题行
        lines = section.split('\n')
        if len(lines) > 1:
            section = '\n'.join(lines[1:])
        return section.strip()[:2000] or None
