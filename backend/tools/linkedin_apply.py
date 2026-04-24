"""Application tools — browser-harness powered LinkedIn and external apply flows."""
import json
import os
import re
import inspect
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
from llm_client import (
    create_chat_completion,
    create_client,
)
from .browser_harness import ensure_local_cdp_bypass, run_browser_harness_script
from .email_sender import send_email, smtp_is_configured, resend_is_configured

load_dotenv()

TMP_DIR = Path("/tmp")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
LINK_RE = re.compile(r"https?://[^\s)]+")

def _md_to_pdf(md_path: str, output_path: str) -> bool:
    """Convert Markdown to PDF. Returns True on success. Falls back to md2pdf if weasyprint fails."""
    md_text = Path(md_path).read_text(encoding="utf-8")
    
    # ✅ 尝试方案1：weasyprint (质量最好)
    try:
        import mistune
        from weasyprint import HTML

        html_content = mistune.html(md_text)
        # Add basic CSS for readable PDF
        styled_html = f"""
        <html><head><style>
        body {{ font-family: system-ui, sans-serif; font-size: 11pt; line-height: 1.5; margin: 2cm; }}
        h1 {{ font-size: 18pt; }} h2 {{ font-size: 14pt; }} h3 {{ font-size: 12pt; }}
        </style></head><body>{html_content}</body></html>
        """
        HTML(string=styled_html).write_pdf(output_path)
        print(f"[PDF] weasyprint 成功生成: {output_path}")
        return True
    except ImportError as e1:
        print(f"[PDF] weasyprint 未安装，尝试 md2pdf 降级方案: {e1}")
        
        # ✅ 降级方案：md2pdf (轻量级)
        try:
            import md2pdf
            md2pdf.convert(md_path, output_path)
            print(f"[PDF] md2pdf 成功生成: {output_path}")
            return True
        except ImportError as e2:
            print(f"[PDF] md2pdf 也未安装: {e2}")
            
            # ✅ 终极降级：纯文本→PDF (使用 reportlab)
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
                
                c = canvas.Canvas(output_path, pagesize=letter)
                y_position = 750
                line_height = 14
                
                for line in md_text.split('\n'):
                    if y_position < 50:
                        c.showPage()
                        y_position = 750
                    c.drawString(50, y_position, line[:100])  # 限制行宽
                    y_position -= line_height
                
                c.save()
                print(f"[PDF] reportlab 成功生成: {output_path}")
                return True
            except ImportError as e3:
                print(f"[PDF] 所有 PDF 库都不可用: {e3}")
                return False
    except Exception as e:
        print(f"[PDF] weasyprint 转换失败，尝试 md2pdf: {e}")
        try:
            import md2pdf
            md2pdf.convert(md_path, output_path)
            print(f"[PDF] md2pdf 成功生成: {output_path}")
            return True
        except Exception as e2:
            print(f"[PDF] md2pdf 也失败: {e2}")
            return False


def _build_fallback(
    job_id: str,
    job_url: str,
    resume_pdf: str,
    cover_letter_path: str,
    reason: str,
    detail: str = "",
) -> dict:
    """Build a standardised fallback response dict."""
    payload = {
        "status": "fallback",
        "package": {
            "resume_pdf": resume_pdf,
            "cover_letter": cover_letter_path,
            "job_url": job_url,
        },
        "reason": reason,
    }
    if detail:
        payload["detail"] = detail
    return payload


def _is_demo_placeholder_url(job_url: str) -> bool:
    hostname = (urlparse(job_url).hostname or "").lower()
    return hostname in {"example.com", "www.example.com"}


def _extract_email_address(raw: str) -> str:
    match = EMAIL_RE.search(raw or "")
    return match.group(0) if match else ""


_COUNTRY_KEYWORDS = {
    "hong kong": "Hong Kong",
    "hk": "Hong Kong",
    "china": "China",
    "mainland": "China",
    "singapore": "Singapore",
    "australia": "Australia",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "usa": "United States",
    "united states": "United States",
}


def _infer_country(text: str) -> str:
    lower = text.lower()
    for keyword, country in _COUNTRY_KEYWORDS.items():
        if keyword in lower:
            return country
    return "Hong Kong"  # default


def _extract_candidate_profile(resume_path: str) -> dict:
    text = Path(resume_path).read_text(encoding="utf-8", errors="ignore")
    lines = [line.strip(" #*\t") for line in text.splitlines() if line.strip()]
    name = lines[0] if lines else ""
    email = _extract_email_address(text)

    phone_match = PHONE_RE.search(text)
    phone = phone_match.group(1).strip() if phone_match else ""

    linkedin = ""
    github = ""
    website = ""
    for link in LINK_RE.findall(text):
        lower = link.lower()
        if "linkedin.com" in lower and not linkedin:
            linkedin = link
        elif ("github.com" in lower or "gitee.com" in lower) and not github:
            github = link
        elif not website:
            website = link

    # Infer application extras from resume context
    is_student = bool(re.search(r"\bMSc?\b|\bPhD\b|\bBEng\b|\bUniversity\b|\bCollege\b|student", text, re.I))
    country = _infer_country(text)
    current_salary = "N/A (Currently studying)" if is_student else "Negotiable"
    notice_period = "Immediately available" if is_student else "2 weeks"

    return {
        "name": name[:120],
        "email": email,
        "phone": phone[:40],
        "linkedin": linkedin,
        "github": github,
        "website": website,
        "country": country,
        "current_salary": current_salary,
        "expected_salary": "Negotiable",
        "notice_period": notice_period,
    }


