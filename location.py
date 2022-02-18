from pydantic import BaseModel
from typing import List
from .soillayer import SoilLayer

class Location(BaseModel):
    name: str
    x_rd: float
    y_rd: float

    soillayers: List[SoilLayer] = []
