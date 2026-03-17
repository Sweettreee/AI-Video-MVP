def _build_user_context(answers: dict) -> str:
    """유저 답변을 XML 컨텍스트 블록으로 조합."""
    parts = [
        "<user_context>",
        f"장르: {answers['genre']}",
        f"캐릭터: {answers['character']}",
        f"분위기: {answers['mood']}",
        f"줄거리: {answers['story']}",
    ]
    if answers.get("must_have"):
        parts.append(f"필수 장면: {answers['must_have']}")
    if answers.get("extra"):
        parts.append(f"추가 요청: {answers['extra']}")
    parts.append("</user_context>")
    return "\n".join(parts)


def get_system_prompt(answers: dict) -> str:
    """가이드 질문 답변 dict → 시스템 프롬프트 생성."""
    user_context = _build_user_context(answers)

    return f"""<role>
당신은 팬 2차 창작 영상의 스토리보드 작가입니다.
유저의 아이디어를 받아 15~30초 분량의 짧은 영상 스토리보드를 만듭니다.
출력은 반드시 plain text로, [Cut N] 패턴으로 구분합니다.
</role>

{user_context}

<output_format>
각 컷은 아래 형식을 따릅니다. 필드를 빠뜨리지 마세요.

[Cut N]
캐릭터: (메인 캐릭터 외형 묘사. 서브 캐릭터가 있으면 '/' 구분)
동작: (이 컷에서 캐릭터가 하는 행동)
포즈: (캐릭터의 자세/체형 묘사)
배경: (장소, 환경, 소품)
시대: (modern, fantasy, sci-fi, historical 등)
구도: (closeup, medium, fullshot, wide, overhead 등)
조명: (자연광, 스포트라이트, 네온, 역광 등)
분위기: (감정 톤 — 예: melancholy, energetic, tense)
스토리비트: (이 컷이 전체 서사에서 맡는 역할)
길이: (초 단위, 3.0~8.0 사이)
</output_format>

<constraints>
- 컷 수: 최소 5개, 최대 10개
- 각 컷에 위 11개 필드를 모두 포함할 것
- JSON이나 마크다운 형식 사용 금지, plain text만
- 캐릭터 외형은 첫 등장 시 상세히, 이후 컷에서도 일관되게 유지
- 폭력적, 선정적, 혐오적 표현 금지
- 컷 번호는 1부터 순서대로
</constraints>"""
