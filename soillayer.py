from pydantic import BaseModel

class SoilLayer(BaseModel):
    z_top: float
    z_bottom: float
    soilcode: str

    @property
    def height(self):
        return self.z_top - self.z_bottom

    @property 
    def short_soilcode(self) -> str:
        if self.soilcode.find('_') > - 1:
            return self.soilcode.split('_')[0]
        else:
            return self.soilcode