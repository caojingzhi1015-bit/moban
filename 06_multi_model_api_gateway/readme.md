# 06_multi_model_api_gateway — 多模型统一 API 调度网关

## ① 模块解决的核心痛点
- **多模型接口不统一**: DeepSeek/豆包/GPT/Claude/Gemini 各自 API 格式不同，切换成本高
- **单模型不稳定**: DeepSeek 流式连接频繁中断，没有任何故障切换机制
- **成本无法追踪**: Token 用量分散在各平台，缺少统一账单
- **缺少限流保护**: 批量调用时容易触发 API 频率限制

## ② 完整执行业务流水线
```
业务模块调用 → MultiModelGateway.chat_completion()
  ├── 1. 任务分流: 根据 task_type 选择最佳模型 (Lite/Pro)
  ├── 2. 限流检查: RateLimiter 滑动窗口，超限返回 429
  ├── 3. 余额守护: BillingGuard 检查是否超预算
  ├── 4. 全局 Prompt 注入: 自动前置拼接防幻觉约束
  ├── 5. 模型调用:
  │     ├── OpenAI 兼容接口 → DeepSeek / 豆包 / GPT
  │     ├── Claude Messages API
  │     └── Gemini generateContent API
  ├── 6. 失败重试: 最多 3 次，指数退避
  ├── 7. 自动降级: DeepSeek 失败→豆包→GPT→Claude→Gemini
  ├── 8. 用量记录: UsageTracker 按模型统计 token + 成本
  └── 9. 告警检查: 超过阈值打印警告日志
```

## ③ 分流策略表
| 任务类型 | 模型 | 原因 |
|---------|------|------|
| extraction / jd_parse / resume_parse | deepseek_lite | 轻量抽取，成本低 |
| interview / enhanced / generation / resume_gen | deepseek_enhanced | 需高质量输出 |
| vision | deepseek_lite | 图片识别 |

## ④ 与其他模块的数据互通逻辑
- **被 01-05 所有模块调用**: 所有 AI 请求统一经过网关
- **提供用量报告**: 各模块可通过 get_usage_report() 查看 Token 消耗
- **自动拼接全局 Prompt**: 切换模型也不会丢失防幻觉约束
- **输入 api_config.ini**: API Key 集中管理
