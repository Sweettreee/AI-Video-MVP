from pydantic import BaseModel

class ImageRequest(BaseModel):
    """최초 이미지 생성 시 프론트엔드가 보내는 데이터"""
    scene_id: str
    art_style: str
    main_character: str
    action: str
    pose: str
    background: str
    era: str
    composition: str
    lighting: str
    mood: str

class ImageModifyRequest(BaseModel):
    """수정 요청 시 프론트엔드가 보내는 수정된 전체 프롬프트 데이터"""
    scene_id: str
    modified_prompt: str