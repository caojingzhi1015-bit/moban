"""
06_multi_model_api_gateway/main.py — 多模型 API 统一调度网关（可独立运行）

功能:
  - 统一封装 5 家大模型: DeepSeek / 豆包 / ChatGPT / Claude / Gemini
  - 分流策略: 轻量抽取→Lite模型, 简历生成/面试→旗舰模型
  - 断线重试 + 接口故障自动降级切换备用模型
  - 调用限流 + 用量统计 + Token 账单预估 + 余额低阈值告警
  - 所有 AI 请求自动拼接全局防幻觉 Prompt

对外接口: 其余 5 个模块全部调用本网关发起请求
"""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.multi_model_gateway import (
    MultiModelGateway,
    GatewayConfig,
    ModelConfig,
    APIResult,
    safe_parse_json,
)
from common.language_switch import LanguageSwitch

# 导入限流控制（使用模块加载器处理数字开头目录）
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec

_lc_path = Path(__file__).parent / "limit_control.py"
_lc_loader = SourceFileLoader("06_multi_model_api_gateway.limit_control", str(_lc_path))
_lc_spec = spec_from_loader("06_multi_model_api_gateway.limit_control", _lc_loader)
_lc_mod = module_from_spec(_lc_spec)
sys.modules["06_multi_model_api_gateway.limit_control"] = _lc_mod
_lc_loader.exec_module(_lc_mod)

RateLimiter = _lc_mod.RateLimiter
UsageTracker = _lc_mod.UsageTracker
BillingGuard = _lc_mod.BillingGuard
UsageRecord = _lc_mod.UsageRecord


class APIGatewayApp:
    """
    多模型 API 网关应用层
    封装 MultiModelGateway + 限流 + 用量统计 + 余额守护
    """

    def __init__(self, config: GatewayConfig | None = None):
        self.gateway = MultiModelGateway(config=config)
        self.rate_limiter = RateLimiter(
            max_rpm=config.max_rpm if config else 30
        )
        self.usage_tracker = UsageTracker()
        self.billing_guard = BillingGuard(
            alert_threshold=config.balance_alert_threshold if config else 1.0
        )

    async def chat(
        self,
        messages: list[dict],
        task_type: str = "",
        options: dict | None = None,
    ) -> APIResult:
        """
        发起一次完整的 AI 调用（含限流+用量+余额守护）

        Args:
            messages: 消息列表
            task_type: 任务类型
            options: 可选参数

        Returns:
            APIResult
        """
        # 限流检查
        if not self.rate_limiter.acquire():
            return APIResult(
                success=False,
                error="RATE_LIMITED",
                message=f"请求频率超限 (max {self.rate_limiter.max_rpm}/min)",
            )

        # 余额检查
        bill_status = self.billing_guard.add_cost(0)  # 预检
        if not bill_status["ok"]:
            return APIResult(
                success=False,
                error="BUDGET_EXCEEDED",
                message=bill_status["message"],
            )

        # 调用网关
        result = await self.gateway.chat_completion(
            messages=messages,
            task_type=task_type,
            options=options,
        )

        # 记录用量
        if result.success and result.usage:
            p_tokens = result.usage.get("prompt_tokens", 0)
            c_tokens = result.usage.get("completion_tokens", 0)
            # 估算成本（从模型配置）
            model = self.gateway.select_model(task_type)
            cost = (p_tokens / 1000) * model.cost_in + (c_tokens / 1000) * model.cost_out

            self.usage_tracker.record(UsageRecord(
                model=result.model,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                latency_ms=result.latency_ms,
                cost=cost,
            ))
            self.billing_guard.add_cost(cost)

        return result

    def get_status(self) -> dict:
        """获取网关状态摘要"""
        return {
            "usage": self.usage_tracker.get_summary(),
            "latency": self.usage_tracker.get_latency_stats(),
            "rate_limit": {
                "current": self.rate_limiter.current_count,
                "max": self.rate_limiter.max_rpm,
                "remaining": self.rate_limiter.remaining,
            },
            "billing": {
                "total_spent": self.billing_guard.total_spent,
            },
            "models_available": self.gateway.get_available_models(),
            "default_model": self.gateway.default_model,
        }

    async def close(self) -> None:
        await self.gateway.close()


# ═══════════════════════════════════════════════════════════════
# 独立运行入口
# ═══════════════════════════════════════════════════════════════

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="06_multi_model_api_gateway — 多模型网关")
    parser.add_argument("--test", action="store_true", help="测试模型连通性")
    parser.add_argument("--model", default="deepseek_lite", help="测试模型名")
    parser.add_argument("--status", action="store_true", help="查看网关状态")
    parser.add_argument("--prompt", default="你好，请用一句话介绍自己。", help="测试提示词")
    args = parser.parse_args()

    app = APIGatewayApp()

    if args.test:
        print(f"[测试] 模型: {args.model}")
        print(f"[测试] Prompt: {args.prompt}")

        result = await app.chat(
            messages=[{"role": "user", "content": args.prompt}],
            task_type="extraction",
            options={"force_model": args.model, "max_tokens": 200, "temperature": 0.0},
        )
        if result.success:
            print(f"[OK] 响应 ({result.latency_ms:.0f}ms): {result.content[:200]}")
            print(f"[用量] tokens={result.usage}, model={result.model}")
        else:
            print(f"[FAIL] {result.error}: {result.message}")

    if args.status or args.test:
        status = app.get_status()
        print(f"\n=== 网关状态 ===")
        print(json.dumps(status, ensure_ascii=False, indent=2, default=str))

    await app.close()


if __name__ == "__main__":
    asyncio.run(main())
