"""
模块6 —— 多模型API统一调度网关
核心功能：统一封装多家大模型API调用、分流策略、限流重试、用量统计、余额告警
核心技术：令牌桶限流 + 用量追踪 + 成本预估 + 自动故障降级
"""

import time
import json
from collections import deque
from dataclasses import dataclass, field


# ===== 数据结构 =====

@dataclass
class ModelConfig:
    name: str
    model_id: str
    base_url: str
    max_tokens: int = 4096
    context_window: int = 32000
    cost_in: float = 0.0001   # $/1K tokens 输入
    cost_out: float = 0.0002  # $/1K tokens 输出
    tier: str = "lite"        # lite | pro
    provider: str = "openai"  # openai | anthropic | gemini

@dataclass
class APIResult:
    success: bool = False
    content: str = ""
    model: str = ""
    usage: dict = field(default_factory=dict)
    error: str = ""
    latency_ms: float = 0.0

@dataclass
class UsageRecord:
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost: float = 0.0


# ===== 限流器（令牌桶） =====

class RateLimiter:
    """令牌桶限流器 - 控制每分钟最大请求数"""
    def __init__(self, max_rpm: int = 30):
        self.max_rpm = max_rpm
        self.tokens = max_rpm
        self.last_refill = time.time()

    def acquire(self) -> bool:
        """获取一个令牌，成功返回True"""
        now = time.time()
        elapsed = now - self.last_refill
        refill = int(elapsed / 60.0 * self.max_rpm)
        if refill > 0:
            self.tokens = min(self.max_rpm, self.tokens + refill)
            self.last_refill = now
        if self.tokens > 0:
            self.tokens -= 1
            return True
        return False

    @property
    def remaining(self) -> int:
        return max(0, self.tokens)


# ===== 用量追踪器 =====

class UsageTracker:
    """API用量追踪统计器"""
    def __init__(self):
        self.records: list[UsageRecord] = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0

    def record(self, record: UsageRecord):
        self.records.append(record)
        self.total_prompt_tokens += record.prompt_tokens
        self.total_completion_tokens += record.completion_tokens
        self.total_cost += record.cost

    def get_summary(self) -> dict:
        return {
            "total_requests": len(self.records),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cost": round(self.total_cost, 4),
        }

    def get_latency_stats(self) -> dict:
        if not self.records:
            return {"avg_ms": 0, "max_ms": 0, "min_ms": 0}
        latencies = [r.latency_ms for r in self.records if r.latency_ms > 0]
        if not latencies:
            return {"avg_ms": 0, "max_ms": 0, "min_ms": 0}
        return {
            "avg_ms": round(sum(latencies) / len(latencies), 1),
            "max_ms": round(max(latencies), 1),
            "min_ms": round(min(latencies), 1),
        }


# ===== 余额守护器 =====

class BillingGuard:
    """余额阈值告警器"""
    def __init__(self, alert_threshold: float = 1.0, budget_limit: float = 10.0):
        self.alert_threshold = alert_threshold
        self.budget_limit = budget_limit
        self.total_spent = 0.0

    def add_cost(self, cost: float) -> dict:
        """记录花费并检查余额状态"""
        self.total_spent += cost
        remaining = self.budget_limit - self.total_spent
        if remaining <= 0:
            return {"ok": False, "message": f"预算已超限（已用${self.total_spent:.2f}）"}
        if remaining < self.alert_threshold:
            return {"ok": True, "message": f"余额不足(${remaining:.2f})，请及时充值"}
        return {"ok": True, "message": "余额充足"}


# ===== 核心网关 =====

