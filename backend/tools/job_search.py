"""MCP Tool 1: browser_job_search — browser-use powered (Zhipu GLM via OpenAI compat)."""
import json
import os
import uuid
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
CACHED_JOBS_PATH = Path(__file__).parent.parent / "data" / "cached_jobs.json"

# 智谱 OpenAI 兼容端点，无需 Anthropic API key
_ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"
_ZHIPU_API_KEY  = os.getenv("ZHIPUAI_API_KEY", "")


async def browser_job_search(
    query: str,
    location: str = "remote",
    limit: int = 10,
    source: str = "hn",   # "hn" | "remoteok"
) -> list[dict]:
    """
    Search jobs using browser-use agent.
    Falls back to RemoteOK API, then cached_jobs.json.
    Returns list[dict] matching the Job schema.
    """
    if source == "hn":
        try:
            return await _fetch_hn_jobs(query, limit)
        except Exception as e:
            print(f"[job_search] HN failed ({e}), trying RemoteOK...")
            try:
                return _fetch_remoteok_jobs(query, limit)
            except Exception as e2:
                print(f"[job_search] RemoteOK failed ({e2}), loading cache...")
                return _load_cached_jobs(query, limit)

    if source == "remoteok":
        try:
            return _fetch_remoteok_jobs(query, limit)
        except Exception as e:
            print(f"[job_search] RemoteOK failed ({e}), loading cache...")
            return _load_cached_jobs(query, limit)

    return _load_cached_jobs(query, limit)


async def _fetch_hn_jobs(query: str, limit: int) -> list[dict]:
    """Use browser-use to scrape HN Who's Hiring (driven by Zhipu GLM)."""
    from browser_use import Agent, Browser, BrowserConfig
    from langchain_openai import ChatOpenAI  # 用 OpenAI 兼容接口对接智谱

    llm = ChatOpenAI(
        model="glm-4",
        api_key=_ZHIPU_API_KEY,
        base_url=_ZHIPU_BASE_URL,
    )
    browser = Browser(config=BrowserConfig(headless=False))

    task = (
        f"Go to https://news.ycombinator.com/submitted?id=whoishiring . "
        f"Find the most recent 'Ask HN: Who is Hiring?' thread and click on it. "
        f"Read through the comments and find up to {min(limit * 2, 20)} job postings "
        f"that mention '{query}'. "
        f"For each matching job, extract: company name, job title, remote/location, "
        f"and the full job description text. "
        f"Return a JSON array with fields: title, company, url (use the HN comment URL), "
        f"description, location. Return ONLY the JSON array, no other text."
    )

    agent = Agent(task=task, llm=llm, browser=browser)
    result = await agent.run()

    # Parse result — browser-use returns the last agent message
    raw = result.final_result() if hasattr(result, "final_result") else str(result)
    try:
        # Extract JSON from result
        import re
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            jobs_raw = json.loads(match.group())
        else:
            jobs_raw = json.loads(raw)
    except Exception:
        raise ValueError(f"Could not parse browser-use result as JSON: {raw[:200]}")

    return [_normalize_job(j, source="hn") for j in jobs_raw[:limit]]


def _fetch_remoteok_jobs(query: str, limit: int) -> list[dict]:
    """Fetch from RemoteOK public JSON API (no browser needed)."""
    resp = requests.get(
        "https://remoteok.com/api",
        headers={"User-Agent": "job-hunt-agent/1.0"},
        timeout=15,
    )
    resp.raise_for_status()
    all_jobs = [j for j in resp.json() if isinstance(j, dict) and j.get("position")]

    query_lower = query.lower()
    matched = [
        j for j in all_jobs
        if query_lower in (j.get("position", "") + j.get("description", "")).lower()
    ]

    return [_normalize_job(j, source="remoteok") for j in matched[:limit]]


def _load_cached_jobs(query: str, limit: int) -> list[dict]:
    """Load from cached_jobs.json as last resort."""
    if not CACHED_JOBS_PATH.exists():
        raise FileNotFoundError(f"cached_jobs.json not found at {CACHED_JOBS_PATH}")

    with open(CACHED_JOBS_PATH) as f:
        jobs = json.load(f)

    query_lower = query.lower()
    matched = [
        j for j in jobs
        if query_lower in (j.get("title", "") + j.get("description", "")).lower()
    ] or jobs  # if no match, return all cached

    return matched[:limit]


def _normalize_job(raw: dict, source: str) -> dict:
    """Normalize to Job schema."""
    return {
        "job_id": raw.get("id") or raw.get("slug") or str(uuid.uuid4()),
        "title": raw.get("title") or raw.get("position", "Unknown"),
        "company": raw.get("company", "Unknown"),
        "url": raw.get("url") or raw.get("apply_url", ""),
        "description": raw.get("description", "")[:2000],  # cap length
        "location": raw.get("location", "Remote"),
        "source": source,
        "posted_at": raw.get("date") or raw.get("epoch", ""),
        "match_score": 0,   # scored separately by agent
        "match_reason": "缓存预置数据，未计算匹配分" if source == "cached" else "",
    }
