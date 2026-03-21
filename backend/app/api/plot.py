import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.app.db import models
from backend.app.db.database import get_db
from backend.app.schemas.project import (
    PlotRequest,
    PlotGenerateResponse,
    PlotEvalResponse,
    PlotEvaluateRequest,
    PlotModifyRequest,
    PlotConfirmRequest,
    PlotAdviceRequest,
    HumanEvalRequest,
    HumanEvalResponse,
)

logger = logging.getLogger(__name__)
from backend.app.api.deps import load_project
from backend.app.services.plot_generator import generate_plot, GenerationError
from backend.app.services.plot_evaluator import full_eval
from backend.app.services.plot_advisor import generate_advice
from backend.app.services.plot_converter import parse_storyboard, ParseError
from backend.app.services.character_sheet import extract_global_context

router = APIRouter()


# ── POST /api/plot/generate ────────────────────────────────

@router.post("/generate", response_model=PlotGenerateResponse)
def generate(req: PlotRequest, db: Session = Depends(get_db)):
    """유저 입력 → GlobalContext 생성 → 스토리보드 생성.

    1. PlotRequest → answers dict 변환
    2. generate_plot()으로 plain text 생성
    3. 임시 파싱으로 scenes 추출 → extract_global_context()
    4. Project DB 생성 (answers, plain_text, global_context 저장)
    """
    answers = req.model_dump() # Pydantic 모델 객체 → Python 딕셔너리로 변환

    try:
        plain_text = generate_plot(answers)
    except GenerationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # GlobalContext 생성 (Claude 1회 호출)
    try:
        scenes = parse_storyboard(plain_text)
        global_ctx = extract_global_context(answers, scenes)
        global_ctx_json = global_ctx.model_dump_json()
    except Exception as e:
        # GlobalContext 생성 실패해도 스토리보드 자체는 반환
        logger.warning(f"GlobalContext 생성 실패 (스토리보드는 정상 반환): {e}")
        global_ctx_json = None

    # DB 저장
    project = models.Project(
        user_prompt=answers.get("story", ""),
        genre=answers.get("genre", ""),
        art_style=answers.get("mood", ""),
        status="generated",
        current_stage="plot_generated",
        answers_json=json.dumps(answers, ensure_ascii=False),
        plain_text=plain_text,
        global_context_json=global_ctx_json,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return PlotGenerateResponse(
        project_id=project.id,
        plain_text=plain_text,
    )


# ── POST /api/plot/evaluate ────────────────────────────────

_TEMPLATE_SUGGESTIONS = [
    {"genre": "kpop", "story": "아이돌이 콘서트 무대에서 팬들과 함께하는 감동적인 장면"},
    {"genre": "anime", "story": "주인공이 숙적과 마지막 결전을 벌이는 클라이맥스"},
    {"genre": "game", "story": "영웅이 마왕을 쓰러뜨리고 세계를 구하는 엔딩"},
]

@router.post("/evaluate", response_model=PlotEvalResponse)
def evaluate(req: PlotEvaluateRequest, db: Session = Depends(get_db)):
    """현재 스토리보드 평가. Code Grader + Model Grader.

    연속 실패 횟수를 추적하여 무한 루프를 방지한다.
    - 3회: 템플릿 예시 제안
    - 5회: 진행 경고
    - 7회: 강제 중단 (HTTP 422)
    """
    project = load_project(req.project_id, db)

    if not project.plain_text:
        raise HTTPException(status_code=400, detail="스토리보드가 아직 생성되지 않았습니다.")

    failure_count = project.failure_count or 0

    # 7회 연속 실패 → 강제 중단
    if failure_count >= 7:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "연속 7회 평가 실패. 새 프로젝트를 시작하거나 입력을 크게 바꿔주세요.",
                "failure_count": failure_count,
                "action": "abort",
                "template_suggestions": _TEMPLATE_SUGGESTIONS,
            },
        )

    result = full_eval(project.plain_text)

    # 실패/통과에 따라 카운터 업데이트
    if result.passed:
        project.failure_count = 0
    else:
        project.failure_count = failure_count + 1

    project.current_stage = "eval_passed" if result.passed else "eval_failed"
    db.commit()

    # 응답에 루프 방지 힌트 추가
    new_count = project.failure_count or 0
    loop_warning = None
    template_suggestions = None
    if new_count >= 5:
        loop_warning = f"연속 {new_count}회 실패. 입력을 크게 바꿔보세요. (7회 시 강제 중단)"
    elif new_count >= 3:
        template_suggestions = _TEMPLATE_SUGGESTIONS

    return PlotEvalResponse(
        code_scores=result.code_scores,
        code_average=result.code_average,
        model_scores=result.model_scores,
        model_average=result.model_average,
        total_average=result.total_average,
        passed=result.passed,
        failed_items=result.failed_items,
        previous_total=result.previous_total,
        model_reasoning=result.model_reasoning,
        failure_count=new_count,
        loop_warning=loop_warning,
        template_suggestions=template_suggestions,
    )


# ── POST /api/plot/advice ──────────────────────────────────

@router.post("/advice")
def advice(req: PlotAdviceRequest, db: Session = Depends(get_db)):
    """failed_items 기반 개선 가이드. evaluate 결과의 failed_items를 전달받는다."""
    project = load_project(req.project_id, db)

    if not project.plain_text:
        raise HTTPException(status_code=400, detail="스토리보드가 아직 생성되지 않았습니다.")

    advice_text = generate_advice(
        plain_text=project.plain_text,
        failed_items=req.failed_items,
        feedback=req.feedback,
    )

    return {"project_id": req.project_id, "advice": advice_text}


