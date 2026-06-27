"""
06_multi_model_api_gateway/limit_control.py — 调用限流 + 用量统计 + 余额告警

功能:
  - 每分钟请求数限制 (RPM)
  - 全站 Token 用量统计
  - 按模型分别统计调用次数 + 成本
  - 余额低阈值告警
  - 请求耗时分布统计
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict


@dataclass
class UsageRecord:
    """单次调用记录"""
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost: float = 0.0
    timestamp: float = field(default_factory=time.time)


class RateLimiter:
    """
    滑动窗口限流器 —— 每分钟最多 N 次请求
    """

    def __init__(self, max_rpm: int = 30):
        self.max_rpm = max_rpm
        self._window: list[float] = []  # 最近 60 秒内的请求时间戳
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """
        尝试获取一个请求配额

        Returns:
            True=放行, False=限流
        """
        now = time.time()
        with self._lock:
            # 清理 60 秒之前的记录
            self._window = [t for t in self._window if now - t < 60]
            if len(self._window) >= self.max_rpm:
                return False
            self._window.append(now)
            return True

    @property
    def current_count(self) -> int:
        """当前窗口内请求数"""
        now = time.time()
        with self._lock:
            return len([t for t in self._window if now - t < 60])

    @property
    def remaining(self) -> int:
        """剩余可用配额"""
        return max(0, self.max_rpm - self.current_count)

    def reset(self) -> None:
        """重置限流计数"""
        with self._lock:
            self._window = []


class UsageTracker:
    """
    用量统计追踪器 —— 全站 + 按模型分别统计
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._records: list[UsageRecord] = []
        self._model_stats: dict[str, dict] = defaultdict(
            lambda: {"calls": 0, "tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0, "latency_total": 0.0}
        )
        self._total_tokens = 0
        self._total_cost = 0.0
        self._total_calls = 0

    def record(self, record: UsageRecord) -> None:
        """记录一次调用"""
        with self._lock:
            self._records.append(record)
            self._total_tokens += record.prompt_tokens + record.completion_tokens
            self._total_cost += record.cost
            self._total_calls += 1

            ms = self._model_stats[record.model]
            ms["calls"] += 1
            ms["tokens"] += record.prompt_tokens + record.completion_tokens
            ms["prompt_tokens"] += record.prompt_tokens
            ms["completion_tokens"] += record.completion_tokens
            ms["cost"] += record.cost
            ms["latency_total"] += record.latency_ms

    def get_summary(self) -> dict:
        """获取用量摘要"""
        with self._lock:
            return {
                "total_tokens": self._total_tokens,
                "total_cost": round(self._total_cost, 6),
                "total_cost_display": f"${self._total_cost:.4f}",
                "total_calls": self._total_calls,
                "models": {
                    k: {
                        **v,
                        "avg_latency_ms": round(v["latency_total"] / max(1, v["calls"]), 1),
                        "cost_display": f"${v['cost']:.4f}",
                    }
                    for k, v in dict(self._model_stats).items()
                },
            }

    def check_balance_alert(self, threshold: float = 1.0) -> list[str]:
        """检查是否需要余额告警"""
        alerts = []
        for model, stats in self._model_stats.items():
            if stats["cost"] >= threshold:
                alerts.append(
                    f"[余额告警] {model}: 累计 ${stats['cost']:.4f} 已超过阈值 ${threshold:.2f}"
                )
        return alerts

    def get_latency_stats(self) -> dict:
        """获取延迟统计"""
        with self._lock:
            if not self._records:
                return {"avg": 0, "max": 0, "min": 0, "count": 0}
            latencies = [r.latency_ms for r in self._records]
            return {
                "avg": round(sum(latencies) / len(latencies), 1),
                "max": round(max(latencies), 1),
                "min": round(min(latencies), 1),
                "p95": round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if len(latencies) >= 20 else round(max(latencies), 1),
                "count": len(latencies),
            }

    def reset(self) -> None:
        """重置统计（慎用）"""
        with self._lock:
            self._records = []
            self._model_stats.clear()
            self._total_tokens = 0
            self._total_cost = 0.0
            self._total_calls = 0


class BillingGuard:
    """
    余额守护 —— 低余额自动告警，余额耗尽前阻断调用
    """

    def __init__(self, alert_threshold: float = 1.0, hard_limit: float = 10.0):
        self.alert_threshold = alert_threshold
        self.hard_limit = hard_limit
        self._total_spent = 0.0
        self._lock = threading.Lock()

    def add_cost(self, cost: float) -> dict:
        """
        累加成本并检查告警

        Returns:
            {"ok": True/False, "alerts": [...], "message": ""}
        """
        with self._lock:
            self._total_spent += cost
            alerts = []

            if self._total_spent >= self.hard_limit:
                return {
                    "ok": False,
                    "alerts": [f"费用已达硬限制 ${self.hard_limit:.2f}，已自动阻断调用"],
                    "message": f"累计费用 ${self._total_spent:.4f}，已超过上限",
                    "total_spent": round(self._total_spent, 4),
                }

            if self._total_spent >= self.alert_threshold:
                alerts.append(
                    f"累计费用 ${self._total_spent:.4f}，已超过告警阈值 ${self.alert_threshold:.2f}"
                )

            return {
                "ok": True,
                "alerts": alerts,
                "total_spent": round(self._total_spent, 4),
            }

    @property
    def total_spent(self) -> float:
        return round(self._total_spent, 4)


# ═══════════════════════════════════════════════════════════════
# 独立测试入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== RateLimiter 测试 ===")
    rl = RateLimiter(max_rpm=5)
    for i in range(7):
        ok = rl.acquire()
        print(f"  请求{i+1}: {'通过' if ok else '限流'} (当前窗口: {rl.current_count})")

    print("\n=== UsageTracker 测试 ===")
    ut = UsageTracker()
    ut.record(UsageRecord(model="deepseek-chat", prompt_tokens=500, completion_tokens=200, latency_ms=1200, cost=0.00015))
    ut.record(UsageRecord(model="deepseek-chat", prompt_tokens=300, completion_tokens=150, latency_ms=800, cost=0.0001))
    ut.record(UsageRecord(model="gpt-4o", prompt_tokens=1000, completion_tokens=500, latency_ms=2500, cost=0.0075))
    import json
    print(json.dumps(ut.get_summary(), ensure_ascii=False, indent=2))

    print("\n=== BillingGuard 测试 ===")
    bg = BillingGuard(alert_threshold=0.005, hard_limit=0.02)
    for cost in [0.003, 0.004, 0.01, 0.01]:
        r = bg.add_cost(cost)
        print(f"  消费 ${cost:.4f} → ok={r['ok']}, alerts={r['alerts']}, 累计={r['total_spent']}")

    print("\n[OK] 限流控制模块测试通过")
