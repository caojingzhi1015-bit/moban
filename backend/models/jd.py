"""JD (Job Description) 结构化数据模型"""
from pydantic import BaseModel, Field
from typing import Optional


class JDRequirement(BaseModel):
    """任职要求"""
    type: str  # "hard_skill" | "soft_skill" | "education" | "experience" | "other"
    value: str
    required: bool = True  # 是否必须 vs 加分项
    source_text: Optional[str] = None


class JDResponsibility(BaseModel):
    """岗位职责"""
    value: str
    source_text: Optional[str] = None


class JDExtractResponse(BaseModel):
    """JD 解析完整响应"""
    success: bool = True
    hard_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    industry: list[str] = Field(default_factory=list)
    years_required: Optional[str] = None
    education_required: Optional[str] = None
    salary_range: Optional[str] = None
    position_title: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None  # 全职/实习/兼职/远程
    requirements: list[JDRequirement] = Field(default_factory=list)
    responsibilities: list[JDResponsibility] = Field(default_factory=list)
    method: str = "regex"  # "llm" | "regex"
    confidence: float = 0.7
    error: Optional[str] = None
