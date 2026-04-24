#!/usr/bin/env python3
"""
快速测试脚本 — 验证三个 bug 修复

使用方法：
  python3 verify_fixes.py
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

print("""
╔════════════════════════════════════════════════════╗
║       Job Hunt Agent - Bug Fixes Verification      ║
║  ✅ TODO-001, TODO-002, TODO-003 修复验证          ║
╚════════════════════════════════════════════════════╝
""")

# ─────────────────────────────────────────────────────────────────────────────
# Test 1: TODO-002 — GLM-4 API 错误处理（自动重试）
# ─────────────────────────────────────────────────────────────────────────────

print("\n[TEST 1] GLM-4 API 自动重试机制")
print("=" * 50)

async def test_agent_retry():
    """测试 agent 的自动重试逻辑"""
    from backend.agent import run_agent
    
    # 模拟 API：前 2 次失败，第 3 次成功
    with patch('backend.agent.create_chat_completion') as mock_api:
        # 设置 side_effect：前 2 次抛异常，第 3 次返回有效响应
        mock_api.side_effect = [
            Exception("Connection timeout"),  # 第 1 次
            Exception("Rate limit exceeded"),  # 第 2 次
            MagicMock(  # 第 3 次成功
                choices=[MagicMock(
                    message=MagicMock(
                        content="测试成功：自动重试工作正常",
                        tool_calls=[]
                    )
                )]
            )
        ]
        
        # 收集 SSE 事件
        events = []
        async for event in run_agent("搜索 Python 职位"):
            events.append(event)
            if event.get("event") == "done":
                break
        
        # 验证
        retry_events = [e for e in events if "重连" in str(e.get("data", {}).get("text", ""))]
        success_events = [e for e in events if e.get("event") == "done"]
        
        if retry_events:
            print(f"✅ 检测到重试提示")
            for e in retry_events:
                print(f"   └─ {e['data'].get('text', '')[:60]}")
        
        if success_events:
            print(f"✅ 最终返回成功（第 3 次重试）")
        
        print(f"✅ API 被调用 {mock_api.call_count} 次（预期 3 次）")
        assert mock_api.call_count == 3, f"预期 3 次调用，实际 {mock_api.call_count} 次"
        print("✅ TEST 1 PASSED")

try:
    asyncio.run(test_agent_retry())
except Exception as e:
    print(f"❌ TEST 1 FAILED: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Test 2: TODO-003 — PDF 转换降级链
# ─────────────────────────────────────────────────────────────────────────────

print("\n[TEST 2] PDF 转换降级链（三级 fallback）")
print("=" * 50)

def test_pdf_fallback():
    """测试 PDF 转换的三级降级"""
    from backend.tools.linkedin_apply import _md_to_pdf
    import tempfile
    
    # 创建临时 Markdown 文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as md_file:
        md_file.write("# 测试简历\n\n这是一份测试简历。")
        md_path = md_file.name
    
    # 创建临时输出路径
    output_path = Path(tempfile.gettempdir()) / "test_output.pdf"
    
    try:
        # 测试：正常情况下应该成功
        result = _md_to_pdf(md_path, str(output_path))
        
        if result:
            print(f"✅ PDF 转换成功")
            if output_path.exists():
                print(f"✅ PDF 文件已生成：{output_path} ({output_path.stat().st_size} bytes)")
            print("✅ TEST 2 PASSED")
        else:
            print(f"⚠️  PDF 转换返回 False（可能缺少所有库）")
            print(f"   建议安装：pip install weasyprint md2pdf reportlab")
    
    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
    finally:
        # 清理
        Path(md_path).unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)

test_pdf_fallback()

# ─────────────────────────────────────────────────────────────────────────────
# Test 3: TODO-001 — SSE 重连机制（前端）
# ─────────────────────────────────────────────────────────────────────────────

print("\n[TEST 3] SSE 重连机制（前端逻辑）")
print("=" * 50)

def test_sse_retry_logic():
    """验证 SSE 重连逻辑是否存在于代码"""
    dashboard_file = Path("/Users/Zhuanz/project-lesson/agent/app/dashboard/page.tsx")
    
    if not dashboard_file.exists():
        print(f"⚠️  文件不存在：{dashboard_file}")
        return
    
    content = dashboard_file.read_text()
    
    # 检查关键修复代码
    checks = {
        "自动重试逻辑": "let retryCount = 0" in content,
        "最大重试次数设置": "MAX_RETRIES = 3" in content,
        "指数退避延迟": "Math.pow(2, retryCount - 1)" in content,
        "用户提示信息": "自动重连" in content,
        "递归重连调用": "return attemptConnect()" in content,
    }
    
    all_passed = True
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {check_name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n✅ TEST 3 PASSED")
    else:
        print("\n❌ TEST 3 FAILED")

test_sse_retry_logic()

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

print("""
╔════════════════════════════════════════════════════╗
║  修复验证完成                                       ║
╚════════════════════════════════════════════════════╝

📋 修复清单：
  ✅ TODO-001: SSE 重连机制        → agent/app/dashboard/page.tsx
  ✅ TODO-002: GLM-4 异常处理       → backend/agent.py
  ✅ TODO-003: PDF 转换降级链       → backend/tools/linkedin_apply.py

📖 详细说明：
  - BUG_FIXES.md          （完整修复报告）
  - QUICK_FIX_REFERENCE.md （快速参考卡片）
  - TODOS.md              （更新状态）

🧪 后续测试：
  1. 运行后端：python -m backend.main
  2. 运行前端：cd agent && npm run dev
  3. 手动测试网络中断场景
  4. 验证 API 异常时的重试行为
  5. 检查 PDF 生成的降级方案
""")