def _extract_json_object(raw: str) -> dict:
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not match:
        return {}

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


async def _llm_fill_fields(
    fields: list[dict],
    profile: dict,
    job_title: str = "",
    company: str = "",
) -> dict:
    """
    Ask the LLM to decide what value to fill for each required form field.

    Returns a dict mapping field label → value string.
    """
    if not fields:
        return {}

    fields_desc = json.dumps(fields, ensure_ascii=False, indent=2)
    profile_desc = json.dumps(profile, ensure_ascii=False, indent=2)

    prompt = f"""You are helping fill out a job application form on behalf of a candidate.

Candidate profile:
{profile_desc}

Job: {job_title or "unknown"} at {company or "unknown company"}

Required form fields (some are <select> dropdowns with available options listed):
{fields_desc}

Instructions:
- Return a JSON object where each key is the EXACT field label and the value is what to fill in.
- For select/dropdown fields, choose the BEST MATCHING option from the provided options list.
- For "how did you hear about this job" style questions → use "Online job board"
- For demographic / EEO / voluntary disclosure fields (gender, race, ethnicity, veteran, disability) → use "Prefer not to say" or "Decline to self-identify"
- For salary/compensation fields → use the candidate's expected_salary or "Negotiable"
- For notice period / availability → use the candidate's notice_period
- For country/location → use the candidate's country
- Never fabricate information not derivable from the profile.
- Return ONLY a valid JSON object. No explanation, no markdown, no code fences.

Example output:
{{"Full Name": "John Smith", "How did you hear about this job?": "Online job board", "Country": "Hong Kong"}}"""

    messages = [{"role": "user", "content": prompt}]
    response = create_chat_completion(messages=messages, stage="form_field_fill")
    raw = response.choices[0].message.content if hasattr(response, "choices") else str(response)
    return _extract_json_object(raw)


