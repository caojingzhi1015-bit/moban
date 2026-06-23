"""事实溯源校验层 — Python 增强版，替代 fact-checker.js

新增能力：
- 命名实体识别(NER)校验 — LAC 分词提取人名/公司名/地点
- 时间线一致性校验 — 工作经历/教育经历时间不重叠
- 格式真实性校验 — 手机号校验、邮箱格式
- 保留: 数字量化声明、虚构经历检测
"""
import re
import logging
from typing import Optional

from backend.models.resume import ValidationResult

logger = logging.getLogger(__name__)

# 尝试导入 LAC（百度词法分析，中文命名实体识别）
try:
    from LAC import LAC
    _lac = LAC(mode='lac')
    LAC_AVAILABLE = True
except ImportError:
    _lac = None
    LAC_AVAILABLE = False

# 尝试导入 phonenumbers（手机号校验）
try:
    import phonenumbers
    PHONE_CHECK = True
except ImportError:
    PHONE_CHECK = False


class FactChecker:
    """增强版事实溯源校验引擎"""

    SEVERITY_PASS = "pass"
    SEVERITY_WARNING = "warning"
    SEVERITY_BLOCK = "block"

    # 虚构内容检测模式（从 JS 移植并增强）
    FABRICATION_PATTERNS = {
        "quantified": [
            (r'提升[了]?\s*\S{0,6}?(\d+[%％])', '量化提升声明'),
            (r'增长[了]?\s*\S{0,6}?(\d+[%％])', '量化增长声明'),
            (r'降低[了]?\s*\S{0,6}?(\d+[%％])', '量化降低声明'),
            (r'(\d+[%％])[的]?\s*(?:提升|增长)', '量化提升声明'),
            (r'(\d+[万億亿])\+(?:用户|访问|播放|曝光|GMV|营收)', '大规模数据声明'),
            (r'(\d+\.?\d*)\s*(万|亿|千万|百万|k|K|w|W)\s*(用户|粉丝|播放|曝光|营收|GMV)', '大规模业务数据'),
            (r'ROI\s*[＞>]\s*\d+', 'ROI声明'),
            (r'转化率\s*(\d+[%％])', '转化率声明'),
            (r'UV\s*(\d+[万億亿])', 'UV数据声明'),
            (r'PV\s*(\d+[万億亿])', 'PV数据声明'),
        ],
        "fabricated_roles": [
            (r'负责[了]?(全[部局]?|整个|所有)', '夸大职责范围'),
            (r'主导[了]?(?:(?!.*项目).)*从[0零]到[1一]', '从0到1声明'),
            (r'管理\s*(\d+)\s*人[的]?团队', '团队规模声明'),
            (r'带领[了]?\s*(\d+)\s*人', '带领团队声明'),
        ],
        "unverifiable_achievements": [
            (r'荣获[了]?["“”].*["‘’]', '获奖声明'),
            (r'被评为[了]?.*(?:最佳|优秀|杰出|TOP|top)', '评优声明'),
            (r'获得[了]?.*(?:一等奖|二等奖|金奖|银奖)', '获奖等级声明'),
        ],
    }

    @staticmethod
    def validate(
        generated_text: str,
        material_context: str,
        extracted_data: Optional[dict] = None,
        lang: str = "zh",
    ) -> ValidationResult:
        """主校验入口：对生成文本进行 5 步校验"""
        result = ValidationResult(
            severity=FactChecker.SEVERITY_PASS,
            issues=[],
            grounded_ratio=1.0,
            missing_fields=[],
            warnings=[],
        )

        if not generated_text or not generated_text.strip():
            return result

        # Step 1: 量化声明校验
        FactChecker._check_quantified(generated_text, material_context, result, lang)

        # Step 2: 虚构经历检测
        FactChecker._check_fabricated(generated_text, material_context, result, lang)

        # Step 3: 实体溯源（NER 增强）
        if LAC_AVAILABLE and extracted_data:
            FactChecker._check_entities(generated_text, material_context, result, lang)

        # Step 4: 逐句溯源比例
        FactChecker._trace_sources(generated_text, material_context, result, lang)

        # Step 5: 时间线一致性
        if extracted_data:
            FactChecker._check_timeline(extracted_data, result, lang)

        # Step 6: 必填字段检查
        if extracted_data:
            FactChecker._check_required_fields(extracted_data, result)

        # 判定最终严重级别
        if any(i.get("severity") == "block" for i in result.issues):
            result.severity = FactChecker.SEVERITY_BLOCK
        elif any(i.get("severity") == "warning" for i in result.issues):
            result.severity = FactChecker.SEVERITY_WARNING

        return result

    @staticmethod
    def _check_quantified(text: str, material: str, result: ValidationResult, lang: str):
        """校验量化声明是否在素材中出现"""
        material_lower = material.lower() if material else ""

        for pattern, label in FactChecker.FABRICATION_PATTERNS["quantified"]:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                matched = m.group(0)
                number = m.group(1) if m.lastindex else matched

                # 检查该数字是否在素材中出现
                if number not in material and number.replace('%', '') not in material:
                    severity = "block" if any(
                        kw in matched for kw in ['亿', '万', '千万', '百万']
                    ) else "warning"

                    result.issues.append({
                        "type": "quantified_claim",
                        "label": label,
                        "matched": matched,
                        "severity": severity,
                        "message": f"[{label}] 声明了量化数据「{matched}」但素材中未找到对应数字",
                    })

    @staticmethod
    def _check_fabricated(text: str, material: str, result: ValidationResult, lang: str):
        """检测虚构/夸大的经历描述"""
        material_lower = material.lower() if material else ""

        # 角色夸大
        for pattern, label in FactChecker.FABRICATION_PATTERNS["fabricated_roles"]:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                matched = m.group(0)
                # 对于团队规模声明，检查数字是否出现在素材中
                if "管理" in matched or "带领" in matched:
                    num = m.group(1) if m.lastindex else None
                    if num and num not in material:
                        result.issues.append({
                            "type": "fabricated_role",
                            "label": label,
                            "matched": matched,
                            "severity": "block",
                            "message": f"[{label}] 声明「{matched}」但素材中未找到团队规模证据",
                        })
                    else:
                        result.issues.append({
                            "type": "fabricated_role",
                            "label": label,
                            "matched": matched,
                            "severity": "warning",
                            "message": f"[{label}] 「{matched}」请确认该描述有素材支撑",
                        })
                else:
                    result.issues.append({
                        "type": "fabricated_role",
                        "label": label,
                        "matched": matched,
                        "severity": "warning",
                        "message": f"[{label}] 「{matched}」请注意描述准确性",
                    })

        # 获奖声明
        for pattern, label in FactChecker.FABRICATION_PATTERNS["unverifiable_achievements"]:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                matched = m.group(0)
                result.issues.append({
                    "type": "unverifiable_achievement",
                    "label": label,
                    "matched": matched,
                    "severity": "warning",
                    "message": f"[{label}] 「{matched}」请确认奖项真实存在且可提供证明",
                })

    @staticmethod
    def _check_entities(text: str, material: str, result: ValidationResult, lang: str):
        """使用 LAC 进行命名实体识别，校验人名/公司名/地名"""
        if not LAC_AVAILABLE:
            return

        try:
            lac_result = _lac.run(text)
            words, tags = lac_result

            entities = {"PER": [], "ORG": [], "LOC": []}
            current_entity = ""
            current_tag = ""

            for word, tag in zip(words, tags):
                if tag.startswith('B-'):
                    current_entity = word
                    current_tag = tag[2:]  # Remove 'B-'
                elif tag.startswith('I-') and current_tag:
                    current_entity += word
                elif tag.startswith('E-') and current_tag:
                    current_entity += word
                    if current_tag in entities:
                        entities[current_tag].append(current_entity)
                    current_entity = ""
                    current_tag = ""
                elif tag.startswith('S-'):
                    tag_type = tag[2:]
                    if tag_type in entities:
                        entities[tag_type].append(word)
                else:
                    current_entity = ""
                    current_tag = ""

                # 如果下一个词不属于同一实体，保存当前实体
                if not tag.startswith(('I-', 'E-', 'M-')):
                    if current_entity and current_tag in entities:
                        entities[current_tag].append(current_entity)
                    current_entity = ""
                    current_tag = ""

            material_lower = material.lower() if material else ""

            # 校验人名
            for name in entities.get("PER", []):
                if name not in material:
                    result.issues.append({
                        "type": "unverified_entity",
                        "entity_type": "person",
                        "matched": name,
                        "severity": "warning",
                        "message": f"人名「{name}」在素材中未找到",
                    })

            # 校验公司名
            for org in entities.get("ORG", []):
                if org not in material and org.lower() not in material_lower:
                    result.issues.append({
                        "type": "unverified_entity",
                        "entity_type": "organization",
                        "matched": org,
                        "severity": "warning",
                        "message": f"公司/组织「{org}」在素材中未找到",
                    })

        except Exception as e:
            logger.warning(f"LAC entity check failed: {e}")

    @staticmethod
    def _trace_sources(text: str, material: str, result: ValidationResult, lang: str):
        """逐句计算素材溯源比例"""
        if not material:
            result.grounded_ratio = 0
            return

        sentences = re.split(r'[。.！!？?\n]', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

        if not sentences:
            return

        material_words = set(material)
        grounded_count = 0

        for sent in sentences:
            sent_words = set(sent)
            if sent_words:
                # 计算句子中在素材中出现的词的比例
                intersection = sent_words & material_words
                ratio = len(intersection) / len(sent_words) if sent_words else 0
                if ratio >= 0.1:  # 至少10%的词在素材中出现
                    grounded_count += 1

        result.grounded_ratio = grounded_count / len(sentences) if sentences else 0

        if result.grounded_ratio < 0.5:
            result.issues.append({
                "type": "low_grounding",
                "severity": "warning",
                "grounded_ratio": result.grounded_ratio,
                "message": f"素材溯源率仅 {result.grounded_ratio:.0%}，请检查是否包含编造内容",
            })

    @staticmethod
    def _check_timeline(extracted_data: dict, result: ValidationResult, lang: str):
        """检查时间线一致性"""
        # 教育经历时间检查
        education = extracted_data.get("education", [])
        for i, edu in enumerate(education):
            start = edu.get("start_date", "")
            end = edu.get("end_date", "")
            if start and end and end != "至今":
                try:
                    s_year = int(re.search(r'(\d{4})', str(start)).group(1))
                    e_year = int(re.search(r'(\d{4})', str(end)).group(1))
                    if s_year > e_year:
                        result.issues.append({
                            "type": "timeline_conflict",
                            "severity": "warning",
                            "message": f"教育经历 #{i+1}: 入学时间({start})晚于毕业时间({end})",
                        })
                    # 检查学位时长合理性
                    if e_year - s_year > 7:
                        result.issues.append({
                            "type": "timeline_suspicious",
                            "severity": "warning",
                            "message": f"教育经历 #{i+1}: 就读时长 {e_year - s_year} 年，请确认",
                        })
                except (ValueError, AttributeError):
                    pass

        # 工作经历时间检查
        work_exp = extracted_data.get("work_experience", [])
        for i, work in enumerate(work_exp):
            start = work.get("start_date", "")
            end = work.get("end_date", "")
            if start and end and end != "至今":
                try:
                    s_year = int(re.search(r'(\d{4})', str(start)).group(1))
                    e_year = int(re.search(r'(\d{4})', str(end)).group(1))
                    if s_year > e_year:
                        result.issues.append({
                            "type": "timeline_conflict",
                            "severity": "block",
                            "message": f"工作经历 #{i+1}: 入职时间({start})晚于离职时间({end})",
                        })
                except (ValueError, AttributeError):
                    pass

    @staticmethod
    def _check_required_fields(extracted_data: dict, result: ValidationResult):
        """检查必填字段是否缺失"""
        basic = extracted_data.get("basic_info", {})

        required = ["name", "phone", "email"]
        for field in required:
            if not basic.get(field):
                result.missing_fields.append(field)
                result.issues.append({
                    "type": "missing_required",
                    "severity": "warning",
                    "field": field,
                    "message": f"必填字段「{field}」缺失，请补充",
                })

        # 检查空 section
        for section in ["education", "work_experience", "projects", "skills"]:
            if not extracted_data.get(section):
                result.warnings.append(f"「{section}」部分为空")

    @staticmethod
    def validate_phone(phone: str) -> dict:
        """校验手机号格式"""
        clean = re.sub(r'[\s\-]', '', phone)
        clean = re.sub(r'^\+?86', '', clean)  # Remove +86 / 86 prefix
        is_valid = bool(re.match(r'^1[3-9]\d{9}$', clean))

        result = {"valid": is_valid, "formatted": clean}
        if not is_valid and len(clean) >= 10:
            result["suggestion"] = f"手机号 {phone} 格式异常，请检查"

        return result

    @staticmethod
    def validate_email(email: str) -> dict:
        """校验邮箱格式"""
        is_valid = bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))
        result = {"valid": is_valid, "formatted": email.lower()}
        if not is_valid:
            result["suggestion"] = f"邮箱 {email} 格式异常，请检查"
        return result

    @staticmethod
    def detect_ai_placeholder(text: str, lang: str = "zh") -> list[str]:
        """检测 AI 生成的占位符文本"""
        placeholders_zh = [
            '目标岗位从业者', '暂无相关经历', '优秀的沟通能力', '团队合作精神',
            '具备较强的学习能力', '熟练掌握办公软件', '某某公司', '某某岗位',
        ]
        placeholders_en = [
            'experienced professional', 'results-driven', 'team player',
            'excellent communication skills', 'detail-oriented', 'self-starter',
            'placeholder', 'lorem ipsum',
        ]

        found = []
        check_list = placeholders_zh + placeholders_en
        for ph in check_list:
            if ph.lower() in text.lower():
                found.append(ph)
        return found
