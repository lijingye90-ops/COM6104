"""Manus-style ReAct agent — conversational + tool-using.  @card CARD-001"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from dotenv import load_dotenv

import confirm_store
from db import track_application
from llm_client import (
    consume_decision_log,
    create_chat_completion,
    create_client,
    reset_decision_log,
)
from tools.resume_customizer import _extract_pdf_text

load_dotenv()
client = create_client()

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
你是一位专业的求职助手，同时也是一个聪明、自然的对话伙伴。

**对话原则：**
- 对于闲聊、提问、问候等普通对话，直接用自然语言回复，不要调用任何工具。
- 只有当用户明确需要搜索职位、定制简历、投递申请、查阅网页等实际任务时，才选择合适的工具。
- 不要把每条消息都当成求职任务触发——先理解用户意图，再决定是否用工具。
- 回复简洁、友好，像真人助手一样，避免机械式输出。

**你能做的事（工具能力）：**
- 搜索网络获取最新信息
- 打开和分析网页
- 搜索招聘职位
- 根据职位 JD 定制简历和求职信
- 生成面试准备材料
- 自动投递职位
- 读写本地文件
- 执行 Python 代码做分析计算
- 在关键操作前向你确认

**执行复杂任务时：**
1. 先简述你的执行计划（格式：## 执行计划，后跟编号步骤）
2. 逐步执行，每步完成后说明结果和下一步
3. 重要操作前主动用 ask_user 工具获取确认
4. 全部完成后，给出清晰的结果摘要

[用户简历摘要]
{resume_summary}

[持久记忆]
{memory_block}"""

# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "在网上搜索信息。适用于查询最新招聘信息、公司背景、行业资讯等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer", "description": "最多返回条数，默认 6"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": "打开一个网页并提取其主要文本内容。适用于查看招聘页、公司官网、新闻文章等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要打开的网页 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "job_search",
            "description": "在招聘平台搜索职位。返回匹配的职位列表，含标题、公司、链接、描述摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "职位关键词，如 'Python backend engineer'"},
                    "location": {"type": "string", "description": "地点或 'remote'，默认 remote"},
                    "limit": {"type": "integer", "description": "最多返回条数，默认 10"},
                    "source": {"type": "string", "enum": ["hn", "remoteok"], "description": "数据源，默认 remoteok"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_customizer",
            "description": "根据职位 JD 定制简历。解析用户 PDF 简历，生成定制版 Markdown 简历 + HTML diff + Cover Letter。",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_path": {"type": "string", "description": "本地 PDF 简历路径"},
                    "job_description": {"type": "string", "description": "目标职位完整 JD"},
                    "job_id": {"type": "string", "description": "职位 ID，用于命名输出文件"},
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
                    "company": {"type": "string", "description": "目标公司名称"},
                    "job_title": {"type": "string", "description": "目标职位名称"},
                    "job_description": {"type": "string", "description": "职位 JD"},
                },
                "required": ["company", "job_title", "job_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply",
            "description": "自动投递职位。支持 LinkedIn Easy Apply 和外部招聘页面。遇到障碍时会降级返回投递包。",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_url": {"type": "string", "description": "职位页面 URL"},
                    "resume_md_path": {"type": "string", "description": "定制后的 Markdown 简历路径"},
                    "job_id": {"type": "string", "description": "职位 ID"},
                    "cover_letter_path": {"type": "string", "description": "Cover Letter 路径（可选）"},
                    "job_title": {"type": "string", "description": "职位名称（可选）"},
                    "company": {"type": "string", "description": "公司名称（可选）"},
                },
                "required": ["job_url", "resume_md_path", "job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "读取本地文件内容。支持 .txt、.md、.json、.csv、.py 等文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件绝对路径"},
                    "encoding": {"type": "string", "description": "文件编码，默认 utf-8"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "将内容写入本地文件。会覆盖已有文件。返回写入路径。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件绝对路径"},
                    "content": {"type": "string", "description": "要写入的文本内容"},
                    "encoding": {"type": "string", "description": "文件编码，默认 utf-8"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "python_exec",
            "description": "执行一段 Python 代码。适合数据分析、格式转换、简单计算等。返回 stdout/stderr 和执行状态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要执行的 Python 代码"},
                    "timeout": {"type": "integer", "description": "超时秒数，默认 30"},
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "向用户提问或请求确认。在执行重要操作（如投递简历、写入文件）前使用。用户可以回答是/否或提供具体信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "要向用户提出的问题"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "terminate",
            "description": "结束当前任务，给出最终总结。所有任务完成或无法继续时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "最终总结消息"},
                },
                "required": ["message"],
            },
        },
    },
]


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_agent(
    user_message: str,
    resume_path: str | None = None,
    conversation_history: list[dict] | None = None,
    memory_context: dict[str, str] | None = None,
    conversation_id: str = "",
):
    """
    ReAct agent loop. Async generator yielding SSE event dicts.
    Supports casual conversation (no tools) and tool-using task execution.
    """
    # ── Build system prompt ───────────────────────────────────────────────
    resume_summary = "（用户尚未上传简历）"
    if resume_path:
        try:
            text = _extract_pdf_text(Path(resume_path))
            resume_summary = text.strip() if text.strip() else "（简历内容为空）"
        except Exception as e:
            resume_summary = f"（简历解析失败: {e}）"

    memory_lines = [
        f"- {k}: {v}" for k, v in (memory_context or {}).items() if v
    ]
    memory_block = "\n".join(memory_lines) if memory_lines else "（暂无持久记忆）"

    system_content = SYSTEM_PROMPT.format(
        resume_summary=resume_summary,
        memory_block=memory_block,
    )

    # ── Build message history ─────────────────────────────────────────────
    content = user_message
    if resume_path:
        content += f"\n\n[简历文件路径: {resume_path}]"

    messages: list[dict] = [{"role": "system", "content": system_content}]
    for item in conversation_history or []:
        role = item.get("role")
        text = item.get("content")
        if role in {"user", "assistant"} and text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": content})

    last_tool_result = None

    for round_num in range(30):  # max 30 rounds
        # ── Call LLM ──────────────────────────────────────────────────────
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
            print(f"[agent] LLM error round {round_num}: {e}", flush=True)
            if round_num < 2:
                yield {"event": "reasoning", "data": {"text": f"连接异常，重试中... ({e})"}}
                await asyncio.sleep(2)
                continue
            yield {"event": "error", "data": {"message": f"LLM 调用失败: {e}"}}
            return

        message = response.choices[0].message

        # ── No tool calls → direct answer ─────────────────────────────────
        if not message.tool_calls:
            yield {
                "event": "done",
                "data": {
                    "message": message.content or "",
                    "last_tool_result": last_tool_result,
                },
            }
            return

        # ── Has tool calls → emit reasoning if present ────────────────────
        if message.content:
            import re
            plan_match = re.search(r"##\s*执行计划\s*(.*)", message.content, re.DOTALL)
            if plan_match:
                steps = []
                for line in plan_match.group(1).splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("##"):
                        break
                    m = re.match(r"^\d+\.\s*(.+)$", stripped)
                    if m:
                        steps.append(m.group(1).strip())
                if steps:
                    yield {"event": "plan", "data": {"steps": steps}}
            yield {"event": "reasoning", "data": {"text": message.content}}

        messages.append(message.model_dump())

        # ── Execute tool calls ────────────────────────────────────────────
        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            print(f"[agent] tool={fn_name} args={json.dumps(fn_args, ensure_ascii=False)[:120]}", flush=True)

            # ── terminate → end loop ──────────────────────────────────────
            if fn_name == "terminate":
                final_msg = fn_args.get("message", "任务完成")
                yield {
                    "event": "done",
                    "data": {"message": final_msg, "last_tool_result": last_tool_result},
                }
                return

            # ── ask_user → pause and wait for frontend confirmation ───────
            if fn_name == "ask_user":
                question = fn_args.get("question", "请确认是否继续？")
                event = confirm_store.arm(conversation_id) if conversation_id else None
                yield {
                    "event": "await_confirm",
                    "data": {"question": question, "tool_call_id": tool_call.id},
                }
                if event is not None:
                    try:
                        await asyncio.wait_for(event.wait(), timeout=300)
                        decision = confirm_store.take(conversation_id)
                    except asyncio.TimeoutError:
                        confirm_store.take(conversation_id)
                        decision = None
                else:
                    # no conversation_id, default to confirmed
                    decision = True

                result: dict
                if decision is True:
                    result = {"confirmed": True, "answer": "是，用户已确认"}
                elif decision is False:
                    result = {"confirmed": False, "answer": "否，用户拒绝"}
                else:
                    result = {"confirmed": False, "answer": "超时未响应，已取消"}

                messages.append({
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False),
                    "tool_call_id": tool_call.id,
                })
                continue

            # ── Regular tool call ─────────────────────────────────────────
            yield {"event": "tool_start", "data": {"tool": fn_name, "args": fn_args}}

            try:
                reset_decision_log()
                tool_result = await _call_tool(fn_name, fn_args)
                last_tool_result = {"tool": fn_name, "result": tool_result}
                result_str = json.dumps(tool_result, ensure_ascii=False)
            except Exception as e:
                tool_result = {"error": str(e), "traceback": traceback.format_exc()}
                last_tool_result = {"tool": fn_name, "result": tool_result}
                result_str = json.dumps(tool_result, ensure_ascii=False)

            for decision in consume_decision_log():
                yield {"event": "decision", "data": decision}
            yield {"event": "tool_result", "data": {"tool": fn_name, "result": tool_result}}

            messages.append({
                "role": "tool",
                "content": result_str,
                "tool_call_id": tool_call.id,
            })

    # Loop exhausted
    yield {
        "event": "done",
        "data": {
            "message": "Agent 达到最大迭代次数（30），返回现有结果。",
            "last_tool_result": last_tool_result,
        },
    }


