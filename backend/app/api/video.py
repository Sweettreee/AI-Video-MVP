from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.schemas.video import VideoGenerateRequest

# 👇 [수정됨] 새로 만든 fal 함수를 가져옵니다.
from app.service.video import generate_video_from_fal

router = APIRouter()

@router.post("")
def create_scene_video(req: VideoGenerateRequest, db: Session = Depends(get_db)):
    """3. DB에 저장된 최종 이미지와 프롬프트를 자동으로 가져와 비디오를 생성합니다."""
    try:
        # 1. DB에서 해당 씬 데이터 조회
        scene = db.query(models.Scene).filter(models.Scene.id == req.scene_id).first()
        
        if not scene:
            raise HTTPException(status_code=404, detail=f"Scene({req.scene_id})을 찾을 수 없습니다.")

        # 2. 필수 데이터(이미지 URL, 프롬프트)가 DB에 있는지 검사
        if not scene.draft_image_url or not scene.generated_image_prompt:
            raise HTTPException(
                status_code=400, 
                detail="아직 이미지가 생성되지 않은 씬입니다. 이미지를 먼저 생성해 주세요."
            )

        # 3. 비디오 생성 서비스 호출 (입력값이 아닌 DB에 저장된 값을 사용)
        print(f"🎬 DB에서 데이터를 가져와 영상을 생성합니다. (Scene ID: {req.scene_id})")
        
        # 👇 [수정됨] 구글 veo 함수 대신 fal 함수를 호출합니다!
        video_url = generate_video_from_fal(
            prompt=scene.generated_image_prompt, 
            image_url=scene.draft_image_url
        )
        
        # 4. 생성된 비디오 정보를 DB에 기록
        scene.veo2_prompt = scene.generated_image_prompt 
        scene.clip_video_url = video_url
        scene.video_status = "done"
        
        db.commit()
        db.refresh(scene)
        print(f"✅ 비디오 생성 및 DB 업데이트 완료")

        return {
            "scene_id": req.scene_id,
            "message": "비디오 생성이 성공적으로 완료되었습니다.",
            "video_url": video_url,
            "video_status": "done"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"비디오 생성 중 서버 에러 발생: {str(e)}")