"""文档解析接口 — POST /api/parse

接受文件上传，返回结构化文本 + 版面信息
"""
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from backend.config import MAX_UPLOAD_SIZE
from backend.models.common import ParseResponse
from backend.pipeline.ingestion import DocumentIngestion
from backend.pipeline.layout_parser import LayoutParser
from backend.pipeline.ocr_engine import OCREngine
from backend.pipeline.table_extractor import TableExtractor
from backend.stores.material_store import get_store, create_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["parse"])

ingestion = DocumentIngestion()
layout_parser = LayoutParser()
ocr_engine = OCREngine()
table_extractor = TableExtractor()


@router.post("/parse", response_model=ParseResponse)
async def parse_document(
    file: UploadFile = File(..., description="待解析文件"),
    lang: str = Form(default="zh", description="语言: zh/en"),
):
    """解析上传的文档，返回结构化 Markdown 和版面信息"""
    # 验证文件大小
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"文件过大，最大 {MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    mime_type = file.content_type or ""

    session_id = str(uuid.uuid4())[:12]

    try:
        # Step 1: 摄入（Unstructured → MarkItDown → fallback）
        doc = await ingestion.ingest(content, file.filename, mime_type)

        # Step 2: 版面解析（仅 PDF）
        layout = None
        if doc.doc_type == "pdf":
            try:
                layout_result = await layout_parser.parse_bytes(content, file.filename)
                layout = {
                    "sections": layout_result.sections,
                    "tables": layout_result.tables,
                    "images": layout_result.images,
                    "reading_order": layout_result.reading_order,
                    "page_count": layout_result.page_count,
                    "method": layout_result.method,
                }
            except Exception as e:
                logger.warning(f"Layout parsing skipped: {e}")

        # Step 3: 图片 OCR（如果是图片文件）
        if doc.doc_type == "image" and doc.method == "image_pending_ocr":
            try:
                ocr_result = await ocr_engine.recognize(content, lang)
                doc.markdown = ocr_result.full_text
                doc.raw_text = ocr_result.full_text
                doc.method = ocr_result.method
            except Exception as e:
                logger.warning(f"OCR failed: {e}")

        # Step 4: 创建会话并保存解析结果
        store = get_store()
        session = store.create_session()
        session_id = session.session_id

        return ParseResponse(
            success=True,
            type=doc.doc_type,
            file_name=file.filename,
            markdown=doc.markdown,
            raw_text=doc.raw_text,
            layout=layout,
            method=doc.method,
            session_id=session_id,
        )

    except Exception as e:
        logger.exception(f"Parse failed for {file.filename}")
        raise HTTPException(500, f"解析失败: {str(e)}")


@router.get("/parse/health")
async def parse_health():
    """检查解析服务可用性"""
    return {
        "status": "ok",
        "services": {
            "unstructured": _check_unstructured(),
            "markitdown": _check_markitdown(),
            "mineru": _check_mineru(),
            "paddleocr": _check_paddleocr(),
            "docling": _check_docling(),
        },
    }


def _check_unstructured() -> str:
    try:
        from unstructured.partition.auto import partition
        return "available"
    except ImportError:
        return "unavailable"

def _check_markitdown() -> str:
    try:
        from markitdown import MarkItDown
        return "available"
    except ImportError:
        return "unavailable"

def _check_mineru() -> str:
    try:
        from magic_pdf.pipe.UNIPipe import UNIPipe
        return "available"
    except ImportError:
        return "unavailable"

def _check_paddleocr() -> str:
    try:
        from paddleocr import PaddleOCR
        return "available"
    except ImportError:
        return "unavailable"

def _check_docling() -> str:
    try:
        from docling.document_converter import DocumentConverter
        return "available"
    except ImportError:
        return "unavailable"
