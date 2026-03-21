import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.app.db import models
from backend.app.db.database import get_db, SessionLocal
from backend.app.schemas.image import (
    ImageRequest,
    ImageModifyRequest,
    ImageGenerateAllRequest,
    ImageModifyByTextRequest,
)
from backend.app.api.deps import load_project, load_global_context, load_scenes_from_db
from backend.app.schemas.scene import Scene
from backend.app.services.image import (
    generate_image_from_hf,
    upload_to_cloudinary,
)
from backend.app.services.character_sheet import compose_cut_prompt, extract_global_context
from backend.app.services.plot_generator import generate_plot, GenerationError
from backend.app.services.plot_evaluator import focused_eval
from backend.app.services.plot_converter import (
    parse_storyboard,
    scenes_to_plain_text,
    diff_scenes,
    ParseError,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── POST /api/image (단건 이미지 생성) ──────────────────────

@router.post("")
def generate_scene_image(req: ImageRequest, db: Session = Depends(get_db)):
    """단건 이미지 생성. GlobalContext 기반 compose_cut_prompt 사용."""
    db_scene = db.query(models.Scene).filter(
        models.Scene.id == req.scene_id
    ).first()
    if not db_scene:
        raise HTTPException(
            status_code=404, detail=f"Scene({req.scene_id})을 찾을 수 없습니다."
        )

    project = load_project(db_scene.project_id, db)
    global_ctx = load_global_context(project)
    scene = Scene.model_validate_json(db_scene.scene_data)
    final_prompt = compose_cut_prompt(global_ctx, scene)

    # W7: generating 상태 먼저 마킹
    db_scene.image_status = "generating"
    db.commit()

    try:
        generated_image_bytes = generate_image_from_hf(final_prompt)
        real_image_url = upload_to_cloudinary(generated_image_bytes)
    except Exception as e:
        db_scene.image_status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"이미지 생성 실패: {str(e)}")

    db_scene.generated_image_prompt = final_prompt
    db_scene.draft_image_url = real_image_url
    db_scene.image_status = "done"
    db.commit()

    return {
        "scene_id": req.scene_id,
        "generated_image_prompt": final_prompt,
        "image_url": real_image_url,
        "image_status": "done",
    }


# ── BackgroundTask: 이미지 일괄 생성 ─────────────────────────

async def _bg_generate_all_images(
    project_id: str,
    scene_tasks: list[tuple[str, int, str]],  # (scene_id, cut_number, prompt)
) -> None:
    """백그라운드에서 이미지 일괄 생성. 자체 DB 세션 사용."""
    db = SessionLocal()
    try:
        loop = asyncio.get_running_loop()
        sem = asyncio.Semaphore(3)

        async def _generate_one(scene_id: str, cut_number: int, prompt: str):
            async with sem:
                try:
                    image_bytes = await loop.run_in_executor(None, generate_image_from_hf, prompt)
                    image_url = await loop.run_in_executor(None, upload_to_cloudinary, image_bytes)
                    return scene_id, cut_number, prompt, image_url, None
                except Exception as e:
                    return scene_id, cut_number, prompt, None, str(e)

        task_results = await asyncio.gather(
            *[_generate_one(sid, cn, p) for sid, cn, p in scene_tasks]
        )

        db_scene_map = {
            s.id: s for s in db.query(models.Scene)
            .filter(models.Scene.project_id == project_id).all()
        }

        has_success = False
        for scene_id, cut_number, prompt, image_url, error in task_results:
            db_scene = db_scene_map.get(scene_id)
            if not db_scene:
                continue
            if error:
                db_scene.image_status = "failed"
                logger.error(f"Cut {cut_number} 이미지 생성 실패: {error}")
            else:
                db_scene.generated_image_prompt = prompt
                db_scene.draft_image_url = image_url
                db_scene.image_status = "done"
                has_success = True

        if has_success:
            project = db.query(models.Project).filter(
                models.Project.id == project_id
            ).first()
            if project:
                project.current_stage = "images_generated"

        db.commit()

    except Exception as e:
        logger.error(f"백그라운드 이미지 생성 에러 (project={project_id}): {e}")
        # generating 상태로 멈춘 씬 모두 failed 처리
        db.query(models.Scene).filter(
            models.Scene.project_id == project_id,
            models.Scene.image_status == "generating",
        ).update({"image_status": "failed"})
        db.commit()
    finally:
        db.close()


# ── POST /api/image/generate-all (전체 컷 일괄 생성) ─────────

@router.post("/generate-all")
async def generate_all_images(
    req: ImageGenerateAllRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """프로젝트의 모든 Scene에 대해 GlobalContext 기반 이미지 일괄 생성.

    C4: 즉시 반환, 실제 생성은 BackgroundTasks에서 수행.
    W7: 즉시 "generating" 상태 마킹 → 폴링이 즉시 진행 상황 확인 가능.
    폴링: GET /api/image/{project_id}/scenes
    """
    project = load_project(req.project_id, db)
    global_ctx = load_global_context(project)

    db_scenes = (
        db.query(models.Scene)
        .filter(models.Scene.project_id == req.project_id)
        .order_by(models.Scene.scene_number)
        .all()
    )
    if not db_scenes:
        raise HTTPException(
            status_code=400,
            detail="확정된 Scene이 없습니다. /api/plot/confirm을 먼저 호출하세요.",
        )

    # ORM 데이터 미리 추출 + generating 상태 마킹
    scene_tasks = []
    for db_scene in db_scenes:
        scene = Scene.model_validate_json(db_scene.scene_data)
        prompt = compose_cut_prompt(global_ctx, scene)
        db_scene.image_status = "generating"
        scene_tasks.append((db_scene.id, scene.cut_number, prompt))

    db.commit()

    background_tasks.add_task(_bg_generate_all_images, req.project_id, scene_tasks)

    return {"project_id": req.project_id, "images": []}


# ── POST /api/image/modify (단건 프롬프트 수정) ──────────────

@router.post("/modify")
def modify_scene_image(req: ImageModifyRequest, db: Session = Depends(get_db)):
    """단건 이미지 수정 (프론트엔드에서 프롬프트 직접 지정)."""
    scene = db.query(models.Scene).filter(
        models.Scene.id == req.scene_id
    ).first()
    if not scene:
        raise HTTPException(
            status_code=404, detail=f"Scene({req.scene_id})을 찾을 수 없습니다."
        )

    try:
        generated_image_bytes = generate_image_from_hf(req.modified_prompt)
        new_image_url = upload_to_cloudinary(generated_image_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 수정 실패: {str(e)}")

    scene.generated_image_prompt = req.modified_prompt
    scene.draft_image_url = new_image_url
    scene.image_status = "modified"
    db.commit()

    return {
        "scene_id": req.scene_id,
        "updated_prompt": req.modified_prompt,
        "new_image_url": new_image_url,
        "image_status": "modified",
    }


# ── POST /api/image/modify-by-text (텍스트 수정 → diff → focused_eval → 재생성) ─

@router.post("/modify-by-text")
def modify_by_text(req: ImageModifyByTextRequest, db: Session = Depends(get_db)):
    """유저 텍스트 수정 요청 → 스토리보드 수정 → diff → focused_eval → 변경 컷만 재생성."""
    project = load_project(req.project_id, db)

    if not project.plain_text or not project.answers_json:
        raise HTTPException(status_code=400, detail="스토리보드가 없습니다.")

    answers = json.loads(project.answers_json)
    old_scenes = load_scenes_from_db(req.project_id, db)

    # 1. 스토리보드 수정
    old_plain = scenes_to_plain_text(old_scenes)
    try:
        new_plain = generate_plot(
            answers=answers,
            previous_storyboard=old_plain,
            modification_request=req.modification_request,
        )
    except GenerationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 2. 새 Scene 파싱
    try:
        new_scenes = parse_storyboard(new_plain)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 3. diff
    changed_cuts = diff_scenes(old_scenes, new_scenes)

    # C1: eval_passed 필드 항상 포함
    if not changed_cuts:
        return {
            "project_id": req.project_id,
            "changed_cuts": [],
            "eval_passed": True,
            "eval_result": {"total_average": None},
            "message": "변경된 컷이 없습니다.",
            "images": [],
        }

    # 4. focused_eval
    eval_result = focused_eval(changed_cuts, new_plain, previous_total=None)

    if not eval_result.passed:
        return {
            "project_id": req.project_id,
            "changed_cuts": changed_cuts,
            "eval_passed": False,
            "eval_result": {
                "total_average": eval_result.total_average,
                "failed_items": eval_result.failed_items,
                "code_scores": eval_result.code_scores,
                "model_scores": eval_result.model_scores,
            },
            "message": "수정된 스토리보드가 평가를 통과하지 못했습니다.",
        }

    # 5. W10: GlobalContext 재생성 (캐릭터/화풍 변경 반영)
    try:
        new_global_ctx = extract_global_context(answers, new_scenes)
        project.global_context_json = new_global_ctx.model_dump_json()
        global_ctx = new_global_ctx
    except Exception:
        global_ctx = load_global_context(project)  # 실패 시 기존 컨텍스트 사용

    # 6. DB 업데이트 — 기존 이미지 정보 보존 후 scenes 교체
    old_db_scenes = (
        db.query(models.Scene)
        .filter(models.Scene.project_id == req.project_id)
        .order_by(models.Scene.scene_number)
        .all()
    )
    old_image_map = {
        s.scene_number: {
            "prompt": s.generated_image_prompt,
            "url": s.draft_image_url,
            "status": s.image_status,
        }
        for s in old_db_scenes
    }

    project.plain_text = new_plain
    db.query(models.Scene).filter(
        models.Scene.project_id == req.project_id
    ).delete()

    db_scenes_new = []
    for scene in new_scenes:
        db_scene = models.Scene(
            project_id=req.project_id,
            scene_number=scene.cut_number,
            scene_data=scene.model_dump_json(),
        )
        db.add(db_scene)
        db_scenes_new.append(db_scene)

    db.flush()

    # 7. 변경된 컷만 이미지 재생성
    results = []
    for db_scene, scene in zip(db_scenes_new, new_scenes):
        if scene.cut_number not in changed_cuts:
            old_info = old_image_map.get(scene.cut_number, {})
            db_scene.generated_image_prompt = old_info.get("prompt")
            db_scene.draft_image_url = old_info.get("url")
            db_scene.image_status = old_info.get("status", "pending")
            # W2: "unchanged" → "done" 으로 정규화 (프론트엔드 union 타입 호환)
            results.append({
                "cut_number": scene.cut_number,
                "image_url": old_info.get("url"),
                "image_status": "done",
            })
            continue

        prompt = compose_cut_prompt(global_ctx, scene)
        try:
            image_bytes = generate_image_from_hf(prompt)
            image_url = upload_to_cloudinary(image_bytes)
        except Exception as e:
            results.append({
                "cut_number": scene.cut_number,
                "image_status": "failed",
                "error": str(e),
            })
            continue

        db_scene.generated_image_prompt = prompt
        db_scene.draft_image_url = image_url
        # W1: "regenerated" → "modified" 으로 정규화 (프론트엔드 union 타입 호환)
        db_scene.image_status = "modified"
        results.append({
            "cut_number": scene.cut_number,
            "image_url": image_url,
            "image_status": "modified",
        })

    project.current_stage = "images_modified"
    db.commit()

    return {
        "project_id": req.project_id,
        "changed_cuts": changed_cuts,
        "eval_passed": True,
        "eval_result": {
            "total_average": eval_result.total_average,
        },
        "images": results,
    }


# ── GET /api/image/{project_id}/scenes ────────────────────

@router.get("/{project_id}/scenes")
def get_image_scenes(project_id: str, db: Session = Depends(get_db)):
    """프로젝트의 모든 Scene 이미지 상태 조회."""
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
                "image_status": s.image_status,
                "prompt": s.generated_image_prompt,
            }
            for s in db_scenes
        ],
    }
