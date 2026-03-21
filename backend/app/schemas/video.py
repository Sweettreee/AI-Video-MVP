from pydantic import BaseModel


class VideoGenerateRequest(BaseModel):
    """단건 비디오 생성 (scene_id 지정)."""
    scene_id: str


class VideoGenerateAllRequest(BaseModel):
    """프로젝트 전체 비디오 일괄 생성."""
    project_id: str
