from backend.app.prompts.advisor import (
    get_advisor_system_prompt,
    get_advisor_user_message,
    get_human_feedback_user_message,
)
from backend.app.schemas.feedback import Feedback
from backend.app.services.claude_client import call_claude

_STATIC_FALLBACK = (
    "캐릭터 외형(의상, 헤어, 체형)을 첫 등장 컷에서 구체적으로 묘사하고 이후 컷에서 일관되게 유지하세요. "
    "각 컷의 배경과 조명을 '역광의 황금빛 일몰' 수준으로 구체적으로 지정하세요. "
    "스토리비트 필드에 도입/전개/클라이맥스/마무리 역할을 명시하여 서사 흐름을 만드세요."
)


def generate_advice(
    plain_text: str,
    failed_items: list[str],
    feedback: list[Feedback] | None = None,
    previous_advice: str | None = None,
) -> str:
    """failed_items 기반 또는 Human Eval 피드백 기반 개선 가이드라인 생성.

    feedback=None → 자동 평가 후 (Phase 3): failed_items 기반 가이드
    feedback=list[Feedback] → Human Eval 불만족 시 (Phase 4): 타겟팅된 가이드
    API 실패 시 static fallback 반환 (루프 중단 방지).
    previous_advice가 있으면 다른 방향의 조언을 요청.
    """
    system_prompt = get_advisor_system_prompt()

    if feedback:
        feedback_dicts = [f.model_dump() for f in feedback]
        user_message = get_human_feedback_user_message(plain_text, feedback_dicts)
    else:
        user_message = get_advisor_user_message(plain_text, failed_items)

    if previous_advice:
        user_message += (
            f"\n\n<previous_advice>\n{previous_advice}\n</previous_advice>\n\n"
            "이전 조언과 다른 새로운 방향의 개선책을 제시해주세요."
        )

    response = call_claude(system_prompt, user_message, cache_system=True)

    if not response or not response.strip():
        return _STATIC_FALLBACK

    return response
