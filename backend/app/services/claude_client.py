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
    model: str | None = None,
) -> str:
    """Claude API 호출 → 응답 텍스트 반환.

    cache_system=True면 시스템 프롬프트에 cache_control 적용 (eval/advisor 루프에서 비용 90% 절감).
    model 지정 시 해당 모델 사용 (예: C5 unsafe 검수에 Haiku).
    SDK 내장 재시도: 429/500+/529 자동 지수 백오프.
    """
    used_model = model or settings.MODEL

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
        model=used_model,
        max_tokens=settings.MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text


def call_claude_structured(
    system_prompt: str,
    user_message: str,
    output_schema: type,
    use_thinking: bool = False,
    cache_system: bool = False,
):
    """Structured Outputs로 JSON 구조 강제 → Pydantic 객체 반환.

    tool use 패턴으로 output_schema의 JSON schema를 강제.
    use_thinking=True면 확장 사고 활성화 (채점 품질 향상).
    실패 시 None 반환 (refusal, max_tokens, API 에러).
    """
    tool_name = output_schema.__name__
    tool_schema = output_schema.model_json_schema()

    tools = [
        {
            "name": tool_name,
            "description": f"Return results as {tool_name}",
            "input_schema": tool_schema,
        }
    ]

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

    kwargs = {
        "model": settings.MODEL,
        "max_tokens": settings.MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user_message}],
        "tools": tools,
        "tool_choice": {"type": "tool", "name": tool_name},
    }

    if use_thinking:
        kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": settings.THINKING_BUDGET,
        }
        kwargs["max_tokens"] = settings.THINKING_BUDGET + settings.MAX_TOKENS

    response = client.messages.create(**kwargs)

    if response.stop_reason == "max_tokens":
        return None

    for block in response.content:
        if block.type == "tool_use":
            return output_schema.model_validate(block.input)

    return None


def count_tokens(system_prompt: str, user_message: str) -> int:
    """입력 토큰 수 사전 체크. MAX_INPUT_TOKENS 초과 방지용."""
    result = client.messages.count_tokens(
        model=settings.MODEL,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return result.input_tokens
