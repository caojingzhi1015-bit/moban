"""
common/fact_check_validator.py — 双层校验引擎
校验层1: 格式正则（手机号/邮箱/时间逻辑/空白字段）
校验层2: 素材溯源（量化声明/虚构经历/逐句溯源率）
拦截无来源的幻觉内容，所有业务模块统一调用
"""

import re
import json
from typing import Any


class FactCheckValidator:
    """双层校验引擎 —— 格式正则 + 素材溯源"""

    # ──────────── Layer 1: 格式正则校验 ────────────

    @staticmethod
    def validate_format(data: dict) -> list[dict]:
        """
        校验数据格式：手机号/邮箱/时间逻辑/必填字段缺失
        返回 issue 列表，severity 分 'warning' 和 'block'
        """
        issues: list[dict] = []
        bi = data.get("basic_info") or data.get("base_info") or {}

        # 手机号格式校验
        phone = (bi.get("phone") or "").replace(" ", "").replace("-", "")
        if phone and not re.match(r"^(\+?86)?1[3-9]\d{9}$", phone):
            issues.append({
                "type": "format_phone", "severity": "warning",
                "field": "phone", "msg": "手机号格式异常",
            })

        # 邮箱格式校验
        email = bi.get("email") or ""
        if email and not re.match(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email
        ):
            issues.append({
                "type": "format_email", "severity": "warning",
                "field": "email", "msg": "邮箱格式异常",
            })

        # 时间逻辑冲突检测
        for w in data.get("work_experience") or data.get("work_experience_list") or []:
            s = FactCheckValidator._try_parse_year(w.get("start_date"))
            e = FactCheckValidator._try_parse_year(w.get("end_date"))
            if s and e and s > e:
                issues.append({
                    "type": "time_conflict", "severity": "block",
                    "msg": f"时间冲突: {w.get('company', '?')} "
                           f"{w.get('start_date', '?')}-{w.get('end_date', '?')}",
                })

        # 必填字段缺失检查
        for f in ("name", "phone", "email"):
            if not bi.get(f):
                issues.append({
                    "type": "missing_field", "severity": "warning",
                    "field": f, "msg": f"缺失必填字段: {f}",
                })

        return issues

    # ──────────── Layer 2: 素材溯源校验 ────────────

    @staticmethod
    def validate_sources(
        generated_text: str,
        material_context: str,
        opts: dict | None = None,
    ) -> dict:
        """
        校验生成文本是否可溯源至原始素材
        检测：量化声明伪造、虚构经历、溯源率计算
        """
        opts = opts or {}
        issues: list[dict] = []
        mat_lower = (material_context or "").lower()

        # 量化声明检测 —— 数字是否在原文中出现
        quant_patterns: list[tuple[str, str]] = [
            (r"提升\S{0,6}?(\d+[%％])", "量化提升"),
            (r"增长\S{0,6}?(\d+[%％])", "量化增长"),
            (r"(\d+[万億亿])\+", "大规模数据"),
            (r"ROI\s*[＞>]\s*\d+", "ROI声明"),
        ]
        for pat, label in quant_patterns:
            for m in re.finditer(pat, generated_text):
                g1 = m.group(1) if m.lastindex else None
                if g1 and g1.lower() not in mat_lower:
                    issues.append({
                        "type": "quantified", "severity": "warning",
                        "label": label, "matched": m.group(0),
                    })

        # 虚构经历检测 —— 管理规模/夸大职责未在原文出现
        fab_patterns: list[tuple[str, str]] = [
            (r"带领\s*(\d+)\s*人", "团队规模"),
            (r"管理\s*(\d+)\s*人", "管理规模"),
            (r"负责全[部局]?", "夸大职责"),
        ]
        for pat, label in fab_patterns:
            for m in re.finditer(pat, generated_text):
                g1 = m.group(1) if m.lastindex else None
                if g1 and g1 not in mat_lower:
                    issues.append({
                        "type": "fabricated", "severity": "block",
                        "label": label, "matched": m.group(0),
                    })

        # 逐句溯源率计算
        sentences = [
            s.strip()
            for s in re.split(r"[。.!！?？\n]", generated_text)
            if len(s.strip()) > 5
        ]
        grounded = 0
        for s in sentences:
            words = set(s)
            mat_words = set(material_context or "")
            overlap = len([w for w in words if w in mat_words])
            if overlap / max(1, len(words)) >= 0.1:
                grounded += 1
        ratio = grounded / len(sentences) if sentences else 0

        # 严重程度判定
        if any(i["severity"] == "block" for i in issues):
            severity = "block"
        elif issues:
            severity = "warning"
        else:
            severity = "pass"

        return {
            "severity": severity,
            "issues": issues,
            "grounded_ratio": round(ratio, 3),
            "total_sentences": len(sentences),
            "grounded_sentences": grounded,
        }

    # ──────────── 综合校验入口 ────────────

    @staticmethod
    def validate_all(data: dict, material_context: str = "") -> dict:
        """
        综合双层校验入口
        Args:
            data: 待校验的结构化数据
            material_context: 原始素材文本（用于溯源）
        Returns:
            {"format": [...], "source": {...}}
        """
        return {
            "format": FactCheckValidator.validate_format(data),
            "source": FactCheckValidator.validate_sources(
                json.dumps(data, ensure_ascii=False, default=str),
                material_context,
            ),
        }

    # ──────────── 工具 ────────────

    @staticmethod
    def _try_parse_year(value: Any) -> int | None:
        """从各种格式中提取年份"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        m = re.search(r"(\d{4})", str(value))
        return int(m.group(1)) if m else None
