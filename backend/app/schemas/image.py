from pydantic import BaseModel


class ImageRequest(BaseModel):
    art_style: str
    main_character: str
    action: str
    pose: str
    background: str
    era: str
    composition: str
    lighting: str
    mood: str
