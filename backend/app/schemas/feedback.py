from pydantic import BaseModel


class Feedback(BaseModel):
    feedback_type: str  # fan_appeal_mismatch / pacing_issue / input_mismatch
    detail: str         # character_appearance / no_climax / missing_scene 등
    target_cuts: list[int] = []
    free_text: str | None = None