def _build_browser_harness_external_apply_script(
    job_url: str,
    resume_pdf_path: str,
    cover_letter_path: str,
    job_title: str,
    company: str,
    profile: dict,
) -> str:
    # JS templates embedded as JSON strings to avoid f-string brace escaping hell.
    # Each template is a self-contained IIFE; callers substitute __PLACEHOLDER__ before
    # passing to js().

    _ANALYZE_JS = (
        "(() => {"
        "const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();"
        "const visible = (el) => {"
        "  if (!el) return false;"
        "  const style = window.getComputedStyle(el);"
        "  const rect = el.getBoundingClientRect();"
        "  return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;"
        "};"
        "const labelText = (el) => {"
        "  if (!el) return '';"
        "  const aria = el.getAttribute('aria-label'); if (aria) return normalize(aria);"
        "  const id = el.id;"
        "  if (id) { const lbl = document.querySelector('label[for=\"' + CSS.escape(id) + '\"]'); if (lbl) return normalize(lbl.innerText || lbl.textContent || ''); }"
        "  const wrapper = el.closest('label'); if (wrapper) return normalize(wrapper.innerText || wrapper.textContent || '');"
        "  const prev = el.previousElementSibling;"
        "  if (prev && ['LABEL','SPAN','DIV','P'].includes(prev.tagName)) return normalize(prev.innerText || prev.textContent || '');"
        "  const section = el.closest('[data-testid], .application-form, form, section');"
        "  if (section) { const h = section.querySelector('label,h1,h2,h3,legend'); if (h) return normalize(h.innerText || h.textContent || ''); }"
        "  return '';"
        "};"
        "const anchors = Array.from(document.querySelectorAll('a, button, [role=\"button\"]')).filter(visible);"
        "const forms = Array.from(document.querySelectorAll('form')).filter(visible);"
        "const fileInputs = Array.from(document.querySelectorAll('input[type=\"file\"]'));"
        "const submit = anchors.find(el => /submit application|submit|apply now|send application/i.test(normalize(el.innerText || el.textContent || '')));"
        "const appTab = anchors.find(el => /application/i.test(normalize(el.innerText || el.textContent || '')));"
        "const applyCta = anchors.find(el => /apply|continue|view job|see job/i.test(normalize(el.innerText || el.textContent || '')));"
        "const mailto = anchors.find(el => /^mailto:/i.test(el.getAttribute('href') || ''));"
        "const emailText = document.body.innerText.match(/[\\w.+-]+@[\\w.-]+\\.\\w+/);"
        "const formLike = forms.length > 0 || fileInputs.length > 0 || !!submit;"
        "const allRequiredFields = [];"
        "const skipLabel = /^(select\\.{0,3}|choose\\.{0,3}|please select|--|\\u2014)$/i;"
        "if (formLike) {"
        "  const req = Array.from(document.querySelectorAll('input, textarea, select')).filter(el => {"
        "    if (!visible(el)) return false;"
        "    const t = (el.getAttribute('type') || '').toLowerCase();"
        "    if (['hidden','submit','button','reset','file'].includes(t)) return false;"
        "    return el.required || el.getAttribute('aria-required') === 'true';"
        "  });"
        "  for (const f of req) {"
        "    const label = labelText(f);"
        "    if (!label || skipLabel.test(label)) continue;"
        "    const val = normalize(f.value || '');"
        "    if (val) continue;"
        "    const info = {label, tag: f.tagName.toLowerCase(), type: f.getAttribute('type') || ''};"
        "    if (f.tagName.toLowerCase() === 'select') {"
        "      info.options = Array.from(f.options).map(o => normalize(o.text)).filter(t => t && !skipLabel.test(t));"
        "    }"
        "    allRequiredFields.push(info);"
        "  }"
        "}"
        "const titleLinks = anchors.map(el => ({ text: normalize(el.innerText || el.textContent || ''), href: el.getAttribute('href') || '' })).filter(i => i.text && i.href && !i.href.startsWith('#'));"
        "return {"
        "  url: location.href, title: document.title,"
        "  body: normalize(document.body.innerText).slice(0, 3000),"
        "  hasMailto: !!mailto, mailto: mailto ? (mailto.getAttribute('href') || '') : '', foundEmail: emailText ? emailText[0] : '',"
        "  hasApplicationTab: !!appTab, hasApplyCta: !!applyCta,"
        "  hasFormLike: formLike, hasSubmit: !!submit, fileInputCount: fileInputs.length,"
        "  titleLinks, allRequiredFields,"
        "};"
        "})()"
    )

    _APPLY_FILL_MAP_JS = (
        "(() => {"
        "const fillMap = __FILL_MAP__;"
        "const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();"
        "const visible = el => { if (!el) return false; const s = window.getComputedStyle(el); const r = el.getBoundingClientRect(); return s.visibility !== 'hidden' && s.display !== 'none' && r.width > 0 && r.height > 0; };"
        "const labelText = el => {"
        "  if (!el) return '';"
        "  const aria = el.getAttribute('aria-label'); if (aria) return (aria || '').replace(/\\s+/g, ' ').trim();"
        "  const id = el.id; if (id) { const lbl = document.querySelector('label[for=\"' + CSS.escape(id) + '\"]'); if (lbl) return (lbl.innerText || lbl.textContent || '').replace(/\\s+/g, ' ').trim(); }"
        "  const wrapper = el.closest('label'); if (wrapper) return (wrapper.innerText || wrapper.textContent || '').replace(/\\s+/g, ' ').trim();"
        "  const prev = el.previousElementSibling; if (prev) return (prev.innerText || prev.textContent || '').replace(/\\s+/g, ' ').trim();"
        "  return '';"
        "};"
        "const normMap = {};"
        "for (const [k, v] of Object.entries(fillMap)) normMap[norm(k)] = v;"
        "const getBestValue = label => {"
        "  const nl = norm(label);"
        "  if (normMap[nl]) return normMap[nl];"
        "  for (const [k, v] of Object.entries(normMap)) { if (nl.includes(k) || k.includes(nl)) return v; }"
        "  return null;"
        "};"
        "const touched = [];"
        "for (const field of Array.from(document.querySelectorAll('input, textarea, select'))) {"
        "  if (!visible(field) || field.disabled || field.readOnly) continue;"
        "  const t = (field.getAttribute('type') || '').toLowerCase();"
        "  if (['hidden','file','submit','button'].includes(t)) continue;"
        "  const label = labelText(field);"
        "  const value = getBestValue(label);"
        "  if (!value) continue;"
        "  if ((field.value || '').trim()) continue;"
        "  if (field.tagName.toLowerCase() === 'select') {"
        "    const opts = Array.from(field.options);"
        "    const nv = norm(value);"
        "    const best = opts.find(o => norm(o.text) === nv) || opts.find(o => norm(o.text).includes(nv)) || opts.find(o => nv.includes(norm(o.text).replace(/^(select|choose|--|—).*/i, '')));"
        "    if (best) { field.value = best.value; field.dispatchEvent(new Event('change', {bubbles: true})); touched.push(label); }"
        "  } else {"
        "    field.focus(); field.value = value;"
        "    field.dispatchEvent(new Event('input', {bubbles: true}));"
        "    field.dispatchEvent(new Event('change', {bubbles: true}));"
        "    touched.push(label);"
        "  }"
        "}"
        "return touched;"
        "})()"
    )

    payload = {
        "job_url": job_url,
        "resume_pdf_path": resume_pdf_path,
        "cover_letter_path": cover_letter_path,
        "job_title": job_title,
        "company": company,
        "profile": profile,
    }
    analyze_js_literal = json.dumps(_ANALYZE_JS)
    apply_fill_js_literal = json.dumps(_APPLY_FILL_MAP_JS)

    return f"""
import json
import urllib.request as _req

payload = {json.dumps(payload, ensure_ascii=False)}
job_url = payload["job_url"]
resume_pdf_path = payload["resume_pdf_path"]
cover_letter_path = payload["cover_letter_path"]
job_title = payload["job_title"]
company = payload["company"]
profile = payload["profile"]

_ANALYZE_JS = {analyze_js_literal}
_APPLY_FILL_MAP_JS = {apply_fill_js_literal}


def emit(result):
    print(json.dumps(result, ensure_ascii=False))


def emit_progress(stage, message, **extra):
    ev = {{"__browser_harness_event__": "progress", "stage": stage, "message": message}}
    ev.update(extra)
    print(json.dumps(ev, ensure_ascii=False))


def wait_page():
    wait_for_load()
    wait(1.2)


def analyze():
    return js(_ANALYZE_JS)


def apply_fill_map(fill_map):
    fill_json = json.dumps(fill_map, ensure_ascii=False)
    script = _APPLY_FILL_MAP_JS.replace("__FILL_MAP__", fill_json)
    return js(script)


def llm_fill_fields(fields):
    # Call the local backend to have LLM decide fill values for form fields.
    data = json.dumps({{"fields": fields, "profile": profile, "job_title": job_title, "company": company}}).encode("utf-8")
    req = _req.Request(
        "http://localhost:8000/api/internal/llm-fill",
        data=data,
        headers={{"Content-Type": "application/json"}},
        method="POST",
    )
    try:
        with _req.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read())
            return result if isinstance(result, dict) else {{}}
    except Exception as e:
        emit_progress("llm_fill_error", str(e)[:300])
        return {{}}


def click_application_tab():
    return js(
        \"\"\"
(() => {{
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const el = Array.from(document.querySelectorAll('a, button, [role="button"]'))
    .find((node) => visible(node) && /application/i.test((node.innerText || node.textContent || '').trim()));
  if (!el) return false;
  el.click();
  return true;
}})()
        \"\"\"
    )


def click_apply_cta():
    return js(
        \"\"\"
(() => {{
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const candidates = Array.from(document.querySelectorAll('a, button, [role="button"]')).filter((node) => visible(node));
  const preferred = candidates.find((node) => /apply now|apply|continue|view job/i.test((node.innerText || node.textContent || '').trim()));
  if (!preferred) return false;
  preferred.click();
  return true;
}})()
        \"\"\"
    )


def click_matching_role():
    return js(
        \"\"\"
(() => {{
  const target = {json.dumps((job_title or "").lower())};
  const tokens = target.split(/[^a-z0-9+]+/).filter(Boolean);
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const links = Array.from(document.querySelectorAll('a[href]')).filter((el) => visible(el));
  let best = null; let bestScore = -1;
  for (const link of links) {{
    const text = (link.innerText || link.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    if (!text) continue;
    let score = 0;
    if (target && text.includes(target)) score += 100;
    for (const token of tokens) {{ if (token && text.includes(token)) score += 10; }}
    if (score > bestScore) {{ bestScore = score; best = link; }}
  }}
  if (!best || bestScore <= 0) return false;
  best.click();
  return true;
}})()
        \"\"\"
    )


def upload_standard_files():
    return js(
        \"\"\"
(() => {{
  const resumePath = {json.dumps(resume_pdf_path)};
  const coverPath = {json.dumps(cover_letter_path)};
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden';
  }};
  const labelText = (el) => {{
    const id = el.id;
    if (id) {{
      const label = document.querySelector(`label[for="${{CSS.escape(id)}}"]`);
      if (label) return (label.innerText || label.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    }}
    const wrapper = el.closest('label');
    if (wrapper) return (wrapper.innerText || wrapper.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    const prev = el.previousElementSibling;
    return prev ? (prev.innerText || prev.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase() : '';
  }};
  const uploads = [];
  for (const input of Array.from(document.querySelectorAll('input[type="file"]'))) {{
    if (!visible(input)) continue;
    const label = labelText(input);
    const isCover = /cover letter/i.test(label);
    uploads.push({{selector: input.id ? `#${{input.id}}` : null, label, path: isCover ? coverPath : resumePath, isCover}});
  }}
  return uploads;
}})()
        \"\"\"
    )


def do_uploads(entries):
    done = []
    for entry in entries:
        selector = entry.get("selector")
        path = entry.get("path")
        if not selector or not path:
            continue
        upload_file(selector, path)
        done.append(entry.get("label") or selector)
        wait(0.8)
    return done


def submit_application():
    return js(
        \"\"\"
(() => {{
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]')).filter(visible);
  const target = buttons.find((el) => /submit application|submit|send application/i.test((el.innerText || el.textContent || el.value || '').trim()));
  if (!target) return false;
  target.click();
  return true;
}})()
        \"\"\"
    )


new_tab(job_url)
emit_progress("open_job", "已打开目标职位入口页", url=job_url)
wait_page()

for hop in range(8):
    state = analyze()
    emit_progress("page_analyzed", "已分析当前页面状态", hop=hop + 1, url=state.get("url"), title=state.get("title"))

    if state.get("hasMailto"):
        emit({{"status": "email_only", "apply_email": state.get("foundEmail") or state.get("mailto", "")}})
        raise SystemExit

    if "/login" in (state.get("url") or "").lower() or "sign in" in (state.get("title") or "").lower():
        emit({{"status": "login_wall"}})
        raise SystemExit

    if state.get("hasFormLike"):
        emit_progress("form_detected", "检测到申请表单，正在上传文件", hop=hop + 1)
        uploads = upload_standard_files()
        do_uploads(uploads)
        emit_progress("files_uploaded", "文件上传完成", uploads=uploads)
        wait(1)

        state = analyze()
        fields = state.get("allRequiredFields") or []

        if fields:
            emit_progress("llm_filling", f"发现 {{len(fields)}} 个必填字段，正在用 AI 推断填写内容", count=len(fields))
            fill_map = llm_fill_fields(fields)
            if fill_map:
                touched = apply_fill_map(fill_map)
                emit_progress("llm_filled", f"AI 已填写 {{len(touched)}} 个字段", fields=touched)
                wait(1)
            # Re-check after LLM fill
            state = analyze()
            remaining = state.get("allRequiredFields") or []
            if remaining:
                emit({{"status": "non_standard_field", "fields": remaining}})
                raise SystemExit

        if submit_application():
            emit_progress("submit_clicked", "已点击提交按钮，等待站点确认", hop=hop + 1)
            wait(2)
            emit({{"status": "applied"}})
            raise SystemExit

        emit({{"status": "non_standard_field", "fields": []}})
        raise SystemExit

    if state.get("hasApplicationTab") and click_application_tab():
        emit_progress("open_application_tab", "发现 Application 标签，正在切换到申请页", hop=hop + 1)
        wait_page()
        continue

    if click_matching_role():
        emit_progress("open_matching_role", "当前是职位列表页，已点击最匹配的岗位", hop=hop + 1, target=job_title)
        wait_page()
        continue

    if state.get("hasApplyCta") and click_apply_cta():
        emit_progress("click_apply_cta", "发现 Apply/Continue 按钮，正在进入申请流程", hop=hop + 1)
        wait_page()
        continue

emit({{"status": "no_application_path"}})
"""


