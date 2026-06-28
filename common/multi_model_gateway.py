"""
common/multi_model_gateway.py — 多模型统一API网关
兼容: DeepSeek(默认) | 豆包 | ChatGPT | Claude | Gemini
功能: 统一OpenAI兼容封装 | 分流策略 | 限流/重试/降级 | 用量统计 | 余额告警
前置: 所有AI请求自动拼接全局防幻觉Prompt
"""

import os
import re
import json
import time
import hashlib
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

import httpx

# ──────────── 加载全局防幻觉 Prompt ────────────

def _load_global_prompt() -> str:
    """加载全局防幻觉提示词"""
    prompt_paths = [
        Path(__file__).parent / "global_const_prompt.txt",
        Path(__file__).parent.parent / "common" / "global_const_prompt.txt",
    ]
    for p in prompt_paths:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return (
        "【全局底层防幻觉强制总提示词】"
        "1.仅使用用户素材库文字，禁止编造。"
        "2.无法确认返回null。"
        "3.只输出纯净JSON。"
        "4.字段名严格匹配Schema。"
        "5.多段经历逐条拆分。"
        "6.禁止生成占位符描述。"
    )

GLOBAL_PROMPT = _load_global_prompt()


# ──────────── 数据类 ────────────

@dataclass
class ModelConfig:
    """单个模型配置"""
    name: str
    model_id: str
    base_url: str
    api_key: str = ""
    max_tokens: int = 4096
    context_window: int = 32000
    cost_in: float = 0.0001   # $/1K tokens 输入
    cost_out: float = 0.0002  # $/1K tokens 输出
    tier: str = "lite"        # lite | pro
    provider: str = "openai"  # openai | anthropic | gemini


@dataclass
class APIResult:
    """统一的API调用结果"""
    success: bool
    content: str = ""
    model: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""
    error: str = ""
    message: str = ""
    status: int = 0
    latency_ms: float = 0.0


@dataclass
class GatewayConfig:
    """网关配置"""
    default_model: str = "deepseek_lite"
    max_rpm: int = 30               # 每分钟最大请求数
    max_retries: int = 3            # 最大重试次数
    retry_delay: float = 1.0       # 重试间隔(秒)
    balance_alert_threshold: float = 10.0  # 余额告警阈值(美元)
    enable_auto_fallback: bool = True     # 自动降级切换模型


# ──────────── 主类 ────────────

