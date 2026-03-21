import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.app.db import models
from backend.app.db.database import get_db, SessionLocal
from backend.app.api.deps import load_project
from backend.app.schemas.video import VideoGenerateRequest, VideoGenerateAllRequest
from backend.app.services.video import generate_video_from_fal, VideoGenerationError

router = APIRouter()
logger = logging.getLogger(__name__)


# ── POST /api/video (단건 영상 생성) ─────────────────────────

@router.post("")
async def create_scene_video(req: VideoGenerateRequest, db: Session = Depends(get_db)):
    """단건 영상 생성. DB에 저장된 이미지 URL + 프롬프트를 자동으로 사용."""
    scene = db.query(models.Scene).filter(models.Scene.id == req.scene_id).first()

    if not scene:
        raise HTTPException(
            status_code=404, detail=f"Scene({req.scene_id})을 찾을 수 없습니다."
        )

    if not scene.draft_image_url or not scene.generated_image_prompt:
        raise HTTPException(
            status_code=400,
            detail="아직 이미지가 생성되지 않은 씬입니다. 이미지를 먼저 생성해 주세요.",
        )

    # W8: generating 상태 먼저 마킹
    scene.video_status = "generating"
    db.commit()

    try:
        video_url = await generate_video_from_fal(
            prompt=scene.generated_image_prompt,
            image_url=scene.draft_image_url,
        )
    except VideoGenerationError as e:
        scene.video_status = "failed"
        db.commit()
        raise HTTPException(
            status_code=500, detail=f"비디오 생성 실패: {str(e)}"
        )

    scene.veo2_prompt = scene.generated_image_prompt
    scene.clip_video_url = video_url
    scene.video_status = "done"
    db.commit()

    return {
        "scene_id": req.scene_id,
        "video_url": video_url,
        "video_status": "done",
    }


# ── BackgroundTask: 영상 일괄 생성 ──────────────────────────

async def _bg_generate_all_videos(
    project_id: str,
    scene_tasks: list[tuple[str, int, str, str]],  # (scene_id, scene_number, prompt, image_url)
) -> None:
    """백그라운드에서 영상 일괄 생성. 자체 DB 세션 사용."""
    db = SessionLocal()
    try:
        sem = asyncio.Semaphore(2)

        async def _generate_one(scene_id, scene_number, prompt, image_url):
            async with sem:
                try:
                    video_url = await generate_video_from_fal(
                        prompt=prompt,
                        image_url=image_url,
                    )
                    return scene_id, scene_number, video_url, "done"
                except VideoGenerationError as e:
                    return scene_id, scene_number, str(e), "failed"

        task_results = await asyncio.gather(
            *[_generate_one(sid, sn, p, iu) for sid, sn, p, iu in scene_tasks]
        )

        db_scene_map = {
            s.id: s for s in db.query(models.Scene)
            .filter(models.Scene.project_id == project_id).all()
        }

        has_success = False
        for scene_id, scene_number, value, status in task_results:
            db_scene = db_scene_map.get(scene_id)
            if not db_scene:
                continue
            if status == "done":
                db_scene.veo2_prompt = db_scene.generated_image_prompt
                db_scene.clip_video_url = value
                db_scene.video_status = "done"
                has_success = True
            else:
                db_scene.video_status = "failed"
                logger.error(f"Cut {scene_number} 영상 생성 실패: {value}")

        if has_success:
            project = db.query(models.Project).filter(
                models.Project.id == project_id
            ).first()
            if project:
                project.current_stage = "videos_generated"

        db.commit()

    except Exception as e:
        logger.error(f"백그라운드 영상 생성 에러 (project={project_id}): {e}")
        db.query(models.Scene).filter(
            models.Scene.project_id == project_id,
            models.Scene.video_status == "generating",
        ).update({"video_status": "failed"})
        db.commit()
    finally:
        db.close()


# ── POST /api/video/generate-all (전체 컷 일괄 영상 생성) ────

@router.post("/generate-all")
async def generate_all_videos(
    req: VideoGenerateAllRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """프로젝트의 모든 Scene에 대해 영상 일괄 생성.

    C4: 즉시 반환, 실제 생성은 BackgroundTasks에서 수행 (타임아웃 방지).
    C7: 이미지 없는 씬은 DB에 "skipped" 기록.
    W8: 생성 대상 씬은 즉시 "generating" 상태 마킹.
    폴링: GET /api/video/{project_id}/scenes
    """
    load_project(req.project_id, db)

    db_scenes = (
        db.query(models.Scene)
        .filter(models.Scene.project_id == req.project_id)
        .order_by(models.Scene.scene_number)
        .all()
    )

    if not db_scenes:
        raise HTTPException(
            status_code=400, detail="생성된 Scene이 없습니다."
        )

    # C7 + W8: 상태 즉시 마킹, tasks 준비
    scene_tasks = []
    for s in db_scenes:
        if not s.draft_image_url or not s.generated_image_prompt:
            s.video_status = "skipped"  # C7: DB에 skipped 기록 (폴링 중단 조건 충족)
        else:
            s.video_status = "generating"  # W8: generating 상태 마킹
            scene_tasks.append((s.id, s.scene_number, s.generated_image_prompt, s.draft_image_url))

    db.commit()

    if scene_tasks:
        background_tasks.add_task(_bg_generate_all_videos, req.project_id, scene_tasks)

    return {"project_id": req.project_id, "videos": []}


# ── GET /api/video/{project_id}/scenes ────────────────────

@router.get("/{project_id}/scenes")
async def get_video_scenes(project_id: str, db: Session = Depends(get_db)):
    """프로젝트의 모든 Scene 영상 상태 조회."""
    load_project(project_id, db)

    db_scenes = (
        db.query(models.Scene)
        .filter(models.Scene.project_id == project_id)
        .order_by(models.Scene.scene_number)
        .all()
    )

    return {
        "project_id": project_id,
        "scenes": [
            {
                "scene_id": s.id,
                "cut_number": s.scene_number,
                "image_url": s.draft_image_url,
                "video_url": s.clip_video_url,
                "video_status": s.video_status,
            }
            for s in db_scenes
        ],
    }


# ── POST /api/video/finalize/{project_id} ─────────────────

@router.post("/finalize/{project_id}")
async def finalize_video(project_id: str, db: Session = Depends(get_db)):
    """모든 클립 URL을 순서대로 수집 → final_video_url에 저장.

    MVP: 실제 영상 병합 없이 ordered clip list를 반환.
    """
    project = load_project(project_id, db)

    db_scenes = (
        db.query(models.Scene)
        .filter(models.Scene.project_id == project_id)
        .order_by(models.Scene.scene_number)
        .all()
    )

    clips = [
        {
            "cut_number": s.scene_number,
            "video_url": s.clip_video_url,
            "image_url": s.draft_image_url,
            "video_status": s.video_status,
        }
        for s in db_scenes
    ]

    ready_clips = [c for c in clips if c["video_url"]]
    if not ready_clips:
        raise HTTPException(
            status_code=400,
            detail="생성된 영상 클립이 없습니다. /api/video/generate-all을 먼저 호출하세요.",
        )

    project.final_video_url = json.dumps([c["video_url"] for c in ready_clips], ensure_ascii=False)
    project.current_stage = "finalized"
    db.commit()

    return {
        "project_id": project_id,
        "total_clips": len(clips),
        "ready_clips": len(ready_clips),
        "clips": clips,
        "clip_urls": [c["video_url"] for c in ready_clips],
    }
