from pydantic import BaseModel

class SoilType(BaseModel):
    name: str
    color: str