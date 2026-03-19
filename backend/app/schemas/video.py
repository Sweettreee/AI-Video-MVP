from pydantic import BaseModel

class VideoGenerateRequest(BaseModel):
    """비디오 생성 시 프론트엔드가 보내는 데이터 (이제 ID만 받음!)"""
    scene_id: str