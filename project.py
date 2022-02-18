from pydantic import BaseModel
from pathlib import Path
from typing import List
import math

from .cpt import CPT
from .soiltype import SoilType
from .location import Location
from .soilinvestigation import SoilInvestigation, SoilInvestigationEnum

class Project(BaseModel):
    soiltypes: List[SoilType] = []
    locations: List[Location] = []
    soilinvestigations: List[SoilInvestigation] = []

    @property
    def has_locations(self):
        return len(self.locations) > 0

    @property
    def cpts(self):
        return [si for si in self.soilinvestigations if si.stype == SoilInvestigationEnum.CPT]

    @property
    def boreholes(self):
        return [si for si in self.soilinvestigations if si.stype == SoilInvestigationEnum.BOREHOLE]

    def get_closest(self, x_rd: float, y_rd: float, max_distance=1e9, num=4):
        locs = [(math.hypot(si.x_rd - x_rd, si.y_rd - y_rd), si) for si in self.soilinvestigations]
        locs = [l for l in locs if l[0] < max_distance]
        return sorted(locs, key=lambda x:x[0])[:num]
    
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

    def export_to_dam(self, filename: str):
        f = open(filename, 'w')
        f.write("soilprofile_id;top_level;soil_name\n")
        for location in self.locations:
            if len(location.soillayers) == 0:
                continue
            for i, soillayer in enumerate(location.soillayers):
                if i==0:
                    z = 10.0
                else:
                    z = soillayer.z_top
                f.write(f"{location.name};{z:.2f};{soillayer.soilcode}\n")
        f.close()

