"""Shared helpers for running browser-harness scripts via the user's real browser."""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
from pathlib import Path


BROWSER_HARNESS_PROGRESS_MARKER = "__browser_harness_event__"


def ensure_local_cdp_bypass() -> None:
    """Route localhost CDP traffic around any global HTTP proxy."""
    bypass_hosts = ["localhost", "127.0.0.1", "::1"]

    for key in ("NO_PROXY", "no_proxy"):
        current = os.getenv(key, "")
        hosts = [host.strip() for host in current.split(",") if host.strip()]
        for host in bypass_hosts:
            if host not in hosts:
                hosts.append(host)
        os.environ[key] = ",".join(hosts)


def _resolve_browser_harness_binary() -> str:
    binary = shutil.which("browser-harness")
    if binary:
        return binary

    fallback = Path.home() / ".local" / "bin" / "browser-harness"
    if fallback.exists():
        return str(fallback)

    raise RuntimeError("browser_harness_not_installed")


async def _emit_progress(on_event, payload: dict) -> None:
    if on_event is None:
        return
    maybe_awaitable = on_event(payload)
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


async def run_browser_harness_script(script: str, *, timeout: int = 180, on_event=None) -> dict:
    """Run a browser-harness Python snippet and stream intermediate progress events."""
    binary = _resolve_browser_harness_binary()
    ensure_local_cdp_bypass()

    env = os.environ.copy()
    env["NO_PROXY"] = os.environ.get("NO_PROXY", env.get("NO_PROXY", ""))
    env["no_proxy"] = os.environ.get("no_proxy", env.get("no_proxy", ""))

    process = await asyncio.create_subprocess_exec(
        binary,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    process.stdin.write(script.encode("utf-8"))
    await process.stdin.drain()
    process.stdin.close()

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    final_payload: dict | None = None

    async def read_stdout() -> None:
        nonlocal final_payload
        while True:
            raw_line = await process.stdout.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            stdout_lines.append(line)
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                await _emit_progress(
                    on_event,
                    {"stage": "stdout", "message": line},
                )
                continue

            if isinstance(payload, dict) and payload.get(BROWSER_HARNESS_PROGRESS_MARKER) == "progress":
                progress_event = payload.copy()
                progress_event.pop(BROWSER_HARNESS_PROGRESS_MARKER, None)
                await _emit_progress(on_event, progress_event)
                continue

            if isinstance(payload, dict):
                final_payload = payload
                continue

            await _emit_progress(
                on_event,
                {"stage": "stdout", "message": json.dumps(payload, ensure_ascii=False)},
            )

    async def read_stderr() -> None:
        while True:
            raw_line = await process.stderr.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            stderr_lines.append(line)
            await _emit_progress(
                on_event,
                {"stage": "stderr", "message": line},
            )

    try:
        await asyncio.wait_for(
            asyncio.gather(read_stdout(), read_stderr(), process.wait()),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeError(f"browser_harness_timeout:{timeout}") from exc

    if process.returncode != 0:
        error_output = "\n".join(stderr_lines or stdout_lines).strip()
        raise RuntimeError(error_output or f"browser_harness_failed:{process.returncode}")

    if final_payload is None:
        raise RuntimeError("browser_harness_empty_output")
    if not isinstance(final_payload, dict):
        raise RuntimeError("browser_harness_non_object_output")
    return final_payload
