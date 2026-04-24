import tempfile
import uuid
from pathlib import Path

import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from agent import run_agent
from db import (
    get_conversation_context,
    get_memory_items,
    init_db,
    list_applications,
    list_chat_messages,
    save_chat_message,
    set_memory_item,
    track_application,
    upsert_conversation,
)
from workflow import run_workflow, build_workflow_payload
from workflow_store import get_workflow_state, init_workflow_store
from tools.job_search import browser_job_search
from tools.resume_customizer import resume_customizer
from tools.resume_customizer import _extract_pdf_text
from tools.interview_prep import interview_prep
from tools.linkedin_apply import (
    linkedin_auto_apply,
    external_auto_apply,
    build_email_application_assist,
)
from tools.email_sender import send_email_via_resend
from llm_client import get_base_url, get_model, get_model_routing_summary, get_pool_size

app = FastAPI(title="Job Hunt Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],  # Next.js dev server(s)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    init_workflow_store()


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta/model")
def model_meta():
    return {
        "model": get_model(),
        "base_url": get_base_url(),
        "pool_size": get_pool_size(),
        "routing": get_model_routing_summary(),
    }


@app.get("/api/jobs/search")
async def search_jobs(
    query: str,
    location: str = "remote",
    limit: int = 10,
    source: str = "remoteok",
):
    jobs = await browser_job_search(
        query=query,
        location=location,
        limit=limit,
        source=source,
    )
    return {"jobs": jobs}


# ── Agent chat ───────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    resume_path: str | None = None
    conversation_id: str | None = None


class WorkflowRequest(BaseModel):
    goal: str
    resume_path: str | None = None
    conversation_id: str | None = None


class JobApplyRequest(BaseModel):
    job_id: str
    title: str
    company: str
    url: str
    description: str
    resume_path: str


class ResumeCustomizeRequest(BaseModel):
    resume_path: str
    job_description: str
    job_id: str | None = None
    generate_cover_letter: bool = True


class InterviewPrepRequest(BaseModel):
    company: str
    job_title: str
    job_description: str


class SendEmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    resume_path: str = ""
    cover_letter_path: str = ""


@app.get("/api/chat/history")
def chat_history(conversation_id: str):
    raw_state = get_workflow_state(conversation_id)
    workflow_payload = build_workflow_payload(raw_state) if raw_state else None
    return {
        "conversation_id": conversation_id,
        "messages": list_chat_messages(conversation_id),
        "memory": get_memory_items(),
        "workflow": workflow_payload,
    }


@app.get("/api/workflow/state")
def workflow_state(conversation_id: str):
    state = get_workflow_state(conversation_id)
    return {
        "conversation_id": conversation_id,
        "workflow": state,
    }


@app.post("/api/workflow/run")
async def workflow_run(req: WorkflowRequest):
    conversation_id = req.conversation_id or str(uuid.uuid4())
    memory_items = get_memory_items()
    effective_resume_path = req.resume_path or memory_items.get("last_resume_path")
    upsert_conversation(
        conversation_id=conversation_id,
        title=req.goal[:80],
        last_resume_path=effective_resume_path or "",
    )
    save_chat_message(
        conversation_id=conversation_id,
        role="user",
        content=req.goal,
        event_type="user",
        payload={"resume_path": effective_resume_path or "", "workflow": True},
    )
    set_memory_item("last_user_goal", req.goal)
    if effective_resume_path:
        set_memory_item("last_resume_path", effective_resume_path)

    async def event_stream():
        async for event in run_workflow(
            goal=req.goal,
            conversation_id=conversation_id,
            resume_path=effective_resume_path,
        ):
            event_type = event.get("event", "message")
            payload = event.get("data", {})
            content = payload.get("text") or payload.get("content") or payload.get("message") or ""
            if event_type in {"plan", "reasoning", "done", "error"}:
                save_chat_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=content,
                    event_type=event_type,
                    payload=payload,
                )
            data = json.dumps(payload, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Conversation-Id": conversation_id,
        },
    )


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Main agent endpoint. Accepts a natural language message.
    Returns SSE stream of agent events.
    """
    conversation_id = req.conversation_id or str(uuid.uuid4())
    memory_items = get_memory_items()
    effective_resume_path = req.resume_path or memory_items.get("last_resume_path")
    prior_history = get_conversation_context(conversation_id)
    upsert_conversation(
        conversation_id=conversation_id,
        title=req.message[:80],
        last_resume_path=effective_resume_path or "",
    )
    save_chat_message(
        conversation_id=conversation_id,
        role="user",
        content=req.message,
        event_type="user",
        payload={"resume_path": effective_resume_path or ""},
    )
    set_memory_item("last_user_goal", req.message)
    if effective_resume_path:
        set_memory_item("last_resume_path", effective_resume_path)

    async def event_stream():
        async for event in run_agent(
            req.message,
            effective_resume_path,
            conversation_history=prior_history,
            memory_context=get_memory_items(),
        ):
            event_type = event.get("event", "message")
            payload = event.get("data", {})
            content = payload.get("text") or payload.get("content") or payload.get("message") or ""
            if event_type in {"plan", "reasoning", "done", "error"}:
                save_chat_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=content,
                    event_type=event_type,
                    payload=payload,
                )
            data = json.dumps(payload, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Conversation-Id": conversation_id,
        },
    )


@app.post("/api/jobs/apply")
async def apply_job(req: JobApplyRequest):
    if not req.url:
        raise HTTPException(400, "职位链接不能为空")

    try:
        customized = resume_customizer(
            resume_path=req.resume_path,
            job_description=req.description,
            job_id=req.job_id,
            generate_cover_letter=True,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        record = track_application(
            job_id=req.job_id,
            title=req.title,
            company=req.company,
            url=req.url,
            status="fallback",
            notes=f"resume_customizer_unavailable: {exc}",
        )
        return {
            "application": record,
            "apply_result": {
                "status": "fallback",
                "reason": "resume_customizer_unavailable",
                "detail": str(exc),
            },
        }

    if "linkedin.com" in req.url.lower():
        apply_result = await linkedin_auto_apply(
            job_url=req.url,
            resume_md_path=customized["resume_file_path"],
            job_id=req.job_id,
            cover_letter_path=customized.get("cover_letter_file_path", ""),
        )
    else:
        apply_result = await external_auto_apply(
            job_url=req.url,
            resume_md_path=customized["resume_file_path"],
            job_id=req.job_id,
            cover_letter_path=customized.get("cover_letter_file_path", ""),
            job_title=req.title,
            company=req.company,
        )

    notes = apply_result.get("detail") or apply_result.get("reason", "")
    if apply_result.get("status") == "fallback" and apply_result.get("reason") == "email_only_application":
        package = apply_result.get("package", {})
        apply_result["email_assist"] = build_email_application_assist(
            company=req.company,
            title=req.title,
            job_url=req.url,
            resume_pdf_path=package.get("resume_pdf", ""),
            cover_letter_path=customized.get("cover_letter_file_path", ""),
            apply_email=package.get("apply_email", ""),
        )

    record = track_application(
        job_id=req.job_id,
        title=req.title,
        company=req.company,
        url=req.url,
        status=apply_result.get("status", "fallback"),
        resume_file_path=customized["resume_file_path"],
        cover_letter_path=customized.get("cover_letter_file_path", ""),
        notes=notes,
    )

    return {
        "application": record,
        "apply_result": apply_result,
    }


@app.post("/api/resume/customize")
def customize_resume(req: ResumeCustomizeRequest):
    try:
        result = resume_customizer(
            resume_path=req.resume_path,
            job_description=req.job_description,
            job_id=req.job_id,
            generate_cover_letter=req.generate_cover_letter,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return result


@app.post("/api/interview/prep")
def prepare_interview(req: InterviewPrepRequest):
    return interview_prep(
        company=req.company,
        job_title=req.job_title,
        job_description=req.job_description,
    )


@app.post("/api/email/send")
def send_email(req: SendEmailRequest):
    try:
        return send_email_via_resend(
            to_email=req.to_email,
            subject=req.subject,
            body=req.body,
            resume_path=req.resume_path,
            cover_letter_path=req.cover_letter_path,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc


# ── Resume upload ─────────────────────────────────────────────────────────

@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload a PDF resume. Returns the server-side file path.
    The path is used in subsequent /api/chat calls.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 格式")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir="/tmp")
    content = await file.read()
    tmp.write(content)
    tmp.close()

    preview_text = ""
    try:
        preview_text = _extract_pdf_text(Path(tmp.name))[:2000]
    except Exception:
        preview_text = ""

    return {
        "path": tmp.name,
        "filename": file.filename,
        "preview_text": preview_text,
        "size_bytes": len(content),
    }


# ── Applications ─────────────────────────────────────────────────────────

@app.get("/api/applications")
def get_applications():
    return list_applications()


class TrackRequest(BaseModel):
    job_id: str
    title: str
    company: str
    url: str
    status: str = "saved"
    resume_file_path: str = ""
    cover_letter_path: str = ""
    notes: str = ""


@app.post("/api/applications")
def save_application(req: TrackRequest):
    record = track_application(**req.model_dump())
    return record


# ── Diff viewer ───────────────────────────────────────────────────────────

@app.get("/api/diff/{job_id}", response_class=HTMLResponse)
def view_diff(job_id: str):
    """Serve the HTML diff file for a job."""
    diff_path = Path(f"/tmp/diff_{job_id}.html")
    if not diff_path.exists():
        raise HTTPException(404, "Diff 文件不存在，请先定制简历")
    return HTMLResponse(content=diff_path.read_text(encoding="utf-8"))


@app.get("/api/memory")
def memory_items():
    """Return all persistent memory items as a dict.
    This lets the frontend display the memory store even when no conversation_id exists.
    """
    return get_memory_items()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
