"""LLM JSON 安全解析 — 处理截断、格式异常、markdown包裹"""
import json
import re
import logging

logger = logging.getLogger(__name__)


def parse_json_safely(text: str, fallback: dict | None = None) -> dict:
    """安全解析 LLM 返回的 JSON，处理各种常见异常"""
    if not text or not text.strip():
        return fallback or {}

    text = text.strip()

    # 1. 移除 markdown 代码块包裹
    md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if md_match:
        text = md_match.group(1).strip()

    # 2. 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. 尝试提取第一个 { 到最后一个 } 之间的内容
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # 4. 修复常见 JSON 问题后重试
    fixed = fix_common_json_issues(text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 5. 修复截断的 JSON
    fixed = fix_truncated_json(text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    logger.warning(f"[JSON] Failed to parse: {text[:200]}...")
    return fallback or {}


def fix_common_json_issues(text: str) -> str:
    """修复 LLM 输出的常见 JSON 格式问题"""
    # 移除尾部逗号（objects/arrays）
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    # 单引号转双引号（简单场景）
    # 不处理太复杂的情况以免误伤

    # 移除注释
    text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    # 移除 BOM
    text = text.replace('﻿', '')

    # 修复中文引号
    text = text.replace('“', '"').replace('”', '"')
    text = text.replace('‘', "'").replace('’', "'")

    # 修复未闭合的字符串值（简单处理：给字符串值加上引号）
    text = re.sub(r':\s*([^\s",\[\]{}]+)(\s*[,}])', r': "\1"\2', text)

    return text


def fix_truncated_json(text: str) -> str:
    """修复被截断的 JSON — 补全未闭合的大括号和引号"""
    # 移除被截断的最后一个不完整字段
    # 找到最后一个完整的逗号或冒号
    depth = 0
    for i in range(len(text) - 1, -1, -1):
        if text[i] == '{':
            depth -= 1
        elif text[i] == '}':
            depth += 1
        elif text[i] == ',' and depth == 0:
            text = text[:i]
            break

    # 补全未闭合的结构
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')

    # 检查是否有未闭合的字符串
    in_string = False
    for ch in text:
        if ch == '"':
            in_string = not in_string
    if in_string:
        text += '"'

    # 补全括号
    text += ']' * max(0, open_brackets)
    text += '}' * max(0, open_braces)

    return text
