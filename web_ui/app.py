"""
web_ui/app.py — CareerAI 求职助手 (Streamlit)
纯 Python，深色主题 + 液态银粒子 + 左右双栏布局
"""

import sys
import os
import json
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# ═══════════════════════════════════════════════════════════════
# API Key 加载 — 统一入口（优先 st.secrets，兜底 .env / 环境变量）
# 策略：直接注入 os.environ，Gateway.__init__ 自带 _load_api_keys_from_env()
# ═══════════════════════════════════════════════════════════════

# Step 1: 加载 .env 文件（本地开发）
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    if _env_path.exists():
        _load_dotenv(_env_path, override=False)
except Exception:
    pass

# Step 2: 从 Streamlit Secrets 注入 os.environ（Streamlit Cloud）
# 注意：此时 st 尚未初始化，必须用延迟回调。这里只定义函数，由 get_gateway() 调用。
_KEYS_INJECTED = False

_SECRET_ENV_MAP = {
    "CAREERAI_API_KEY_DEEPSEEK": "deepseek",
    "CAREERAI_API_KEY_DOUBAO": "doubao",
    "CAREERAI_API_KEY_GEMINI": "gemini",
    "CAREERAI_API_KEY_CLAUDE": "claude",
    "CAREERAI_API_KEY_CHATGPT": "gpt",
}

def _inject_secrets_to_env():
    """将 st.secrets 中的 API Key 同步到 os.environ（幂等，仅执行一次）。"""
    global _KEYS_INJECTED
    if _KEYS_INJECTED:
        return
    _KEYS_INJECTED = True

    import streamlit as st
    injected = []
    for env_var in _SECRET_ENV_MAP:
        val = ""
        try:
            # st.secrets 支持 [] 访问和属性访问，但不一定有 .get()
            val = st.secrets[env_var]
        except Exception:
            try:
                val = getattr(st.secrets, env_var, "")
            except Exception:
                pass
        val = str(val).strip() if val else ""
        if val and not os.environ.get(env_var, "").strip():
            os.environ[env_var] = val
            injected.append(env_var)
    if injected:
        print(f"[API] Injected from st.secrets: {injected}")

import streamlit as st

from common.language_switch import LanguageSwitch


# ── 安全异步执行（兼容 Streamlit 事件循环）──

def _run_async(coro):
    """
    在 Streamlit 回调中安全执行异步函数。

    Streamlit 1.28+ 在部分场景有自己的事件循环，
    此时 asyncio.run() 会在当前线程抛出 RuntimeError。

    策略:
      1. 尝试直接 asyncio.run() —— 适用于无事件循环的线程
      2. RuntimeError → 用线程池在新线程中执行（绕过事件循环冲突）
      3. 所有异常透传，让调用方处理 UI 展示
    """
    import concurrent.futures
    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        if "event loop" in str(e).lower() or "cannot be called" in str(e).lower():
            # 已有事件循环（Streamlit 内部线程）→ 用线程池隔离
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        raise
    except Exception:
        # 业务异常直接透传
        raise

from common.multi_model_gateway import MultiModelGateway
from common.ocr_pdf_processor import OcrPdfProcessor
from common.module_loader import load_attr

JDParser = load_attr("01_jd_parser.main.JDParser")
ResumeParser = load_attr("02_resume_parser.main.ResumeParser")
InfoEnquiryAgent = load_attr("03_info_enquiry_agent.main.InfoEnquiryAgent")
TargetResumeGenerator = load_attr("04_target_resume_generator.main.TargetResumeGenerator")
export_resume = load_attr("04_target_resume_generator.word_pdf_exporter.export_resume")
AIInterviewer = load_attr("05_ai_interviewer.main.AIInterviewer")

from web_ui.resume_preview import render_dual_preview, render_self_intro