def _build_browser_harness_linkedin_apply_script(
    job_url: str,
    resume_pdf_path: str,
    cover_letter_path: str,
    profile: dict,
) -> str:
    payload = {
        "job_url": job_url,
        "resume_pdf_path": resume_pdf_path,
        "cover_letter_path": cover_letter_path,
        "profile": profile,
    }
    return f"""
import json

payload = {json.dumps(payload, ensure_ascii=False)}
job_url = payload["job_url"]
resume_pdf_path = payload["resume_pdf_path"]
cover_letter_path = payload["cover_letter_path"]
profile = payload["profile"]


def emit(result):
    print(json.dumps(result, ensure_ascii=False))


def emit_progress(stage, message, **extra):
    payload = {{"__browser_harness_event__": "progress", "stage": stage, "message": message}}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))


def wait_page():
    wait_for_load()
    wait(1.2)


def analyze():
    return js(
        \"\"\"
(() => {{
  const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const buttons = Array.from(document.querySelectorAll('button, [role="button"], a')).filter(visible);
  const fileInputs = Array.from(document.querySelectorAll('input[type="file"]')).filter(visible);
  const body = normalize(document.body.innerText);
  const easyApply = buttons.find((el) => /easy apply/i.test(normalize(el.innerText || el.textContent || '')));
  const nextBtn = buttons.find((el) => /next|review/i.test(normalize(el.innerText || el.textContent || '')));
  const submitBtn = buttons.find((el) => /submit application|submit/i.test(normalize(el.innerText || el.textContent || '')));
  const dismissBtn = buttons.find((el) => /dismiss|close/i.test(normalize(el.getAttribute('aria-label') || el.innerText || '')));
  const requiredUnknown = [];
  const knownPatterns = [/name/i, /email/i, /phone/i, /mobile/i, /resume/i, /cover letter/i, /linkedin/i, /website/i];
  const labelText = (el) => {{
    const aria = el.getAttribute('aria-label');
    if (aria) return normalize(aria);
    const id = el.id;
    if (id) {{
      const label = document.querySelector(`label[for="${{CSS.escape(id)}}"]`);
      if (label) return normalize(label.innerText || label.textContent || '');
    }}
    const wrapper = el.closest('label');
    if (wrapper) return normalize(wrapper.innerText || wrapper.textContent || '');
    return '';
  }};
  const requiredFields = Array.from(document.querySelectorAll('input, textarea, select')).filter((el) => {{
    if (!visible(el)) return false;
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'file'].includes(type)) return false;
    return el.required || el.getAttribute('aria-required') === 'true';
  }});
  for (const field of requiredFields) {{
    const label = labelText(field);
    const val = normalize(field.value || '');
    const known = knownPatterns.some((pattern) => pattern.test(label));
    if (!known && !val) {{
      requiredUnknown.push({{label, tag: field.tagName.toLowerCase(), type: field.getAttribute('type') || ''}});
    }}
  }}
  return {{
    url: location.href,
    title: document.title,
    body,
    hasEasyApply: !!easyApply,
    hasNext: !!nextBtn,
    hasSubmit: !!submitBtn,
    hasFileInput: fileInputs.length > 0,
    requiredUnknown,
    loginWall: /sign in|join linkedin/i.test(body) || /login-submit/i.test(location.href),
    applied: /application submitted|your application was sent|done/i.test(body),
  }};
}})()
        \"\"\"
    )


def click_matching_button(pattern):
    return js(
        \"\"\"
(() => {{
  const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const regex = new RegExp(pattern, 'i');
  const buttons = Array.from(document.querySelectorAll('button, [role="button"], a')).filter(visible);
  const target = buttons.find((el) => regex.test(normalize(el.getAttribute('aria-label') || el.innerText || el.textContent || '')));
  if (!target) return false;
  target.click();
  return true;
}})()
        \"\"\"
    )


def fill_standard_fields():
    return js(
        \"\"\"
(() => {{
  const profile = {json.dumps(profile, ensure_ascii=False)};
  const normalize = (text) => (text || '').replace(/\\s+/g, ' ').trim();
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const labelText = (el) => {{
    const aria = el.getAttribute('aria-label');
    if (aria) return normalize(aria);
    const id = el.id;
    if (id) {{
      const label = document.querySelector(`label[for="${{CSS.escape(id)}}"]`);
      if (label) return normalize(label.innerText || label.textContent || '');
    }}
    const wrapper = el.closest('label');
    if (wrapper) return normalize(wrapper.innerText || wrapper.textContent || '');
    return '';
  }};
  const valueFor = (label) => {{
    if (/email/i.test(label)) return profile.email || '';
    if (/phone|mobile/i.test(label)) return profile.phone || '';
    if (/name/i.test(label)) return profile.name || '';
    if (/linkedin/i.test(label)) return profile.linkedin || '';
    if (/website|portfolio|github/i.test(label)) return profile.website || profile.github || '';
    return '';
  }};
  for (const field of Array.from(document.querySelectorAll('input, textarea'))) {{
    if (!visible(field) || field.disabled || field.readOnly) continue;
    const type = (field.getAttribute('type') || '').toLowerCase();
    if (['hidden', 'file', 'submit', 'button', 'checkbox', 'radio'].includes(type)) continue;
    const label = labelText(field).toLowerCase();
    const value = valueFor(label);
    if (!value || (field.value || '').trim()) continue;
    field.focus();
    field.value = value;
    field.dispatchEvent(new Event('input', {{bubbles: true}}));
    field.dispatchEvent(new Event('change', {{bubbles: true}}));
  }}
  return true;
}})()
        \"\"\"
    )


def upload_resume():
    return js(
        \"\"\"
(() => {{
  const visible = (el) => {{
    if (!el) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }};
  const input = Array.from(document.querySelectorAll('input[type="file"]')).find(visible);
  return input && input.id ? `#${{input.id}}` : '';
}})()
        \"\"\"
    )


new_tab(job_url)
emit_progress("open_job", "已打开 LinkedIn 职位页", url=job_url)
wait_page()

for _ in range(8):
    state = analyze()
    emit_progress("page_analyzed", "已分析 LinkedIn 当前页面状态", url=state.get("url"), title=state.get("title"))
    if state.get("applied"):
        emit({{"status": "applied"}})
        raise SystemExit
    if state.get("loginWall"):
        emit({{"status": "login_wall"}})
        raise SystemExit
    if state.get("requiredUnknown"):
        emit({{"status": "non_standard_field", "fields": state.get("requiredUnknown")}})
        raise SystemExit
    if state.get("hasEasyApply") and click_matching_button("easy apply"):
        emit_progress("click_easy_apply", "已点击 Easy Apply，准备进入申请表单")
        wait_page()
        continue

    fill_standard_fields()
    selector = upload_resume()
    if selector:
        upload_file(selector, resume_pdf_path)
        emit_progress("resume_uploaded", "已上传简历文件", selector=selector)
        wait(1)
    if state.get("hasSubmit") and click_matching_button("submit application|submit"):
        emit_progress("submit_clicked", "已点击 LinkedIn 提交按钮，等待结果确认")
        wait_page()
        state = analyze()
        if state.get("applied"):
            emit({{"status": "applied"}})
            raise SystemExit
    if state.get("hasNext") and click_matching_button("next|review"):
        emit_progress("next_step", "已点击 Next/Review，继续处理多步申请")
        wait_page()
        continue

emit({{"status": "no_easy_apply"}})
"""