class MockAPIGateway:
    """
    多模型API网关（模拟版本）
    封装：限流保护 + 用量统计 + 余额守护 + 模型路由
    """
    def __init__(self, max_rpm: int = 30):
        self.rate_limiter = RateLimiter(max_rpm=max_rpm)
        self.usage_tracker = UsageTracker()
        self.billing_guard = BillingGuard()
        self.models = {
            "deepseek_lite": ModelConfig("DeepSeek-Lite", "deepseek-chat", "http://localhost:8000/v1", tier="lite"),
            "deepseek_pro": ModelConfig("DeepSeek-Pro", "deepseek-reasoner", "http://localhost:8000/v1", tier="pro"),
            "gpt_mini": ModelConfig("GPT-4o-mini", "gpt-4o-mini", "http://localhost:8000/v1", tier="lite"),
            "claude_sonnet": ModelConfig("Claude-3.5-Sonnet", "claude-3-5-sonnet", "http://localhost:8000/v1", tier="pro"),
        }
        self.default_model = "deepseek_lite"

    def select_model(self, task_type: str) -> ModelConfig:
        """根据任务类型选择模型"""
        if task_type in ("resume_generate", "interview"):
            return self.models.get("deepseek_pro", self.models["deepseek_lite"])
        return self.models["deepseek_lite"]

    def chat(self, messages: list[dict], task_type: str = "", options: dict = None) -> APIResult:
        """发起一次完整的AI调用（含限流+用量+余额守护）"""
        opts = options or {}

        # 1. 限流检查
        if not self.rate_limiter.acquire():
            return APIResult(success=False, error="RATE_LIMITED",
                             message=f"请求频率超限 (max {self.rate_limiter.max_rpm}/min)")

        # 2. 余额检查
        bill_status = self.billing_guard.add_cost(0)
        if not bill_status["ok"]:
            return APIResult(success=False, error="BUDGET_EXCEEDED", message=bill_status["message"])

        # 3. 模拟API调用（实际项目中这里调用真实LLM API）
        start = time.time()
        model = self.select_model(task_type)
        if opts.get("force_model"):
            model = self.models.get(opts["force_model"], model)

        # 模拟响应延迟
        time.sleep(0.3)

        prompt = messages[-1]["content"] if messages else ""
        prompt_chars = len(prompt)
        simulated_tokens = prompt_chars // 2  # 模拟token计数

        content = f"[{model.name} 模拟响应] 已收到您的请求（{prompt_chars}字符）。在实际部署中，此处将返回大模型生成的回答。任务类型：{task_type or '通用'}。"

        latency = (time.time() - start) * 1000

        result = APIResult(
            success=True, content=content,
            model=model.model_id,
            usage={"prompt_tokens": simulated_tokens, "completion_tokens": simulated_tokens // 2},
            latency_ms=latency)

        # 4. 记录用量
        if result.usage:
            cost = (result.usage["prompt_tokens"] / 1000) * model.cost_in + \
                   (result.usage["completion_tokens"] / 1000) * model.cost_out
            self.usage_tracker.record(UsageRecord(
                model=model.model_id,
                prompt_tokens=result.usage["prompt_tokens"],
                completion_tokens=result.usage["completion_tokens"],
                latency_ms=latency, cost=cost))
            self.billing_guard.add_cost(cost)

        return result

    def get_status(self) -> dict:
        return {
            "usage": self.usage_tracker.get_summary(),
            "latency": self.usage_tracker.get_latency_stats(),
            "rate_limit": {"max": self.rate_limiter.max_rpm, "remaining": self.rate_limiter.remaining},
            "billing": {"total_spent": round(self.billing_guard.total_spent, 4),
                        "budget_limit": self.billing_guard.budget_limit},
            "models_available": {k: v.model_id for k, v in self.models.items()},
            "default_model": self.default_model,
        }


def run():
    print("="*60)
    print("  模块6：多模型API统一调度网关")
    print("  功能：限流保护 / 用量统计 / 余额守护 / 模型路由")
    print("="*60)

    gateway = MockAPIGateway(max_rpm=30)

    print("\n[测试1：模型路由选择]")
    print(f"  通用任务→{gateway.select_model('extraction').name}")
    print(f"  简历生成→{gateway.select_model('resume_generate').name}")
    print(f"  面试任务→{gateway.select_model('interview').name}")

    print("\n[测试2：模拟API调用]")
    result = gateway.chat(
        messages=[{"role": "user", "content": "请分析以下职位描述中的技能要求……"}],
        task_type="extraction",
        options={"max_tokens": 200, "temperature": 0.0})
    print(f"  状态: {'成功' if result.success else '失败'}")
    print(f"  模型: {result.model}")
    print(f"  延迟: {result.latency_ms:.0f}ms")
    print(f"  Token: {result.usage}")
    print(f"  响应: {result.content[:80]}...")

    print("\n[测试3：限流保护测试]")
    gateway.rate_limiter.tokens = 0
    r2 = gateway.chat([{"role": "user", "content": "test"}])
    print(f"  被限流: {r2.error == 'RATE_LIMITED'} ({r2.message})")

    print("\n[测试4：网关状态总览]")
    status = gateway.get_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))

    print("\n[核心代码说明]")
    print("  · RateLimiter: 令牌桶限流算法（控制RPM）")
    print("  · UsageTracker: API用量追踪（token/请求数/成本）")
    print("  · BillingGuard: 余额阈值守护（预警+封顶）")
    print("  · select_model(): 按任务类型分流（lite vs pro）")


if __name__ == "__main__":
    run()
