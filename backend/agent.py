"""Zhipu GLM tool_use main loop — orchestrates the 3 tools.  @card CARD-001"""
import json
import os
import asyncio
import re
from pathlib import Path
from dotenv import load_dotenv
from tools import browser_job_search, resume_customizer, interview_prep
from tools.resume_customizer import _extract_pdf_text
from db import track_application
from llm_client import (
    consume_decision_log,
    create_chat_completion,
    create_client,
    get_model,
    reset_decision_log,
)

load_dotenv()
client = create_client()

# ── System prompt template ────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
你是专业的求职助手。你能够：
1. 理解复杂的多步骤求职需求
2. 制定执行计划（格式：## 执行计划，后跟编号步骤）并逐步执行
3. 每完成一个工具调用后，分析结果并说明下一步决策
4. 根据中间结果做出判断（如：哪些职位匹配度最高）
5. 如果某个步骤失败，跳过该项继续处理其他项
6. 所有步骤完成后，输出结构化 JSON 汇总报告

当收到复杂需求时，先说出你的执行计划，再逐步执行。
每完成一个步骤，简要说明结果和下一步决策。
最终输出包含 {{"summary": {{...}}}} 的 JSON 块。

[用户简历摘要]
{resume_summary}"""

# ── Tool definitions (OpenAI-compatible format used by Zhipu) ───────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browser_job_search",
            "description": "搜索职位。使用浏览器爬取 HN Who's Hiring 或 RemoteOK，返回匹配职位列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":    {"type": "string",  "description": "职位关键词，如 'Python backend engineer'"},
                    "location": {"type": "string",  "description": "地点或 'remote'，默认 remote"},
                    "limit":    {"type": "integer", "description": "最多返回条数，默认 10"},
                    "source":   {"type": "string",  "enum": ["hn", "remoteok"], "description": "数据源，默认 hn"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_customizer",
            "description": "根据职位 JD 定制简历。解析 PDF 简历，生成定制版 Markdown + HTML diff + Cover Letter。",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_path":           {"type": "string",  "description": "本地 PDF 简历路径"},
                    "job_description":       {"type": "string",  "description": "目标职位完整 JD"},
                    "job_id":                {"type": "string",  "description": "职位 ID，用于命名输出文件"},
                    "generate_cover_letter": {"type": "boolean", "description": "是否生成 Cover Letter，默认 true"},
                },
                "required": ["resume_path", "job_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "interview_prep",
            "description": "生成面试准备材料：5 道最可能被问到的面试题 + STAR 框架答案。",
            "parameters": {
                "type": "object",
                "properties": {
                    "company":         {"type": "string", "description": "目标公司名称"},
                    "job_title":       {"type": "string", "description": "目标职位名称"},
                    "job_description": {"type": "string", "description": "职位 JD"},
                },
                "required": ["company", "job_title", "job_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_auto_apply",
            "description": "自动投递 LinkedIn Easy Apply 职位。需要职位 URL 和定制简历路径。",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_url": {"type": "string", "description": "LinkedIn 职位页 URL"},
                    "resume_md_path": {"type": "string", "description": "定制后的 Markdown 简历路径"},
                    "job_id": {"type": "string", "description": "职位 ID"},
                    "cover_letter_path": {"type": "string", "description": "Cover Letter 路径（可选）"},
                },
                "required": ["job_url", "resume_md_path", "job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "external_auto_apply",
            "description": "自动投递非 LinkedIn 的外部招聘页面。browser harness 分析表单结构、填写标准字段、上传简历并提交。遇到 login wall 或非标准字段时降级返回投递包。",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_url":           {"type": "string", "description": "职位申请页 URL（非 LinkedIn）"},
                    "resume_md_path":    {"type": "string", "description": "定制后的 Markdown 简历路径"},
                    "job_id":            {"type": "string", "description": "职位 ID"},
                    "cover_letter_path": {"type": "string", "description": "Cover Letter 路径（可选）"},
                    "job_title":         {"type": "string", "description": "职位名称，用于匹配岗位链接（可选）"},
                    "company":           {"type": "string", "description": "公司名称（可选）"},
                },
                "required": ["job_url", "resume_md_path", "job_id"],
            },
        },
    },
]


# ── Agent loop (async generator yielding SSE events) ─────────────────────────

async def run_agent(
    user_message: str,
    resume_path: str | None = None,
    conversation_history: list[dict] | None = None,
    memory_context: dict[str, str] | None = None,
):
    """
    Run the job hunt agent as an async generator.
    Yields dicts with SSE event structure: {"event": ..., "data": {...}}
    """
    # ── Extract resume text for system prompt injection ───────────────────
    resume_summary = "（用户尚未上传简历）"
    if resume_path:
        try:
            resume_summary = _extract_pdf_text(Path(resume_path))
            if not resume_summary.strip():
                resume_summary = "（简历内容为空）"
        except Exception as e:
            resume_summary = f"（简历解析失败: {e}）"

    memory_lines = []
    if memory_context:
        for key, value in memory_context.items():
            if value:
                memory_lines.append(f"- {key}: {value}")
    memory_block = "\n".join(memory_lines) if memory_lines else "（暂无持久记忆）"
    system_content = (
        SYSTEM_PROMPT.format(resume_summary=resume_summary)
        + f"\n\n[持久记忆]\n{memory_block}"
    )

    # ── Build initial messages ────────────────────────────────────────────
    content = user_message
    if resume_path:
        content += f"\n\n[简历文件路径: {resume_path}]"

    messages = [{"role": "system", "content": system_content}]
    for item in conversation_history or []:
        role = item.get("role")
        text = item.get("content")
        if role in {"user", "assistant"} and text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": content})

    last_tool_result = None

    for _ in range(20):  # max 20 rounds
        # ── Call GLM-4 with error handling ────────────────────────────────
        try:
            reset_decision_log()
            response = create_chat_completion(
                client=client,
                stage="agent_orchestrator",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            for decision in consume_decision_log():
                yield {"event": "decision", "data": decision}
        except Exception as e:
            for decision in consume_decision_log():
                yield {"event": "decision", "data": decision}
            
            # ✅ 改进：记录错误但继续尝试，而不是硬中止
            import traceback
            error_msg = f"LLM API 调用失败 (第 {_+1} 轮): {e}\n{traceback.format_exc()}"
            print(f"[agent] {error_msg}", flush=True)
            
            # 如果已有工具结果，返回现有结果；否则重试或返回错误
            if last_tool_result is not None:
                yield {
                    "event": "done",
                    "data": {
                        "message": f"模型暂时不可用，已返回当前阶段的可用结果。错误信息：{e}",
                        "last_tool_result": last_tool_result,
                    },
                }
                return
            elif _ < 3:  # 前3次失败时自动重试
                yield {
                    "event": "reasoning",
                    "data": {
                        "text": f"第 {_+1} 次 LLM 调用失败，等待 2 秒后重试...\n错误: {str(e)[:100]}"
                    },
                }
                await asyncio.sleep(2)
                continue  # 进入下一轮循环重试
            else:
                # 多次失败后返回错误
                yield {"event": "error", "data": {"message": error_msg}}
                return

        message = response.choices[0].message

        # ── No tool calls → final answer or reasoning ────────────────────
        if not message.tool_calls:
            if last_tool_result is not None:
                # Tools were used previously, this is the final answer
                yield {
                    "event": "done",
                    "data": {
                        "message": message.content or "",
                        "last_tool_result": last_tool_result,
                    },
                }
            else:
                # No tools used yet — this is reasoning / direct answer
                yield {
                    "event": "done",
                    "data": {
                        "message": message.content or "",
                        "last_tool_result": None,
                    },
                }
            return

        # ── Has tool calls → yield reasoning first if content present ────
        if message.content:
            plan_steps = _extract_plan_steps(message.content)
            if plan_steps:
                yield {"event": "plan", "data": {"steps": plan_steps}}
            yield {"event": "reasoning", "data": {"text": message.content}}

        # Append assistant message (with tool_calls) to history
        messages.append(message.model_dump())

        # ── Execute each tool call ────────────────────────────────────────
        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            print(f"[agent] tool={fn_name} args={json.dumps(fn_args, ensure_ascii=False)[:120]}")

            yield {"event": "tool_start", "data": {"tool": fn_name, "args": fn_args}}

            try:
                reset_decision_log()
                result = await _call_tool(fn_name, fn_args)
                last_tool_result = {"tool": fn_name, "result": result}
                result_str = json.dumps(result, ensure_ascii=False)
            except Exception as e:
                result = {"error": str(e)}
                last_tool_result = {"tool": fn_name, "result": result}
                result_str = json.dumps(result, ensure_ascii=False)

            for decision in consume_decision_log():
                yield {"event": "decision", "data": decision}
            yield {"event": "tool_result", "data": {"tool": fn_name, "result": result}}

            # Zhipu format: role="tool", tool_call_id must match
            messages.append({
                "role": "tool",
                "content": result_str,
                "tool_call_id": tool_call.id,
            })
    else:
        # Loop exhausted 20 iterations — yield partial results
        yield {
            "event": "done",
            "data": {
                "message": "Agent 达到最大迭代次数（20），返回部分结果。",
                "last_tool_result": last_tool_result,
            },
        }


def _extract_plan_steps(content: str) -> list[str]:
    match = re.search(r"##\s*执行计划\s*(.*)", content, re.DOTALL)
    if not match:
        return []

    steps: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        numbered = re.match(r"^\d+\.\s*(.+)$", stripped)
        if numbered:
            steps.append(numbered.group(1).strip())
        elif steps and not stripped.startswith("##"):
            # Continuation line for the previous step.
            steps[-1] = f"{steps[-1]} {stripped}"
        elif stripped.startswith("##"):
            break
    return steps


async def _call_tool(name: str, args: dict):
    if name == "browser_job_search":
        return await browser_job_search(**args)
    if name == "resume_customizer":
        return resume_customizer(**args)
    if name == "interview_prep":
        return interview_prep(**args)
    if name == "linkedin_auto_apply":
        from tools.linkedin_apply import linkedin_auto_apply
        return await linkedin_auto_apply(**args)
    if name == "external_auto_apply":
        from tools.linkedin_apply import external_auto_apply
        return await external_auto_apply(**args)
    raise ValueError(f"Unknown tool: {name}")