# ── Tool implementations ──────────────────────────────────────────────────────

async def _call_tool(name: str, args: dict) -> dict:
    if name == "web_search":
        from tools.web_search import web_search
        return {"results": web_search(**args)}

    if name == "browser_open":
        return await _browser_open(args["url"])

    if name == "job_search":
        from tools.job_search import browser_job_search
        return await browser_job_search(**args)

    if name == "resume_customizer":
        from tools.resume_customizer import resume_customizer
        return resume_customizer(**args)

    if name == "interview_prep":
        from tools.interview_prep import interview_prep
        return interview_prep(**args)

    if name == "apply":
        return await _apply(**args)

    if name == "file_read":
        return _file_read(**args)

    if name == "file_write":
        return _file_write(**args)

    if name == "python_exec":
        return await _python_exec(**args)

    raise ValueError(f"Unknown tool: {name}")


async def _browser_open(url: str) -> dict:
    """Open a URL with the browser harness and extract page text."""
    try:
        from tools.browser_harness import run_browser_harness_script
        script = f"""
import asyncio, time
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto({url!r}, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(1)
        text = await page.evaluate("document.body.innerText")
        title = await page.title()
        return {{"title": title, "url": page.url, "text": text[:3000]}}

import asyncio, sys, json
result = asyncio.run(main())
print(json.dumps(result, ensure_ascii=False))
"""
        result = await run_browser_harness_script(script, timeout=45)
        return result
    except Exception as e:
        # Fallback: simple HTTP fetch
        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)[:3000]
            return {"url": url, "text": text, "via": "http_fallback"}
        except Exception as e2:
            return {"error": str(e2), "url": url}


async def _apply(
    job_url: str,
    resume_md_path: str,
    job_id: str,
    cover_letter_path: str = "",
    job_title: str = "",
    company: str = "",
) -> dict:
    from tools.linkedin_apply import linkedin_auto_apply, external_auto_apply
    if "linkedin.com" in job_url.lower():
        return await linkedin_auto_apply(
            job_url=job_url,
            resume_md_path=resume_md_path,
            job_id=job_id,
            cover_letter_path=cover_letter_path,
        )
    return await external_auto_apply(
        job_url=job_url,
        resume_md_path=resume_md_path,
        job_id=job_id,
        cover_letter_path=cover_letter_path,
        job_title=job_title,
        company=company,
    )


def _file_read(path: str, encoding: str = "utf-8") -> dict:
    resolved = Path(path).resolve()
    try:
        content = resolved.read_text(encoding=encoding)
        return {"path": str(resolved), "content": content, "size": len(content)}
    except FileNotFoundError:
        return {"error": f"文件不存在: {path}"}
    except Exception as e:
        return {"error": str(e)}


def _file_write(path: str, content: str, encoding: str = "utf-8") -> dict:
    resolved = Path(path).resolve()
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding=encoding)
        return {"path": str(resolved), "written_bytes": len(content.encode(encoding))}
    except Exception as e:
        return {"error": str(e)}


async def _python_exec(code: str, timeout: int = 30) -> dict:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": f"执行超时（{timeout}s）", "code": code[:200]}
        return {
            "returncode": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }
    finally:
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass
