from pydantic import BaseModel
from enum import IntEnum


class SoilInvestigationEnum(IntEnum):
    NONE = 0
    CPT = 1
    BOREHOLE = 2

class SoilInvestigation(BaseModel):
    stype: SoilInvestigationEnum = SoilInvestigationEnum.NONE
    filename: str
    x_rd: float
    y_rd: float

    @classmethod 
    def from_file(obj, filename) -> 'SoilInvestigation':
        try:
            lines = open(filename, 'r', encoding="latin-1").readlines()
            for line in lines:
                if line.find('#XYID') > -1:
                    args = [s.strip() for s in line.split(',')]
                    x_rd = float(args[1])
                    y_rd = float(args[2])
                    return SoilInvestigation(
                        filename = str(filename),
                        x_rd = x_rd,
                        y_rd = y_rd
                    )
        except Exception as e:
            print(f"Error reading {filename}, '{e}'")
            return None

        print(f"Could not find #XYID in '{filename}'")
        return None


