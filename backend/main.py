"""CareerAI Backend — FastAPI 入口

文档解析 + 简历提取 + LLM 代理 + 面试系统
"""
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import CORS_ORIGINS, DEBUG, LOG_LEVEL, HOST, PORT
from backend.api.parse import router as parse_router
from backend.api.extract import router as extract_router
from backend.api.llm_proxy import router as llm_router
from backend.api.interview import router as interview_router
from backend.models.common import HealthResponse

# === Logging ===
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# === Lifespan ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 CareerAI Backend starting...")
    # 预检服务可用性
    services = _check_services()
    available = sum(1 for v in services.values() if v == "available")
    logger.info(f"Services: {available}/{len(services)} available — {services}")
    yield
    logger.info("CareerAI Backend shutting down...")


def _check_services() -> dict:
    """检查所有服务的可用性"""
    status = {}

    # SmartResume (vLLM)
    try:
        import httpx
        resp = httpx.get("http://localhost:8100/health", timeout=2)
        status["smartresume"] = "available" if resp.status_code == 200 else "unreachable"
    except Exception:
        status["smartresume"] = "unavailable"

    # MinerU
    try:
        from magic_pdf.pipe.UNIPipe import UNIPipe
        status["mineru"] = "available"
    except ImportError:
        status["mineru"] = "unavailable (install magic-pdf)"

    # Unstructured.io
    try:
        from unstructured.partition.auto import partition
        status["unstructured"] = "available"
    except ImportError:
        status["unstructured"] = "unavailable (install unstructured)"

    # MarkItDown
    try:
        from markitdown import MarkItDown
        status["markitdown"] = "available"
    except ImportError:
        status["markitdown"] = "unavailable (install markitdown)"

    # PaddleOCR
    try:
        from paddleocr import PaddleOCR
        status["paddleocr"] = "available"
    except ImportError:
        status["paddleocr"] = "unavailable (install paddleocr)"

    # Docling
    try:
        from docling.document_converter import DocumentConverter
        status["docling"] = "available"
    except ImportError:
        status["docling"] = "unavailable (install docling)"

    # DeepSeek API
    from backend.config import DEEPSEEK_API_KEY
    status["deepseek_api"] = "available" if DEEPSEEK_API_KEY else "unconfigured (set DEEPSEEK_API_KEY)"

    # Claude API
    from backend.config import CLAUDE_API_KEY
    status["claude_api"] = "available" if CLAUDE_API_KEY else "unconfigured"

    # GPT API
    from backend.config import OPENAI_API_KEY
    status["gpt_api"] = "available" if OPENAI_API_KEY else "unconfigured"

    # Gemini API
    from backend.config import GEMINI_API_KEY
    status["gemini_api"] = "available" if GEMINI_API_KEY else "unconfigured"

    # GPU
    try:
        import torch
        status["gpu"] = f"available (CUDA: {torch.cuda.is_available()}, devices: {torch.cuda.device_count()})"
    except ImportError:
        status["gpu"] = "unavailable (torch not installed)"

    return status


# === App ===
app = FastAPI(
    title="CareerAI Backend",
    description="AI 求职助手后端 — 文档解析 + 简历提取 + LLM 代理",
    version="1.0.0",
    lifespan=lifespan,
)

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Routers ===
app.include_router(parse_router)
app.include_router(extract_router)
app.include_router(llm_router)
app.include_router(interview_router)


# === Middleware: Request logging ===
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.2f}s)")
    return response


# === Error handlers ===
@app.exception_handler(413)
async def too_large_handler(request: Request, exc):
    return JSONResponse(
        status_code=413,
        content={"success": False, "error": "文件过大，请上传小于 20MB 的文件"},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.exception(f"Internal error: {request.url}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "服务器内部错误", "detail": str(exc) if DEBUG else None},
    )


# === Health ===
@app.get("/api/health", response_model=HealthResponse)
async def health():
    """健康检查 + 服务状态"""
    import torch
    return HealthResponse(
        status="ok",
        version="1.0.0",
        services=_check_services(),
        gpu_available=torch.cuda.is_available() if torch else False,
    )


# === Root ===
@app.get("/")
async def root():
    return {
        "name": "CareerAI Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "parse": "POST /api/parse",
            "extract_resume": "POST /api/extract/resume",
            "extract_jd": "POST /api/extract/jd",
            "llm_chat": "POST /api/llm/chat",
            "interview_chat": "POST /api/interview/chat",
            "health": "GET /api/health",
        },
    }


# === Main ===
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level=LOG_LEVEL.lower(),
    )