# ── POST /api/plot/modify ──────────────────────────────────

@router.post("/modify", response_model=PlotGenerateResponse)
def modify(req: PlotModifyRequest, db: Session = Depends(get_db)):
    """기존 스토리보드 수정. previous_storyboard + modification_request."""
    project = load_project(req.project_id, db)

    if not project.plain_text or not project.answers_json:
        raise HTTPException(status_code=400, detail="스토리보드가 아직 생성되지 않았습니다.")

    answers = json.loads(project.answers_json)

    try:
        new_plain_text = generate_plot(
            answers=answers,
            previous_storyboard=project.plain_text,
            modification_request=req.modification_request,
        )
    except GenerationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # GlobalContext 재생성 (캐릭터 변경 반영)
    try:
        new_scenes = parse_storyboard(new_plain_text)
        new_ctx = extract_global_context(answers, new_scenes)
        project.global_context_json = new_ctx.model_dump_json()
    except Exception:
        pass  # GlobalContext 실패해도 스토리보드 수정 자체는 진행

    # DB 업데이트 — 수정 성공 시 연속 실패 카운터 리셋
    project.plain_text = new_plain_text
    project.current_stage = "modified"
    project.failure_count = 0
    db.commit()

    return PlotGenerateResponse(
        project_id=project.id,
        plain_text=new_plain_text,
    )


# ── POST /api/plot/human-eval ─────────────────────────────

@router.post("/human-eval", response_model=HumanEvalResponse)
def human_eval(req: HumanEvalRequest, db: Session = Depends(get_db)):
    """Human Eval (H1~H3) — 유저 셀프 체크.

    evaluate 통과 후 유저가 직접 스토리보드를 검토하고 체크한다.
    H1~H3 모두 통과 시 current_stage = "human_eval_passed" 로 업데이트.
    하나라도 실패 시 실패 항목을 반환하고 수정을 유도한다.
    """
    project = load_project(req.project_id, db)

    if not project.plain_text:
        raise HTTPException(status_code=400, detail="스토리보드가 아직 생성되지 않았습니다.")

    # AI 평가를 통과한 후에만 Human Eval 진행 가능
    if project.current_stage not in ("eval_passed", "human_eval_failed"):
        raise HTTPException(
            status_code=400,
            detail="AI 평가를 통과해야 합니다. /api/plot/evaluate 를 호출하세요.",
        )

    failed_items = []
    if not req.H1:
        failed_items.append("H1: 팬덤 취향에 맞지 않습니다")
    if not req.H2:
        failed_items.append("H2: 감정 흐름이 자연스럽지 않습니다")
    if not req.H3:
        failed_items.append("H3: 처음 아이디어가 충분히 반영되지 않았습니다")

    passed = len(failed_items) == 0

    # Human Eval 결과 저장
    project.human_eval_json = json.dumps(
        {
            "H1": req.H1,
            "H2": req.H2,
            "H3": req.H3,
            "feedback": req.feedback,
            "passed": passed,
        },
        ensure_ascii=False,
    )

    if passed:
        project.current_stage = "human_eval_passed"
        message = "Human Eval 통과. /api/plot/confirm 으로 스토리보드를 확정할 수 있습니다."
    else:
        project.current_stage = "human_eval_failed"
        message = "Human Eval 미통과. /api/plot/modify 로 스토리보드를 수정해주세요."

    db.commit()

    return HumanEvalResponse(
        project_id=req.project_id,
        passed=passed,
        failed_items=failed_items,
        message=message,
    )


# ── POST /api/plot/confirm ─────────────────────────────────

@router.post("/confirm")
def confirm(req: PlotConfirmRequest, db: Session = Depends(get_db)):
    """스토리보드 확정 → JSON 변환 → DB에 Scene 저장."""
    project = load_project(req.project_id, db)

    if not project.plain_text:
        raise HTTPException(status_code=400, detail="스토리보드가 아직 생성되지 않았습니다.")

    if project.current_stage not in ("human_eval_passed", "plot_confirmed"):
        raise HTTPException(
            status_code=400,
            detail="Human Eval을 먼저 완료해주세요. /api/plot/human-eval 을 호출하세요.",
        )

    try:
        scenes = parse_storyboard(project.plain_text)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 기존 Scene 삭제 후 새로 저장
    db.query(models.Scene).filter(models.Scene.project_id == project.id).delete()

    for scene in scenes:
        db_scene = models.Scene(
            project_id=project.id,
            scene_number=scene.cut_number,
            scene_data=scene.model_dump_json(),
        )
        db.add(db_scene)

    project.status = "confirmed"
    project.current_stage = "plot_confirmed"
    project.confirmed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "project_id": project.id,
        "scene_count": len(scenes),
        "scenes": [s.model_dump() for s in scenes],
    }


# ── GET /api/plot/{project_id} ─────────────────────────────

@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    """프로젝트 상태 + 스토리보드 조회."""
    project = load_project(project_id, db)

    return {
        "project_id": project.id,
        "status": project.status,
        "current_stage": project.current_stage,
        "genre": project.genre,
        "plain_text": project.plain_text,
        "has_global_context": project.global_context_json is not None,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }
