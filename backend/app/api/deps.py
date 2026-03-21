from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.db import models
from backend.app.schemas.scene import GlobalContext, Scene


def load_project(project_id: str, db: Session) -> models.Project:
    """DB에서 프로젝트 로드. 없으면 404."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=404, detail=f"Project({project_id})를 찾을 수 없습니다."
        )
    return project


def load_global_context(project: models.Project) -> GlobalContext:
    """프로젝트의 GlobalContext 로드. 없으면 400."""
    if not project.global_context_json:
        raise HTTPException(
            status_code=400,
            detail="GlobalContext가 생성되지 않았습니다. /api/plot/generate를 먼저 호출하세요.",
        )
    return GlobalContext.model_validate_json(project.global_context_json)


def load_scenes_from_db(project_id: str, db: Session) -> list[Scene]:
    """DB에서 확정된 Scene 리스트 로드. 없으면 400."""
    db_scenes = (
        db.query(models.Scene)
        .filter(models.Scene.project_id == project_id)
        .order_by(models.Scene.scene_number)
        .all()
    )
    if not db_scenes:
        raise HTTPException(
            status_code=400,
            detail="확정된 Scene이 없습니다. /api/plot/confirm을 먼저 호출하세요.",
        )
    return [Scene.model_validate_json(s.scene_data) for s in db_scenes]
