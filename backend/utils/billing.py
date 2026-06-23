"""Token 计费追踪 — 服务端实现（替代 billing-guard.js）"""

import time
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelUsage:
    """单个模型的用量统计"""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class BillingReport:
    total_tokens: int = 0
    total_cost: float = 0.0
    rpm_current: int = 0
    rpm_limit: int = 60
    daily_tokens: int = 0
    daily_limit: int = 1_000_000
    daily_percent: float = 0.0
    free_tokens_remaining: int = 100_000
    env: str = "production"
    api_configured: bool = True
    models: dict[str, ModelUsage] = field(default_factory=dict)


# 模型定价 (USD/1K tokens)
MODEL_PRICING = {
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-reasoner": {"input": 0.00055, "output": 2.19},
    "deepseek-vl": {"input": 0.00055, "output": 2.19},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-opus-4-8": {"input": 0.015, "output": 0.075},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
}


class TokenTracker:
    """Token 用量追踪器（单例）"""

    _instance: Optional["TokenTracker"] = None

    def __init__(self):
        self._report = BillingReport()
        self._lock = threading.Lock()
        self._minute_requests: list[float] = []
        self._daily_reset_time = time.time()

    @classmethod
    def get_instance(cls) -> "TokenTracker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def track(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """记录一次 API 调用"""
        pricing = MODEL_PRICING.get(model, {"input": 0.001, "output": 0.002})
        cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]

        with self._lock:
            now = time.time()

            # RPM 跟踪
            self._minute_requests = [t for t in self._minute_requests if now - t < 60]
            self._minute_requests.append(now)

            # 每日重置
            if now - self._daily_reset_time > 86400:
                self._daily_reset_time = now
                self._report.daily_tokens = 0

            # 更新统计
            model_usage = self._report.models.setdefault(model, ModelUsage())
            model_usage.calls += 1
            model_usage.input_tokens += input_tokens
            model_usage.output_tokens += output_tokens
            model_usage.total_cost += cost

            total = input_tokens + output_tokens
            self._report.total_tokens += total
            self._report.total_cost += cost
            self._report.daily_tokens += total
            self._report.rpm_current = len(self._minute_requests)
            self._report.daily_percent = (self._report.daily_tokens / self._report.daily_limit) * 100

    def predict_cost(self, model: str, input_tokens: int, output_tokens: int = 0) -> float:
        """预估成本"""
        pricing = MODEL_PRICING.get(model, {"input": 0.001, "output": 0.002})
        return (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]

    def get_report(self) -> BillingReport:
        return self._report


def estimate_cost(model: str, input_tokens: int, output_tokens: int = 0) -> float:
    return TokenTracker.get_instance().predict_cost(model, input_tokens, output_tokens)
