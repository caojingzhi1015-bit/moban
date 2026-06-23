"""OCR 增强层 — 替代 Tesseract.js + DeepSeek-VL 浏览器调用

PaddleOCR (主) + DeepSeek-VL API (降级)
"""
import io
import base64
import logging
from typing import Optional

from backend.config import (
    PADDLEOCR_ENABLED, PADDLEOCR_LANG,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
)

logger = logging.getLogger(__name__)

_paddleocr_available = False
_ocr_instance = None

try:
    from paddleocr import PaddleOCR
    _paddleocr_available = True
except ImportError:
    logger.info("PaddleOCR not installed — using DeepSeek-VL API for OCR")


class OCRResult:
    """OCR 结果"""
    def __init__(self):
        self.full_text: str = ""
        self.lines: list[dict] = []  # [{text, confidence, bbox}]
        self.method: str = "unknown"
        self.usage: Optional[dict] = None


class OCREngine:
    """OCR 引擎"""

    async def recognize(self, image_bytes: bytes, lang: str = "zh") -> OCRResult:
        """识别图片文字"""
        # Level 1: PaddleOCR (本地)
        if PADDLEOCR_ENABLED and _paddleocr_available:
            try:
                return self._recognize_paddle(image_bytes, lang)
            except Exception as e:
                logger.warning(f"PaddleOCR failed: {e}, falling back to DeepSeek-VL")

        # Level 2: DeepSeek-VL API
        if DEEPSEEK_API_KEY:
            try:
                return await self._recognize_deepseek_vl(image_bytes, lang)
            except Exception as e:
                logger.warning(f"DeepSeek-VL OCR failed: {e}")

        # Level 3: 返回错误
        result = OCRResult()
        result.method = "failed"
        result.full_text = "[OCR 失败：无可用的 OCR 引擎。请安装 PaddleOCR 或配置 DeepSeek API Key]"
        return result

    def _recognize_paddle(self, image_bytes: bytes, lang: str) -> OCRResult:
        """PaddleOCR 本地识别"""
        global _ocr_instance

        if _ocr_instance is None:
            ocr_lang = PADDLEOCR_LANG
            if lang == "en":
                ocr_lang = "en"
            _ocr_instance = PaddleOCR(
                use_angle_cls=True,
                lang=ocr_lang,
                use_gpu=False,  # 根据部署环境调整
                show_log=False,
            )

        # PaddleOCR 接受 numpy array 或 image path
        import numpy as np
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)

        ocr_result = _ocr_instance.ocr(image_np, cls=True)

        result = OCRResult()
        result.method = "paddleocr"

        if not ocr_result or not ocr_result[0]:
            result.full_text = ""
            return result

        lines = []
        for line_info in ocr_result[0]:
            bbox = line_info[0]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            text = line_info[1][0]
            confidence = line_info[1][1]

            lines.append({
                "text": text,
                "confidence": confidence,
                "bbox": bbox,
            })

        result.lines = lines
        result.full_text = "\n".join(l["text"] for l in lines)

        logger.info(f"[PaddleOCR] Recognized {len(lines)} lines")
        return result

    async def _recognize_deepseek_vl(self, image_bytes: bytes, lang: str) -> OCRResult:
        """DeepSeek-VL API 远程 OCR"""
        import httpx

        data_url = self._to_data_url(image_bytes)

        prompt = (
            "你是一个精准的OCR识别工具。请严格识别并提取图片中的所有文字内容，保持原文格式和结构。\n"
            "规则：\n"
            "1. 逐字逐行识别，不遗漏任何文字\n"
            "2. 保持原文的段落结构、标题层级\n"
            "3. 如果是简历：提取姓名、联系方式、教育经历、工作经历、项目经历、技能证书、自我评价\n"
            "4. 如果是JD：完整提取岗位职责、任职要求、技能要求\n"
            "5. 数字、日期、百分比必须精确识别，不能近似或编造\n"
            "6. 不要添加任何不属于图片原文的内容"
        ) if lang == "zh" else (
            "Extract ALL text from this image precisely. "
            "Keep original structure. Do not add or fabricate any content."
        )

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={
                    "model": "deepseek-vl",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": data_url}},
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.01,
                },
            )
            response.raise_for_status()
            data = response.json()

            result = OCRResult()
            result.method = "deepseek-vl"
            result.full_text = data["choices"][0]["message"]["content"]
            result.usage = data.get("usage", {})
            return result

    @staticmethod
    def _to_data_url(image_bytes: bytes, mime: str = "image/png") -> str:
        """转 base64 data URL"""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime};base64,{b64}"
