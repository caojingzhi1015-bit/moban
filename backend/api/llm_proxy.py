"""LLM 代理接口 — POST /api/llm/*

所有 LLM API key 保存于服务端，浏览器不可见。
支持：DeepSeek / Claude / GPT / Gemini
"""
import logging
import httpx
from fastapi import APIRouter, HTTPException

from backend.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL_LITE, DEEPSEEK_MODEL_REASONER,
    CLAUDE_API_KEY, CLAUDE_MODEL,
    OPENAI_API_KEY, OPENAI_MODEL,
    GEMINI_API_KEY, GEMINI_MODEL,
)
from backend.models.common import LLMChatRequest, LLMChatResponse
from backend.utils.billing import TokenTracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/llm", tags=["llm"])

token_tracker = TokenTracker.get_instance()

# 各模型配置
MODEL_CONFIGS = {
    "deepseek": {
        "url": f"{DEEPSEEK_BASE_URL}/chat/completions",
        "headers": {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        "model": DEEPSEEK_MODEL_LITE,
        "api_key": DEEPSEEK_API_KEY,
    },
    "deepseek-reasoner": {
        "url": f"{DEEPSEEK_BASE_URL}/chat/completions",
        "headers": {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
        "model": DEEPSEEK_MODEL_REASONER,
        "api_key": DEEPSEEK_API_KEY,
    },
    "claude": {
        "url": "https://api.anthropic.com/v1/messages",
        "headers": {
            "x-api-key": CLAUDE_API_KEY or "",
            "anthropic-version": "2023-06-01",
        },
        "model": CLAUDE_MODEL,
        "api_key": CLAUDE_API_KEY,
    },
    "gpt": {
        "url": "https://api.openai.com/v1/chat/completions",
        "headers": {"Authorization": f"Bearer {OPENAI_API_KEY}"},
        "model": OPENAI_MODEL,
        "api_key": OPENAI_API_KEY,
    },
    "gemini": {
        "url": f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        "model": GEMINI_MODEL,
        "api_key": GEMINI_API_KEY,
    },
}


@router.post("/chat", response_model=LLMChatResponse)
async def llm_chat(request: LLMChatRequest):
    """统一的 LLM 对话代理"""
    model_key = request.model
    config = MODEL_CONFIGS.get(model_key)

    if not config:
        raise HTTPException(400, f"不支持的模型: {model_key}。支持: {list(MODEL_CONFIGS.keys())}")

    if not config["api_key"]:
        raise HTTPException(401, f"模型 {model_key} 未配置 API Key。请在服务端设置环境变量。")

    try:
        if model_key.startswith("deepseek"):
            return await _call_deepseek(request, config)
        elif model_key == "claude":
            return await _call_claude(request, config)
        elif model_key == "gpt":
            return await _call_gpt(request, config)
        elif model_key == "gemini":
            return await _call_gemini(request, config)
    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API error: {e.response.status_code} {e.response.text[:200]}")
        raise HTTPException(e.response.status_code, f"LLM API 错误: {e.response.text[:500]}")
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(500, f"LLM 调用失败: {str(e)}")


async def _call_deepseek(request: LLMChatRequest, config: dict) -> LLMChatResponse:
    """DeepSeek API (OpenAI compatible)"""
    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.extend(request.messages)

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            config["url"],
            headers=config["headers"],
            json={
                "model": config["model"],
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    usage = data.get("usage", {})
    token_tracker.track(
        config["model"],
        usage.get("prompt_tokens", 0),
        usage.get("completion_tokens", 0),
    )

    return LLMChatResponse(
        content=data["choices"][0]["message"]["content"],
        model=config["model"],
        usage=usage,
        finish_reason=data["choices"][0].get("finish_reason"),
    )


async def _call_claude(request: LLMChatRequest, config: dict) -> LLMChatResponse:
    """Claude API (Anthropic)"""
    system = request.system_prompt or ""
    messages = request.messages

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            config["url"],
            headers=config["headers"],
            json={
                "model": config["model"],
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "system": system,
                "messages": messages,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    usage = data.get("usage", {})
    token_tracker.track(
        config["model"],
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
    )

    return LLMChatResponse(
        content=data["content"][0]["text"],
        model=config["model"],
        usage=usage,
        finish_reason=data.get("stop_reason"),
    )


async def _call_gpt(request: LLMChatRequest, config: dict) -> LLMChatResponse:
    """GPT-4o API (OpenAI)"""
    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.extend(request.messages)

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            config["url"],
            headers=config["headers"],
            json={
                "model": config["model"],
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    usage = data.get("usage", {})
    token_tracker.track(
        config["model"],
        usage.get("prompt_tokens", 0),
        usage.get("completion_tokens", 0),
    )

    return LLMChatResponse(
        content=data["choices"][0]["message"]["content"],
        model=config["model"],
        usage=usage,
        finish_reason=data["choices"][0].get("finish_reason"),
    )


async def _call_gemini(request: LLMChatRequest, config: dict) -> LLMChatResponse:
    """Gemini API"""
    # 转换消息格式
    contents = []
    for msg in request.messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg["content"]}],
        })

    if request.system_prompt:
        # Gemini 使用 systemInstruction
        request_body = {
            "system_instruction": {"parts": [{"text": request.system_prompt}]},
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
    else:
        request_body = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }

    url = f"{config['url']}?key={config['api_key']}"

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=request_body)
        resp.raise_for_status()
        data = resp.json()

    content = data["candidates"][0]["content"]["parts"][0]["text"]
    usage = data.get("usageMetadata", {})

    token_tracker.track(
        config["model"],
        usage.get("promptTokenCount", 0),
        usage.get("candidatesTokenCount", 0),
    )

    return LLMChatResponse(
        content=content,
        model=config["model"],
        usage=usage,
        finish_reason=data["candidates"][0].get("finishReason"),
    )


@router.get("/models")
async def list_models():
    """列出可用的模型及其状态"""
    models = {}
    for key, config in MODEL_CONFIGS.items():
        models[key] = {
            "model_id": config["model"],
            "available": bool(config["api_key"]),
        }
    return {"models": models}


@router.get("/billing")
async def get_billing():
    """获取 Token 使用统计"""
    report = token_tracker.get_report()
    return {
        "total_tokens": report.total_tokens,
        "total_cost_usd": round(report.total_cost, 4),
        "rpm_current": report.rpm_current,
        "rpm_limit": report.rpm_limit,
        "daily_tokens": report.daily_tokens,
        "daily_limit": report.daily_limit,
        "daily_percent": round(report.daily_percent, 1),
        "models": {
            name: {
                "calls": m.calls,
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "cost_usd": round(m.total_cost, 4),
            }
            for name, m in report.models.items()
        },
    }