def build_email_application_assist(
    company: str,
    title: str,
    job_url: str,
    resume_pdf_path: str,
    cover_letter_path: str = "",
    apply_email: str = "",
) -> dict:
    subject = f"Application for {title} - {company}"

    cover_letter_text = ""
    if cover_letter_path and Path(cover_letter_path).exists():
        try:
            cover_letter_text = Path(cover_letter_path).read_text(encoding="utf-8").strip()
        except OSError:
            cover_letter_text = ""

    if cover_letter_text:
        body = (
            f"Hello {company} hiring team,\n\n"
            f"I am writing to apply for the {title} position.\n\n"
            f"{cover_letter_text}\n\n"
            "I have attached my resume for your review. Thank you for your time and consideration.\n\n"
            "Best regards,"
        )
    else:
        body = (
            f"Hello {company} hiring team,\n\n"
            f"I am writing to apply for the {title} position listed here: {job_url}\n\n"
            "I have attached my resume for your review and would welcome the opportunity to discuss my fit for the role.\n\n"
            "Thank you for your time and consideration.\n\n"
            "Best regards,"
        )

    try:
        client = create_client()
        response = create_chat_completion(
            client=client,
            stage="cover_letter",
            messages=[
                {
                    "role": "system",
                    "content": "You write concise job application emails. Return strict JSON only.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Company: {company}\n"
                        f"Role: {title}\n"
                        f"Job URL: {job_url}\n"
                        f"Recipient email: {apply_email or 'unknown'}\n"
                        f"Draft seed:\n{body}\n\n"
                        'Return JSON with keys "subject" and "body". Keep it professional and concise.'
                    ),
                },
            ],
        )
        raw = response.choices[0].message.content or ""
        parsed = _extract_json_object(raw)
        if isinstance(parsed.get("subject"), str) and parsed["subject"].strip():
            subject = parsed["subject"].strip()
        if isinstance(parsed.get("body"), str) and parsed["body"].strip():
            body = parsed["body"].strip()
    except Exception:
        pass

    return {
        "apply_email": apply_email,
        "subject": subject,
        "body": body,
        "resume_pdf": resume_pdf_path,
        "cover_letter": cover_letter_path,
        "job_url": job_url,
    }


