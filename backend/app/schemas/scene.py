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

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def coerce_duration(cls, v):
        """문자열로 들어온 경우 float 변환 시도."""
        try:
            return float(v)
        except (TypeError, ValueError):
            return 5.0  # 변환 실패 시 기본값
