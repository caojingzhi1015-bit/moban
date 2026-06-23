"""全局配置中心 - 模型路径、API keys、GPU 设置"""
import os
from pathlib import Path

# === Project Root ===
ROOT_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# === Server ===
HOST = os.getenv("CAREERAI_HOST", "0.0.0.0")
PORT = int(os.getenv("CAREERAI_PORT", "8000"))
DEBUG = os.getenv("CAREERAI_DEBUG", "true").lower() == "true"

# === GPU / Device ===
DEVICE = os.getenv("CAREERAI_DEVICE", "auto")  # "cuda", "cpu", "auto"
USE_GPU = DEVICE != "cpu"

# === SmartResume (Alibaba) ===
SMARTRESUME_ENABLED = os.getenv("SMARTRESUME_ENABLED", "true").lower() == "true"
SMARTRESUME_MODEL = os.getenv("SMARTRESUME_MODEL", "Alibaba-EI/Qwen3-0.6B-resume")
SMARTRESUME_VLLM_URL = os.getenv("SMARTRESUME_VLLM_URL", "http://localhost:8100/v1")
SMARTRESUME_TIMEOUT = int(os.getenv("SMARTRESUME_TIMEOUT", "30"))

# === MinerU (PDF Layout) ===
MINERU_ENABLED = os.getenv("MINERU_ENABLED", "true").lower() == "true"
MINERU_MODEL_PATH = os.getenv("MINERU_MODEL_PATH", "./models/MinerU")
MINERU_DEVICE_MODE = os.getenv("MINERU_DEVICE_MODE", "cuda" if USE_GPU else "cpu")

# === Unstructured.io ===
UNSTRUCTURED_ENABLED = os.getenv("UNSTRUCTURED_ENABLED", "true").lower() == "true"
UNSTRUCTURED_STRATEGY = os.getenv("UNSTRUCTURED_STRATEGY", "hi_res")  # "hi_res", "fast", "auto"

# === Docling (Table Extraction) ===
DOCLING_ENABLED = os.getenv("DOCLING_ENABLED", "false").lower() == "true"  # 重资源，默认关闭

# === PaddleOCR ===
PADDLEOCR_ENABLED = os.getenv("PADDLEOCR_ENABLED", "true").lower() == "true"
PADDLEOCR_LANG = os.getenv("PADDLEOCR_LANG", "ch")

# === DeepSeek API (LLM 降级) ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL_LITE = os.getenv("DEEPSEEK_MODEL_LITE", "deepseek-chat")
DEEPSEEK_MODEL_REASONER = os.getenv("DEEPSEEK_MODEL_REASONER", "deepseek-reasoner")

# === Claude API ===
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6-20250514")

# === GPT API ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# === Gemini API ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# === Session & CORS ===
SESSION_TTL = int(os.getenv("SESSION_TTL", "1800"))  # 30分钟无活动过期
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# === File Limits ===
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# === Logging ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
