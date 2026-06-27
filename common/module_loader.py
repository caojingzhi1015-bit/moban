"""
common/module_loader.py — 动态模块加载器
解决 Python 无法直接 import 数字开头目录的问题

用法:
  JDParser = load_module("01_jd_parser", "main", "JDParser")
  ResumeParser = load_module("02_resume_parser", "main", "ResumeParser")
"""

import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent


def load_module(dir_name: str, file_name: str, attr_name: str | None = None) -> Any:
    """
    从数字开头的目录动态加载模块

    Args:
        dir_name: 目录名 (如 "01_jd_parser")
        file_name: 文件名 (如 "main"，不含 .py)
        attr_name: 要获取的属性名，为 None 则返回整个模块

    Returns:
        模块或模块属性
    """
    module_path = _PROJECT_ROOT / dir_name / f"{file_name}.py"
    if not module_path.exists():
        raise FileNotFoundError(f"模块文件不存在: {module_path}")

    # 使用不重复的模块名
    module_key = f"{dir_name}.{file_name}"

    # 如果已经加载过，直接返回缓存
    if module_key in sys.modules:
        mod = sys.modules[module_key]
    else:
        loader = SourceFileLoader(module_key, str(module_path))
        spec = spec_from_loader(module_key, loader)
        if spec is None:
            raise ImportError(f"无法创建模块 spec: {module_path}")
        mod = module_from_spec(spec)
        sys.modules[module_key] = mod

        # 确保项目根目录在 sys.path
        root = str(_PROJECT_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)

        loader.exec_module(mod)

    if attr_name:
        return getattr(mod, attr_name)
    return mod


def load_attr(qualified: str) -> Any:
    """
    快捷加载: "01_jd_parser.main.JDParser" → JDParser 类
    """
    parts = qualified.split(".")
    if len(parts) < 2:
        raise ValueError(f"格式应为 'dir.file.attr', 收到: {qualified}")
    mod = load_module(parts[0], parts[1])
    for attr in parts[2:]:
        mod = getattr(mod, attr)
    return mod
