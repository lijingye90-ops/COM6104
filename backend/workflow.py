"""Demo-first 3-agent workflow orchestration."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from db import get_conversation_context
from llm_client import create_chat_completion, create_client
from tools.job_search import browser_job_search
from tools.interview_prep import interview_prep
from tools.resume_customizer import _extract_pdf_text, resume_customizer
from tools.linkedin_apply import (
    build_email_application_assist,
    external_auto_apply,
    linkedin_auto_apply,
)
from tools.email_sender import send_email
from workflow_store import (
    create_or_reset_workflow_state,
    get_workflow_state,
    update_workflow_state,
)

client = create_client()
JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _plan_steps() -> list[str]:
    return [
        "Agent A 搜索外部职位来源并汇总候选岗位",
        "Agent B 评估匹配度并推荐 1 个最佳岗位",
        "Agent C 生成定制简历与求职信",
        "基于生成材料发起投递，并保存可恢复状态",
        "生成面试准备材料：5 道高频题 + STAR 答案",
    ]


def _summarize_jobs(jobs: list[dict], limit: int = 3) -> list[dict]:
    summary = []
    for job in jobs[:limit]:
        summary.append(
            {
                "job_id": job.get("job_id", ""),
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "url": job.get("url", ""),
                "description": (job.get("description") or "")[:800],
                "match_score": job.get("match_score", 0),
                "match_reason": job.get("match_reason", ""),
            }
        )
    return summary


def _agent_cards(state: dict) -> dict[str, dict]:
    stage = state.get("current_stage", "started")
    recommended = state.get("recommended_job") or {}
    apply_result = state.get("apply_result") or {}
    last_error = state.get("last_error", "")

    def status_for(role_stage: str) -> str:
        ordering = {
            "started": 0,
            "search_done": 1,
            "match_done": 2,
            "materials_done": 3,
            "apply_done": 4,
            "error": 99,
        }
        target = ordering[role_stage]
        current = ordering.get(stage, 0)
        if stage == "error" and last_error:
            return "error"
        if current > target:
            return "done"
        if current == target:
            return "done"
        if current + 1 == target:
            return "running"
        return "pending"

    return {
        "search": {
            "label": "Agent A",
            "title": "职位搜索",
            "status": "done" if stage in {"search_done", "match_done", "materials_done", "apply_done"} else ("error" if stage == "error" else "running"),
            "detail": (
                f"已收集 {len(state.get('search_results') or [])} 个候选岗位"
                if state.get("search_results")
                else "负责搜索外部职位来源"
            ),
        },
        "match": {
            "label": "Agent B",
            "title": "匹配评估",
            "status": (
                "done"
                if stage in {"match_done", "materials_done", "apply_done"}
                else "running" if stage == "search_done" else "error" if stage == "error" else "pending"
            ),
            "detail": (
                f"推荐 {recommended.get('company', '目标公司')} / {recommended.get('title', '目标岗位')}"
                if recommended
                else "负责选择最优岗位"
            ),
        },
        "customize": {
            "label": "Agent C",
            "title": "材料定制",
            "status": (
                "done"
                if stage in {"materials_done", "apply_done"}
                else "running" if stage == "match_done" else "error" if stage == "error" else "pending"
            ),
            "detail": (
                Path(state.get("resume_file_path", "")).name
                if state.get("resume_file_path")
                else "负责生成定制简历与求职信"
            ),
        },
        "apply": {
            "label": "Apply",
            "title": "投递执行",
            "status": (
                "done"
                if stage == "apply_done"
                else "running" if stage == "materials_done" else "error" if stage == "error" else "pending"
            ),
            "detail": (
                apply_result.get("status")
                or "负责发起真实投递或降级到可继续状态"
            ),
        },
    }


def build_workflow_payload(state: dict) -> dict:
    recommended = state.get("recommended_job") or {}
    apply_result = state.get("apply_result") or {}
    return {
        "conversation_id": state.get("conversation_id"),
        "goal": state.get("goal", ""),
        "status": state.get("status", "running"),
        "current_stage": state.get("current_stage", "started"),
        "recommended_job": recommended,
        "top_jobs_summary": state.get("search_results") or [],
        "artifact_paths": {
            "resume_file_path": state.get("resume_file_path", ""),
            "cover_letter_path": state.get("cover_letter_path", ""),
        },
        "apply_result": apply_result,
        "last_error": state.get("last_error", ""),
        "updated_at": state.get("updated_at", ""),
        "agents": _agent_cards(state),
    }


def _extract_resume_summary(resume_path: str | None) -> str:
    if not resume_path:
        return "（暂无简历摘要）"
    try:
        return _extract_pdf_text(Path(resume_path))[:2000] or "（简历内容为空）"
    except Exception as exc:
        return f"（简历解析失败: {exc}）"


def _parse_match_result(raw: str) -> dict | None:
    match = JSON_OBJECT_RE.search(raw or "")
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _start_progress_task(coro_factory):
    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def progress_callback(payload: dict) -> None:
        await queue.put(payload)

    task = asyncio.create_task(coro_factory(progress_callback))
    return task, queue


async def _yield_progress_updates(task, queue: asyncio.Queue, *, tool: str, agent: str):
    while True:
        if task.done() and queue.empty():
            break
        try:
            payload = await asyncio.wait_for(queue.get(), timeout=0.2)
        except asyncio.TimeoutError:
            continue
        yield {
            "event": "tool_progress",
            "data": {
                "tool": tool,
                "agent": agent,
                **payload,
            },
        }


async def _agent_a_search_worker(goal: str, progress_callback=None) -> list[dict]:
    return await browser_job_search(
        query=goal,
        location="remote",
        limit=10,
        source="hn",
        progress_callback=progress_callback,
    )


async def _agent_b_match_worker(goal: str, jobs: list[dict], resume_path: str | None = None) -> dict:
    if not jobs:
        raise ValueError("Agent B 无法评估，因为没有候选职位。")
    if len(jobs) == 1:
        selected = jobs[0].copy()
        selected["selection_reason"] = "只有一个候选职位，默认选为当前最佳匹配。"
        return selected

    resume_summary = _extract_resume_summary(resume_path)
    messages = [
        {
            "role": "system",
            "content": (
                "你是 Agent B，负责在候选岗位中选出最适合用户的一项。"
                "请返回严格 JSON，包含 job_id 和 selection_reason。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"求职目标：{goal}\n\n"
                f"简历摘要：\n{resume_summary}\n\n"
                f"候选岗位：\n{json.dumps(_summarize_jobs(jobs, limit=5), ensure_ascii=False)}\n\n"
                "请从中选择最匹配的一项，输出 JSON："
                '{"job_id":"...", "selection_reason":"..."}'
            ),
        },
    ]
    response = await asyncio.to_thread(
        create_chat_completion,
        client=client,
        stage="agent_orchestrator",
        messages=messages,
    )
    payload = _parse_match_result(response.choices[0].message.content or "")
    selected_job_id = payload.get("job_id") if payload else None
    selection_reason = payload.get("selection_reason") if payload else ""
    selected = next((job for job in jobs if str(job.get("job_id")) == str(selected_job_id)), jobs[0]).copy()
    selected["selection_reason"] = selection_reason or "按匹配度与简历相关性综合选出该岗位。"
    return selected


async def _agent_c_customize_worker(resume_path: str | None, job: dict) -> dict:
    if not resume_path:
        raise ValueError("缺少简历路径，Agent C 无法生成定制材料。")
    return await asyncio.to_thread(
        resume_customizer,
        resume_path=resume_path,
        job_description=job.get("description") or job.get("selection_reason") or "",
        job_id=str(job.get("job_id") or ""),
        generate_cover_letter=True,
    )


async def _agent_d_interview_prep_worker(job: dict) -> dict:
    return await asyncio.to_thread(
        interview_prep,
        company=job.get("company") or "目标公司",
        job_title=job.get("title") or "目标职位",
        job_description=job.get("description") or job.get("selection_reason") or "",
    )


async def _apply_worker(job: dict, customized: dict, progress_callback=None) -> dict:
    url = job.get("url") or ""
    if not url:
        return {
            "status": "fallback",
            "reason": "missing_job_url",
            "detail": "目标岗位缺少可投递链接，已保留定制材料供手动继续。",
        }
    if "linkedin.com" in url.lower():
        return await linkedin_auto_apply(
            job_url=url,
            resume_md_path=customized["resume_file_path"],
            job_id=str(job.get("job_id") or ""),
            cover_letter_path=customized.get("cover_letter_file_path", ""),
            progress_callback=progress_callback,
        )
    return await external_auto_apply(
        job_url=url,
        resume_md_path=customized["resume_file_path"],
        job_id=str(job.get("job_id") or ""),
        cover_letter_path=customized.get("cover_letter_file_path", ""),
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        progress_callback=progress_callback,
    )


async def _maybe_send_email_only_application(job: dict, customized: dict, apply_result: dict) -> tuple[dict, dict | None]:
    if apply_result.get("status") != "fallback" or apply_result.get("reason") != "email_only_application":
        return apply_result, None

    package = apply_result.get("package", {})
    email_assist = build_email_application_assist(
        company=job.get("company", ""),
        title=job.get("title", ""),
        job_url=job.get("url", ""),
        resume_pdf_path=package.get("resume_pdf", ""),
        cover_letter_path=customized.get("cover_letter_file_path", ""),
        apply_email=package.get("apply_email", ""),
    )
    apply_result = {**apply_result, "email_assist": email_assist}

    try:
        email_result = await asyncio.to_thread(
            send_email,
            to_email=email_assist.get("apply_email", ""),
            subject=email_assist.get("subject", ""),
            body=email_assist.get("body", ""),
            resume_path=email_assist.get("resume_pdf", ""),
            cover_letter_path=email_assist.get("cover_letter", ""),
        )
    except Exception as exc:
        apply_result["email_send_error"] = str(exc)
        return apply_result, None

    sent_result = {
        "status": "applied",
        "job_id": str(job.get("job_id") or ""),
        "detail": f"Application email sent via {email_result.get('provider', 'email')}",
        "channel": "email",
        "package": package,
        "email_assist": email_assist,
        "email_result": email_result,
    }
    return sent_result, email_result


def _done_payload(
    state: dict,
    last_tool_result: dict | None = None,
    interview_result: dict | None = None,
) -> dict:
    recommended = state.get("recommended_job") or {}
    apply_result = state.get("apply_result") or {}
    details = {
        "current_stage": state.get("current_stage", ""),
        "recommended_company": recommended.get("company", ""),
        "recommended_title": recommended.get("title", ""),
        "apply_status": apply_result.get("status", ""),
    }
    details = {key: value for key, value in details.items() if value}
    summary = "全流程已完成（搜索→匹配→定制→投递→面试准备），可刷新页面继续查看与恢复。"
    if apply_result.get("status"):
        summary = f"全流程已完成，当前投递状态：{apply_result.get('status')}。"
    payload = {
        "summary": summary,
        "message": summary,
        "details": details,
        "workflow_state": build_workflow_payload(state),
        "last_tool_result": last_tool_result,
    }
    if interview_result:
        payload["interview_prep"] = interview_result
    return payload


async def run_workflow(
    *,
    goal: str,
    conversation_id: str,
    resume_path: str | None = None,
):
    """
    Orchestrate the explicit Agent A / B / C workflow.

    State machine:
      started -> search_done -> match_done -> materials_done -> apply_done
                     +-------------------> error <--------------------+
    """
    state = get_workflow_state(conversation_id)
    if state is None or state.get("goal") != goal:
        state = create_or_reset_workflow_state(
            conversation_id,
            goal=goal,
            input_resume_path=resume_path or "",
        )

    yield {"event": "plan", "data": {"steps": _plan_steps()}}
    yield {"event": "workflow", "data": build_workflow_payload(state)}

    jobs = state.get("search_results") or []
    recommended_job = state.get("recommended_job") or {}
    customized: dict | None = None

    try:
        if state["current_stage"] == "started":
            yield {"event": "reasoning", "data": {"text": "Agent A 开始搜索职位，并把候选岗位交给 Agent B。"}}
            search_args = {"query": goal, "location": "remote", "limit": 10, "source": "hn"}
            yield {
                "event": "tool_start",
                "data": {"tool": "browser_job_search", "args": search_args, "agent": "Agent A"},
            }
            search_task, search_queue = _start_progress_task(
                lambda progress_callback: _agent_a_search_worker(goal, progress_callback=progress_callback)
            )
            async for progress_event in _yield_progress_updates(
                search_task,
                search_queue,
                tool="browser_job_search",
                agent="Agent A",
            ):
                yield progress_event
            jobs = await search_task
            summarized_jobs = _summarize_jobs(jobs, limit=3)
            state = update_workflow_state(
                conversation_id,
                current_stage="search_done",
                search_results=summarized_jobs,
                status="running",
                last_error="",
            )
            yield {
                "event": "tool_result",
                "data": {"tool": "browser_job_search", "result": summarized_jobs, "agent": "Agent A"},
            }
            yield {"event": "workflow", "data": build_workflow_payload(state)}
        else:
            jobs = state.get("search_results") or []
            yield {"event": "reasoning", "data": {"text": "已复用 Agent A 的搜索结果，本轮不会重复搜索。"}}

        if state["current_stage"] == "search_done":
            yield {"event": "reasoning", "data": {"text": "Agent B 正在评估匹配度，并选择 1 个最佳岗位。"}}
            yield {
                "event": "tool_start",
                "data": {"tool": "agent_b_match", "args": {"goal": goal}, "agent": "Agent B"},
            }
            recommended_job = await _agent_b_match_worker(goal, jobs, resume_path=resume_path)
            state = update_workflow_state(
                conversation_id,
                current_stage="match_done",
                recommended_job=recommended_job,
                status="running",
                last_error="",
            )
            yield {
                "event": "tool_result",
                "data": {"tool": "agent_b_match", "result": recommended_job, "agent": "Agent B"},
            }
            yield {"event": "workflow", "data": build_workflow_payload(state)}
        else:
            recommended_job = state.get("recommended_job") or {}
            if recommended_job:
                yield {"event": "reasoning", "data": {"text": "已复用 Agent B 的推荐结果，本轮不会重复评估。"}}

        if state["current_stage"] == "match_done":
            yield {"event": "reasoning", "data": {"text": "Agent C 正在生成定制简历和求职信。"}}
            yield {
                "event": "tool_start",
                "data": {
                    "tool": "resume_customizer",
                    "args": {"job_id": recommended_job.get("job_id")},
                    "agent": "Agent C",
                },
            }
            yield {
                "event": "tool_progress",
                "data": {
                    "tool": "resume_customizer",
                    "agent": "Agent C",
                    "stage": "resume_customize_start",
                    "message": "正在根据目标岗位生成定制简历和求职信",
                },
            }
            customized = await _agent_c_customize_worker(resume_path, recommended_job)
            state = update_workflow_state(
                conversation_id,
                current_stage="materials_done",
                resume_file_path=customized.get("resume_file_path", ""),
                cover_letter_path=customized.get("cover_letter_file_path", ""),
                status="running",
                last_error="",
            )
            yield {
                "event": "tool_result",
                "data": {"tool": "resume_customizer", "result": customized, "agent": "Agent C"},
            }
            yield {"event": "workflow", "data": build_workflow_payload(state)}
        else:
            if state.get("resume_file_path"):
                yield {"event": "reasoning", "data": {"text": "已复用 Agent C 的材料产物，本轮不会重复生成。"}}
                customized = {
                    "resume_file_path": state.get("resume_file_path", ""),
                    "cover_letter_file_path": state.get("cover_letter_path", ""),
                }

        last_tool_result = None
        interview_result = None
        if state["current_stage"] == "materials_done":
            yield {"event": "reasoning", "data": {"text": "开始发起真实投递。如果外部站点阻塞，会降级为可继续状态。"}}
            yield {
                "event": "tool_start",
                "data": {
                    "tool": "apply_worker",
                    "args": {"job_id": recommended_job.get("job_id")},
                    "agent": "Apply",
                },
            }
            apply_task, apply_queue = _start_progress_task(
                lambda progress_callback: _apply_worker(
                    recommended_job,
                    customized or {},
                    progress_callback=progress_callback,
                )
            )
            async for progress_event in _yield_progress_updates(
                apply_task,
                apply_queue,
                tool="apply_worker",
                agent="Apply",
            ):
                yield progress_event
            apply_result = await apply_task

            if apply_result.get("status") == "fallback" and apply_result.get("reason") == "email_only_application":
                yield {"event": "reasoning", "data": {"text": "检测到该岗位只接受邮箱投递，正在自动生成并发送申请邮件。"}}
                package = apply_result.get("package", {})
                yield {
                    "event": "tool_start",
                    "data": {
                        "tool": "send_email",
                        "args": {"to_email": package.get("apply_email", "")},
                        "agent": "Apply",
                    },
                }
                apply_result, email_result = await _maybe_send_email_only_application(
                    recommended_job,
                    customized or {},
                    apply_result,
                )
                if email_result is not None:
                    yield {
                        "event": "tool_result",
                        "data": {
                            "tool": "send_email",
                            "result": email_result,
                            "agent": "Apply",
                        },
                    }
                else:
                    email_error = apply_result.get("email_send_error", "邮件发送未执行")
                    yield {
                        "event": "tool_progress",
                        "data": {
                            "tool": "send_email",
                            "agent": "Apply",
                            "stage": "email_send_skipped",
                            "message": f"自动邮件发送未完成，将保留邮件投递包供继续处理：{email_error}",
                        },
                    }

            last_tool_result = {"tool": "apply_worker", "result": apply_result}
            state = update_workflow_state(
                conversation_id,
                current_stage="apply_done",
                status="completed",
                apply_result=apply_result,
                last_error="",
            )
            yield {
                "event": "tool_result",
                "data": {"tool": "apply_worker", "result": apply_result, "agent": "Apply"},
            }
            yield {"event": "workflow", "data": build_workflow_payload(state)}

            # Step 5 — interview prep (best-effort, never blocks done)
            try:
                yield {"event": "reasoning", "data": {"text": "投递完成，正在生成面试准备材料…"}}
                yield {
                    "event": "tool_start",
                    "data": {
                        "tool": "interview_prep",
                        "args": {"job_id": recommended_job.get("job_id")},
                        "agent": "Interview",
                    },
                }
                yield {
                    "event": "tool_progress",
                    "data": {
                        "tool": "interview_prep",
                        "agent": "Interview",
                        "stage": "interview_prep_start",
                        "message": "正在根据岗位描述生成面试准备题库与 STAR 答案",
                    },
                }
                interview_result = await _agent_d_interview_prep_worker(recommended_job)
                yield {
                    "event": "tool_result",
                    "data": {"tool": "interview_prep", "result": interview_result, "agent": "Interview"},
                }
            except Exception as exc:
                yield {"event": "reasoning", "data": {"text": f"面试准备生成失败（不影响投递结果）：{exc}"}}

            yield {"event": "done", "data": _done_payload(state, last_tool_result=last_tool_result, interview_result=interview_result)}
            return

        if state["current_stage"] == "apply_done":
            yield {"event": "done", "data": _done_payload(state)}
            return

        yield {"event": "done", "data": _done_payload(state)}
    except Exception as exc:
        state = update_workflow_state(
            conversation_id,
            status="error",
            current_stage="error",
            last_error=str(exc),
        )
        yield {"event": "workflow", "data": build_workflow_payload(state)}
        yield {
            "event": "error",
            "data": {
                "message": str(exc),
                "workflow_state": build_workflow_payload(state),
            },
        }
