"""MCP Tool 3: interview_prep — generates interview questions + STAR answers."""
import json
import re
from dotenv import load_dotenv
from llm_client import create_chat_completion, create_client

load_dotenv()
client = create_client()


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


def _fallback_questions(company: str, title: str) -> list[dict]:
    prompts = [
        f"请介绍一个你最能代表自己能力的 {title} 项目经历。",
        f"如果加入 {company}，你会如何在前 30 天内熟悉业务并开始产出？",
        f"你做过哪些性能优化、稳定性提升或工程效率改进？",
        "请讲一次你处理复杂协作或需求变化的经历。",
        "如果线上出现严重故障，你会如何排查、沟通和复盘？",
    ]
    return [
        {
            "question": prompt,
            "star": {
                "S": "补充这次事件发生的背景、团队环境和业务场景。",
                "T": "说明你当时负责的目标、约束和必须解决的问题。",
                "A": "拆解你的分析过程、关键动作和取舍。",
                "R": "量化结果，并补一句你从中学到了什么。",
            },
        }
        for prompt in prompts
    ]


def _generate_questions(company: str, title: str, jd: str) -> list[dict]:
    """Single Claude call: generate 5 Q&A pairs in JSON."""
    try:
        resp = create_chat_completion(
            client=client,
            stage="interview_prep",
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
    except Exception:
        return _fallback_questions(company, title)

    raw = resp.choices[0].message.content
    # Extract JSON array from response
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: return structured placeholder if parsing fails
    return _fallback_questions(company, title)
