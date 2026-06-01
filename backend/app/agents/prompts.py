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
