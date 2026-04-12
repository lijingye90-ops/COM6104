# TODOS

## TODO-001: SSE 重连机制
**Status:** pending
**Priority:** Low
**What:** 前端 EventSource 断开时自动重连，显示"连接中断，重连中…"提示。
**Why:** 网络抖动时 SSE 断开，用户看到永远加载中。EventSource 原生支持自动重连，只需监听 onerror 事件并显示 UI 提示。~10 行前端代码。
**Depends on:** Chat UI 组件完成后

## TODO-002: GLM-4 API 错误处理
**Status:** pending
**Priority:** Medium
**What:** agent.py 的 GLM-4 API 调用加 try/except，catch rate limit、500 错误，通过 SSE 发 error 事件。
**Why:** 现有 agent.py 的 for loop 没有 try/except，API 异常直接崩溃到 FastAPI 500。Agent 不应默默卡死。~15 行代码。
**Depends on:** agent.py SSE 改造完成后

## TODO-003: weasyprint 安装失败 fallback
**Status:** pending
**Priority:** Low
**What:** linkedin_apply.py 中 MD→PDF 转换加 try/except，weasyprint import 失败时用 md2pdf 或直接返回 fallback 投递包。
**Why:** weasyprint 需要 OS 级依赖（pango, cairo），漏装会默默崩溃。双依赖 try/except 避免因一个依赖问题导致整个投递流程失败。
**Depends on:** linkedin_apply.py 完成后
