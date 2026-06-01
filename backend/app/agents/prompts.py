"""Single source for all agent prompt templates.

Each template is a callable that returns a fully-formatted user message
string. System prompts are kept separate and short — model-tuning
should change templates here, not node code.
"""
from __future__ import annotations

COORDINATOR_SYSTEM = (
    "당신은 학습 코디네이터입니다. 사용자의 의도와 약점 목록을 보고 "
    "다음으로 풀 문제의 주제와 난이도를 결정합니다. "
    "응답은 반드시 JSON만 출력하세요."
)


def coordinator_prompt(
    user_intent: str, weak_topics: list[str], all_topics: list[str]
) -> str:
    weak = ", ".join(weak_topics) if weak_topics else "(없음)"
    topics = ", ".join(all_topics)
    return f"""사용자 의도: "{user_intent}"
사용 가능한 주제: {topics}
사용자의 최근 약점 Top3: {weak}

다음을 JSON으로만 응답하시오 (다른 텍스트 금지):
{{
  "topic": "<주제명>",
  "difficulty": <1|2|3>,
  "target_weakness": <true if 약점 보강 목적이면, else false>,
  "reason": "<한 문장 근거>"
}}"""


QGEN_SYSTEM = (
    "당신은 한국 정보처리기사 실기 시험 출제자입니다. 주어진 학습 자료를 바탕으로 "
    "서술형 문제 한 개와 모범답안, 그리고 채점 루브릭(3~5개 항목)을 동시에 생성합니다. "
    "응답은 반드시 JSON만 출력하세요."
)


def qgen_prompt(topic: str, difficulty: int, context_chunks: list[str]) -> str:
    context = "\n\n".join(f"[자료 {i + 1}]\n{c}" for i, c in enumerate(context_chunks))
    return f"""주제: {topic}
난이도: {difficulty} (1=쉬움, 2=보통, 3=어려움)

참고 자료:
{context}

다음 JSON 형식으로만 응답하시오:
{{
  "question": "<서술형 문제 한 문장>",
  "model_answer": "<모범답안 3~5문장>",
  "rubric": [
    {{"point": "<채점 기준>", "weight": <0~1>, "keywords": ["<키워드>", ...]}}
  ]
}}

루브릭 가중치 합은 1.0이 되어야 합니다."""


GRADER_SYSTEM = (
    "당신은 한국 정보처리기사 실기 시험 채점자입니다. "
    "주어진 루브릭에 따라 학습자 답안을 항목별로 채점하고, "
    "각 항목의 일치 여부와 부분점수를 합산해 최종 점수(0~1)를 산정합니다. "
    "응답은 반드시 JSON만 출력하세요."
)


def grader_prompt(
    question: str,
    model_answer: str,
    rubric: list[dict[str, object]],
    user_answer: str,
) -> str:
    rubric_str = "\n".join(
        f"{i + 1}. {r['point']} (가중치 {r['weight']}, 키워드 {r.get('keywords', [])})"
        for i, r in enumerate(rubric)
    )
    return f"""문제: {question}

모범답안: {model_answer}

루브릭:
{rubric_str}

학습자 답안:
\"\"\"
{user_answer}
\"\"\"

JSON으로만 응답하시오:
{{
  "score": <0.0~1.0>,
  "rationale": "<루브릭 항목별 채점 근거 한 문단>",
  "feedback": "<학습자에게 줄 보강 가이드 한 문단>",
  "missing_points": ["<빠진 키워드 또는 핵심 개념>", ...]
}}"""
