from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# DB 및 라우터 모듈 임포트
from app.db import models
from app.db.database import engine
from app.api.image import router as image_router

# 서버 실행 전, 테이블이 없으면 생성
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ESTAID Hackathon MVP API (Refactored)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 조립 (app/api/image.py의 라우터들을 /api/image 주소로 묶어줍니다)
app.include_router(image_router, prefix="/api/image", tags=["Image Creation"])

@app.get("/")
def read_root():
    return {
        "message": "ESTAID 해커톤 API 서버 정상 작동 중! 🚀 (구조화 완료)",
        "tip": "브라우저 주소창 끝에 /docs 를 붙여 테스트하세요."
    }