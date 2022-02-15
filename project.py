from pydantic import BaseModel
from pathlib import Path
from typing import List

from .soiltype import SoilType
from .location import Location

class Project(BaseModel):
    soiltypes: List[SoilType] = []
    locations: List[Location] = []



    @property
    def has_locations(self):
        return len(self.locations) > 0

    def reset(self):
        self.locations = []
    
    def soiltypes_from_csvstring(self, s: str):
        lines = [l for l in s.split('\n') if len(l)>0]
        for line in lines:
            args = [a.strip() for a in line.split(',')]
            self.soiltypes.append(SoilType(
                name = args[0] ,
                color = args[1]
            ))

    def locations_from_csvfile(self, filename: str):
        if Path(filename).exists():
            lines = open(filename, 'r').readlines()

            for line in lines[1:]:
                args = [s.strip() for s in line.split(',')]
                try:
                    self.locations.append(Location(
                        name = args[0],
                        x_rd = float(args[1]),
                        y_rd = float(args[2])
                    ))
                except: # log errors to the Python console in QGis
                    print(f"Could not read location from line '{line}'")


