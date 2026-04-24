"""MCP Tool 1: browser_job_search — browser-harness powered job navigation + AI ranking."""
import asyncio
import inspect
import json
import re
import uuid
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from llm_client import (
    create_chat_completion,
    create_client,
)
from .browser_harness import run_browser_harness_script

load_dotenv()
CACHED_JOBS_PATH = Path(__file__).parent.parent / "data" / "cached_jobs.json"
HN_SUBMISSIONS_URL = "https://news.ycombinator.com/submitted?id=whoishiring"
HN_THREAD_URL_RE = re.compile(r"https://news\.ycombinator\.com/item\?id=\d+")
TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9+#]+")


async def browser_job_search(
    query: str,
    location: str = "remote",
    limit: int = 10,
    source: str = "hn",   # "hn" | "remoteok"
    progress_callback=None,
) -> list[dict]:
    """
    Search jobs using browser-use agent.
    Falls back to RemoteOK API, then cached_jobs.json.
    Returns list[dict] matching the Job schema.
    """
    await _emit_progress(
        progress_callback,
        stage="search_init",
        message=f"开始搜索职位，来源={source}，query={query}",
        source=source,
        query=query,
    )

    if source == "hn":
        try:
            jobs = await _fetch_hn_jobs(query, location, limit, progress_callback=progress_callback)
            if jobs:
                await _emit_progress(
                    progress_callback,
                    stage="search_complete",
                    message=f"HN 搜索完成，得到 {len(jobs)} 个候选岗位",
                    count=len(jobs),
                    source="hn",
                )
                return jobs
            raise ValueError("HN returned no jobs")
        except Exception as e:
            print(f"[job_search] HN failed ({e}), trying RemoteOK...")
            await _emit_progress(
                progress_callback,
                stage="search_fallback",
                message=f"HN 搜索失败，准备回退到 RemoteOK：{e}",
                source="hn",
                error=str(e),
            )
            try:
                jobs = await asyncio.to_thread(_fetch_remoteok_jobs, query, limit)
                if jobs:
                    await _emit_progress(
                        progress_callback,
                        stage="search_complete",
                        message=f"RemoteOK 搜索完成，得到 {len(jobs)} 个候选岗位",
                        count=len(jobs),
                        source="remoteok",
                    )
                    return jobs
                raise ValueError("RemoteOK returned no jobs")
            except Exception as e2:
                print(f"[job_search] RemoteOK failed ({e2}), loading cache...")
                await _emit_progress(
                    progress_callback,
                    stage="search_fallback",
                    message=f"RemoteOK 失败，加载缓存职位：{e2}",
                    source="remoteok",
                    error=str(e2),
                )
                return await asyncio.to_thread(_load_cached_jobs, query, limit)

    if source == "remoteok":
        try:
            jobs = await asyncio.to_thread(_fetch_remoteok_jobs, query, limit)
            if jobs:
                await _emit_progress(
                    progress_callback,
                    stage="search_complete",
                    message=f"RemoteOK 搜索完成，得到 {len(jobs)} 个候选岗位",
                    count=len(jobs),
                    source="remoteok",
                )
                return jobs
            raise ValueError("RemoteOK returned no jobs")
        except Exception as e:
            print(f"[job_search] RemoteOK failed ({e}), loading cache...")
            await _emit_progress(
                progress_callback,
                stage="search_fallback",
                message=f"RemoteOK 失败，加载缓存职位：{e}",
                source="remoteok",
                error=str(e),
            )
            return await asyncio.to_thread(_load_cached_jobs, query, limit)

    return await asyncio.to_thread(_load_cached_jobs, query, limit)


async def _emit_progress(progress_callback, **payload) -> None:
    if progress_callback is None:
        return
    maybe_awaitable = progress_callback(payload)
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


async def _fetch_hn_jobs(query: str, location: str, limit: int, progress_callback=None) -> list[dict]:
    """Use browser-harness for navigation, then parse HN comments locally and rank with AI."""
    await _emit_progress(
        progress_callback,
        stage="hn_navigation",
        message="正在打开 whoishiring 页面并定位最新 HN 招聘帖",
    )
    thread_url = await _get_latest_hn_thread_url_via_browser(progress_callback=progress_callback)
    await _emit_progress(
        progress_callback,
        stage="hn_thread_found",
        message=f"已进入最新 HN 招聘帖：{thread_url}",
        thread_url=thread_url,
    )
    await _emit_progress(
        progress_callback,
        stage="hn_fetch_comments",
        message="正在抓取 HN 根评论并筛掉回复楼层",
        thread_url=thread_url,
    )
    comments = await asyncio.to_thread(_fetch_hn_root_comments, thread_url)
    await _emit_progress(
        progress_callback,
        stage="hn_comments_loaded",
        message=f"已加载 {len(comments)} 条 HN 根评论，开始用模型抽取职位",
        comment_count=len(comments),
    )
    jobs = await _extract_relevant_hn_jobs_with_ai_async(
        comments=comments,
        query=query,
        location=location,
        limit=limit,
        progress_callback=progress_callback,
    )
    if not jobs:
        raise ValueError("No relevant HN jobs extracted")
    return jobs[:limit]


