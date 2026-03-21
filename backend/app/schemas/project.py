from pydantic import BaseModel

from backend.app.schemas.feedback import Feedback


class PlotRequest(BaseModel):
    genre: str
    character: str
    mood: str
    story: str
    must_have: str | None = None
    extra: str | None = None


class PlotGenerateResponse(BaseModel):
    project_id: str
    plain_text: str


class PlotEvalResponse(BaseModel):
    code_scores: dict[str, float]
    code_average: float
    model_scores: dict[str, float]
    model_average: float
    total_average: float
    passed: bool
    failed_items: list[str]
    previous_total: float | None = None
    model_reasoning: str | None = None
    # 무한루프 방지
    failure_count: int | None = None
    loop_warning: str | None = None
    template_suggestions: list[dict] | None = None


class PlotModifyRequest(BaseModel):
    project_id: str
    modification_request: str

class PlotConfirmRequest(BaseModel):
    project_id: str


class PlotEvaluateRequest(BaseModel):
    project_id: str


class PlotAdviceRequest(BaseModel):
    project_id: str
    failed_items: list[str] = []
    feedback: list[Feedback] | None = None



class HumanEvalRequest(BaseModel):
    project_id: str
    H1: bool  # Fan-appeal: 팬덤 취향에 맞는가
    H2: bool  # Emotional pacing: 흐름이 자연스러운가
    H3: bool  # Input faithfulness: 유저 아이디어가 반영되었는가
    feedback: str | None = None  # 자유 텍스트 피드백 (선택)


class HumanEvalResponse(BaseModel):
    project_id: str
    passed: bool
    failed_items: list[str]
    message: str
