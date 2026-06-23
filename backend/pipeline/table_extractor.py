"""表格专用提取层 — 按需调用

Docling (IBM) → Camelot → tabula-py → regex

Docling: 表格提取 TEDS 0.887（开源最高）
"""
import logging
from typing import Optional

from backend.config import DOCLING_ENABLED

logger = logging.getLogger(__name__)

_docling_available = False
_camelot_available = False

try:
    from docling.document_converter import DocumentConverter
    _docling_available = True
except ImportError:
    logger.info("Docling not installed — table extraction limited")

try:
    import camelot
    _camelot_available = True
except ImportError:
    logger.info("Camelot not installed")


class TableResult:
    """表格提取结果"""
    def __init__(self):
        self.tables: list[dict] = []  # [{headers: [], rows: [[],...], page: int}]
        self.method: str = "unknown"


class TableExtractor:
    """表格提取器"""

    async def extract(self, file_path: str) -> TableResult:
        """从 PDF 提取表格"""
        # Level 1: Docling
        if DOCLING_ENABLED and _docling_available:
            try:
                return await self._extract_docling(file_path)
            except Exception as e:
                logger.warning(f"Docling table extraction failed: {e}")

        # Level 2: Camelot
        if _camelot_available:
            try:
                return self._extract_camelot(file_path)
            except Exception as e:
                logger.warning(f"Camelot table extraction failed: {e}")

        # Level 3: 返回空
        result = TableResult()
        result.method = "unavailable"
        return result

    async def extract_from_bytes(self, file_bytes: bytes) -> TableResult:
        """从 bytes 提取表格"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            return await self.extract(tmp_path)
        finally:
            import os
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _extract_docling(self, file_path: str) -> TableResult:
        """Docling 表格提取"""
        converter = DocumentConverter()
        result_doc = converter.convert(file_path)

        result = TableResult()
        result.method = "docling"

        for table in result_doc.document.tables:
            table_data = {
                "headers": [],
                "rows": [],
                "page": getattr(table, "page", 0),
            }

            # 提取表头
            if hasattr(table, "header") and table.header:
                table_data["headers"] = [
                    cell.text for cell in table.header.cells
                ]

            # 提取数据行
            for row in table.data:
                if hasattr(row, "cells"):
                    table_data["rows"].append([
                        cell.text for cell in row.cells
                    ])

            result.tables.append(table_data)

        logger.info(f"[Docling] Extracted {len(result.tables)} tables")
        return result

    async def _extract_camelot(self, file_path: str) -> TableResult:
        """Camelot 表格提取"""
        tables = camelot.read_pdf(file_path, pages="all", flavor="lattice")

        if not tables or len(tables) == 0:
            # 尝试 stream 模式
            tables = camelot.read_pdf(file_path, pages="all", flavor="stream")

        result = TableResult()
        result.method = "camelot"

        for table in tables:
            result.tables.append({
                "headers": [],
                "rows": table.df.values.tolist(),
                "page": table.page,
                "accuracy": table.accuracy,
            })

        logger.info(f"[Camelot] Extracted {len(result.tables)} tables")
        return result
