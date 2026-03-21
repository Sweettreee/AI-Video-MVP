from pydantic import BaseModel


class ImageRequest(BaseModel):
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
    scene_id: str
    modified_prompt: str


class ImageGenerateAllRequest(BaseModel):
    project_id: str


class ImageModifyByTextRequest(BaseModel):
    project_id: str
    modification_request: str
