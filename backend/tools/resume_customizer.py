"""MCP Tool 2: resume_customizer — GLM-powered resume tailoring + HTML diff."""
import difflib
import uuid
import os
from pathlib import Path
from zhipuai import ZhipuAI
from dotenv import load_dotenv
import pdfplumber

load_dotenv()
TMP_DIR = Path("/tmp")
client = ZhipuAI(api_key=os.getenv("ZHIPUAI_API_KEY"))


def resume_customizer(
    resume_path: str,
    job_description: str,
    job_id: str | None = None,
    generate_cover_letter: bool = True,
) -> dict:
    """
    Customize a resume for a specific JD.
    Returns dict matching CustomizedResume schema.
    Only supports .pdf input — raises ValueError for other formats.
    """
    path = Path(resume_path)
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"只支持 PDF 格式，收到: {path.suffix}")
    if not path.exists():
        raise FileNotFoundError(f"简历文件不存在: {resume_path}")

    jid = job_id or str(uuid.uuid4())[:8]

    # 1. Parse PDF
    original_text = _extract_pdf_text(path)

    # 2. Customize resume (Claude call 1)
    customized_text = _customize_resume(original_text, job_description)

    # 3. Cover letter (Claude call 2, optional)
    cover_letter = ""
    cover_letter_file_path = ""
    if generate_cover_letter:
        cover_letter = _generate_cover_letter(original_text, job_description)
        cover_letter_file_path = str(TMP_DIR / f"cover_{jid}.md")
        Path(cover_letter_file_path).write_text(cover_letter, encoding="utf-8")

    # 4. Write customized resume to disk
    resume_file_path = str(TMP_DIR / f"resume_{jid}.md")
    Path(resume_file_path).write_text(customized_text, encoding="utf-8")

    # 5. Generate HTML diff
    diff_html_path = str(TMP_DIR / f"diff_{jid}.html")
    _write_diff_html(original_text, customized_text, diff_html_path)

    return {
        "original_text": original_text[:500],  # truncated for MCP response
        "customized_text": customized_text,
        "diff_html_path": diff_html_path,
        "resume_file_path": resume_file_path,
        "cover_letter": cover_letter,
        "cover_letter_file_path": cover_letter_file_path,
    }


def _extract_pdf_text(path: Path) -> str:
    lines = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _customize_resume(original: str, jd: str) -> str:
    resp = client.chat.completions.create(
        model="glm-4",
        messages=[
            {
                "role": "system",
                "content": "你是资深简历改写专家。根据 JD 优化简历，突出相关经验和技能关键词，保持事实准确，不捏造经历。",
            },
            {
                "role": "user",
                "content": (
                    f"原始简历（纯文本）：\n{original[:1500]}\n\n"
                    f"目标职位 JD：\n{jd[:1000]}\n\n"
                    "请输出改写后的简历（Markdown 格式，保留所有章节标题，只改内容不改结构）。"
                ),
            },
        ],
    )
    return resp.choices[0].message.content


def _generate_cover_letter(original: str, jd: str) -> str:
    resp = client.chat.completions.create(
        model="glm-4",
        messages=[{
            "role": "user",
            "content": (
                f"简历摘要：\n{original[:800]}\n\n"
                f"目标 JD：\n{jd[:600]}\n\n"
                "请生成一封 200 字以内的中文 Cover Letter，突出与 JD 的匹配点。"
            ),
        }],
    )
    return resp.choices[0].message.content


def _write_diff_html(original: str, customized: str, output_path: str) -> None:
    """Generate a side-by-side HTML diff."""
    original_lines = original.splitlines()
    customized_lines = customized.splitlines()

    diff = difflib.HtmlDiff(wrapcolumn=80)
    html = diff.make_file(
        original_lines,
        customized_lines,
        fromdesc="原始简历",
        todesc="定制版简历",
        context=True,
        numlines=3,
    )
    # Inject minimal styling to make it readable
    styled = html.replace(
        "</head>",
        "<style>body{font-family:system-ui,sans-serif;font-size:13px;padding:1rem}"
        "table.diff{width:100%} .diff_header{background:#f0f0f0;padding:4px}"
        ".diff_add{background:#d4edda} .diff_chg{background:#fff3cd}"
        ".diff_sub{background:#f8d7da}</style></head>",
    )
    Path(output_path).write_text(styled, encoding="utf-8")
