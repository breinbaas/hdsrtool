from pydantic import BaseModel

class Location(BaseModel):
    name: str
    x_rd: float
    y_rd: float