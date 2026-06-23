"""SmartResume Schema — 结构化简历数据模型"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class BasicInfo(BaseModel):
    """基础个人身份信息"""
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    target_job: Optional[str] = None
    expect_salary: Optional[str] = None
    onboard_time: Optional[str] = None
    birth_date: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    source_index: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    """教育经历"""
    school: Optional[str] = None
    major: Optional[str] = None
    degree: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    gpa: Optional[str] = None
    awards: list[str] = Field(default_factory=list)
    source_index: list[str] = Field(default_factory=list)


class WorkExperienceEntry(BaseModel):
    """工作/实习经历"""
    company: Optional[str] = None
    position: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    department: Optional[str] = None
    duties: Optional[str] = None  # 工作职责描述
    achievements: list[str] = Field(default_factory=list)  # 量化成果
    source_index: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    """项目经历"""
    name: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    results: Optional[str] = None  # 项目成果
    source_index: list[str] = Field(default_factory=list)


class SkillEntry(BaseModel):
    """技能"""
    name: str
    category: Optional[str] = None  # 编程语言/框架/工具/语言/其他
    level: Optional[str] = None  # 精通/熟练/了解
    source_index: list[str] = Field(default_factory=list)


class CertificateEntry(BaseModel):
    """证书/资质"""
    name: str
    date: Optional[str] = None
    issuing_authority: Optional[str] = None
    source_index: list[str] = Field(default_factory=list)


class LanguageEntry(BaseModel):
    """语言能力"""
    name: str
    level: Optional[str] = None  # 母语/流利/CET-6/IELTS 7.0
    source_index: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """提取结果校验"""
    severity: str = "pass"  # "pass" | "warning" | "block"
    issues: list[dict] = Field(default_factory=list)
    grounded_ratio: float = 1.0  # 素材溯源比例 (0-1)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResumeExtractResponse(BaseModel):
    """简历信息提取完整响应"""
    success: bool = True
    basic_info: BasicInfo = Field(default_factory=BasicInfo)
    education: list[EducationEntry] = Field(default_factory=list)
    work_experience: list[WorkExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: list[SkillEntry] = Field(default_factory=list)
    certificates: list[CertificateEntry] = Field(default_factory=list)
    languages: list[LanguageEntry] = Field(default_factory=list)
    self_assessment: Optional[str] = None
    source_index: dict = Field(default_factory=dict)  # 原始文本索引
    validation: Optional[ValidationResult] = None
    method: str = "regex"  # "smartresume" | "llm" | "regex"
    confidence: float = 0.7  # 置信度 (0-1)
    session_id: Optional[str] = None
    error: Optional[str] = None
