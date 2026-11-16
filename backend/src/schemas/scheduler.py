from pydantic import BaseModel, Field
class LimitInput(BaseModel):
    max_concurrent: int = Field(ge=1, le=8)
