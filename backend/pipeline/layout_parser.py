"""版面解析层 — 替代 PDF.js 纯文本提取

使用 MinerU v2.5 (主) → PyMuPDF (降级)

MinerU 能力:
- 版面检测 (YOLOv10): 标题/正文/表格/图片/公式
- 阅读顺序重建
- 表格识别 (RapidTable)
- 输出 Markdown + JSON
"""
import logging
from pathlib import Path
from typing import Optional

from backend.config import MINERU_ENABLED, MINERU_MODEL_PATH, MINERU_DEVICE_MODE

logger = logging.getLogger(__name__)

_mineru_available = False
_pymupdf_available = False

try:
    import fitz  # PyMuPDF
    _pymupdf_available = True
except ImportError:
    logger.info("PyMuPDF not installed")

# MinerU 导入是复杂的（magic-pdf 包），仅在启用时加载
if MINERU_ENABLED:
    try:
        from magic_pdf.pipe.UNIPipe import UNIPipe
        from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
        _mineru_available = True
    except ImportError:
        logger.info("MinerU not installed — using PyMuPDF for layout parsing")


class LayoutResult:
    """版面解析结果"""
    def __init__(self):
        self.markdown: str = ""
        self.sections: list[dict] = []  # 章节信息
        self.tables: list[dict] = []    # 表格信息
        self.images: list[dict] = []    # 图片位置
        self.reading_order: list[int] = []  # 阅读顺序
        self.page_count: int = 0
        self.method: str = "unknown"


class LayoutParser:
    """版面解析器"""

    async def parse(self, file_path: str) -> LayoutResult:
        """解析 PDF 版面结构"""
        if MINERU_ENABLED and _mineru_available:
            try:
                return await self._parse_mineru(file_path)
            except Exception as e:
                logger.warning(f"MinerU failed: {e}, falling back to PyMuPDF")

        return await self._parse_pymupdf(file_path)

    async def parse_bytes(self, file_bytes: bytes, file_name: str = "document.pdf") -> LayoutResult:
        """从 bytes 解析"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            return await self.parse(tmp_path)
        finally:
            import os
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _parse_mineru(self, file_path: str) -> LayoutResult:
        """MinerU v2.5 版面解析"""
        result = LayoutResult()

        # MinerU 管道
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()

        # 创建临时输出目录
        import tempfile
        output_dir = tempfile.mkdtemp(prefix="mineru_")

        try:
            # MinerU 1.x API
            # jso_useful_key 中的 _pdf_type: "scan" 表示扫描件
            pipe = UNIPipe(pdf_bytes, jso_useful_key={"_pdf_type": ""})
            pipe.pipe_classify()  # 分类（扫描件/电子件）
            pipe.pipe_parse()     # 解析

            # 获取内容列表
            content_list = pipe.pipe_mk_uni_format(output_dir, drop_mode="none")
            md_content = pipe.pipe_mk_markdown(output_dir, drop_mode="none")

            result.markdown = md_content

            # 提取章节和表格
            for item in content_list:
                if item.get("type") == "table":
                    result.tables.append({
                        "page": item.get("page_idx", 0),
                        "bbox": item.get("bbox", []),
                        "content": item.get("content", ""),
                    })

            result.method = "mineru"
            logger.info(f"[MinerU] Parsed layout: {len(content_list)} elements")
        except Exception as e:
            logger.error(f"MinerU parse error: {e}")
            raise
        finally:
            import shutil
            try:
                shutil.rmtree(output_dir)
            except Exception:
                pass

        return result

    async def _parse_pymupdf(self, file_path: str) -> LayoutResult:
        """PyMuPDF 降级版面解析"""
        result = LayoutResult()

        if not _pymupdf_available:
            result.markdown = "[PyMuPDF 不可用]"
            result.method = "unavailable"
            return result

        pdf = fitz.open(file_path)
        result.page_count = pdf.page_count

        all_blocks = []

        for page_num in range(pdf.page_count):
            page = pdf[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block["type"] == 0:  # 文本块
                    block_info = {
                        "page": page_num,
                        "type": "text",
                        "bbox": list(block["bbox"]),
                        "text": "",
                        "lines": [],
                    }
                    for line in block.get("lines", []):
                        line_text = "".join(
                            span["text"] for span in line.get("spans", [])
                        )
                        if line_text.strip():
                            block_info["lines"].append({
                                "text": line_text,
                                "bbox": list(line["bbox"]),
                            })
                    if block_info["lines"]:
                        block_info["text"] = "\n".join(l["text"] for l in block_info["lines"])
                        all_blocks.append(block_info)

                elif block["type"] == 1:  # 图片块
                    result.images.append({
                        "page": page_num,
                        "bbox": list(block["bbox"]),
                        "size": (block.get("width", 0), block.get("height", 0)),
                    })

        # 按页面和 y 坐标排序（阅读顺序）
        all_blocks.sort(key=lambda b: (b["page"], b["bbox"][1], b["bbox"][0]))

        # 构建 markdown
        md_lines = []
        sections = []
        current_section = {"title": "", "content": []}

        for block in all_blocks:
            text = block["text"]
            md_lines.append(text)
            md_lines.append("")

            current_section["content"].append(text)

        result.markdown = "\n".join(md_lines)
        result.sections = [current_section] if current_section["content"] else []
        result.reading_order = list(range(len(all_blocks)))
        result.method = "pymupdf"

        logger.info(f"[PyMuPDF] Parsed {pdf.page_count} pages, {len(all_blocks)} blocks")
        pdf.close()
        return result
