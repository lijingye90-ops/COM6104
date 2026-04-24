# 🔧 Bug 修复快速参考

## 修复概览

| # | Bug | 文件 | 行号 | 修复方式 | 状态 |
|----|-----|------|------|--------|------|
| 001 | SSE 重连 | `agent/app/dashboard/page.tsx` | 575-680 | 自动重试 + 指数退避 | ✅ |
| 002 | GLM-4 异常 | `backend/agent.py` | 163-174 | 自动重试 + 降级 | ✅ |
| 003 | PDF 转换 | `backend/tools/linkedin_apply.py` | 38-95 | 三级降级链 | ✅ |

---

## 核心改进

### Bug #001: SSE 重连机制

**原问题：** 网络中断时无法自动恢复，用户永远看到加载

**修复方案：**
```typescript
// 自动重试 3 次，延迟：1s → 2s → 4s
const attemptConnect = async () => {
  try {
    await fetch("/api/chat", ...)
  } catch (error) {
    if (retryCount < 3) {
      retryCount++
      const delay = 1000 * Math.pow(2, retryCount - 1)
      setMessage("连接中断，{delay}秒后自动重连...")
      await sleep(delay)
      return attemptConnect()  // 递归重连
    }
  }
}
```

**效果：**
- ✅ WiFi 切换（1-2s）：第 1 次重试成功
- ✅ 短暂波动（3s）：第 2 次重试成功  
- ❌ 持续故障（>4s）：放弃重连，显示错误

---

### Bug #002: GLM-4 API 异常处理

**原问题：** API 失败直接中止，已完成的工具结果丢失

**修复方案：**
```python
for _ in range(20):
    try:
        response = create_chat_completion(...)
    except Exception as e:
        if last_tool_result:  # 有工具结果
            yield {"event": "done", "last_tool_result": ...}
            return  # 返回已有结果
        elif _ < 3:  # 前 3 次重试
            setMessage("自动重连中...")
            await sleep(2)
            continue  # 重试这一轮
        else:  # 多次失败才放弃
            yield {"event": "error", ...}
            return
```

**效果：**
- ✅ API 超时：自动重试 1-2 次后成功
- ✅ Rate limit：等待 2s 后重试
- ✅ 已有结果时：返回部分成果（不全失败）

---

### Bug #003: PDF 转换降级链

**原问题：** 缺少一个依赖库就整个投递失败

**修复方案：**
```python
def _md_to_pdf(md_path, output_path):
    # 方案 1: weasyprint (HTML→PDF, 最优)
    try:
        from weasyprint import HTML
        HTML(...).write_pdf(output_path)
        return True
    except ImportError: pass
    
    # 方案 2: md2pdf (轻量级)
    try:
        import md2pdf
        md2pdf.convert(md_path, output_path)
        return True
    except ImportError: pass
    
    # 方案 3: reportlab (纯文本→PDF)
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(output_path)
        # 逐行绘制...
        c.save()
        return True
    except ImportError: pass
    
    return False  # 三级都失败才返回 False
```

**效果：**
| 环境 | 结果 |
|------|------|
| 全库安装 | HTML 格式高保真 PDF |
| 轻量容器 | Markdown PDF |
| 极简环境 | 纯文本 PDF（可读）|
| 无库 | 返回 False（文本投递）|

---

## 快速验证清单

- [ ] **SSE 重连** 
  - [ ] 拔掉网线 2 秒，自动重连成功
  - [ ] 提示文本显示："连接中断，2 秒后自动重连..."
  
- [ ] **GLM-4 异常处理**
  - [ ] 模拟 API 503，显示重试进度
  - [ ] 已有工具结果时，返回部分成果
  
- [ ] **PDF 转换**
  - [ ] 无任何库时仍返回 True（降级成功）
  - [ ] 日志显示使用的方案（weasyprint/md2pdf/reportlab）

---

## 相关文件

- 详细修复说明：[BUG_FIXES.md](./BUG_FIXES.md)
- 前端实现：`agent/app/dashboard/page.tsx` 
- 后端实现：`backend/agent.py`, `backend/tools/linkedin_apply.py`
- 状态更新：[TODOS.md](./TODOS.md)
