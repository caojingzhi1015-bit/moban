"""
streamlit_app.py — Streamlit Cloud 入口（重定向到 web_ui/app.py）
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

# 运行实际的 Streamlit 应用
import runpy
runpy.run_path(str(Path(__file__).parent / "web_ui" / "app.py"))
