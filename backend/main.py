"""FastAPI backend — serves the Next.js frontend."""
import asyncio
import os
import tempfile
import uuid
from pathlib import Path
from collections import OrderedDict

import json

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

from agent import run_agent
from db import init_db, seed_db, track_application, list_applications

app = FastAPI(title="Job Hunt Agent API")

# ── Short-term memory: session store ────────────────────────────────────────
# Stores conversation history per session_id (excludes system message).
# Capped at 100 sessions (oldest evicted first) to avoid unbounded memory use.
_MAX_SESSIONS = 100
SESSIONS: OrderedDict[str, list] = OrderedDict()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    seed_db()


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Agent chat ───────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    resume_path: str | None = None
    session_id: str | None = None  # pass this back on subsequent turns


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Main agent endpoint. Accepts a natural language message.
    Returns SSE stream of agent events.

    Short-term memory: include session_id from a previous response to continue
    a conversation. A new session_id is created and sent back as a
    'session_id' SSE event on the first call.
    """
    # Resolve or create session
    sid = req.session_id if req.session_id and req.session_id in SESSIONS else str(uuid.uuid4())
    history = SESSIONS.get(sid, [])

    async def event_stream():
        # Send session_id first so the frontend can persist it
        yield f"event: session_id\ndata: {json.dumps({'session_id': sid})}\n\n"

        async for event in run_agent(req.message, req.resume_path, history=history):
            if event.get("event") == "session_update":
                # Update in-memory session store
                new_history = event["data"]["history"]
                SESSIONS[sid] = new_history
                SESSIONS.move_to_end(sid)
                # Evict oldest session if over cap
                if len(SESSIONS) > _MAX_SESSIONS:
                    SESSIONS.popitem(last=False)
                continue  # don't forward this internal event to the client

            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}), ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.delete("/api/session/{session_id}")
def clear_session(session_id: str):
    """Clear a specific session's conversation history."""
    SESSIONS.pop(session_id, None)
    return {"status": "cleared"}


# ── Resume upload ─────────────────────────────────────────────────────────

@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload a PDF resume. Returns the server-side file path.
    The path is used in subsequent /api/chat calls.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 格式")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    content = await file.read()
    tmp.write(content)
    tmp.close()

    return {"path": tmp.name, "filename": file.filename}


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
