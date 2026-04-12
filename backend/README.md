# Job Hunt Agent — Backend

Python backend (FastAPI + browser-use + Claude).

## Setup

```bash
cp .env.example .env
# fill in ANTHROPIC_API_KEY

uv sync
playwright install chromium
```

## Run

```bash
uv run python main.py
# → http://localhost:8000
```

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Main agent endpoint |
| POST | `/api/resume/upload` | Upload PDF resume |
| GET | `/api/applications` | List all tracked applications |
| POST | `/api/applications` | Save/update an application |
| GET | `/api/diff/{job_id}` | View HTML resume diff |

## Chat examples

```json
{"message": "找 remote 的 Python backend 职位"}
{"message": "帮我定制简历投第一个职位", "resume_path": "/tmp/resume.pdf"}
{"message": "帮我准备 Acme Tech 的面试"}
```
