"""信息提取接口 — POST /api/extract/resume + /api/extract/jd"""
import logging
from fastapi import APIRouter, HTTPException

from backend.models.common import ExtractRequest
from backend.models.resume import ResumeExtractResponse
from backend.models.jd import JDExtractResponse, JDRequirement, JDResponsibility
from backend.pipeline.orchestrator import ExtractionOrchestrator
from backend.pipeline.smart_extractor import SmartExtractor
from backend.pipeline.fact_checker import FactChecker
from backend.utils.text_normalizer import normalize_text, find_tech_stack

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/extract", tags=["extract"])

orchestrator = ExtractionOrchestrator()


@router.post("/resume", response_model=ResumeExtractResponse)
async def extract_resume(request: ExtractRequest):
    """从文本中提取简历结构化信息（6 步流水线）"""
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(400, "文本过短，请提供完整的简历内容（至少 10 个字符）")

    try:
        result = await orchestrator.run_full_pipeline(
            text=request.text,
            file_name="用户输入",
            method=request.method,
            lang=request.lang,
            session_id=request.session_id,
        )
        return result

    except Exception as e:
        logger.exception("Resume extraction failed")
        # 降级：直接返回 regex 提取结果
        try:
            extracted = SmartExtractor._level3_regex(normalize_text(request.text), request.lang)
            return ResumeExtractResponse(
                success=True,
                basic_info=extracted.get("basic_info", {}),
                education=extracted.get("education", []),
                work_experience=extracted.get("work_experience", []),
                projects=extracted.get("projects", []),
                skills=extracted.get("skills", []),
                certificates=extracted.get("certificates", []),
                languages=extracted.get("languages", []),
                self_assessment=extracted.get("self_assessment"),
                method="regex",
                confidence=0.5,
                error=str(e),
            )
        except Exception:
            raise HTTPException(500, f"提取失败: {str(e)}")


@router.post("/jd", response_model=JDExtractResponse)
async def extract_jd(request: ExtractRequest):
    """从 JD 文本中提取结构化信息"""
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(400, "文本过短，请提供完整的 JD 内容")

    try:
        return _extract_jd_regex(request.text, request.lang)
    except Exception as e:
        logger.exception("JD extraction failed")
        raise HTTPException(500, f"JD 解析失败: {str(e)}")


