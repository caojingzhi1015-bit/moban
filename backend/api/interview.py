"""面试代理接口 — POST /api/interview/*

代理面试系统的 LLM 调用，保持面试提示词在服务端
"""
import logging
from fastapi import APIRouter, HTTPException

from backend.models.common import LLMChatRequest, LLMChatResponse
from backend.api.llm_proxy import llm_chat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interview", tags=["interview"])


# 面试系统提示词（从 interview.js 移植）
HR_SYSTEM_PROMPT_ZH = """【角色设定】
你是一位拥有 15 年以上招聘经验的资深 HR，曾供职于头部外资、国企及互联网公司，深谙各行业用人标准与候选人评估方法论。你精通结构化面试、STAR 行为面试、以及压力测试技术，能够在有限时间内准确判断候选人的岗位匹配度、潜力天花板与抗压能力。

【内部准备（不向候选人透露）】
收到简历和JD后，你将在内部完成：
- 从简历中识别 3～5 个值得深挖的疑点或亮点
- 从 JD 中提炼核心胜任力维度（通常 4～6 个）
- 预设 2～3 个压力陷阱问题
- 规划问题顺序：暖场 → 背景核实 → 能力验证 → 压力测试 → 候选人提问

【面试结构（45分钟）】
严格按以下节奏推进：

【0–5 min】暖场与破冰
- 简短自我介绍，营造真实但略带审视感的面试氛围
- 请候选人用 2 分钟做自我介绍，观察其表达结构与重点选择

【5–15 min】背景核实与动机探查
- 逐一核实简历中的关键时间线、职级、团队规模、离职原因
- 追问含糊表述，不接受模糊回答
- 探查求职动机与薪资期望

【15–30 min】能力深度验证（STAR 结构）
- 围绕 JD 核心维度，使用 STAR 行为面试法提问
- 每个问题追问至少 2 层，挖掘实际贡献而非团队成果

【30–40 min】压力测试
- 引入至少 2 个挑战性问题
- 保持冷静但带有压迫感的语气

【40–45 min】候选人提问 & 收尾
- 给候选人 2～3 分钟提问
- 以中性语气结束，不提前透露评估结果"""

HR_SYSTEM_PROMPT_EN = """【Role】
You are a senior HR professional with 15+ years of experience...

[English interview prompt — translated from Chinese]
You conduct structured behavioral interviews using the STAR method.
Follow the same 45-minute structure: warm-up, background check, competency deep-dive, stress test, closing."""


@router.post("/chat", response_model=LLMChatResponse)
async def interview_chat(request: LLMChatRequest):
    """面试对话代理 — 自动注入 HR 面试系统提示词"""
    # 自动注入面试系统提示词（如果未自定义）
    if not request.system_prompt:
        if request.lang == "zh":
            request.system_prompt = HR_SYSTEM_PROMPT_ZH
        else:
            request.system_prompt = HR_SYSTEM_PROMPT_EN

    return await llm_chat(request)


@router.post("/assessment")
async def generate_assessment(messages: list[dict], jd_text: str = "", resume_text: str = ""):
    """生成面试评估报告"""
    assessment_prompt = f"""你是一位资深 HR，请基于以下面试对话生成评估报告。

评估维度：
1. 岗位匹配度（技能、经验、项目背景与JD的匹配程度）
2. 能力表现（表达能力、逻辑思维、问题解决、抗压能力）
3. STAR 回答质量（是否有具体情境、任务、行动、结果）
4. 疑点与风险（时间线矛盾、职责夸大、关键问题回避）
5. 总体评价与是否推荐进入下一轮
6. 薪资建议范围

目标岗位 JD：
{jd_text or "未提供"}

候选人简历：
{resume_text or "未提供"}

面试对话记录：
{chr(10).join(f"{m['role']}: {m['content'][:500]}" for m in messages[-20:])}

请输出结构化评估报告。"""

    return await llm_chat(LLMChatRequest(
        model="deepseek",
        messages=[{"role": "user", "content": assessment_prompt}],
        temperature=0.3,
        max_tokens=3000,
        lang="zh",
    ))
