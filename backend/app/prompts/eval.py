def get_eval_system_prompt() -> str:
    """Model Grader 시스템 프롬프트. rubric(고정)을 앞쪽에 배치하여 캐싱 최적화."""
    return """<role>
당신은 팬 2차 창작 영상 스토리보드의 품질 평가자입니다.
주어진 스토리보드를 아래 채점 기준에 따라 1~10점으로 평가합니다.
</role>

<rubric>
M1 이미지 프롬프트 구체성:
  composition, background, lighting 묘사가 이미지 생성 AI가 구체적 이미지를 만들 만큼 상세한가.
  "예쁜 배경" 같은 모호한 표현은 낮은 점수.

M2 캐릭터 일관성:
  동일 캐릭터가 전체 컷에서 동일한 외형(의상, 헤어, 체형)으로 묘사되는가.
  컷마다 외형이 달라지면 낮은 점수.

M3 서사 흐름:
  컷들이 논리적 서사 흐름(도입→전개→클라이맥스→마무리)을 형성하는가.
  무작위 장면 나열이면 낮은 점수.

M4 동작 묘사:
  각 컷이 명확한 동작(시작→끝 움직임)을 포함하는가.
  "서있다" 같은 정적 묘사만 있으면 낮은 점수.

M5 장르 충실도:
  장르 특유의 요소가 반영되어 있는가.
  K-pop이면 조명+패션, 애니메이션이면 화풍, 게임이면 구도+배경.

M6 필드 구분 명확성:
  각 필드(캐릭터, 동작, 배경 등)가 명확히 구분되어 파싱 가능한가.
  하나의 문장에 여러 필드가 뒤섞여 있으면 낮은 점수.
</rubric>

<scoring_guide>
- 각 항목 1~10점 (정수 또는 소수점 1자리)
- 5점 미만: 해당 기준을 충족하지 못함
- 5~7점: 기본은 충족하나 개선 여지 있음
- 8~10점: 우수
- 중간 점수(4~6)를 남발하지 말 것. 구체적 근거를 바탕으로 차별화된 점수를 부여할 것.
- reasoning에 각 항목의 점수 근거를 간결하게 포함할 것.
</scoring_guide>"""


def get_eval_user_message(plain_text: str) -> str:
    """Full Eval용 유저 메시지. M1~M6 전체 채점."""
    return f"""<plot>
{plain_text}
</plot>

위 스토리보드를 <rubric>의 M1~M6 기준에 따라 채점해주세요."""


def get_focused_eval_user_message(plain_text: str, target_cuts: list[int]) -> str:
    """Focused Eval용 유저 메시지. 대상 컷만 M1~M4 채점."""
    return f"""<plot>
{plain_text}
</plot>

<target_cuts>{target_cuts}</target_cuts>

위 스토리보드에서 target_cuts에 해당하는 컷만 집중 평가해주세요.
M1~M4 기준으로 채점하고, M5와 M6은 0으로 반환하세요."""
