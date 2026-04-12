"""MCP Tool 3: interview_prep — generates interview questions + STAR answers."""
import json
import os
import re
from zhipuai import ZhipuAI
from dotenv import load_dotenv

load_dotenv()
client = ZhipuAI(api_key=os.getenv("ZHIPUAI_API_KEY"))


def interview_prep(
    company: str,
    job_title: str,
    job_description: str,
) -> dict:
    """
    Generate 5 interview questions with STAR framework answers.
    MVP: uses JD only (no external search).
    Returns dict matching InterviewPrep schema.
    """
    questions_with_stars = _generate_questions(company, job_title, job_description)

    return {
        "company": company,
        "role": job_title,
        "questions": [q["question"] for q in questions_with_stars],
        "star_answers": questions_with_stars,
    }


def _generate_questions(company: str, title: str, jd: str) -> list[dict]:
    """Single Claude call: generate 5 Q&A pairs in JSON."""
    resp = client.chat.completions.create(
        model="glm-4",
        messages=[
            {
                "role": "system",
                "content": "你是专业的面试教练，擅长帮求职者准备 STAR 结构答案。",
            },
            {
                "role": "user",
                "content": (
                    f"公司：{company}\n"
                    f"岗位：{title}\n"
                    f"JD 摘要：{jd[:800]}\n\n"
                    "请生成 5 道最可能被问到的面试题，并为每道题提供 STAR 框架答案。\n"
                    "输出严格 JSON 格式（数组，共 5 个对象）：\n"
                    '[{"question":"...","star":{"S":"情境...","T":"任务...","A":"行动...","R":"结果..."}}]'
                ),
            },
        ],
    )

    raw = resp.choices[0].message.content
    # Extract JSON array from response
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: return structured placeholder if parsing fails
    return [
        {
            "question": f"请介绍一下你在 {title} 方面最有代表性的项目经历？",
            "star": {
                "S": "（根据 JD 自行填写情境）",
                "T": "（你的具体任务）",
                "A": "（你采取的行动）",
                "R": "（最终结果和数据）",
            },
        }
    ]
