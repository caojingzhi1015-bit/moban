"""
common/language_switch.py — 中英文双语切换统一工具
全局双语控制，一键切换：UI、简历、自我介绍、面试对话同步切换语种
"""

from __future__ import annotations

from typing import Literal

Lang = Literal["zh", "en"]


class LanguageSwitch:
    """中英文双语切换单例 —— 全局统一翻译输出"""

    _lang: Lang = "zh"

    # ═════════════════════════════════════════════════════════
    # 完整翻译字典，覆盖所有业务模块的 UI 文本
    # ═════════════════════════════════════════════════════════

    DICT: dict[str, dict[Lang, str]] = {
        # ── 通用 ──
        "app_title":      {"zh": "CareerAI 求职助手", "en": "CareerAI - Job Assistant"},
        "no_data":        {"zh": "暂无数据", "en": "No data"},
        "please_input":   {"zh": "请先输入内容", "en": "Please input content first"},
        "extracting":     {"zh": "提取文字 + AI 解析中...", "en": "Extracting text + AI parsing..."},
        "generating":     {"zh": "生成中...", "en": "Generating..."},
        "extract_done":   {"zh": "解析完成", "en": "Parsing complete"},
        "generate_done":  {"zh": "生成完成", "en": "Generation complete"},
        "save":           {"zh": "保存", "en": "Save"},
        "export":         {"zh": "导出", "en": "Export"},
        "preview":        {"zh": "预览", "en": "Preview"},
        "upload":         {"zh": "上传文件", "en": "Upload File"},
        "loading":        {"zh": "加载中...", "en": "Loading..."},
        "confirm":        {"zh": "确认", "en": "Confirm"},
        "cancel":         {"zh": "取消", "en": "Cancel"},
        "back":           {"zh": "返回", "en": "Back"},
        "reset":          {"zh": "重置", "en": "Reset"},
        "download":       {"zh": "下载", "en": "Download"},
        "close":          {"zh": "关闭", "en": "Close"},
        "footer":         {"zh": "CareerAI 2026 | Python + Streamlit", "en": "CareerAI 2026 | Python + Streamlit"},

        # ── API Key ──
        "api_key_missing":{"zh": "未配置 API Key", "en": "API Key not configured"},
        "api_key_warning":{
            "zh": "⚠️ 未配置 API Key，面试使用本地模拟引擎。如需 AI 驱动的自然对话，请在环境变量中设置 `CAREERAI_API_KEY_DEEPSEEK=sk-xxx`。",
            "en": "⚠️ No API Key configured. Interview uses local simulation engine. Set `CAREERAI_API_KEY_DEEPSEEK=sk-xxx` for AI-powered conversation.",
        },
        "rate_limited":   {"zh": "请求频率过高，请稍后重试", "en": "Rate limited. Please try again later."},
        "api_error":      {"zh": "API 调用失败", "en": "API call failed"},

        # ── 文件解析 ──
        "file_parse_failed":  {"zh": "文件解析失败", "en": "File parsing failed"},
        "file_parse_error":   {"zh": "文件解析异常", "en": "File parsing error"},
        "file_empty":         {"zh": "文件上传失败：读取到空内容，请重新上传。", "en": "Upload failed: empty file. Please re-upload."},
        "ocr_unavailable":    {"zh": "OCR 不可用，请手动输入", "en": "OCR unavailable. Please type manually."},
        "scanned_pdf_hint":   {
            "zh": "⚠️ 当前PDF为扫描件/图片型PDF，无法自动提取文字。请将正文粘贴到左侧文本框。",
            "en": "⚠️ This PDF is a scanned/image-based file. Text cannot be auto-extracted. Please paste the content into the text box.",
        },
        "pdf_hint_jd": {
            "zh": "💡 电子文字PDF可自动解析；扫描照片PDF请直接粘贴正文文字，避免识别失败。",
            "en": "💡 Text-based PDFs are auto-parsed. For scanned/image PDFs, please paste the text below to avoid extraction failures.",
        },
        "pdf_hint_resume": {
            "zh": "💡 电子文字PDF/Word可自动解析；扫描照片PDF请直接粘贴正文文字，避免识别失败。",
            "en": "💡 Text-based PDF/Word files are auto-parsed. For scanned/image documents, please paste the text below.",
        },

        # ── 校验 ──
        "format_phone":   {"zh": "手机号格式异常", "en": "Invalid phone format"},
        "format_email":   {"zh": "邮箱格式异常", "en": "Invalid email format"},
        "time_conflict":  {"zh": "时间逻辑冲突", "en": "Timeline conflict"},
        "missing_field":  {"zh": "缺失必填字段", "en": "Missing required field"},
        "fabricated":     {"zh": "检测到虚构内容", "en": "Fabricated content detected"},
        "hallucination_blocked": {"zh": "检测到 AI 编造内容，已拦截", "en": "AI hallucination detected, blocked"},

        # ── 模块名称 ──
        "module_jd":      {"zh": "JD 解析", "en": "JD Parsing"},
        "module_resume":  {"zh": "简历解析", "en": "Resume Parsing"},
        "module_enquiry": {"zh": "缺口分析与追问", "en": "Gap Analysis & Questions"},
        "module_generate":{"zh": "简历生成", "en": "Generate Resume"},
        "module_interview":{"zh": "AI 模拟面试", "en": "AI Mock Interview"},
        "module_api":     {"zh": "API 网关", "en": "API Gateway"},

        # ── 简历字段 ──
        "field_name":     {"zh": "姓名", "en": "Name"},
        "field_phone":    {"zh": "电话", "en": "Phone"},
        "field_email":    {"zh": "邮箱", "en": "Email"},
        "field_city":     {"zh": "城市", "en": "City"},
        "field_education":{"zh": "教育经历", "en": "Education"},
        "field_work":     {"zh": "工作经历", "en": "Work Experience"},
        "field_projects": {"zh": "项目经历", "en": "Projects"},
        "field_skills":   {"zh": "技能", "en": "Skills"},
        "field_certs":    {"zh": "证书", "en": "Certificates"},
        "field_languages":{"zh": "语言能力", "en": "Languages"},
        "field_self_intro":{"zh": "自我评价", "en": "Self-Introduction"},
        "field_job":      {"zh": "目标岗位", "en": "Target Position"},
        "field_salary":   {"zh": "期望薪资", "en": "Expected Salary"},

        # ── JD 字段 ──
        "jd_position":    {"zh": "岗位", "en": "Position"},
        "jd_skills":      {"zh": "技能", "en": "Skills"},

        # ── 简历预览 ──
        "preview_desktop":  {"zh": "💻 电脑端预览", "en": "💻 Desktop Preview"},
        "preview_mobile":   {"zh": "📱 手机端预览", "en": "📱 Mobile Preview"},
        "preview_section_summary": {"zh": "个人概述", "en": "Professional Summary"},
        "preview_section_work":    {"zh": "工作经历", "en": "Work Experience"},
        "preview_section_edu":     {"zh": "教育经历", "en": "Education"},
        "preview_section_skills":  {"zh": "技能证书", "en": "Skills & Certificates"},
        "preview_tech":     {"zh": "技术栈", "en": "Tech Stack"},
        "preview_certs":    {"zh": "证书", "en": "Certificates"},
        "preview_lang":     {"zh": "语言", "en": "Languages"},
        "preview_jd_match": {"zh": "JD 匹配", "en": "JD Match"},
        "preview_jd_miss":  {"zh": "JD 缺失", "en": "JD Gap"},
        "preview_expected": {"zh": "期望薪资", "en": "Expected"},
        "preview_salary":   {"zh": "期望薪资", "en": "Expected Salary"},

        # ── 追问 ──
        "enquiry_title":      {"zh": "缺口分析与追问", "en": "Gap Analysis & Questions"},
        "enquiry_find_gaps":  {"zh": "分析缺口", "en": "Find Gaps"},
        "enquiry_analyzing":  {"zh": "AI 分析 JD 与简历差异...", "en": "AI analyzing JD vs resume gaps..."},
        "enquiry_answer":     {"zh": "回答", "en": "Answer"},

        # ── 简历生成 ──
        "gen_title":      {"zh": "生成简历", "en": "Generate Resume"},
        "gen_button":     {"zh": "生成简历 + 自我介绍", "en": "Generate Resume + Self-Intro"},
        "gen_done":       {"zh": "简历已生成！", "en": "Resume generated!"},
        "gen_preview_tab":{"zh": "简历预览", "en": "Resume Preview"},
        "gen_intro_tab":  {"zh": "自我介绍", "en": "Self-Intro"},

        # ── 自我介绍 ──
        "intro_title":    {"zh": "🎤 自我介绍", "en": "🎤 Self-Introduction"},
        "intro_reading_time": {"zh": "朗读时长约 {} 秒 ({} 字)", "en": "Reading time ~{}s ({} chars)"},

        # ── 面试 ──
        "interview_title":      {"zh": "AI 模拟面试", "en": "AI Mock Interview"},
        "interview_start":      {"zh": "开始面试", "en": "Start Interview"},
        "interview_starting":   {"zh": "开始面试 ({persona})", "en": "Start Interview ({persona})"},
        "interview_placeholder":{
            "zh": "输入你的回答...（输入「继续」跳过当前话题）",
            "en": "Your answer... (type 'continue' or 'next' to skip topic)",
        },
        "interview_thinking":   {"zh": "面试官思考中...", "en": "Interviewer is thinking..."},
        "interview_report_btn": {"zh": "生成面试评估报告", "en": "Generate Interview Report"},
        "interview_report_title":{"zh": "面试评估报告", "en": "Interview Report"},
        "interview_analyzing":  {"zh": "分析中...", "en": "Analyzing..."},
        "interview_reset":      {"zh": "重置面试", "en": "Reset Interview"},
        "interview_no_jd":      {"zh": "请先解析 JD 和简历，再开始面试", "en": "Parse JD and Resume first, then start the interview"},
        "interview_phase":      {"zh": "面试阶段", "en": "Interview Phase"},
        "interview_hr_label":   {"zh": "HR", "en": "HR"},
        "interview_tech_label": {"zh": "Tech", "en": "Tech"},
        "interview_stress_label":{"zh": "Stress", "en": "Stress"},
        "interview_english_label":{"zh": "English", "en": "English"},

        # ── 侧边栏 ──
        "sidebar_lang":   {"zh": "语言", "en": "LANGUAGE"},
        "sidebar_model":  {"zh": "AI 模型", "en": "AI MODEL"},
        "sidebar_interviewer": {"zh": "面试官", "en": "INTERVIEWER"},
        "sidebar_export": {"zh": "导出", "en": "EXPORT"},
        "sidebar_export_hint": {"zh": "先生成简历后可导出", "en": "Generate a resume first"},
        "sidebar_export_btn":  {"zh": "下载 Word + PDF", "en": "Download Word + PDF"},

        # ── 导出 ──
        "export_word_ok": {"zh": "Word 导出成功", "en": "Word exported"},
        "export_pdf_ok":  {"zh": "PDF 导出成功", "en": "PDF exported"},
        "exporting":      {"zh": "导出中...", "en": "Exporting..."},

        # ── JD / 简历上传 ──
        "or_paste_jd":    {"zh": "或粘贴 JD 文本", "en": "Or paste JD text"},
        "or_paste_resume":{"zh": "或粘贴简历文本", "en": "Or paste resume text"},
        "placeholder_jd": {"zh": "在此粘贴岗位描述...\n\n如果PDF为扫描件/图片型，请将JD文字粘贴到此处。", "en": "Paste job description here...\n\nFor scanned/image PDFs, paste JD text here."},
        "placeholder_resume": {"zh": "在此粘贴简历内容...\n\n如果PDF为扫描件/图片型，请将简历文字粘贴到此处。", "en": "Paste resume content here...\n\nFor scanned/image PDFs, paste resume text here."},
        "btn_parse_jd":   {"zh": "解析 JD", "en": "Parse JD"},
        "btn_parse_resume":{"zh": "解析简历", "en": "Parse Resume"},
        "parse_done_jd":  {"zh": "✅ JD 解析完成", "en": "✅ JD Parsed"},
        "parse_done_resume":{"zh": "✅ 简历解析完成", "en": "✅ Resume Parsed"},
        "parse_failed":   {"zh": "解析失败", "en": "Parse failed"},
        "parse_warning_scanned": {"zh": "请将正文粘贴到上方文本框中。", "en": "Please paste content into the text box above."},
        "upload_or_paste": {"zh": "请上传文件或粘贴文本", "en": "Please upload a file or paste text"},
    }

    # ═════════════════════════════════════════════════════════
    # API
    # ═════════════════════════════════════════════════════════

    @classmethod
    def t(cls, key: str, lang: Lang | None = None, **fmt) -> str:
        """
        获取翻译文本。
        - key 不存在时返回 key 本身
        - 支持 str.format(**fmt) 传参
        """
        entry = cls.DICT.get(key)
        if not entry:
            return key
        text = entry.get(lang or cls._lang, entry.get("zh", key))
        if fmt:
            text = text.format(**fmt)
        return text

    @classmethod
    def set_lang(cls, lang: Lang) -> None:
        cls._lang = lang

    @classmethod
    def get_lang(cls) -> Lang:
        return cls._lang

    @classmethod
    def is_zh(cls) -> bool:
        return cls._lang == "zh"
