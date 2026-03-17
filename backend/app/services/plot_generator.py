import re

from backend.app.core.config import settings
from backend.app.prompts.system import get_system_prompt
from backend.app.services.claude_client import call_claude, count_tokens


class GenerationError(Exception):
    pass


def generate_plot(
    answers: dict,
    previous_storyboard: str | None = None,
    modification_request: str | None = None,
) -> str:
    """가이드 질문 답변 → Claude 호출 → plain text 스토리보드 반환.

    첫 생성: previous_storyboard=None
    수정: previous_storyboard + modification_request → 수정된 부분만 반영
    """
    system_prompt = get_system_prompt(answers)

    if previous_storyboard and modification_request:
        user_message = (
            f"<previous_storyboard>\n{previous_storyboard}\n</previous_storyboard>\n\n"
            f"<modification>\n{modification_request}\n</modification>\n\n"
            "위 스토리보드에서 수정 요청된 부분만 반영하여 전체 스토리보드를 다시 작성해주세요."
        )
    else:
        user_message = "위 user_context를 바탕으로 스토리보드를 작성해주세요."

    token_count = count_tokens(system_prompt, user_message)
    if token_count > settings.MAX_INPUT_TOKENS:
        raise GenerationError(
            f"입력이 너무 깁니다 ({token_count:,} 토큰). "
            f"최대 {settings.MAX_INPUT_TOKENS:,} 토큰까지 가능합니다. "
            "입력을 줄여주세요."
        )

    cache = previous_storyboard is not None

    for attempt in range(2):
        response = call_claude(system_prompt, user_message, cache_system=cache)

        if not response or not response.strip():
            if attempt == 0:
                continue
            raise GenerationError(
                "스토리보드 생성에 실패했습니다. 다른 아이디어로 시도해보세요."
            )

        if not re.search(r"\[Cut \d+\]", response):
            if attempt == 0:
                continue
            raise GenerationError(
                "스토리보드 형식이 올바르지 않습니다. 다른 아이디어로 시도해보세요."
            )

        return response

    raise GenerationError("스토리보드 생성에 실패했습니다.")