async def _get_latest_hn_thread_url_via_browser(progress_callback=None) -> str:
    script = f"""
import json

def emit_progress(stage, message, **extra):
    payload = {{"__browser_harness_event__": "progress", "stage": stage, "message": message}}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))

emit_progress("open_submissions", "浏览器已启动，准备打开 whoishiring 提交页")
new_tab({HN_SUBMISSIONS_URL!r})
wait_for_load()
wait(1.0)

emit_progress("scan_submissions", "正在扫描 whoishiring 页面上的最新招聘帖链接")
clicked = js(\"\"\"
(() => {{
  const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const links = Array.from(document.querySelectorAll('a[href]')).filter(visible);
  const target = links.find((el) => /ask hn: who is hiring\\?/i.test(normalize(el.innerText || el.textContent || '')));
  if (!target) return false;
  target.click();
  return true;
}})()
\"\"\")
wait_for_load()
wait(1.0)
emit_progress("thread_ready", "已点击最新 HN 招聘帖，准备返回线程 URL", clicked=clicked, url=page_info()["url"])
print(json.dumps({{"clicked": clicked, "url": page_info()["url"]}}))
"""
    payload = await run_browser_harness_script(script, on_event=progress_callback)
    raw = payload.get("url", "")
    match = HN_THREAD_URL_RE.search(raw or "")
    if not match:
        raise ValueError(f"Could not parse HN thread URL from browser-harness result: {raw[:200]}")
    return match.group(0)


