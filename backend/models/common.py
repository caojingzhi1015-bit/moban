"""通用请求/响应 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


class ParseRequest(BaseModel):
    lang: str = Field(default="zh", description="语言: zh/en")


class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000, description="待提取文本")
    method: str = Field(default="auto", description="提取方法: auto/smartresume/llm/regex")
    session_id: Optional[str] = Field(default=None, description="会话 ID")
    lang: str = Field(default="zh", description="语言: zh/en")


class LLMChatRequest(BaseModel):
    model: str = Field(default="deepseek", description="模型: deepseek/claude/gpt/gemini")
    messages: list[dict] = Field(..., min_length=1, max_length=100, description="对话消息")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=1, le=32000)
    system_prompt: Optional[str] = Field(default=None, description="系统提示词（覆盖默认）")
    lang: str = Field(default="zh")


class LLMChatResponse(BaseModel):
    content: str
    model: str
    usage: dict = Field(default_factory=dict)
    finish_reason: Optional[str] = None


class ParseResponse(BaseModel):
    success: bool = True
    type: str  # "pdf", "image", "docx", "txt", etc.
    file_name: str
    markdown: str = ""
    raw_text: str = ""
    layout: Optional[dict] = None
    method: str = "unknown"  # "mineru", "unstructured", "pymupdf", "plain_text"
    session_id: str
    usage: Optional[dict] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    services: dict = Field(default_factory=dict)
    gpu_available: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: int = 500
