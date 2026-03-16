import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_prompt = Column(Text, nullable=False)
    genre = Column(String, nullable=False)
    art_style = Column(String, nullable=False)
    status = Column(String, default="draft")
    progress = Column(Integer, default=0)
    current_stage = Column(String, nullable=True)
    final_video_url = Column(Text, nullable=True)
    
    # 시간 저장
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at = Column(DateTime, nullable=True)

    # 연결된 씬(Cut)들을 가져오기 위한 관계 설정
    scenes = relationship("Scene", back_populates="project")


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"))
    scene_number = Column(Integer, nullable=False)
    
    # 세부 컷 정보 (명세서에 따라 JSON 문자열로 저장)
    scene_data = Column(Text, nullable=False) 
    
    # AI 생성 관련 데이터
    generated_image_prompt = Column(Text, nullable=True)
    draft_image_url = Column(Text, nullable=True)
    veo2_prompt = Column(Text, nullable=True)
    clip_video_url = Column(Text, nullable=True)
    
    image_status = Column(String, default="pending")
    video_status = Column(String, default="pending")

    # 연결된 프로젝트 정보를 가져오기 위한 관계 설정
    project = relationship("Project", back_populates="scenes")