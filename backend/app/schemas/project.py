from pydantic import BaseModel


class PlotRequest(BaseModel):
    genre: str
    character: str
    mood: str
    story: str
    must_have: str | None = None
    extra: str | None = None