def _extract_jd_regex(text: str, lang: str) -> JDExtractResponse:
    """Regex-based JD keyword extraction — 移植自 resume-engine.js parseJD()"""
    clean = normalize_text(text)

    # 硬技能
    hard_patterns = [
        r'Python', r'Java\b', r'JavaScript', r'TypeScript', r'React', r'Vue', r'Angular',
        r'Node\.?js', r'Golang', r'Rust', r'C\+\+', r'SQL', r'MySQL', r'PostgreSQL',
        r'MongoDB', r'Redis', r'Docker', r'Kubernetes', r'K8s', r'AWS', r'Azure', r'GCP',
        r'TensorFlow', r'PyTorch', r'Machine\s*Learning', r'Deep\s*Learning', r'NLP', r'LLM',
        r'Excel', r'Tableau', r'Power\s*BI', r'Spark', r'Hadoop', r'Flink',
        r'Figma', r'Sketch', r'Photoshop', r'Illustrator', r'After\s*Effects', r'Canva',
        r'短视频', r'抖音', r'快手', r'小红书', r'B站', r'Bilibili', r'YouTube', r'TikTok',
        r'微信', r'微博', r'公众号', r'社群', r'私域', r'小程序', r'视频号',
        r'SEO', r'SEM', r'信息流', r'竞价', r'广告投放', r'千川', r'巨量',
        r'直播', r'带货', r'电商', r'天猫', r'京东', r'拼多多', r'Shopify',
        r'数据分析', r'用户研究', r'AB\s*[Tt]est', r'增长', r'用户增长', r'黑客增长',
        r'项目管理', r'敏捷', r'Scrum', r'Jira', r'Confluence', r'Notion',
        r'Linux', r'Git', r'CI/CD', r'Jenkins', r'Terraform', r'Ansible',
        r'Premiere', r'Final\s*Cut', r'达芬奇', r'剪映',
        r'Spring\s*Boot', r'Django', r'Flask', r'FastAPI', r'Express', r'Next\.?js',
    ]

    hard_skills = []
    import re
    for pat in hard_patterns:
        m = re.search(pat, clean, re.IGNORECASE)
        if m and m.group(0) not in hard_skills:
            hard_skills.append(m.group(0))

    # 软技能
    soft_patterns = [
        r'沟通', r'协作', r'团队合作', r'领导力', r'管理', r'执行力',
        r'抗压', r'解决问题', r'逻辑思维', r'创新', r'学习能力',
        r'自驱', r'责任心', r'结果导向', r'用户导向', r'同理心',
        r'跨部门', r'推动', r'影响力', r'演讲', r'汇报', r'谈判',
        r'Ownership', r'Leadership', r'Communication', r'Team\s*[Ww]ork',
    ]
    soft_skills = []
    for pat in soft_patterns:
        m = re.search(pat, clean, re.IGNORECASE)
        if m and m.group(0) not in soft_skills:
            soft_skills.append(m.group(0))

    # 行业
    industry_patterns = [
        (r'互联网', '互联网/IT'),
        (r'金融', '金融'),
        (r'教育', '教育'),
        (r'医疗', '医疗健康'),
        (r'电商', '电商/零售'),
        (r'游戏', '游戏'),
        (r'广告', '媒体/广告'),
        (r'SaaS', 'SaaS/企业服务'),
        (r'AI|人工智能|大模型', 'AI/人工智能'),
        (r'汽车', '汽车/出行'),
        (r'新能源', '新能源'),
        (r'芯片|半导体', '芯片/半导体'),
        (r'制造', '制造业'),
        (r'咨询', '咨询'),
    ]
    industry = []
    for pat, label in industry_patterns:
        if re.search(pat, clean, re.IGNORECASE) and label not in industry:
            industry.append(label)

    # 年限
    years_match = re.search(r'(\d+)[\s-]*年(以上)?(工作经验|经验|工作年限)?', clean)
    years_required = years_match.group(1) + '年' if years_match else None

    # 学历
    edu_match = re.search(r'(本科|硕士|博士|大专|MBA|EMBA)(及以上|以上)?(学历)?', clean)
    education_required = edu_match.group(0) if edu_match else None

    # 薪资
    salary_match = re.search(r'(\d+[kK]-?\d*[kK]|\d+千-\d+千|\d+万-\d+万)', clean)
    salary_range = salary_match.group(0) if salary_match else None

    # 职位
    title_match = re.search(
        r'(前端|后端|全栈|产品|设计|运营|市场|销售|算法|数据|测试|开发|工程师|经理|总监|专员|主管|架构师|实习生|分析师)',
        clean
    )
    position_title = title_match.group(0) if title_match else None

    # 地点
    from backend.utils.text_normalizer import extract_city
    location = extract_city(clean)

    # 职责和要求（简化版）
    responsibilities = []
    requirements = []

    # 提取以"负责"、"参与"、"主导"开头的职责句
    resp_pattern = r'(?:负责|参与|主导|协助|推动|管理|协调).*?(?:[。；;]|$)'
    for m in re.finditer(resp_pattern, clean):
        text = m.group(0).strip()
        if text and len(text) > 5:
            responsibilities.append(JDResponsibility(value=text))

    # 提取以"要求"、"必备"、"加分"、"精通"开头的条件
    req_pattern = r'(?:要求|必备|加分项|精通|熟悉|了解|掌握|熟练).*?(?:[。；;]|$)'
    for m in re.finditer(req_pattern, clean):
        text = m.group(0).strip()
        if text and len(text) > 5:
            requirements.append(JDRequirement(type="hard_skill", value=text))

    return JDExtractResponse(
        success=True,
        hard_skills=hard_skills,
        soft_skills=soft_skills,
        industry=industry,
        years_required=years_required,
        education_required=education_required,
        salary_range=salary_range,
        position_title=position_title,
        location=location,
        requirements=requirements[:10],
        responsibilities=responsibilities[:10],
        method="regex",
        confidence=0.8,
    )