# ── Page Config ──
st.set_page_config(
    page_title="CareerAI - Job Assistant",
    page_icon="[CA]",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS: fixed sidebar 260px + dark glass theme + particle fix ──
STYLE_CSS = """
/* Fixed sidebar width 260px */
[data-testid="stSidebar"] {
    min-width: 260px !important;
    max-width: 260px !important;
    background: rgba(10, 10, 22, 0.92) !important;
    backdrop-filter: blur(20px);
    border-right: 1px solid rgba(100, 120, 170, 0.15);
}
[data-testid="stSidebar"] > div:first-child {
    padding: 16px 12px;
}

/* Main content padding */
.main .block-container {
    padding: 1rem 2rem !important;
    max-width: 100% !important;
}

/* Dark background */
.stApp {
    background: linear-gradient(135deg, #0a0a12 0%, #10101c 40%, #0d0d18 70%, #0a0a12 100%) !important;
}

/* Glass cards */
.glass-card {
    background: rgba(18, 18, 35, 0.7) !important;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(110, 120, 160, 0.18);
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.03);
    color: #d0d4e8;
}

/* Inputs - dark, taller */
.stTextInput input, .stTextArea textarea, .stSelectbox > div {
    background: rgba(12, 12, 26, 0.85) !important;
    border: 1px solid rgba(100, 115, 160, 0.25) !important;
    border-radius: 10px !important;
    color: #d8dcef !important;
    min-height: 44px !important;
}
.stTextArea textarea {
    min-height: 150px !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
}

/* Buttons - wider, more spacing */
.stButton > button {
    background: linear-gradient(135deg, rgba(55, 75, 135, 0.55), rgba(35, 50, 95, 0.55)) !important;
    border: 1px solid rgba(130, 150, 200, 0.35) !important;
    border-radius: 12px !important;
    color: #d0d8f0 !important;
    min-height: 44px !important;
    font-size: 15px !important;
    padding: 8px 20px !important;
    transition: all 0.25s ease;
    width: 100% !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, rgba(75, 95, 160, 0.65), rgba(50, 65, 115, 0.65)) !important;
    border-color: rgba(160, 180, 230, 0.5) !important;
    box-shadow: 0 0 20px rgba(90, 120, 190, 0.2);
}

/* Expander */
.stExpander {
    background: rgba(15, 15, 30, 0.6) !important;
    border: 1px solid rgba(100, 115, 160, 0.15) !important;
    border-radius: 12px !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(15, 15, 28, 0.5) !important;
    border-radius: 12px !important;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    color: #888aab !important;
    border-radius: 10px !important;
    font-size: 14px !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: rgba(55, 75, 135, 0.35) !important;
    color: #c0d0f0 !important;
}

/* Labels and text */
.stMarkdown, .stCaption {
    color: #b8c0d8 !important;
}
h1, h2, h3 {
    color: #c8d4f0 !important;
}

/* Radio buttons */
.stRadio [data-baseweb="radio"] {
    gap: 8px;
}

/* Particle container - below everything */
#liquid-silver-bg {
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    z-index: -999;
    overflow: hidden;
    pointer-events: none;
}
.liquid-particle {
    position: absolute;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, rgba(170,185,210,0.3), rgba(120,135,165,0.08), transparent);
    box-shadow: 0 0 6px rgba(150,165,195,0.15);
    animation: floatUp var(--duration) var(--delay) linear infinite;
    opacity: 0;
    pointer-events: none;
}
@keyframes floatUp {
    0% { transform: translateY(105vh) translateX(0px) scale(0.3); opacity: 0; }
    5% { opacity: 0.3; }
    40% { transform: translateY(55vh) translateX(var(--drift2)) scale(0.8); opacity: 0.25; }
    70% { transform: translateY(25vh) translateX(var(--drift3)) scale(0.5); opacity: 0.12; }
    100% { transform: translateY(-5vh) translateX(var(--drift4)) scale(0.15); opacity: 0; }
}
.liquid-stream {
    position: absolute;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(130,150,180,0.15), rgba(160,175,200,0.25), rgba(130,150,180,0.15), transparent);
    animation: streamDrift var(--stream-duration) var(--stream-delay) linear infinite;
    opacity: 0;
    pointer-events: none;
}
@keyframes streamDrift {
    0% { transform: translateX(-120%) translateY(var(--stream-y)); opacity: 0; }
    10% { opacity: 0.25; }
    50% { opacity: 0.15; }
    90% { opacity: 0.03; }
    100% { transform: translateX(120%) translateY(calc(var(--stream-y) + 200px)); opacity: 0; }
}
.particle-xs { width: 3px; height: 3px; }
.particle-sm { width: 5px; height: 5px; }
.particle-md { width: 8px; height: 8px; }
.particle-lg { width: 12px; height: 12px; }
"""

def inject_css():
    """注入 CSS + 粒子背景"""
    # 粒子 HTML
    parts = '<div id="liquid-silver-bg">'
    sizes = ["particle-xs","particle-sm","particle-md","particle-lg"]
    import random; random.seed(42)
    for i in range(50):
        sz = sizes[i%4]
        parts += f'<div class="liquid-particle {sz}" style="left:{(i*17+3)%100}%;--duration:{8+(i%7)*2}s;--delay:{(i*0.7)%10}s;--drift1:{(i%11-5)*8}px;--drift2:{(i%9-4)*12}px;--drift3:{(i%7-3)*10}px;--drift4:{(i%13-6)*6}px;"></div>'
    for i in range(8):
        y = (i*73+15)%100
        parts += f'<div class="liquid-stream" style="top:{y}%;width:40%;left:30%;--stream-duration:{12+(i%5)*3}s;--stream-delay:{(i*1.5)%8}s;--stream-y:{y}px;"></div>'
    parts += '</div>'

    st.markdown(f"<style>{STYLE_CSS}</style>{parts}", unsafe_allow_html=True)

inject_css()

# ── Session State ──
DEFAULTS = {
    "lang":"zh","jd_raw_text":"","jd_parsed":None,"resume_raw_text":"",
    "resume_parsed":None,"questions":[],"question_answers":{},
    "generated_result":None,"interviewer":None,"interview_messages":[],
    "interview_persona":"hr",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# 同步 LanguageSwitch 类变量与 Streamlit session state（解决 Streamlit 重跑时类变量重置问题）
LanguageSwitch.set_lang(st.session_state.lang)

PERSONA_LABELS = {"hr":"HR","tech":"Tech","stress":"Stress","english":"English"}
t = lambda key, **fmt: LanguageSwitch.t(key, st.session_state.lang, **fmt)

# ── Gateway（缓存 + 自动注入 st.secrets）──
@st.cache_resource
def get_gateway() -> MultiModelGateway:
    """获取网关实例（Streamlit 缓存），首次调用时注入 st.secrets 到环境变量"""
    _inject_secrets_to_env()  # 同步 st.secrets → os.environ（一次）
    return MultiModelGateway()  # __init__ 自带 _load_api_keys_from_env()

def _check_api_status() -> bool:
    """检查是否有至少一个 API Key 已配置"""
    try:
        gw = get_gateway()
        return any(gw.validate_api_keys().values())
    except Exception:
        return False

# ═══════════════════════════════════════════════════
# SIDEBAR - 260px fixed, high-contrast glass design
# ═══════════════════════════════════════════════════
SIDEBAR_CSS = """
<style>
/* --- Sidebar glass card wrapper --- */
.sb-card {
    background: rgba(22,22,42,0.75);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(110,120,165,0.2);
    border-radius: 14px;
    padding: 14px 12px;
    margin-bottom: 12px;
}
.sb-title {
    color: #FFFFFF !important;
    font-size: 14px;
    font-weight: 700;
    margin: 0 0 10px 0;
    letter-spacing: 0.5px;
}
.sb-divider {
    height: 1px;
    background: rgba(130,145,180,0.2);
    margin: 10px 0 14px 0;
}

/* --- Language toggle buttons --- */
.lang-toggle { display:flex; gap:0; border-radius:10px; overflow:hidden; width:100%; }
.lang-btn {
    flex:1; text-align:center; padding:8px 0; font-size:14px; font-weight:700;
    cursor:pointer; border:none; transition:all 0.2s; outline:none;
}
.lang-btn.active {
    background:#E8710A; color:#FFFFFF; font-weight:800;
    box-shadow: 0 0 12px rgba(232,113,10,0.4);
}
.lang-btn.inactive {
    background:rgba(50,50,70,0.7); color:#777799;
    border:1px solid rgba(100,110,140,0.25);
}
.lang-btn:hover.inactive { color:#aaaacc; }

/* --- Selectbox card style --- */
.sb-select-label {
    color: #FFFFFF !important;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 4px;
}
div[data-testid="stSelectbox"] > div > div {
    background: rgba(48,50,72,0.85) !important;
    border: 1px solid rgba(130,145,180,0.35) !important;
    border-radius: 10px !important;
}
div[data-testid="stSelectbox"] label {
    color: #FFFFFF !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}
div[data-testid="stSelectbox"] [data-baseweb="select"] {
    background: rgba(48,50,72,0.85) !important;
}
div[data-testid="stSelectbox"] [data-baseweb="select"] input {
    color: #F2F2F2 !important;
}

/* --- Sidebar button --- */
[data-testid="stSidebar"] .stButton > button {
    background: rgba(50,55,80,0.8) !important;
    border: 1px solid rgba(130,145,180,0.3) !important;
    color: #e0e4f4 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}
.sidebar .stButton > button:hover {
    background: rgba(65,70,100,0.85) !important;
    border-color: rgba(160,175,210,0.5) !important;
}
</style>
"""
st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)

with st.sidebar:
    # ── 1. Language ──
    st.markdown('<div class="sb-card">', unsafe_allow_html=True)
    st.markdown(f'<p class="sb-title">{t("sidebar_lang")}</p>', unsafe_allow_html=True)

    is_zh = st.session_state.lang == "zh"
    c_zh, c_en = st.columns(2)
    with c_zh:
        if st.button(
            "● ZH" if is_zh else "  ZH",
            key="lang_zh", use_container_width=True,
            type="primary" if is_zh else "secondary",
        ):
            if not is_zh:
                st.session_state.lang = "zh"
                LanguageSwitch.set_lang("zh")
                st.rerun()
    with c_en:
        if st.button(
            "● EN" if not is_zh else "  EN",
            key="lang_en", use_container_width=True,
            type="primary" if not is_zh else "secondary",
        ):
            if is_zh:
                st.session_state.lang = "en"
                LanguageSwitch.set_lang("en")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # ── 2. API Key 输入（用户自带 Key）──
    st.markdown('<div class="sb-card">', unsafe_allow_html=True)
    st.markdown(f'<p class="sb-title">🔑 API KEY</p>', unsafe_allow_html=True)

    # 选择 AI 提供商
    api_provider = st.selectbox(
        "AI Provider",
        ["deepseek", "doubao", "gpt", "claude", "gemini"],
        format_func=lambda x: {
            "deepseek": "DeepSeek (推荐/便宜)",
            "doubao": "Doubao (豆包)",
            "gpt": "GPT-4o",
            "claude": "Claude",
            "gemini": "Gemini",
        }.get(x, x),
        label_visibility="collapsed",
        key="sidebar_api_provider",
    )

    # API Key 输入框
    env_key_name = f"CAREERAI_API_KEY_{api_provider.upper()}"
    current_val = os.environ.get(env_key_name, "")

    user_key = st.text_input(
        "输入你的 API Key",
        type="password",
        value=current_val[:8] + "..." + current_val[-4:] if current_val and len(current_val) > 12 else current_val,
        placeholder="sk-xxxxxxxxxxxxxxxx",
        label_visibility="collapsed",
        key="sidebar_api_key_input",
    )

    # 点击 Apply 生效
    if st.button("🔗 应用 Key", key="btn_apply_key", use_container_width=True):
        if user_key and not user_key.startswith("sk-...") and len(user_key) > 10:
            os.environ[env_key_name] = user_key
            # 清除 gateway 缓存（如果有的话）
            st.cache_resource.clear()
            st.success(f"✅ {api_provider} Key 已生效！")
            st.rerun()
        elif user_key and "..." in user_key:
            st.info("Key 已在使用中")
        else:
            st.warning("请输入有效的 API Key")

    # 状态显示
    if _check_api_status():
        gw = get_gateway()
        configured = [k for k, v in gw.validate_api_keys().items() if v]
        st.success(f"✅ 已连接: {', '.join(configured)}")
    else:
        st.warning("⚠️ 请粘贴你的 API Key")
        st.caption("💡 [获取免费 DeepSeek Key](https://platform.deepseek.com/api_keys)")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── 3. Model ──
    st.markdown('<div class="sb-card">', unsafe_allow_html=True)
    st.markdown(f'<p class="sb-title">{t("sidebar_model")}</p>', unsafe_allow_html=True)
    model_choice = st.selectbox(
        "Select model",
        ["deepseek_lite","deepseek_enhanced","doubao","gpt","claude","gemini"],
        format_func=lambda x: {
            "deepseek_lite":"DeepSeek Lite",
            "deepseek_enhanced":"DeepSeek Pro",
            "doubao":"Doubao",
            "gpt":"GPT-4o",
            "claude":"Claude",
            "gemini":"Gemini",
        }.get(x,x),
        label_visibility="collapsed",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # ── 4. Interviewer ──
    st.markdown('<div class="sb-card">', unsafe_allow_html=True)
    st.markdown(f'<p class="sb-title">{t("sidebar_interviewer")}</p>', unsafe_allow_html=True)
    persona = st.selectbox(
        "Select persona",
        ["hr","tech","stress","english"],
        format_func=lambda x: PERSONA_LABELS.get(x,x),
        label_visibility="collapsed",
    )
    st.session_state.interview_persona = persona
    st.markdown("</div>", unsafe_allow_html=True)

    # ── 5. Export ──
    st.markdown('<div class="sb-card">', unsafe_allow_html=True)
    st.markdown(f'<p class="sb-title">{t("sidebar_export")}</p>', unsafe_allow_html=True)
    if st.session_state.generated_result:
        if st.button(t("sidebar_export_btn"), key="btn_export", use_container_width=True):
            with st.spinner(t("exporting")):
                paths = export_resume(
                    st.session_state.generated_result, "./exports",
                    f"resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                )
            st.success(f"Word: {paths['word']}")
            st.success(f"PDF: {paths['pdf']}")
    else:
        st.caption(t("sidebar_export_hint"))
    st.markdown("</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════
# MAIN PAGE - Dual Column Layout
# ═══════════════════════════════════════════════════

st.markdown("""
<div style="text-align:center;padding:10px 0;">
  <h1 style="font-size:2.2rem;margin:0;background:linear-gradient(135deg,#8899cc,#aabbee,#8899cc);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">
    CareerAI
  </h1>
</div>
""", unsafe_allow_html=True)

# ── Module 1: JD + Resume Upload (2-col) ──
st.markdown('<div class="glass-card">', unsafe_allow_html=True)

col_jd, col_resume = st.columns(2)

with col_jd:
    st.markdown(f"### {t('module_jd')}")
    jd_file = st.file_uploader(t("module_jd") + " (image/PDF/txt)", type=["png","jpg","jpeg","pdf","txt"], key="jd_up")
    st.caption(t("pdf_hint_jd"))
    jd_text = st.text_area(t("or_paste_jd"), value=st.session_state.jd_raw_text, height=160, key="jd_txt",
                           placeholder=t("placeholder_jd"))

    if st.button(t("btn_parse_jd"), key="btn_jd", use_container_width=True):
        if jd_file or jd_text.strip():
            with st.spinner(t("extracting")):
                input_data = None
                tmp_path = None
                if jd_file:
                    # 稳健写入：先保存到服务器临时目录，避免 Streamlit 内存字节流空内容 BUG
                    file_bytes = jd_file.read()
                    if not file_bytes:
                        st.error("文件上传失败：读取到空内容，请重新上传。")
                    else:
                        suffix = f".{jd_file.name.split('.')[-1]}" if "." in jd_file.name else ""
                        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
                        with open(tmp_fd, "wb") as f:
                            f.write(file_bytes)
                        input_data = tmp_path
                elif jd_text.strip():
                    input_data = jd_text.strip()
                if input_data:
                    try:
                        gateway = get_gateway()
                        result = _run_async(JDParser.parse(input_data, gateway=gateway, lang=st.session_state.lang))
                        st.session_state.jd_parsed = result
                        st.session_state.jd_raw_text = result.get("_raw_text","")
                        st.success(t("parse_done_jd"))
                    except RuntimeError as e:
                        msg = str(e)
                        if "解析失败" in msg or "扫描件" in msg or "图片型" in msg:
                            st.warning(f"{msg}\n\n💡 {t('parse_warning_scanned')}")
                        else:
                            st.error(f"{t('parse_failed')}: {e}")
                    except Exception as e:
                        st.error(f"{t('file_parse_error')}: {e}")
                # 清理临时文件
                if tmp_path and Path(tmp_path).exists():
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
        else:
            st.warning(t("upload_or_paste"))

    if st.session_state.jd_parsed:
        jd = st.session_state.jd_parsed
        st.info(f"{t('jd_position')}: {jd.get('position','?')} | {t('jd_skills')}: {', '.join(jd.get('hard_skills',[])[:6])}")

with col_resume:
    st.markdown(f"### {t('module_resume')}")
    resume_file = st.file_uploader(t("module_resume") + " (image/PDF/docx/txt)", type=["png","jpg","jpeg","pdf","docx","doc","txt"], key="cv_up")
    st.caption(t("pdf_hint_resume"))
    resume_text = st.text_area(t("or_paste_resume"), value=st.session_state.resume_raw_text, height=160, key="cv_txt",
                               placeholder=t("placeholder_resume"))

    if st.button(t("btn_parse_resume"), key="btn_cv", use_container_width=True):
        if resume_file or resume_text.strip():
            with st.spinner(t("extracting")):
                input_data = None
                tmp_path = None
                if resume_file:
                    file_bytes = resume_file.read()
                    if not file_bytes:
                        st.error("文件上传失败：读取到空内容，请重新上传。")
                    else:
                        suffix = f".{resume_file.name.split('.')[-1]}" if "." in resume_file.name else ""
                        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
                        with open(tmp_fd, "wb") as f:
                            f.write(file_bytes)
                        input_data = tmp_path
                elif resume_text.strip():
                    input_data = resume_text.strip()
                if input_data:
                    try:
                        gateway = get_gateway()
                        result = _run_async(ResumeParser.parse(input_data, gateway=gateway, lang=st.session_state.lang))
                        st.session_state.resume_parsed = result
                        st.session_state.resume_raw_text = result.get("_raw_text","")
                        st.success(t("parse_done_resume"))
                    except RuntimeError as e:
                        msg = str(e)
                        if "解析失败" in msg or "扫描件" in msg or "图片型" in msg:
                            st.warning(f"{msg}\n\n💡 {t('parse_warning_scanned')}")
                        else:
                            st.error(f"{t('parse_failed')}: {e}")
                    except Exception as e:
                        st.error(f"{t('file_parse_error')}: {e}")
                # 清理临时文件
                if tmp_path and Path(tmp_path).exists():
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
        else:
            st.warning(t("upload_or_paste"))

    if st.session_state.resume_parsed:
        rp = st.session_state.resume_parsed
        bi = rp.get("basic_info",{})
        st.info(f"{t('field_name')}: {bi.get('name','?')} | {t('field_work')}: {len(rp.get('work_experience',[]))} | {t('field_projects')}: {len(rp.get('projects',[]))}")

st.markdown("</div>", unsafe_allow_html=True)

# ── Module 2: Enquiry ──
if st.session_state.jd_parsed and st.session_state.resume_parsed:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(f"### {t('module_enquiry')}")
    if st.button(t("enquiry_find_gaps"), key="btn_enq"):
        with st.spinner(t("enquiry_analyzing")):
            gateway = get_gateway()
            st.session_state.questions = InfoEnquiryAgent.generate_questions(
                st.session_state.jd_parsed, st.session_state.resume_parsed,
                lang=st.session_state.lang, gateway=gateway)
    for i, q in enumerate(st.session_state.questions):
        with st.expander(f"Q{i+1}: {q['question'][:80]}...", expanded=(i==0)):
            st.markdown(f"**{q['question']}**")
            ans = st.text_area(t("enquiry_answer") + ":", key=f"ans_{i}", height=70)
            if ans.strip():
                st.session_state.question_answers[i] = {"question":q, "answer":ans.strip()}
    st.markdown("</div>", unsafe_allow_html=True)

# ── Module 3: Resume Gen + Preview ──
if st.session_state.jd_parsed and st.session_state.resume_parsed:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown(f"### {t('module_generate')}")
    if st.button(t("gen_button"), key="btn_gen", use_container_width=True):
        extra = {}
        if st.session_state.question_answers:
            extra["qa_entries"] = list(st.session_state.question_answers.values())
        result = TargetResumeGenerator.generate(
            st.session_state.jd_parsed, st.session_state.resume_parsed,
            extra_info=extra if extra else None, lang=st.session_state.lang)
        st.session_state.generated_result = result
        st.success(t("gen_done"))
    if st.session_state.generated_result:
        tab1, tab2 = st.tabs([t("gen_preview_tab"), t("gen_intro_tab")])
        with tab1:
            render_dual_preview(st.session_state.generated_result, st.session_state.lang)
        with tab2:
            si = st.session_state.generated_result.get("self_intro",{})
            c1, c2 = st.columns(2)
            with c1: render_self_intro(si, "zh")
            with c2: render_self_intro(si, "en")
    st.markdown("</div>", unsafe_allow_html=True)

# ── Module 4: Interview ──
st.markdown('<div class="glass-card">', unsafe_allow_html=True)
st.markdown(f"### {t('module_interview')}")

# API Key 状态检查（带详细反馈）
gw_status = get_gateway()
api_keys_ok = _check_api_status()
if not api_keys_ok:
    st.error(
        "🔑 **未检测到 API Key！**\n\n"
        "👈 **在左侧边栏粘贴你的 API Key 即可使用**\n\n"
        "💡 免费获取 DeepSeek Key: https://platform.deepseek.com/api_keys"
    )
else:
    configured = [k for k, v in gw_status.validate_api_keys().items() if v]
    st.success(f"✅ API 已连接: {', '.join(configured)}")

if st.session_state.jd_parsed and st.session_state.resume_parsed:
    ci, cr = st.columns([3,1])
    with ci:
        persona_label = PERSONA_LABELS.get(st.session_state.interview_persona, "HR")
        if st.button(f"{t('interview_starting')} ({persona_label})", key="btn_intv"):
            interviewer = AIInterviewer()
            interviewer.init_session(st.session_state.jd_parsed, st.session_state.resume_parsed,
                                     persona=st.session_state.interview_persona)
            st.session_state.interviewer = interviewer
            st.session_state.interview_messages = [
                {"role":"assistant","content":interviewer.get_opening(st.session_state.interview_persona, st.session_state.lang)}]
    with cr:
        if st.button(t("reset"), key="btn_rst"):
            st.session_state.interviewer = None
            st.session_state.interview_messages = []
            st.rerun()

    # 用 st.chat_message 展示对话
    for msg in st.session_state.interview_messages:
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar="🎯"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg["content"])

    # 使用 st.chat_input（Streamlit 原生聊天组件，自动处理 rerun，无需手动按钮）
    if st.session_state.interviewer:
        prompt = st.chat_input(t("interview_placeholder"))
        if prompt and prompt.strip():
            answer = prompt.strip()
            with st.spinner(t("interview_thinking")):
                try:
                    gateway = get_gateway()
                    res = _run_async(st.session_state.interviewer.chat(
                        answer, gateway=gateway,
                        persona=st.session_state.interview_persona,
                        lang=st.session_state.lang))
                    st.session_state.interview_messages.append({"role":"user","content":answer})
                    st.session_state.interview_messages.append({"role":"assistant","content":res["reply"]})
                except Exception as e:
                    st.session_state.interview_messages.append({"role":"user","content":answer})
                    st.session_state.interview_messages.append({"role":"assistant","content":f"[系统异常: {e}]"})
            st.rerun()

        # Generate Report 按钮（对话 >= 4 轮后出现）
        if len(st.session_state.interview_messages) >= 4:
            if st.button(t("interview_report_btn"), key="btn_rpt"):
                with st.spinner(t("interview_analyzing")):
                    gateway = get_gateway()
                    report = _run_async(st.session_state.interviewer.generate_report(gateway, lang=st.session_state.lang))
                    st.markdown(f"### {t('interview_report_title')}")
                    st.markdown(report.get("report","Failed"))
else:
    st.info(t("interview_no_jd"))
st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown(f"""<div style="text-align:center;padding:30px;color:#445566;">{t("footer")}</div>""", unsafe_allow_html=True)
