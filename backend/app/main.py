from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import plot, image, video
from app.db.database import engine, _migrate
from app.db import models

# DB 테이블 자동 생성 + 누락 컬럼 마이그레이션
models.Base.metadata.create_all(bind=engine)
_migrate(engine)

app = FastAPI(
    title="AI 2차 창작 영상 제작 서비스",
    description="팬 콘텐츠 스토리보드 생성 → 이미지 → 영상 파이프라인",
    version="0.1.0",
)

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 연결
app.include_router(plot.router, prefix="/api/plot", tags=["Plot Generation"])
app.include_router(image.router, prefix="/api/image", tags=["Image Generation"])
app.include_router(video.router, prefix="/api/video", tags=["Video Generation"])


@app.get("/")
def root():
    return {"message": "AI 2차 창작 영상 제작 서비스 API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
