import json
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# DB 및 라우터 모듈 임포트
from app.db import models
from app.db.database import engine, get_db
from app.api.image import router as image_router
from app.api.video import router as video_router 

# 서버 실행 전, 테이블이 없으면 생성
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ESTAID Hackathon MVP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 조립
app.include_router(image_router, prefix="/api/image", tags=["Image Creation"])
app.include_router(video_router, prefix="/api/video", tags=["Video Creation"])

@app.get("/")
def read_root():
    return {
        "message": "ESTAID 해커톤 API 서버 (이미지 + 비디오) 정상 작동 중! 🚀",
        "tip": "브라우저 주소창 끝에 /docs 를 붙여 테스트하세요."
    }

# 👇 [추가] 개발 및 테스트용 더미 데이터 생성 API
@app.post("/api/dev/dummy", tags=["Development Tools"])
def create_dummy_data(db: Session = Depends(get_db)):
    """이미지 생성 테스트를 위해 가짜 프로젝트와 씬(test-cut-004)을 DB에 강제로 생성합니다."""
    # 이미 존재하는지 확인 (중복 에러 방지)
    existing_scene = db.query(models.Scene).filter(models.Scene.id == "test-cut-004").first()
    if existing_scene:
        return {"message": "이미 test-cut-004 데이터가 DB에 존재합니다. 바로 테스트를 진행하세요!"}

    try: 
        # 1. 가짜 프로젝트 생성
        project = models.Project(
            id="test-project-004",
            user_prompt="열정적인 콘서트 오프닝 씬",
            genre="Music/Drama",
            art_style="realistic concert photography"
        )
        db.add(project)
        
        # 2. 가짜 씬 생성 (팀원이 컷을 분류만 해두고 아직 이미지는 안 만든 상태)
        scene = models.Scene(
            id="test-cut-004",
            project_id="test-project-004",
            scene_number=1,
            scene_data='{"original_korean_prompt": "[Cut 1] 캐릭터: 검은 가죽 재킷을 입은 20대 남성, 젖은 흑발이 이마에 붙어있음..."}', 
            generated_image_prompt=None, # 👈 이미지 생성 전이라 비워둠
            draft_image_url=None, # 👈 이미지 생성 전이라 비워둠
            image_status="pending" # 👈 대기 상태
        )
        db.add(scene)
        
        db.commit()
        return {"message": "✅ 더미 데이터(test-cut-004)가 DB에 성공적으로 생성되었습니다! 이제 /api/image 에 JSON을 넣어 테스트해보세요."}
    except Exception as e:
        db.rollback()
        return {"error": f"더미 데이터 생성 실패: {str(e)}"}