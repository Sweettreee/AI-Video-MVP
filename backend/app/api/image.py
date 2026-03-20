from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.schemas.image import ImageRequest, ImageModifyRequest
from backend.app.services.image import backend_compose_prompt, generate_image_from_hf, upload_to_cloudinary

# 라우터 객체 생성
router = APIRouter()

@router.post("")
def generate_scene_image(req: ImageRequest, db: Session = Depends(get_db)):
    """1. 최초 이미지 생성 API"""
    try:
        final_prompt = backend_compose_prompt(req)
        print("\n⏳ [최초 생성] Hugging Face 모델로 이미지 생성 시작...")
        
        generated_image_bytes = generate_image_from_hf(final_prompt)
        real_image_url = upload_to_cloudinary(generated_image_bytes)
        
        scene = db.query(models.Scene).filter(models.Scene.id == req.scene_id).first()
        if scene:
            scene.generated_image_prompt = final_prompt
            scene.draft_image_url = real_image_url
            scene.image_status = "done"
            db.commit()
            db.refresh(scene)

        return {
            "scene_id": req.scene_id,
            "generated_image_prompt": final_prompt,
            "image_url": real_image_url,
            "image_status": "done"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 생성 실패: {str(e)}")

@router.post("/modify")
def modify_scene_image(req: ImageModifyRequest, db: Session = Depends(get_db)):
    """2. 이미지 수정(재생성) API"""
    try:
        print(f"\n⏳ [수정 반영] 씬({req.scene_id}) 이미지를 재생성합니다...")
        
        generated_image_bytes = generate_image_from_hf(req.modified_prompt)
        new_image_url = upload_to_cloudinary(generated_image_bytes)
        
        scene = db.query(models.Scene).filter(models.Scene.id == req.scene_id).first()
        if scene:
            scene.generated_image_prompt = req.modified_prompt
            scene.draft_image_url = new_image_url
            scene.image_status = "modified"
            db.commit()
            db.refresh(scene)
            print(f"✅ DB 업데이트 완료: 씬({req.scene_id}) 이미지 수정 반영")

        return {
            "message": "이미지가 성공적으로 수정되었습니다.",
            "scene_id": req.scene_id,
            "updated_prompt": req.modified_prompt,
            "new_image_url": new_image_url,
            "image_status": "modified"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 수정 실패: {str(e)}")