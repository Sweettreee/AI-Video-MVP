import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.app.db.database import Base

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    genre: Mapped[str] = mapped_column(String, nullable=False)
    art_style: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    final_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 유저 원본 입력 (가이드 질문 답변, JSON)
    answers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 현재 plain text 스토리보드
    plain_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # GlobalContext (캐릭터 시트 + 화풍 + 색감, JSON)
    global_context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Human Eval 결과 (H1~H3 + 피드백, JSON)
    human_eval_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 연속 평가 실패 횟수 (무한루프 방지)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)

    # 시간 저장
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 연결된 씬(Cut)들을 가져오기 위한 관계 설정
    scenes: Mapped[list["Scene"]] = relationship("Scene", back_populates="project", cascade="all, delete-orphan")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"))
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # 세부 컷 정보 (명세서에 따라 JSON 문자열로 저장)
    scene_data: Mapped[str] = mapped_column(Text, nullable=False)

    # AI 생성 관련 데이터
    generated_image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    veo2_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    clip_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    image_status: Mapped[str] = mapped_column(String, default="pending")
    video_status: Mapped[str] = mapped_column(String, default="pending")

    # 연결된 프로젝트 정보를 가져오기 위한 관계 설정
    project: Mapped["Project"] = relationship("Project", back_populates="scenes")
