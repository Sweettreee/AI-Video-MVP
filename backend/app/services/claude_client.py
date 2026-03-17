from anthropic import Anthropic

from backend.app.core.config import settings

client = Anthropic(
    api_key=settings.ANTHROPIC_API_KEY,
    max_retries=settings.SDK_MAX_RETRIES,
)


def call_claude(
    system_prompt: str,
    user_message: str,
    cache_system: bool = False,
) -> str:
    """Claude API 호출 → 응답 텍스트 반환.

    cache_system=True면 시스템 프롬프트에 cache_control 적용 (eval/advisor 루프에서 비용 90% 절감).
    SDK 내장 재시도: 429/500+/529 자동 지수 백오프.
    """
    if cache_system:
        system = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        system = system_prompt

    response = client.messages.create(
        model=settings.MODEL,
        max_tokens=settings.MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text


def count_tokens(system_prompt: str, user_message: str) -> int:
    """입력 토큰 수 사전 체크. MAX_INPUT_TOKENS 초과 방지용."""
    result = client.messages.count_tokens(
        model=settings.MODEL,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return result.input_tokens