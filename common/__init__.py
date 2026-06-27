# common — 全局公共工具包
# 6个业务模块统一复用：OCR/PDF解析、事实校验、防幻觉Prompt、双语切换、多模型网关

from .ocr_pdf_processor import OcrPdfProcessor
from .fact_check_validator import FactCheckValidator
from .language_switch import LanguageSwitch
from .multi_model_gateway import MultiModelGateway, GatewayConfig

__all__ = [
    "OcrPdfProcessor",
    "FactCheckValidator",
    "LanguageSwitch",
    "MultiModelGateway",
    "GatewayConfig",
]
