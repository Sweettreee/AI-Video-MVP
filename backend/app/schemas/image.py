from pydantic import BaseModel


class ImageRequest(BaseModel):
    scene_id: int
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
    scene_id: int
    modified_prompt: str
