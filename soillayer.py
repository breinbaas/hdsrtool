from pydantic import BaseModel

class SoilLayer(BaseModel):
    z_top: float
    z_bottom: float
    soilcode: str

    @property
    def height(self):
        return self.z_top - self.z_bottom