def _fetch_hn_root_comments(thread_url: str) -> list[dict]:
    resp = requests.get(
        thread_url,
        headers={"User-Agent": "job-hunt-agent/1.0"},
        timeout=20,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    comments = []
    for row in soup.select("tr.comtr"):
        indent_img = row.select_one("td.ind img")
        indent_width = int(indent_img.get("width", "0")) if indent_img else 0
        if indent_width != 0:
            continue

        comment_id = row.get("id")
        commtext = row.select_one(".commtext")
        if not comment_id or not commtext:
            continue

        text = commtext.get_text("\n", strip=True)
        if len(text) < 80:
            continue

        comments.append({
            "comment_id": comment_id,
            "url": f"https://news.ycombinator.com/item?id={comment_id}",
            "text": text[:4000],
        })

    return comments


async def _extract_relevant_hn_jobs_with_ai_async(
    comments: list[dict],
    query: str,
    location: str,
    limit: int,
    progress_callback=None,
) -> list[dict]:
    client = create_client()
    batches = [comments[index:index + 12] for index in range(0, len(comments), 12)]
    extracted_jobs: list[dict] = []

    total_batches = min(len(batches), 6)
    for index, batch in enumerate(batches[:6], start=1):
        await _emit_progress(
            progress_callback,
            stage="hn_llm_batch_start",
            message=f"模型正在抽取第 {index}/{total_batches} 批 HN 评论中的职位",
            batch=index,
            batch_size=len(batch),
        )
        prompt = (
            "You are helping extract relevant job postings from Hacker News 'Who is Hiring' root comments.\n"
            f"User query: {query}\n"
            f"Preferred location: {location}\n"
            f"Return only roles relevant to the query, using semantic matching, synonyms, and adjacent skills.\n"
            "For each relevant role, return JSON objects with keys: "
            "comment_id, title, company, location, description, url, match_score, match_reason.\n"
            f"Return a JSON array with at most {limit} objects.\n\n"
            f"Comments JSON:\n{json.dumps(batch, ensure_ascii=False)}"
        )

        response = await asyncio.to_thread(
            create_chat_completion,
            client=client,
            stage="job_extract",
            messages=[
                {
                    "role": "system",
                    "content": "Extract relevant jobs and return strict JSON only.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
        raw = response.choices[0].message.content or "[]"
        parsed_jobs = _parse_json_array(raw)
        extracted_jobs.extend(parsed_jobs)
        await _emit_progress(
            progress_callback,
            stage="hn_llm_batch_done",
            message=f"第 {index} 批评论抽取完成，得到 {len(parsed_jobs)} 条候选职位",
            batch=index,
            extracted_count=len(parsed_jobs),
        )
        if len(extracted_jobs) >= limit * 2:
            break

    deduped: dict[str, dict] = {}
    for job in extracted_jobs:
        comment_id = str(job.get("comment_id") or job.get("url") or uuid.uuid4())
        if comment_id not in deduped or int(job.get("match_score", 0)) > int(deduped[comment_id].get("match_score", 0)):
            deduped[comment_id] = job

    ranked = sorted(
        deduped.values(),
        key=lambda job: int(job.get("match_score", 0)),
        reverse=True,
    )
    await _emit_progress(
        progress_callback,
        stage="hn_rank_complete",
        message=f"HN 职位抽取与排序完成，保留前 {min(len(ranked), limit)} 条结果",
        count=min(len(ranked), limit),
    )
    return [_normalize_hn_ai_job(job) for job in ranked[:limit]]


def _parse_json_array(raw: str) -> list[dict]:
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []

    return [item for item in parsed if isinstance(item, dict)]


def _normalize_hn_ai_job(raw: dict) -> dict:
    return {
        "job_id": raw.get("comment_id") or str(uuid.uuid4()),
        "title": raw.get("title") or "Unknown",
        "company": raw.get("company") or "Unknown",
        "url": raw.get("url") or "",
        "description": (raw.get("description") or "")[:2000],
        "location": raw.get("location") or "Remote",
        "source": "hn",
        "posted_at": "",
        "match_score": raw.get("match_score") or 0,
        "match_reason": raw.get("match_reason") or "",
    }


def _fetch_remoteok_jobs(query: str, limit: int) -> list[dict]:
    """Fetch from RemoteOK public JSON API (no browser needed)."""
    resp = requests.get(
        "https://remoteok.com/api",
        headers={"User-Agent": "job-hunt-agent/1.0"},
        timeout=15,
    )
    resp.raise_for_status()
    resp.encoding = "utf-8"
    all_jobs = [j for j in resp.json() if isinstance(j, dict) and j.get("position")]

    query_lower = query.lower()
    matched = [
        j for j in all_jobs
        if query_lower in (j.get("position", "") + j.get("description", "")).lower()
    ]

    normalized = [_normalize_job(j, source="remoteok", query=query) for j in matched[:limit]]
    return sorted(normalized, key=lambda job: int(job.get("match_score", 0)), reverse=True)


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

    normalized = [_normalize_job(j, source="cached", query=query) for j in matched[:limit]]
    return sorted(normalized, key=lambda job: int(job.get("match_score", 0)), reverse=True)


def _tokenize_query(query: str) -> list[str]:
    return [token for token in TOKEN_SPLIT_RE.split(query.lower()) if token]


def _score_job_match(title: str, description: str, query: str) -> tuple[int, str]:
    haystack = f"{title} {description}".lower()
    tokens = _tokenize_query(query)
    if not tokens:
        return 0, ""

    matched_tokens = [token for token in tokens if token in haystack]
    title_hits = [token for token in matched_tokens if token in title.lower()]

    if query.lower() in title.lower():
        score = 95
    elif query.lower() in haystack:
        score = 88
    else:
        coverage = len(matched_tokens) / len(tokens)
        score = int(coverage * 75)
        if title_hits:
            score += 15

    score = max(0, min(score, 100))

    if not matched_tokens:
        return score, "关键词未直接命中，仅作为兜底结果返回"
    if title_hits:
        return score, f"标题命中：{', '.join(title_hits[:3])}"
    return score, f"描述命中：{', '.join(matched_tokens[:3])}"


def _normalize_job(raw: dict, source: str, query: str = "") -> dict:
    """Normalize to Job schema."""
    title = raw.get("title") or raw.get("position", "Unknown")
    description = raw.get("description", "")[:2000]
    score, reason = _score_job_match(title, description, query)

    return {
        "job_id": raw.get("id") or raw.get("slug") or str(uuid.uuid4()),
        "title": title,
        "company": raw.get("company", "Unknown"),
        "url": raw.get("url") or raw.get("apply_url", ""),
        "description": description,  # cap length
        "location": raw.get("location", "Remote"),
        "source": source,
        "posted_at": raw.get("date") or raw.get("epoch", ""),
        "match_score": score,
        "match_reason": reason if reason else ("缓存兜底结果" if source == "cached" else ""),
    }
