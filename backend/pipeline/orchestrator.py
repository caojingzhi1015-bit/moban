"""主流水线调度器 — 6步提取流水线

复制 extraction-pipeline.js 的 6-step pipeline 架构：
Step 1: 文件路由 (ingestion + layout parsing)
Step 2: 硬字段正则预提取 (name/phone/email)
Step 3: 深度结构化提取 (SmartResume → LLM → regex 三级降级)
Step 4: Schema Lock (字段约束)
Step 5: 验证 (fact_checker)
Step 6: 导入素材库 (material_store)
"""
import time
import uuid
import logging
from typing import Optional, Callable

from backend.models.resume import (
    ResumeExtractResponse, BasicInfo, EducationEntry, WorkExperienceEntry,
    ProjectEntry, SkillEntry, CertificateEntry, LanguageEntry, ValidationResult,
)
from backend.models.common import ParseResponse
from backend.pipeline.smart_extractor import SmartExtractor
from backend.pipeline.fact_checker import FactChecker
from backend.pipeline.ingestion import DocumentIngestion
from backend.stores.material_store import get_store, create_session

logger = logging.getLogger(__name__)


class ExtractionOrchestrator:
    """6步提取流水线协调器"""

    # 允许的 schema 字段（用于 Schema Lock）
    ALLOWED_BASIC_FIELDS = {
        "name", "phone", "email", "city", "target_job", "expect_salary",
        "onboard_time", "birth_date", "age", "gender",
    }
    ALLOWED_SECTIONS = {
        "education", "work_experience", "projects", "skills",
        "certificates", "languages",
    }

    # AI 占位符（需过滤）
    PLACEHOLDER_VALUES = {
        "无", "暂无", "暂未提供", "未填写", "目标岗位从业者", "求职者",
        "experienced professional", "N/A", "n/a", "null", "NULL",
    }

    def __init__(self):
        self.ingestion = DocumentIngestion()

    async def run_full_pipeline(
        self,
        text: str,
        file_name: str = "用户输入",
        method: str = "auto",
        lang: str = "zh",
        session_id: Optional[str] = None,
        on_progress: Optional[Callable] = None,
    ) -> ResumeExtractResponse:
        """运行完整的 6 步提取流水线"""
        pipeline_log = []
        start_time = time.time()

        def log_step(step: int, msg: str):
            entry = {"step": step, "msg": msg, "timestamp": time.time()}
            pipeline_log.append(entry)
            logger.info(f"[Pipeline Step {step}] {msg}")
            if on_progress:
                on_progress(step, msg)

        # Step 1: 文本预处理（ingestion 层已完成，此处做标准化）
        log_step(1, f"文本标准化完成，共 {len(text)} 字符")

        # Step 2: 硬字段正则预提取（name/phone/email 快速正则，后续可覆盖）
        log_step(2, "硬字段正则预提取 (name/phone/email)...")
        hard_fields = {
            "name": SmartExtractor._extract_name(text),
            "phone": SmartExtractor._extract_phone(text),
            "email": SmartExtractor._extract_email(text),
        }
        log_step(2, f"Pre-extract: name={hard_fields['name']}, phone={hard_fields['phone']}, email={hard_fields['email']}")

        # Step 3: 深度结构化提取（三级降级）
        log_step(3, f"深度结构化提取 (method={method})...")
        extracted = await SmartExtractor.extract(text, method=method, lang=lang)
        extraction_method = extracted.get("method", method)
        confidence = extracted.get("confidence", 0.7)
        log_step(3, f"提取完成: method={extraction_method}, confidence={confidence}")

        # Step 3.5: Schema 归一化 — 将 LLM 输出的新 schema 映射到内部格式
        normalized = self._normalize_llm_schema(extracted)

        # Step 4: Schema Lock — 清理非法字段和占位符
        log_step(4, "Schema Lock — 清理非法字段和占位符...")
        locked = self._schema_lock(normalized, hard_fields)
        log_step(4, f"Schema Lock 完成: basic_info keys={list(locked.get('basic_info',{}).keys())}")

        # Step 5: 验证 — FactChecker 增强版
        log_step(5, "事实溯源校验...")
        material_context = text  # 原始文本作为素材上下文
        validation = FactChecker.validate(
            generated_text=self._flatten_extracted(locked),
            material_context=material_context,
            extracted_data=locked,
            lang=lang,
        )
        log_step(5, f"校验完成: severity={validation.severity}, issues={len(validation.issues)}")

        # Step 6: 导入素材库
        log_step(6, "导入素材库...")
        store = get_store()
        if session_id:
            session = store.get_session(session_id)
        else:
            session = create_session()
            session_id = session.session_id

        session.load_from_extraction({
            **locked,
            "file_type": "text",
            "method": extraction_method,
        }, file_name)
        log_step(6, f"素材库导入完成: session={session_id}")

        # 构建响应
        elapsed = time.time() - start_time
        log_step(0, f"流水线总耗时: {elapsed:.2f}s")

        return ResumeExtractResponse(
            success=True,
            basic_info=BasicInfo(**locked.get("basic_info", {})),
            education=[EducationEntry(**e) for e in locked.get("education", [])],
            work_experience=[WorkExperienceEntry(**w) for w in locked.get("work_experience", [])],
            projects=[ProjectEntry(**p) for p in locked.get("projects", [])],
            skills=[SkillEntry(**s) for s in locked.get("skills", [])],
            certificates=[CertificateEntry(**c) for c in locked.get("certificates", [])],
            languages=[LanguageEntry(**l) for l in locked.get("languages", [])],
            self_assessment=locked.get("self_assessment"),
            source_index=locked.get("source_index", {}),
            validation=validation,
            method=extraction_method,
            confidence=confidence,
            session_id=session_id,
        )

    def _schema_lock(self, extracted: dict, hard_fields: dict) -> dict:
        """Schema Lock — 过滤非法字段，用硬字段覆盖提取结果"""
        locked = {}

        # 锁定 basic_info
        basic = dict(extracted.get("basic_info", {}))
        # 只保留允许的字段
        basic = {k: v for k, v in basic.items() if k in self.ALLOWED_BASIC_FIELDS}
        # 用硬字段覆盖（如果 LLM 提取结果为空）
        for field in ["name", "phone", "email"]:
            if not basic.get(field) and hard_fields.get(field):
                basic[field] = hard_fields[field]
        # 过滤占位符值
        basic = {k: (v if v and str(v).strip() not in self.PLACEHOLDER_VALUES else None) for k, v in basic.items()}
        locked["basic_info"] = basic

        # 锁定各 section
        for section in self.ALLOWED_SECTIONS:
            items = extracted.get(section, [])
            if not isinstance(items, list):
                items = []
            # 过滤占位符
            cleaned = []
            for item in items:
                if isinstance(item, dict):
                    cleaned_item = {
                        k: (v if v and str(v).strip() not in self.PLACEHOLDER_VALUES else None)
                        for k, v in item.items()
                    }
                    cleaned.append(cleaned_item)
                elif isinstance(item, str):
                    if item.strip() not in self.PLACEHOLDER_VALUES:
                        cleaned.append({"name": item})
            locked[section] = cleaned

        # 锁定 self_assessment
        sa = extracted.get("self_assessment")
        if sa and str(sa).strip() in self.PLACEHOLDER_VALUES:
            sa = None
        locked["self_assessment"] = sa

        # 保留 source_index
        locked["source_index"] = extracted.get("source_index", {})

        return locked

    @staticmethod
    def _normalize_llm_schema(extracted: dict) -> dict:
        """将 LLM 输出的新 Prompt 格式映射到内部 API schema

        LLM 输出 (用户新 Prompt):
          base_info → internal basic_info
          education_list → internal education
          work_experience_list → internal work_experience
          project_list → internal projects
          skill_certificate → internal skills + certificates + languages
        """
        # 检测是否已经是旧 schema（无 base_info 但有 basic_info）
        if "basic_info" in extracted and "base_info" not in extracted:
            return extracted  # 已经是内部格式，无需转换

        normalized = {}

        # 归一化 base_info → basic_info
        base = extracted.get("base_info", {})
        if base:
            normalized["basic_info"] = {
                "name": base.get("name"),
                "phone": base.get("phone"),
                "email": base.get("email"),
                "city": base.get("target_city"),
                "target_job": base.get("target_position"),
                "expect_salary": base.get("expected_salary"),
                "onboard_time": base.get("available_onboard_time"),
                "source_index": base.get("source_index", []),
            }
        else:
            normalized["basic_info"] = {}

        # 归一化 education_list → education
        edu_list = extracted.get("education_list", [])
        normalized["education"] = []
        for e in edu_list:
            normalized["education"].append({
                "school": e.get("school_name"),
                "major": e.get("major"),
                "degree": e.get("degree"),
                "start_date": e.get("start_date"),
                "end_date": e.get("end_date"),
                "awards": e.get("scholarship_awards") or [],
                "source_index": e.get("source_index", []),
            })

        # 归一化 work_experience_list → work_experience
        work_list = extracted.get("work_experience_list", [])
        normalized["work_experience"] = []
        for w in work_list:
            normalized["work_experience"].append({
                "company": w.get("company"),
                "position": w.get("position"),
                "start_date": w.get("start_date"),
                "end_date": w.get("end_date"),
                "duties": w.get("job_duty"),
                "achievements": [],
                "source_index": w.get("source_index", []),
            })

        # 归一化 project_list → projects
        proj_list = extracted.get("project_list", [])
        normalized["projects"] = []
        for p in proj_list:
            normalized["projects"].append({
                "name": p.get("project_name"),
                "role": p.get("responsibility"),
                "start_date": None,
                "end_date": None,
                "description": p.get("responsibility"),
                "results": p.get("project_data"),
                "technologies": [],
                "source_index": p.get("source_index", []),
            })
            # 尝试解析 project_time 为日期范围
            pt = p.get("project_time", "")
            if pt:
                from backend.utils.text_normalizer import extract_date_range
                dr = extract_date_range(pt)
                if dr:
                    normalized["projects"][-1]["start_date"] = dr["start"]
                    normalized["projects"][-1]["end_date"] = dr["end"]

        # 归一化 skill_certificate → skills + certificates + languages
        sc = extracted.get("skill_certificate", {})
        normalized["skills"] = []
        normalized["certificates"] = []
        normalized["languages"] = []

        if sc:
            src_idx = sc.get("source_index", [])
            # 语言证书
            for lang_name in (sc.get("language_cert") or []):
                normalized["languages"].append({"name": lang_name, "level": None, "source_index": src_idx})
            # 软件技能
            for skill_name in (sc.get("software_skill") or []):
                normalized["skills"].append({"name": skill_name, "category": "工具", "level": None, "source_index": src_idx})
            # AI 工具
            for tool_name in (sc.get("ai_tool_mastered") or []):
                normalized["skills"].append({"name": tool_name, "category": "AI工具", "level": None, "source_index": src_idx})
            # 其他证书
            for cert_name in (sc.get("other_cert") or []):
                normalized["certificates"].append({"name": cert_name, "date": None, "issuing_authority": None, "source_index": src_idx})

        # 保留 self_assessment
        normalized["self_assessment"] = extracted.get("self_assessment")
        normalized["source_index"] = extracted.get("source_index", {})

        return normalized

    @staticmethod
    def _flatten_extracted(extracted: dict) -> str:
        """将提取结果展平为文本用于校验"""
        parts = []

        basic = extracted.get("basic_info", {})
        for k, v in basic.items():
            if v:
                parts.append(f"{k}: {v}")

        for section in ["education", "work_experience", "projects", "skills", "certificates"]:
            items = extracted.get(section, [])
            for item in items:
                if isinstance(item, dict):
                    parts.extend(str(v) for v in item.values() if v)
                elif isinstance(item, str):
                    parts.append(item)

        sa = extracted.get("self_assessment")
        if sa:
            parts.append(str(sa))

        return "\n".join(parts)