async def _emit_progress(progress_callback, **payload) -> None:
    if progress_callback is None:
        return
    maybe_awaitable = progress_callback(payload)
    if inspect.isawaitable(maybe_awaitable):
        await maybe_awaitable


async def linkedin_auto_apply(
    job_url: str,
    resume_md_path: str,
    job_id: str,
    cover_letter_path: str = "",
    progress_callback=None,
) -> dict:
    """
    Automate LinkedIn Easy Apply for a given job URL.

    Steps:
      1. Convert Markdown resume to PDF.
      2. Load pre-authenticated LinkedIn session.
      3. Use browser-use Agent (Zhipu GLM) to complete Easy Apply.

    Returns:
      - Success  : {"status": "applied", "job_id": "...", "detail": "..."}
      - Fallback : {"status": "fallback", "package": {...}, "reason": "..."}
    """
    resume_pdf_path = str(TMP_DIR / f"resume_{job_id}.pdf")

    # ------------------------------------------------------------------
    # Step 1 — Convert MD resume to PDF
    # ------------------------------------------------------------------
    if not Path(resume_md_path).exists():
        return _build_fallback(
            job_id, job_url, "", cover_letter_path,
            reason=f"resume_not_found: {resume_md_path}",
        )

    await _emit_progress(
        progress_callback,
        stage="prepare_resume_pdf",
        message="正在把定制简历转换为 PDF，供浏览器上传",
        resume_md_path=resume_md_path,
    )
    pdf_ok = _md_to_pdf(resume_md_path, resume_pdf_path)
    if not pdf_ok:
        return _build_fallback(
            job_id, job_url, "", cover_letter_path,
            reason="pdf_conversion_unavailable",
        )

    profile = _extract_candidate_profile(resume_md_path)
    await _emit_progress(
        progress_callback,
        stage="profile_extracted",
        message="已从简历中提取基础资料，准备启动 LinkedIn 申请流程",
        email=profile.get("email", ""),
    )

    try:
        harness_payload = await run_browser_harness_script(
            _build_browser_harness_linkedin_apply_script(
                job_url=job_url,
                resume_pdf_path=resume_pdf_path,
                cover_letter_path=cover_letter_path,
                profile=profile,
            ),
            on_event=progress_callback,
        )
    except Exception as exc:
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason=f"browser_harness_exception: {exc}",
        )

    status = (harness_payload.get("status") or "").strip().lower()
    if status == "applied":
        return {
            "status": "applied",
            "job_id": job_id,
            "detail": "Easy Apply submitted via browser-harness",
        }

    if status == "login_wall":
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason="login_wall",
        )

    if status == "non_standard_field":
        detail = ""
        fields = harness_payload.get("fields")
        if isinstance(fields, list) and fields:
            detail = f"发现 LinkedIn 非标准字段: {json.dumps(fields, ensure_ascii=False)[:400]}"
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason="non_standard_form_field",
            detail=detail,
        )

    if status == "no_easy_apply":
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason="easy_apply_not_available",
        )

    return _build_fallback(
        job_id, job_url, resume_pdf_path, cover_letter_path,
        reason=f"unexpected_harness_response: {json.dumps(harness_payload, ensure_ascii=False)[:200]}",
    )


