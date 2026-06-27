"""
web_ui/resume_preview.py — 电脑 + 手机双窗口简历实时预览渲染
使用 st.components.v1.html 在 iframe 中完整渲染 HTML/CSS，不再明文打印标签。
"""

from __future__ import annotations

import re
import html as html_mod
import streamlit as st
from typing import Any
from common.language_switch import LanguageSwitch


# ═══════════════════════════════════════════════════════════════
# HTML 清洗函数 — 修复碎片标签、补齐文档容器、适配颜色
# ═══════════════════════════════════════════════════════════════

def _clean_html(html_raw: str, is_mobile: bool = False) -> str:
    """
    清洗并规范化 HTML 片段，确保浏览器可正确渲染。

    处理步骤:
      1. 清除首尾零散孤立的闭合标签（</div>, </p>, </h3> 等）
      2. 修复连续重复闭合标签
      3. 自动补全缺失的 <html> + <body> 外层容器
      4. 深色主题下文字强制设为黑色正文（浅色简历模板清晰可读）
      5. 手机端设置 max-width: 360px 模拟手机屏幕
    """
    html = html_raw.strip()

    # ── ① 清除首尾孤立的零散闭合标签 ──
    # 开头：一次匹配多个连续的孤立闭合标签
    html = re.sub(
        r'^(\s*</(?:div|p|h3|h2|span|li|ul|ol|b|i|em|strong)>\s*)+',
        '',
        html,
    )
    # 末尾：一次匹配多个连续的孤立闭合标签（核心修复）
    html = re.sub(
        r'(\s*</(?:div|p|h3|h2|span|li|ul|ol|b|i|em|strong)>\s*)+$',
        '',
        html,
    )

    # ── ② 修复连续重复闭合标签 ──
    html = re.sub(
        r'</(div|p|h3)>\s*\n?\s*</(div|p|h3)>',
        r'</\2>',
        html,
    )

    # ── ③ 修复多余的闭合标签（计数匹配）──
    for tag in ('div', 'p', 'h3', 'span'):
        opens = len(re.findall(rf'<{tag}[\s>]', html))
        closes = len(re.findall(rf'</{tag}>', html))
        excess = closes - opens
        while excess > 0:
            html = re.sub(rf'\s*</{tag}>\s*$', '', html)
            excess -= 1
        # Also handle missing closing tags at end
        while opens > closes:
            html += f'</{tag}>'
            closes += 1

    # ── ④ 折叠多余空行 ──
    html = re.sub(r'\n{3,}', '\n\n', html)

    # ── ⑤ 补齐外层 HTML 文档容器 ──
    max_width = '360px' if is_mobile else '780px'

    # 检测是否已有完整文档结构
    has_html_tag = bool(re.search(r'<!DOCTYPE|<html[\s>]', html, re.IGNORECASE))
    has_body_tag = bool(re.search(r'<body[\s>]', html, re.IGNORECASE))

    if not has_html_tag:
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Microsoft YaHei', 'PingFang SC', 'Helvetica Neue', Arial, sans-serif;
    color: #1a1a2e;
    background: #ffffff;
    max-width: {max_width};
    margin: 0 auto;
    padding: 20px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }}
  h2 {{ color: #1a1a2e; margin-bottom: 8px; }}
  h3 {{ color: #2a3a6e; margin-top: 12px; margin-bottom: 6px; }}
  p  {{ color: #333333; margin: 2px 0; }}
  li {{ color: #444444; line-height: 1.5; }}
  b  {{ color: #1a1a2e; }}
  .jd-matched {{ color: #2a6e3a !important; font-weight: 500; }}
  .jd-missing {{ color: #a04030 !important; font-weight: 500; }}
  .section-divider {{
    border-bottom: 1px solid #e0e0e0;
    margin-bottom: 10px;
    padding-bottom: 6px;
  }}
  @media (max-width: 400px) {{
    body {{ padding: 10px; font-size: 11px; }}
  }}
</style>
</head>
<body>
{html if not has_body_tag else html}
</body>
</html>'''
    elif not has_body_tag:
        # Has <html> but no <body> — wrap content
        html = html.replace('</html>', f'<body>\n{html}\n</body>\n</html>') if '</html>' in html else html

    return html


# ═══════════════════════════════════════════════════════════════
# HTML 安全转义
# ═══════════════════════════════════════════════════════════════

def _e(val: Any) -> str:
    """安全转字符串 + HTML 实体转义，防止标签注入破坏渲染。"""
    if val is None:
        return ""
    return html_mod.escape(str(val), quote=True)


# ═══════════════════════════════════════════════════════════════
# 双窗口预览渲染（主入口）
# ═══════════════════════════════════════════════════════════════

def render_dual_preview(resume_data: dict | None, lang: str = "zh"):
    """
    渲染电脑 + 手机双端简历预览。
    """
    t = lambda k: LanguageSwitch.t(k, lang)
    if not resume_data:
        st.info(t("sidebar_export_hint"))
        return

    resume = resume_data.get("resume", resume_data)

    col_desktop, col_phone = st.columns([3, 1.5])

    with col_desktop:
        st.markdown(f"**{t('preview_desktop')}**")
        html_raw = _render_resume_html(resume, lang, is_mobile=False)
        html_clean = _clean_html(html_raw, is_mobile=False)
        st.components.v1.html(html_clean, height=750, scrolling=True)

    with col_phone:
        st.markdown(f"**{t('preview_mobile')}**")
        html_raw = _render_resume_html(resume, lang, is_mobile=True)
        html_clean = _clean_html(html_raw, is_mobile=True)
        st.components.v1.html(html_clean, height=650, scrolling=True)


# ═══════════════════════════════════════════════════════════════
# 简历 HTML 片段生成（纯结构，不含外层容器）
# ═══════════════════════════════════════════════════════════════

def _render_resume_html(resume: dict, lang: str, is_mobile: bool = False) -> str:
    """
    根据简历数据构造 HTML 片段。

    返回的 HTML 是 Document Fragment（无外层 <html>/<body>），
    交给 _clean_html() 统一包裹外层容器。
    """
    t = lambda k: LanguageSwitch.t(k, lang)

    personal = resume.get("personal") or {}
    experience = resume.get("experience") or []
    education = resume.get("education") or []
    skills = resume.get("skills") or {}
    summary = resume.get("summary") or ""

    # 响应式字号
    title_size = "16px" if is_mobile else "22px"
    section_size = "13px" if is_mobile else "16px"
    body_size = "11px" if is_mobile else "14px"
    padding = "8px" if is_mobile else "14px"

    parts: list[str] = []

    # ── Header / 个人信息 ──
    salary_text = ""
    if personal.get('salary'):
        salary_text = f" | {t('preview_expected')}: {_e(personal.get('salary', ''))}"

    parts.append(f'''
<div style="text-align:center;padding:{padding};border-bottom:2px solid #2a3a6e;margin-bottom:{padding};">
  <h2 style="margin:0 0 4px 0;font-size:{title_size};color:#1a1a2e;letter-spacing:1px;">
    {_e(personal.get('name', ''))}
  </h2>
  <p style="margin:4px 0;font-size:{body_size};color:#555555;">
    {_e(personal.get('phone', ''))}
    {' | ' if personal.get('phone') and personal.get('email') else ''}
    {_e(personal.get('email', ''))}
    {' | ' if (personal.get('phone') or personal.get('email')) and personal.get('city') else ''}
    {_e(personal.get('city', ''))}
  </p>
  <p style="margin:4px 0 0 0;font-size:{body_size};color:#2a3a6e;font-weight:bold;">
    {_e(personal.get('target_job', ''))}{salary_text}
  </p>
</div>''')

    # ── 个人概述 ──
    if summary:
        parts.append(f'''
<div class="section-divider" style="padding:{padding};">
  <h3 style="font-size:{section_size};color:#2a3a6e;margin:0 0 4px 0;">
    {t("preview_section_summary")}
  </h3>
  <p style="font-size:{body_size};line-height:1.7;color:#333333;margin:0;">
    {_e(summary)}
  </p>
</div>''')

    # ── 工作经历 ──
    if experience:
        parts.append(f'''
<div class="section-divider" style="padding:{padding};">
  <h3 style="font-size:{section_size};color:#2a3a6e;margin:0 0 8px 0;">{t("preview_section_work")}</h3>''')

        max_items = 3 if is_mobile else 6
        for exp in experience[:max_items]:
            bullets_html = ""
            for b in (exp.get('bullets') or [])[:3]:
                bullets_html += (
                    f'<li style="font-size:{body_size};color:#444444;'
                    f'margin:2px 0 2px 18px;line-height:1.5;">{_e(b)}</li>'
                )

            relevance = _e(exp.get('jd_relevance', ''))
            relevance_color = "#2a6e3a" if relevance == "高" else "#888888"

            parts.append(f'''
  <div style="margin-bottom:{padding};">
    <div style="display:flex;justify-content:space-between;flex-wrap:wrap;align-items:baseline;">
      <b style="font-size:{body_size};color:#1a1a2e;">{_e(exp.get('position', ''))}</b>
      <span style="color:#888888;font-size:{body_size};">{_e(exp.get('period', ''))}</span>
    </div>
    <p style="font-size:{body_size};color:#555555;margin:2px 0;">
      {_e(exp.get('company', ''))}
      <span style="color:{relevance_color};font-size:11px;margin-left:4px;">
        [JD {('High' if relevance == '高' else 'Medium') if lang == 'en' else relevance}]
      </span>
    </p>
    {bullets_html}
  </div>''')

        parts.append('</div>')

    # ── 教育经历 ──
    if education:
        parts.append(f'''
<div class="section-divider" style="padding:{padding};">
  <h3 style="font-size:{section_size};color:#2a3a6e;margin:0 0 6px 0;">{t("preview_section_edu")}</h3>''')

        for edu in education[:2]:
            parts.append(f'''
  <p style="font-size:{body_size};color:#333333;margin:2px 0;line-height:1.6;">
    <b>{_e(edu.get('school', ''))}</b>
    {' | ' if edu.get('school') else ''}
    {_e(edu.get('major', ''))}
    {' | ' if edu.get('major') else ''}
    {_e(edu.get('degree', ''))}
    {' | ' if edu.get('degree') else ''}
    {_e(edu.get('period', ''))}
  </p>''')

        parts.append('</div>')

    # ── 技能证书 ──
    if skills:
        parts.append(f'''
<div style="padding:{padding};">
  <h3 style="font-size:{section_size};color:#2a3a6e;margin:0 0 6px 0;">{t("preview_section_skills")}</h3>''')

        for key, lk in [
            ("technical", "preview_tech"),
            ("languages", "preview_lang"),
            ("certificates", "preview_certs"),
        ]:
            label = t(lk)
            items = skills.get(key) or []
            if items:
                items_str = "、".join(_e(i) for i in items) if lang == "zh" else ", ".join(_e(i) for i in items)
                parts.append(
                    f'<p style="font-size:{body_size};color:#333333;margin:3px 0;">'
                    f'<b>{label}:</b> {items_str}</p>'
                )

        # JD 匹配 / 缺失
        matched = skills.get("jd_matched") or []
        missing = skills.get("jd_missing") or []
        if matched:
            items_str = "、".join(_e(i) for i in matched) if lang == "zh" else ", ".join(_e(i) for i in matched)
            parts.append(
                f'<p style="font-size:{body_size};color:#2a6e3a;margin:3px 0;" class="jd-matched">'
                f'✓ {t("preview_jd_match")}: {items_str}</p>'
            )
        if missing:
            items_str = "、".join(_e(i) for i in missing) if lang == "zh" else ", ".join(_e(i) for i in missing)
            parts.append(
                f'<p style="font-size:{body_size};color:#a04030;margin:3px 0;" class="jd-missing">'
                f'✗ {t("preview_jd_miss")}: {items_str}</p>'
            )

        parts.append('</div>')

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# 自我介绍渲染（保持不变 — 文字内容，无需 HTML 渲染）
# ═══════════════════════════════════════════════════════════════

def render_self_intro(self_intro: dict, lang: str = "zh"):
    """渲染自我介绍区域（纯文本，使用 text_area）"""
    if not self_intro:
        return
    si = self_intro.get(lang, self_intro.get("zh", {}))
    if not si:
        return

    st.markdown("### 🎤 自我介绍")
    text = si.get("text", "")
    seconds = si.get("estimated_seconds", 0)
    chars = si.get("char_count", 0)

    st.text_area(
        f"朗读时长约 {seconds} 秒 ({chars} 字)",
        value=text,
        height=120,
        key=f"self_intro_{lang}",
    )