class MultiModelGateway:
    """
    多模型统一API调度网关
    其余5个业务模块全部通过本网关发起AI请求
    """

    # 模型预设配置
    MODELS: dict[str, ModelConfig] = {
        "deepseek_lite": ModelConfig(
            name="deepseek_lite", model_id="deepseek-chat",
            base_url="https://api.deepseek.com/v1", max_tokens=4096,
            context_window=32000, cost_in=0.00014, cost_out=0.00028,
            tier="lite", provider="openai",
        ),
        "deepseek_enhanced": ModelConfig(
            name="deepseek_enhanced", model_id="deepseek-reasoner",
            base_url="https://api.deepseek.com/v1", max_tokens=4096,
            context_window=128000, cost_in=0.00055, cost_out=1.10,
            tier="pro", provider="openai",
        ),
        "doubao": ModelConfig(
            name="doubao", model_id="doubao-pro-32k",
            base_url="https://ark.cn-beijing.volces.com/api/v3", max_tokens=4096,
            context_window=32000, cost_in=0.0008, cost_out=0.002,
            tier="pro", provider="openai",
        ),
        "gemini": ModelConfig(
            name="gemini", model_id="gemini-2.5-flash",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            max_tokens=2048, context_window=1000000,
            cost_in=0.00015, cost_out=0.0006,
            tier="pro", provider="gemini",
        ),
        "claude": ModelConfig(
            name="claude", model_id="claude-sonnet-4-6-20250514",
            base_url="https://api.anthropic.com/v1", max_tokens=4096,
            context_window=200000, cost_in=0.003, cost_out=0.015,
            tier="pro", provider="anthropic",
        ),
        "gpt": ModelConfig(
            name="gpt", model_id="gpt-4o",
            base_url="https://api.openai.com/v1", max_tokens=4096,
            context_window=128000, cost_in=0.0025, cost_out=0.01,
            tier="pro", provider="openai",
        ),
    }

    # 任务分流策略表
    TASK_ROUTING: dict[str, str] = {
        "extraction": "deepseek_lite",
        "vision": "deepseek_lite",
        "interview": "deepseek_enhanced",
        "enhanced": "deepseek_enhanced",
        "generation": "deepseek_enhanced",
        "jd_parse": "deepseek_lite",
        "resume_parse": "deepseek_lite",
        "enquiry": "deepseek_enhanced",
        "resume_gen": "deepseek_enhanced",
    }

    # DeepSeek 失败时的降级链
    FALLBACK_CHAIN = ["doubao", "gpt", "claude", "gemini"]

    def __init__(self, config: GatewayConfig | None = None):
        self.config = config or GatewayConfig()
        self._default_model = self.config.default_model
        self._client: httpx.AsyncClient | None = None

        # 用量统计
        self._usage_stats: dict[str, Any] = {
            "total_tokens": 0, "total_cost": 0.0, "calls": 0, "models": {},
        }

        # 限流计数
        self._rpm_counter = {"count": 0, "reset_at": time.time() + 60}

        # 加载全局 Prompt
        self._global_prompt = GLOBAL_PROMPT

        # 从环境变量加载 API Keys
        self._load_api_keys_from_env()

    def _load_api_keys_from_env(self) -> None:
        """从环境变量加载所有 API Key"""
        env_map = {
            "deepseek_lite": "CAREERAI_API_KEY_DEEPSEEK",
            "deepseek_enhanced": "CAREERAI_API_KEY_DEEPSEEK",
            "doubao": "CAREERAI_API_KEY_DOUBAO",
            "gemini": "CAREERAI_API_KEY_GEMINI",
            "claude": "CAREERAI_API_KEY_CLAUDE",
            "gpt": "CAREERAI_API_KEY_CHATGPT",
        }
        for name, env_var in env_map.items():
            val = os.environ.get(env_var, "")
            if val and name in self.MODELS:
                self.MODELS[name].api_key = val

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client:
            try:
                await self._client.aclose()
            except RuntimeError:
                # 事件循环已关闭时忽略
                pass
            self._client = None

    # ──────────── 模型选择 ────────────

    def select_model(self, task_type: str = "") -> ModelConfig:
        """根据任务类型选择最佳模型"""
        model_name = self.TASK_ROUTING.get(task_type, self._default_model)
        return self.MODELS.get(model_name, self.MODELS["deepseek_lite"])

    def get_fallback_models(self, failed_model_name: str) -> list[ModelConfig]:
        """获取降级模型列表（排除已失败的）"""
        candidates = []
        for name in self.FALLBACK_CHAIN:
            if name != failed_model_name and name in self.MODELS:
                cfg = self.MODELS[name]
                if cfg.api_key:
                    candidates.append(cfg)
        return candidates

    # ──────────── 核心调用入口 ────────────

    async def chat_completion(
        self,
        messages: list[dict],
        task_type: str = "",
        options: dict | None = None,
    ) -> APIResult:
        """
        统一的 Chat Completion 入口 — 所有业务模块的 AI 调用经过此处

        Args:
            messages: [{"role": "user", "content": "..."}]
            task_type: extraction / interview / enhanced / generation / jd_parse / resume_parse
            options: {max_tokens, temperature, lang, force_model}

        Returns:
            APIResult: 统一的结果封装
        """
        options = options or {}

        # 支持强制指定模型
        if options.get("force_model"):
            model = self.MODELS.get(options["force_model"])
            if not model:
                return APIResult(success=False, error="INVALID_MODEL", message=f"未知模型: {options['force_model']}")
        else:
            model = self.select_model(task_type)

        if not model.api_key:
            return APIResult(
                success=False, error="API_KEY_MISSING",
                message=f"模型 {model.model_id} 未配置 API Key。请设置环境变量或调用 set_api_key()",
            )

        # 限流检查
        if not self._check_rate_limit():
            return APIResult(success=False, error="RATE_LIMITED", message="请求频率过高，请稍后重试")

        # 拼接全局防幻觉 Prompt（对话型任务用精简版，抽取型用完整版）
        full_messages = self._prepend_global_prompt(messages, task_type)

        # 带重试 + 降级的调用
        return await self._call_with_retry_and_fallback(model, full_messages, options, task_type)

    async def _call_with_retry_and_fallback(
        self,
        model: ModelConfig,
        messages: list[dict],
        options: dict,
        task_type: str,
    ) -> APIResult:
        """带重试和降级的调用逻辑"""
        last_error: APIResult | None = None
        attempted_models: set[str] = set()

        # 主模型重试
        for attempt in range(self.config.max_retries):
            try:
                result = await self._call_model(model, messages, options)
                if result.success:
                    self._track_usage(model, result)
                    return result
                # API 明确返回错误（非网络错误），不重试
                if result.error in ("API_KEY_MISSING", "INSUFFICIENT_BALANCE", "RATE_LIMITED"):
                    last_error = result
                    break
                last_error = result
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_error = APIResult(success=False, error="NETWORK_ERROR", message=str(e))

            # 重试等待
            if attempt < self.config.max_retries - 1:
                await self._async_sleep(self.config.retry_delay * (attempt + 1))

        attempted_models.add(model.name)

        # 自动降级切换
        if self.config.enable_auto_fallback and last_error:
            fallback_models = self.get_fallback_models(model.name)
            for fb_model in fallback_models:
                if fb_model.name in attempted_models:
                    continue
                try:
                    result = await self._call_model(fb_model, messages, options)
                    if result.success:
                        result.message = f"已从 {model.name} 自动降级至 {fb_model.name}"
                        self._track_usage(fb_model, result)
                        return result
                except Exception:
                    pass
                attempted_models.add(fb_model.name)

        return last_error or APIResult(success=False, error="ALL_MODELS_FAILED", message="所有模型调用均失败")

    # ──────────── 具体模型调用 ────────────

    async def _call_model(
        self, model: ModelConfig, messages: list[dict], opts: dict
    ) -> APIResult:
        """根据 provider 类型分发调用"""
        start_time = time.time()

        try:
            if model.provider in ("openai",):
                result = await self._call_openai_compatible(model, messages, opts)
            elif model.provider == "anthropic":
                result = await self._call_claude(model, messages, opts)
            elif model.provider == "gemini":
                result = await self._call_gemini(model, messages, opts)
            else:
                result = await self._call_openai_compatible(model, messages, opts)

            result.latency_ms = (time.time() - start_time) * 1000
            return result
        except httpx.TimeoutException:
            return APIResult(success=False, error="TIMEOUT", message="请求超时", latency_ms=(time.time() - start_time) * 1000)
        except Exception as e:
            return APIResult(success=False, error="API_ERROR", message=str(e), latency_ms=(time.time() - start_time) * 1000)

    async def _call_openai_compatible(
        self, model: ModelConfig, messages: list[dict], opts: dict
    ) -> APIResult:
        """OpenAI 兼容接口调用 (DeepSeek/豆包/GPT)"""
        body = {
            "model": model.model_id,
            "messages": messages,
            "temperature": opts.get("temperature", 0.0),
            "max_tokens": opts.get("max_tokens", model.max_tokens),
        }
        client = await self._get_client()
        resp = await client.post(
            f"{model.base_url}/chat/completions",
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {model.api_key}",
            },
        )

        if resp.status_code != 200:
            try:
                err = resp.json()
            except Exception:
                err = {}
            if resp.status_code == 402:
                return APIResult(success=False, error="INSUFFICIENT_BALANCE", message="账户余额不足，请充值", status=402)
            if resp.status_code == 429:
                return APIResult(success=False, error="RATE_LIMITED", message="API 频率限制", status=429)
            return APIResult(
                success=False, error="HTTP_ERROR", status=resp.status_code,
                message=err.get("error", {}).get("message", resp.reason_phrase),
            )

        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        return APIResult(
            success=True,
            content=choice.get("message", {}).get("content", ""),
            model=model.model_id,
            usage=data.get("usage", {}),
            finish_reason=choice.get("finish_reason", ""),
        )

    async def _call_claude(
        self, model: ModelConfig, messages: list[dict], opts: dict
    ) -> APIResult:
        """Claude API 调用"""
        sys_msg = next((m for m in messages if m["role"] == "system"), None)
        user_msgs = [m for m in messages if m["role"] != "system"]
        body: dict = {
            "model": model.model_id,
            "max_tokens": opts.get("max_tokens", model.max_tokens),
            "temperature": opts.get("temperature", 0.0),
            "messages": user_msgs,
        }
        if sys_msg:
            body["system"] = sys_msg["content"]

        client = await self._get_client()
        resp = await client.post(
            f"{model.base_url}/messages",
            json=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": model.api_key,
                "anthropic-version": "2023-06-01",
            },
        )

        if resp.status_code != 200:
            return APIResult(success=False, error="HTTP_ERROR", status=resp.status_code)

        data = resp.json()
        blocks = data.get("content", [{}])
        return APIResult(
            success=True,
            content=blocks[0].get("text", "") if blocks else "",
            model=model.model_id,
            usage={
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
            } if data.get("usage") else {},
            finish_reason=data.get("stop_reason", ""),
        )

    async def _call_gemini(
        self, model: ModelConfig, messages: list[dict], opts: dict
    ) -> APIResult:
        """Gemini API 调用"""
        sys_inst = next((m for m in messages if m["role"] == "system"), None)
        parts = [{"text": m["content"]} for m in messages if m["role"] != "system"]
        body: dict = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": opts.get("temperature", 0.0),
                "maxOutputTokens": opts.get("max_tokens", model.max_tokens),
            },
        }
        if sys_inst:
            body["systemInstruction"] = {"parts": [{"text": sys_inst["content"]}]}

        url = f"{model.base_url}/models/{model.model_id}:generateContent?key={model.api_key}"
        client = await self._get_client()
        resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})

        if resp.status_code != 200:
            return APIResult(success=False, error="HTTP_ERROR", status=resp.status_code)

        data = resp.json()
        candidates = data.get("candidates", [{}])
        content = (candidates[0] if candidates else {}).get("content", {})
        parts_out = content.get("parts", [{}])
        return APIResult(
            success=True,
            content=parts_out[0].get("text", "") if parts_out else "",
            model=model.model_id,
            usage={
                "prompt_tokens": data.get("usageMetadata", {}).get("promptTokenCount", 0),
                "completion_tokens": data.get("usageMetadata", {}).get("candidatesTokenCount", 0),
            } if data.get("usageMetadata") else {},
        )

    # ──────────── 用量统计与限流 ────────────

    def _track_usage(self, model: ModelConfig, result: APIResult) -> None:
        """记录用量统计"""
        usage = result.usage
        if not usage:
            return

        p_tokens = usage.get("prompt_tokens", 0)
        c_tokens = usage.get("completion_tokens", 0)
        cost = (p_tokens / 1000) * model.cost_in + (c_tokens / 1000) * model.cost_out

        self._usage_stats["total_tokens"] += p_tokens + c_tokens
        self._usage_stats["total_cost"] += cost
        self._usage_stats["calls"] += 1

        ms = self._usage_stats["models"].setdefault(
            model.model_id,
            {"calls": 0, "tokens": 0, "cost": 0.0, "latency_total": 0.0},
        )
        ms["calls"] += 1
        ms["tokens"] += p_tokens + c_tokens
        ms["cost"] += cost
        ms["latency_total"] += result.latency_ms

        # 余额告警
        if self._usage_stats["total_cost"] > self.config.balance_alert_threshold:
            print(f"[余额告警] 累计费用 ${self._usage_stats['total_cost']:.4f} 已超过阈值 ${self.config.balance_alert_threshold:.2f}")

        # 更新限流计数
        self._rpm_counter["count"] += 1

    def _check_rate_limit(self) -> bool:
        """检查是否触发限流"""
        now = time.time()
        if now >= self._rpm_counter["reset_at"]:
            self._rpm_counter["count"] = 0
            self._rpm_counter["reset_at"] = now + 60
            return True
        if self._rpm_counter["count"] >= self.config.max_rpm:
            return False
        return True

    async def _async_sleep(self, seconds: float) -> None:
        """异步等待"""
        import asyncio
        await asyncio.sleep(seconds)

    # ──────────── 全局 Prompt 管理 ────────────

    # ── 对话型任务（不应注入 JSON 输出约束）──
    _CONVERSATIONAL_TASKS = {"interview", "generation", "chat"}

    def _prepend_global_prompt(self, messages: list[dict], task_type: str = "") -> list[dict]:
        """
        在所有消息前拼接全局防幻觉 Prompt。
        对话型任务（interview / generation）跳过 JSON 输出约束，
        避免面试官对候选人输出 JSON 格式。
        """
        if not self._global_prompt:
            return list(messages)
        # 对话型任务：注入精简版约束（不要求 JSON 输出）
        if task_type in self._CONVERSATIONAL_TASKS:
            conversational_prompt = (
                "【全局约束】"
                "1.仅基于用户提供的素材内容进行对话，不编造不存在的经历/技能/项目。"
                "2.无法确认的信息直接说不知道，不推测。"
            )
            has_system = any(m.get("role") == "system" for m in messages)
            if has_system:
                result = []
                for m in messages:
                    if m.get("role") == "system":
                        result.append({
                            "role": "system",
                            "content": conversational_prompt + "\n\n" + m.get("content", ""),
                        })
                    else:
                        result.append(m)
                return result
            else:
                return [{"role": "system", "content": conversational_prompt}] + list(messages)

        # 抽取型任务：注入完整防幻觉 Prompt（含 JSON 输出约束）
        has_system = any(m.get("role") == "system" for m in messages)
        if has_system:
            result = []
            for m in messages:
                if m.get("role") == "system":
                    result.append({
                        "role": "system",
                        "content": self._global_prompt + "\n\n" + m.get("content", ""),
                    })
                else:
                    result.append(m)
            return result
        else:
            return [{"role": "system", "content": self._global_prompt}] + list(messages)

    # ──────────── 公开 API ────────────

    def get_usage_report(self) -> dict:
        """获取用量报告"""
        return {
            **self._usage_stats,
            "rpm": {
                "current": self._rpm_counter["count"],
                "limit": self.config.max_rpm,
            },
            "total_cost_display": f"${self._usage_stats['total_cost']:.4f}",
        }

    def set_default_model(self, name: str) -> bool:
        """设置默认模型"""
        if name in self.MODELS:
            self._default_model = name
            self.config.default_model = name
            return True
        return False

    def set_api_key(self, model_name: str, api_key: str) -> bool:
        """动态设置 API Key"""
        if model_name in self.MODELS:
            self.MODELS[model_name].api_key = api_key
            return True
        return False

    def get_available_models(self) -> list[dict]:
        """获取可用模型列表（含配置状态）"""
        return [
            {
                "name": k,
                "id": v.model_id,
                "tier": v.tier,
                "provider": v.provider,
                "configured": bool(v.api_key),
                "cost_per_1k": f"${v.cost_in:.4f} / ${v.cost_out:.4f}",
            }
            for k, v in self.MODELS.items()
        ]

    def validate_api_keys(self) -> dict[str, bool]:
        """验证所有已配置的 API Key"""
        return {k: bool(v.api_key) for k, v in self.MODELS.items()}

    @property
    def global_prompt(self) -> str:
        return self._global_prompt

    @property
    def default_model(self) -> str:
        return self._default_model


# ──────────── 工具函数 ────────────

def safe_parse_json(text: str) -> dict | None:
    """安全的 JSON 解析，自动从混合内容中提取 JSON 块"""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试匹配 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # 尝试匹配裸 {...} 块
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None
