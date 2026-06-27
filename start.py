#!/usr/bin/env python3
"""
start.py — CareerAI 求职助手一键启动脚本
"""

import sys
import os
import subprocess
import argparse
import webbrowser
import time
from pathlib import Path

# 修复 Windows 终端 GBK 编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 自动加载 .env 中的 API Key
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


def check_dependencies():
    """检查核心依赖是否安装"""
    missing = []
    for mod in ["streamlit", "httpx"]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"[ERROR] 缺少依赖: {', '.join(missing)}")
        print(f"请运行: pip install -r requirements.txt")
        sys.exit(1)


def show_env_status():
    """显示环境变量配置状态"""
    env_keys = {
        "CAREERAI_API_KEY_DEEPSEEK": os.environ.get("CAREERAI_API_KEY_DEEPSEEK", ""),
        "CAREERAI_API_KEY_DOUBAO": os.environ.get("CAREERAI_API_KEY_DOUBAO", ""),
        "CAREERAI_API_KEY_GEMINI": os.environ.get("CAREERAI_API_KEY_GEMINI", ""),
        "CAREERAI_API_KEY_CLAUDE": os.environ.get("CAREERAI_API_KEY_CLAUDE", ""),
        "CAREERAI_API_KEY_CHATGPT": os.environ.get("CAREERAI_API_KEY_CHATGPT", ""),
    }
    print("\n" + "=" * 55)
    print("  CareerAI 求职助手 — 启动中...")
    print("=" * 55)
    print("\n[API Key 状态]")
    for name, val in env_keys.items():
        short = name.replace("CAREERAI_API_KEY_", "")
        if val:
            print(f"  [OK] {short}: {val[:8]}...{val[-4:]}")
        else:
            print(f"  [--] {short}: not set")
    if not any(env_keys.values()):
        print("\n[!] Please set at least one API Key environment variable:")
        print("    e.g.: set CAREERAI_API_KEY_DEEPSEEK=sk-xxx")


def start_streamlit():
    """启动 Streamlit 网页前端"""
    app_path = PROJECT_ROOT / "web_ui" / "app.py"
    if not app_path.exists():
        print(f"[ERROR] 找不到 Streamlit 入口: {app_path}")
        sys.exit(1)

    print(f"\n[Streamlit] 启动网页前端...")
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.port", "8501",
        "--server.headless", "true",
        "--browser.serverAddress", "localhost",
    ]
    return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))


def start_backend():
    """启动 FastAPI 后端服务"""
    backend_path = PROJECT_ROOT / "backend"
    if not backend_path.exists() or not (backend_path / "main.py").exists():
        print("[INFO] 未找到 backend/main.py，跳过 FastAPI 后端启动")
        print("[INFO] 将使用 Streamlit 内置的 Python 模块直接调用（无需独立后端）")
        return None

    print(f"\n[FastAPI] 启动后端服务 (端口 8000)...")
    cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ]
    return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="CareerAI 求职助手 — 一键启动")
    parser.add_argument("--backend", action="store_true", help="仅启动 FastAPI 后端")
    parser.add_argument("--all", action="store_true", help="同时启动后端 + 前端")
    parser.add_argument("--port", type=int, default=8501, help="Streamlit 端口 (默认: 8501)")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    check_dependencies()
    show_env_status()

    processes = []

    try:
        if args.backend:
            # 仅后端
            p = start_backend()
            if p:
                processes.append(p)
                print("\n[FastAPI] 运行中 → http://localhost:8000")
                print("[FastAPI] API 文档 → http://localhost:8000/docs")
                p.wait()
        elif args.all:
            # 同时启动
            p1 = start_backend()
            if p1:
                processes.append(p1)
            time.sleep(2)  # 等后端启动
            p2 = start_streamlit()
            processes.append(p2)

            print("\n" + "=" * 55)
            print("  [OK] CareerAI 已启动!")
            print(f"  [>>] 网页: http://localhost:{args.port}")
            if p1:
                print(f"  API Docs: http://localhost:8000/docs")
            print("=" * 55)

            if not args.no_browser:
                time.sleep(3)
                webbrowser.open(f"http://localhost:{args.port}")

            for p in processes:
                p.wait()
        else:
            # 默认：仅 Streamlit
            p = start_streamlit()
            processes.append(p)

            print("\n" + "=" * 55)
            print("  [OK] CareerAI 已启动!")
            print(f"  [>>] 网页: http://localhost:{args.port}")
            print("  Open the URL above in your browser")
            print("=" * 55)

            if not args.no_browser:
                time.sleep(3)
                webbrowser.open(f"http://localhost:{args.port}")

            p.wait()

    except KeyboardInterrupt:
        print("\n\n[INFO] 正在关闭...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.wait()
        print("[INFO] CareerAI 已停止")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        for p in processes:
            p.terminate()
        sys.exit(1)


if __name__ == "__main__":
    main()
