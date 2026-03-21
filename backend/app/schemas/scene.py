from pydantic import BaseModel, Field, field_validator


class Scene(BaseModel):
    cut_number: int = Field(ge=1)
    main_character: str
    sub_character: str | None = None
    action: str
    pose: str
    background: str
    era: str
    composition: str
    lighting: str
    mood: str
    story_beat: str
    duration_seconds: float = Field(ge=3.0, le=8.0)
    camera_angle: str = ""   # eye level / low angle / high angle / dutch angle / bird's eye
    expression: str = ""     # 캐릭터 표정 묘사
    foreground: str = ""     # 전경 요소 (깊이감)

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def coerce_duration(cls, v):
        """문자열로 들어온 경우 float 변환 시도."""
        try:
            return float(v)
        except (TypeError, ValueError):
            return 5.0  # 변환 실패 시 기본값

class GlobalContext(BaseModel):
    """프로젝트 전체에 공유되는 이미지 생성 컨텍스트.

    모든 컷의 이미지 프롬프트에 동일하게 삽입되어 캐릭터/스타일 일관성을 보장한다.
    """

    main_character: str  # Claude가 생성한 캐릭터 시트 (상세 외형 묘사)
    sub_character: str | None = None
    art_style: str  # anime cel-shading / photorealistic 등
    era: str  # modern / historical korean 등
    color_palette: str  # warm golden / cool blue 등