async def external_auto_apply(
    job_url: str,
    resume_md_path: str,
    job_id: str,
    cover_letter_path: str = "",
    job_title: str = "",
    company: str = "",
    progress_callback=None,
) -> dict:
    """
    Attempt a generic browser-driven apply flow for non-LinkedIn job URLs.

    The agent will try to:
      1. Open the job page.
      2. Find the primary apply/apply now/application button or link.
      3. Follow it if needed.
      4. Upload the generated PDF resume.
      5. Submit only when the form is standard and low-risk.
    """
    resume_pdf_path = str(TMP_DIR / f"resume_{job_id}.pdf")

    if not Path(resume_md_path).exists():
        return _build_fallback(
            job_id, job_url, "", cover_letter_path,
            reason=f"resume_not_found: {resume_md_path}",
        )

    if _is_demo_placeholder_url(job_url):
        return _build_fallback(
            job_id,
            job_url,
            "",
            cover_letter_path,
            reason="demo_placeholder_job_url",
            detail="这是演示占位链接，不是真实投递页面。系统已跳过自动投递，保留材料供演示或手动继续。",
        )

    # mailto: links are email-only — skip browser entirely and send directly
    if job_url.lower().startswith("mailto:"):
        apply_email = _extract_email_address(job_url[len("mailto:"):].split("?")[0].strip())
        resume_pdf_path = str(TMP_DIR / f"resume_{job_id}.pdf")
        pdf_ok = _md_to_pdf(resume_md_path, resume_pdf_path)
        fallback = _build_fallback(
            job_id, job_url, resume_pdf_path if pdf_ok else "", cover_letter_path,
            reason="email_only_application",
        )
        fallback["package"]["apply_email"] = apply_email
        if apply_email and pdf_ok and (smtp_is_configured() or resend_is_configured()):
            try:
                subject = f"Job Application — {job_id}"
                body = ""
                if cover_letter_path and Path(cover_letter_path).exists():
                    cover_text = Path(cover_letter_path).read_text(encoding="utf-8").strip()
                    lines = cover_text.splitlines()
                    if lines and lines[0].startswith("**Subject:**"):
                        subject = lines[0].replace("**Subject:**", "").strip()
                        body = "\n".join(
                            line for line in lines[2:] if line.strip() != "---"
                        ).strip()
                    else:
                        body = cover_text
                email_result = send_email(
                    to_email=apply_email,
                    subject=subject,
                    body=body,
                    resume_path=resume_pdf_path,
                    cover_letter_path=cover_letter_path,
                )
                fallback["status"] = "applied"
                fallback["reason"] = "email_sent"
                fallback["email_result"] = email_result
            except Exception as exc:
                fallback["email_error"] = str(exc)
        return fallback

    await _emit_progress(
        progress_callback,
        stage="prepare_resume_pdf",
        message="正在把定制简历转换为 PDF，供外部站点上传",
        resume_md_path=resume_md_path,
        company=company,
        job_title=job_title,
    )
    pdf_ok = _md_to_pdf(resume_md_path, resume_pdf_path)
    if not pdf_ok:
        return _build_fallback(
            job_id, job_url, "", cover_letter_path,
            reason="pdf_conversion_unavailable",
        )

    profile = _extract_candidate_profile(resume_md_path)
    await _emit_progress(
        progress_callback,
        stage="profile_extracted",
        message="已从简历中提取基础资料，准备启动外部站点申请流程",
        email=profile.get("email", ""),
        company=company,
        job_title=job_title,
    )

    try:
        harness_payload = await run_browser_harness_script(
            _build_browser_harness_external_apply_script(
                job_url=job_url,
                resume_pdf_path=resume_pdf_path,
                cover_letter_path=cover_letter_path,
                job_title=job_title,
                company=company,
                profile=profile,
            ),
            on_event=progress_callback,
        )
    except Exception as exc:
        return _build_fallback(
            job_id,
            job_url,
            resume_pdf_path,
            cover_letter_path,
            reason=f"browser_harness_exception: {exc}",
        )

    status = (harness_payload.get("status") or "").strip().lower()
    if status == "applied":
        return {
            "status": "applied",
            "job_id": job_id,
            "detail": "External application submitted via browser-harness",
        }

    if status == "email_only":
        apply_email = _extract_email_address(harness_payload.get("apply_email", ""))
        fallback = _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason="email_only_application",
        )
        fallback["package"]["apply_email"] = apply_email

        # Attempt to send automatically if email is configured and we have a target address
        if apply_email and (smtp_is_configured() or resend_is_configured()):
            try:
                subject = f"Job Application — {job_id}"
                body = ""
                if cover_letter_path and Path(cover_letter_path).exists():
                    cover_text = Path(cover_letter_path).read_text(encoding="utf-8").strip()
                    lines = cover_text.splitlines()
                    # Extract subject from "**Subject:** ..." first line if present
                    if lines and lines[0].startswith("**Subject:**"):
                        subject = lines[0].replace("**Subject:**", "").strip()
                        body = "\n".join(
                            line for line in lines[2:] if line.strip() != "---"
                        ).strip()
                    else:
                        body = cover_text

                email_result = send_email(
                    to_email=apply_email,
                    subject=subject,
                    body=body,
                    resume_path=resume_pdf_path,
                    cover_letter_path=cover_letter_path,
                )
                fallback["status"] = "applied"
                fallback["reason"] = "email_sent"
                fallback["email_result"] = email_result
            except Exception as exc:
                fallback["email_error"] = str(exc)

        return fallback

    if status == "login_wall":
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason="login_wall",
        )

    if status == "non_standard_field":
        detail = ""
        fields = harness_payload.get("fields")
        if isinstance(fields, list) and fields:
            detail = f"发现非标准必填字段: {json.dumps(fields, ensure_ascii=False)[:400]}"
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason="non_standard_form_field",
            detail=detail,
        )

    if status == "no_application_path":
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason="no_application_path_found",
        )

    return _build_fallback(
        job_id, job_url, resume_pdf_path, cover_letter_path,
        reason=f"unexpected_harness_response: {json.dumps(harness_payload, ensure_ascii=False)[:200]}",
    )
