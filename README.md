# Job Hunt Agent — COM6104 Group Project

An autonomous AI Agent that automates the entire job-hunting workflow:
search → resume customization → interview prep → LinkedIn auto-apply.

## Architecture

```
┌─────────────────────┐        SSE stream        ┌──────────────────────┐
│   Next.js Frontend  │ ◄──────────────────────► │  FastAPI Backend     │
│   (agent/)          │                           │  (backend/)          │
└─────────────────────┘                           │                      │
                                                  │  GLM-4 Agent Loop    │
                                                  │  + Short-term Memory │
                                                  └────────┬─────────────┘
                                                           │ tool calls
                                          ┌────────────────┼────────────────┐
                                          ▼                ▼                ▼
                                   MCP Tool 1       MCP Tool 2/3     MCP Tool 4
                                  job_search      resume/interview  linkedin_apply
                                (browser-use)      (GLM-4 GLM-4)   (browser-use)
```

## Tools (MCP-compliant)

| # | Tool | Description |
|---|------|-------------|
| 1 | `browser_job_search` | Scrapes HN Who's Hiring / RemoteOK via browser-use + GLM-4 |
| 2 | `resume_customizer` | Tailors a PDF resume to a JD; generates HTML diff + Cover Letter |
| 3 | `interview_prep` | Generates 5 STAR-framework interview Q&A pairs |
| 4 | `linkedin_auto_apply` | Automates LinkedIn Easy Apply via browser-use + GLM-4 |

All tools are exposed as an MCP server (`backend/mcp_server.py`) and testable with MCP Inspector.

## Short-term Memory

Each chat session maintains conversation history server-side (keyed by `session_id`).
The frontend receives a `session_id` on the first call and passes it back on subsequent turns,
enabling multi-turn reasoning across multiple API requests.

## Setup

### Prerequisites
- Python ≥ 3.11 with [uv](https://github.com/astral-sh/uv)
- Node.js ≥ 18 with [pnpm](https://pnpm.io)
- Playwright Chromium (for browser-use tools)
- A [Zhipu AI](https://open.bigmodel.cn) API key

### Backend

```bash
cd backend
cp .env.example .env
# Edit .env and set ZHIPUAI_API_KEY=your_key

uv sync
playwright install chromium

uv run python main.py
# → http://localhost:8000
```

### Frontend

```bash
cd agent
pnpm install
pnpm dev
# → http://localhost:3000
```

### MCP Inspector (tool testing)

```bash
cd backend
npx @modelcontextprotocol/inspector uv run python mcp_server.py
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Main agent endpoint (SSE stream) |
| `POST` | `/api/resume/upload` | Upload a PDF resume |
| `GET` | `/api/applications` | List all tracked applications |
| `POST` | `/api/applications` | Save / update an application |
| `GET` | `/api/diff/{job_id}` | View HTML resume diff |
| `DELETE` | `/api/session/{session_id}` | Clear session memory |

### Chat request body

```json
{
  "message": "找 remote 的 Python backend 职位",
  "resume_path": "/tmp/resume.pdf",
  "session_id": "abc123"
}
```

`session_id` is optional on the first call; the server returns one in an SSE `session_id` event.

## Project Structure

```
COM6104/
├── README.md
├── agent/          # Next.js frontend
│   ├── app/
│   └── components/
└── backend/        # FastAPI backend + MCP tools
    ├── main.py         # FastAPI app + session memory
    ├── agent.py        # GLM-4 agent loop
    ├── mcp_server.py   # MCP server (testable via Inspector)
    ├── db.py           # SQLite application tracker
    └── tools/
        ├── job_search.py       # Tool 1
        ├── resume_customizer.py # Tool 2
        ├── interview_prep.py   # Tool 3
        └── linkedin_apply.py   # Tool 4
```

## GitHub

[https://github.com/Phoenix-XInsenZHANG/COM6104](https://github.com/Phoenix-XInsenZHANG/COM6104)
