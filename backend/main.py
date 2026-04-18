"""FastAPI backend — serves the Next.js frontend."""
import asyncio
import os
import tempfile
from pathlib import Path

import json

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

from agent import run_agent
from db import init_db, seed_db, track_application, list_applications

app = FastAPI(title="Job Hunt Agent API")

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


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Main agent endpoint. Accepts a natural language message.
    Returns SSE stream of agent events.
    """
    async def event_stream():
        async for event in run_agent(req.message, req.resume_path):
            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}), ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


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
