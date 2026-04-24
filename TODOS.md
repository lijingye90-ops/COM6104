# TODOS

## TODO-001: SSE 重连机制
**Status:** ✅ **COMPLETED** (2026-04-24)
**Priority:** Low
**What:** 前端 EventSource 断开时自动重连，显示"连接中断，重连中…"提示。
**Why:** 网络抖动时 SSE 断开，用户看到永远加载中。EventSource 原生支持自动重连，只需监听 onerror 事件并显示 UI 提示。~10 行前端代码。
**Implementation:** 
- 添加三次自动重试机制（最多重试 3 次）
- 指数退避策略：1s → 2s → 4s
- 用户提示："连接中断，{delay}秒后自动重连..."
- 文件: `agent/app/dashboard/page.tsx` 行 575-680

## TODO-002: GLM-4 API 错误处理
**Status:** ✅ **COMPLETED** (2026-04-24)
**Priority:** Medium
**What:** agent.py 的 GLM-4 API 调用加 try/except，catch rate limit、500 错误，通过 SSE 发 error 事件。
**Why:** 现有 agent.py 的 for loop 没有 try/except，API 异常直接崩溃到 FastAPI 500。Agent 不应默默卡死。~15 行代码。
**Implementation:**
- 自动重试前 3 轮，指数退避（2s 延迟）
- 已有工具结果时返回部分成果，而非全失败
- 显示重试进度："自动重连中…"
- 文件: `backend/agent.py` 行 163-174

## TODO-003: weasyprint 安装失败 fallback
**Status:** ✅ **COMPLETED** (2026-04-24)
**Priority:** Low
**What:** linkedin_apply.py 中 MD→PDF 转换加 try/except，weasyprint import 失败时用 md2pdf 或直接返回 fallback 投递包。
**Why:** weasyprint 需要 OS 级依赖（pango, cairo），漏装会默默崩溃。双依赖 try/except 避免因一个依赖问题导致整个投递流程失败。
**Implementation:**
- 三级降级链：weasyprint → md2pdf → reportlab
- 详细日志记录每级失败原因
- 至少一级成功则不中断投递流程
- 文件: `backend/tools/linkedin_apply.py` 行 38-95

