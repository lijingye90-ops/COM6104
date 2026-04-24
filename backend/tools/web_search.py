"""Simple web search via DuckDuckGo HTML — no API key required."""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup


def web_search(query: str, max_results: int = 6) -> list[dict]:
    """Search the web. Returns list of {title, url, snippet}."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-hunt-agent/1.0)"}
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=12,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[dict] = []
        for block in soup.select(".result__body")[:max_results]:
            title_el = block.select_one(".result__title")
            url_el = block.select_one(".result__url")
            snippet_el = block.select_one(".result__snippet")
            if title_el:
                results.append(
                    {
                        "title": title_el.get_text(strip=True),
                        "url": url_el.get_text(strip=True) if url_el else "",
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                    }
                )
        return results or [{"title": "无结果", "url": "", "snippet": "未找到相关结果"}]
    except Exception as exc:
        return [{"title": "搜索失败", "url": "", "snippet": str(exc)}]
