import json
import os
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

load_dotenv()

DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"
DEFAULT_MODEL = "glm-4"
RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)

_DECISION_LOG: ContextVar[list[dict[str, Any]]] = ContextVar("llm_decision_log", default=[])


@dataclass(frozen=True)
class LLMProfile:
    stage: str
    label: str
    model: str
    base_url: str
    api_key: str
    reasoning_effort: str = "low"
    thinking_enabled: bool = False
    reason: str = ""
    provider: str = "generic-openai"


def get_api_key() -> str:
    return os.getenv("LLM_API_KEY") or os.getenv("ZHIPUAI_API_KEY", "")


def get_base_url() -> str:
    return os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL


def get_model() -> str:
    return os.getenv("LLM_MODEL") or DEFAULT_MODEL


def get_max_attempts() -> int:
    raw = os.getenv("LLM_MAX_ATTEMPTS", "3")
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


def get_retry_delay() -> float:
    raw = os.getenv("LLM_RETRY_DELAY", "1.0")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 1.0


def get_browser_headless() -> bool:
    raw = os.getenv("BROWSER_HEADLESS", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def get_browser_mode_label() -> str:
    return "后台运行" if get_browser_headless() else "前台可见"


def reset_decision_log() -> None:
    _DECISION_LOG.set([])


def consume_decision_log() -> list[dict[str, Any]]:
    items = list(_DECISION_LOG.get())
    _DECISION_LOG.set([])
    return items


def record_decision(entry: dict[str, Any]) -> None:
    current = list(_DECISION_LOG.get())
    current.append(entry)
    _DECISION_LOG.set(current)


def _detect_provider(base_url: str) -> str:
    lowered = (base_url or "").lower()
    if "deepseek.com" in lowered:
        return "deepseek"
    if "bigmodel.cn" in lowered:
        return "zhipu"
    if "volces.com" in lowered:
        return "ark"
    return "generic-openai"


def _stage_defaults() -> dict[str, dict[str, Any]]:
    return {
        "agent_orchestrator": {
            "tier": "thinking",
            "reasoning_effort": "high",
            "thinking_enabled": True,
            "label": "主 Agent 规划与工具选择",
            "reason": "这是全局规划阶段，需要拆任务、选工具、决定下一步。",
        },
        "job_extract": {
            "tier": "fast",
            "reasoning_effort": "low",
            "thinking_enabled": False,
            "label": "职位抽取与初筛",
            "reason": "这是批量抽取阶段，强调速度和成本，不需要重度思考。",
        },
        "resume_customize": {
            "tier": "thinking",
            "reasoning_effort": "high",
            "thinking_enabled": True,
            "label": "简历定制",
            "reason": "需要结合 JD 做重写、取舍和结构化强调，适合高质量模型。",
        },
        "cover_letter": {
            "tier": "fast",
            "reasoning_effort": "low",
            "thinking_enabled": False,
            "label": "求职信与邮件文案",
            "reason": "这是短文本生成阶段，要求稳定快速，不值得开重思考。",
        },
        "interview_prep": {
            "tier": "thinking",
            "reasoning_effort": "high",
            "thinking_enabled": True,
            "label": "面试准备",
            "reason": "要生成高质量问题和 STAR 回答，需要更强推理。",
        },
        "browser_navigation": {
            "tier": "browser",
            "reasoning_effort": "low",
            "thinking_enabled": False,
            "label": "浏览器导航",
            "reason": "这一步主要是点页面和找入口，优先稳定和低延迟。",
        },
    }


def _env_key(stage: str, suffix: str) -> str:
    return f"LLM_STAGE_{stage.upper()}_{suffix}"


def _get_endpoint_templates() -> list[dict[str, str]]:
    primary = {
        "api_key": get_api_key(),
        "base_url": get_base_url(),
        "model": get_model(),
    }
    endpoints: list[dict[str, str]] = [primary]

    raw_pool = os.getenv("LLM_API_POOL", "").strip()
    if not raw_pool:
        return endpoints

    try:
        parsed = json.loads(raw_pool)
    except json.JSONDecodeError:
        return endpoints

    if not isinstance(parsed, list):
        return endpoints

    seen: set[tuple[str, str, str]] = {
        (primary["api_key"], primary["base_url"], primary["model"])
    }
    for item in parsed:
        if not isinstance(item, dict):
            continue
        api_key = str(item.get("api_key") or primary["api_key"]).strip()
        base_url = str(item.get("base_url") or primary["base_url"]).strip()
        model = str(item.get("model") or primary["model"]).strip()
        if not api_key or not base_url or not model:
            continue
        signature = (api_key, base_url, model)
        if signature in seen:
            continue
        seen.add(signature)
        endpoints.append(
            {
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
            }
        )

    return endpoints


def get_pool_size() -> int:
    return len(_get_endpoint_templates())


def _resolve_model_alias(stage: str, provider: str, base_model: str, tier: str) -> str:
    stage_override = os.getenv(_env_key(stage, "MODEL"), "").strip()
    if stage_override:
        return stage_override

    if tier == "browser":
        browser_model = os.getenv("LLM_MODEL_BROWSER", "").strip()
        if browser_model:
            return browser_model

    if tier == "thinking":
        thinking_model = os.getenv("LLM_MODEL_THINKING", "").strip()
        if thinking_model:
            return thinking_model
        if provider == "deepseek":
            return "deepseek-v4-pro"

    fast_model = os.getenv("LLM_MODEL_FAST", "").strip()
    if fast_model:
        return fast_model
    if provider == "deepseek":
        return "deepseek-v4-flash"

    return base_model


def resolve_llm_profile(stage: str, endpoint_index: int = 0) -> LLMProfile:
    defaults = _stage_defaults().get(stage, _stage_defaults()["agent_orchestrator"])
    templates = _get_endpoint_templates()
    selected = templates[min(max(endpoint_index, 0), len(templates) - 1)]
    provider = _detect_provider(selected["base_url"])

    profile = LLMProfile(
        stage=stage,
        label=defaults["label"],
        model=_resolve_model_alias(stage, provider, selected["model"], defaults["tier"]),
        base_url=os.getenv(_env_key(stage, "BASE_URL"), "").strip() or selected["base_url"],
        api_key=os.getenv(_env_key(stage, "API_KEY"), "").strip() or selected["api_key"],
        reasoning_effort=os.getenv(_env_key(stage, "REASONING"), "").strip() or defaults["reasoning_effort"],
        thinking_enabled=(
            os.getenv(_env_key(stage, "THINKING"), "").strip().lower() == "true"
            if os.getenv(_env_key(stage, "THINKING"), "").strip()
            else defaults["thinking_enabled"]
        ),
        reason=defaults["reason"],
        provider=provider,
    )
    return profile


def get_model_routing_summary() -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for stage in _stage_defaults():
        profile = resolve_llm_profile(stage)
        summary[stage] = {
            "label": profile.label,
            "model": profile.model,
            "base_url": profile.base_url,
            "reasoning_effort": profile.reasoning_effort,
            "thinking_enabled": profile.thinking_enabled,
            "provider": profile.provider,
            "reason": profile.reason,
        }
    return summary


def create_client() -> OpenAI:
    return OpenAI(
        api_key=get_api_key(),
        base_url=get_base_url(),
        max_retries=0,
    )


def _build_client(profile: LLMProfile) -> OpenAI:
    return OpenAI(
        api_key=profile.api_key,
        base_url=profile.base_url,
        max_retries=0,
    )


def _format_pool_error(errors: list[str]) -> RuntimeError:
    joined = " | ".join(errors[-6:])
    return RuntimeError(f"All configured LLM endpoints failed. {joined}")


def _build_request_kwargs(profile: LLMProfile, kwargs: dict[str, Any]) -> dict[str, Any]:
    request_kwargs = dict(kwargs)
    request_kwargs["model"] = profile.model

    if profile.provider == "deepseek":
        if profile.thinking_enabled:
            extra_body = dict(request_kwargs.get("extra_body") or {})
            extra_body["thinking"] = {"type": "enabled"}
            request_kwargs["extra_body"] = extra_body
            request_kwargs["reasoning_effort"] = profile.reasoning_effort
    else:
        request_kwargs["reasoning_effort"] = profile.reasoning_effort

    return request_kwargs


def _record_profile_decision(profile: LLMProfile, endpoint_index: int, attempt: int) -> None:
    record_decision(
        {
            "type": "model_selection",
            "stage": profile.stage,
            "label": profile.label,
            "provider": profile.provider,
            "model": profile.model,
            "base_url": profile.base_url,
            "reasoning_effort": profile.reasoning_effort,
            "thinking_enabled": profile.thinking_enabled,
            "pool_index": endpoint_index + 1,
            "attempt": attempt,
            "reason": profile.reason,
        }
    )


def create_chat_completion(
    *,
    client: OpenAI | None = None,
    stage: str = "agent_orchestrator",
    max_attempts: int | None = None,
    retry_delay: float | None = None,
    **kwargs: Any,
):
    attempts = max_attempts or get_max_attempts()
    delay = get_retry_delay() if retry_delay is None else retry_delay
    endpoint_count = get_pool_size()
    collected_errors: list[str] = []
    last_retryable_error = None

    for endpoint_index in range(endpoint_count):
        profile = resolve_llm_profile(stage, endpoint_index=endpoint_index)
        can_reuse_client = (
            client is not None
            and endpoint_index == 0
            and endpoint_count == 1
            and profile.base_url == get_base_url()
            and profile.api_key == get_api_key()
        )
        active_client = (
            client
            if can_reuse_client
            else _build_client(profile)
        )
        request_kwargs = _build_request_kwargs(profile, kwargs)

        for attempt in range(1, attempts + 1):
            _record_profile_decision(profile, endpoint_index, attempt)
            try:
                return active_client.chat.completions.create(**request_kwargs)
            except RETRYABLE_EXCEPTIONS as exc:
                last_retryable_error = exc
                error_message = f"[{profile.base_url}#{attempt}] {exc.__class__.__name__}: {exc}"
                collected_errors.append(error_message)
                record_decision(
                    {
                        "type": "retryable_error",
                        "stage": stage,
                        "model": profile.model,
                        "base_url": profile.base_url,
                        "attempt": attempt,
                        "pool_index": endpoint_index + 1,
                        "error": str(exc),
                    }
                )
                if attempt < attempts:
                    time.sleep(delay * attempt)
                    continue
                if endpoint_index + 1 < endpoint_count:
                    record_decision(
                        {
                            "type": "endpoint_failover",
                            "stage": stage,
                            "from_model": profile.model,
                            "from_base_url": profile.base_url,
                            "next_pool_index": endpoint_index + 2,
                        }
                    )
                break

    if endpoint_count > 1 and collected_errors:
        raise _format_pool_error(collected_errors)

    if last_retryable_error is not None:
        raise last_retryable_error

    raise RuntimeError("chat completion failed without raising an explicit error")


def build_browser_use_llm(stage: str = "browser_navigation", *, temperature: float = 0.0):
    from browser_use.llm.openai.chat import ChatOpenAI

    profile = resolve_llm_profile(stage)
    record_decision(
        {
            "type": "browser_model_selection",
            "stage": profile.stage,
            "label": profile.label,
            "provider": profile.provider,
            "model": profile.model,
            "base_url": profile.base_url,
            "reasoning_effort": profile.reasoning_effort,
            "thinking_enabled": False,
            "reason": profile.reason,
        }
    )
    kwargs: dict[str, Any] = {
        "model": profile.model,
        "api_key": profile.api_key,
        "base_url": profile.base_url,
        "add_schema_to_system_prompt": True,
        "dont_force_structured_output": True,
        "temperature": temperature,
    }
    if profile.provider != "deepseek" or profile.thinking_enabled:
        kwargs["reasoning_effort"] = profile.reasoning_effort
        kwargs["reasoning_models"] = [profile.model]
    return ChatOpenAI(**kwargs)


def record_browser_mode_decision(stage: str = "browser_navigation", context: str = "") -> bool:
    headless = get_browser_headless()
    record_decision(
        {
            "type": "browser_runtime_mode",
            "stage": stage,
            "label": "浏览器运行模式",
            "headless": headless,
            "mode": get_browser_mode_label(),
            "reason": context or (
                "默认使用后台无头浏览器，避免执行过程中抢占你的前台窗口。"
                if headless
                else "按环境变量配置使用前台可见浏览器。"
            ),
        }
    )
    return headless
