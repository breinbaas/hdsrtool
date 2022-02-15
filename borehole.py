from pydantic import BaseModel
from typing import List
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches

from .soillayer import SoilLayer

GEF_COLUMN_TOP = 1
GEF_COLUMN_BOTTOM = 2

class Borehole(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z_top: float = 0.0
    
    soillayers: List[SoilLayer] = []
    
    name: str = ""
    filedate: str = ""
    startdate: str = ""

    filename: str = ""

    @classmethod
    def from_file(self, filename: str) -> 'Borehole':
        borehole = Borehole()
        borehole.read(filename)        
        return borehole

    @property
    def date(self) -> str:
        """Return the date of the borehole in the following order (if available) startdate, filedata, empty string (no date)

        Args:
            None

        Returns:
            str: date in format YYYYMMDD"""
        if self.startdate != "":
            return self.startdate
        elif self.filedate != "":
            return self.filedate
        else:
            raise ValueError("This geffile has no date or invalid date information.")

    
    @property
    def length(self) -> float:
        return self.z_top - self.z_min    
    
    @property
    def z_min(self) -> float:
        """
        Return the lowest point of the borehole

        Args:
            None

        Returns:
            float: deepest point in borehole
        """
        if len(self.soillayers) > 0:
            return self.soillayers[-1].z_bottom

        raise ValueError("Trying to get z_min of a borehole with no soillayers")

    def read_from_gef_stringlist(self, lines: List[str]) -> None:
        """
        Read a GEF from the indivual lines

        Args:
            lines (List[str]): list of strings

        Returns:
            None
        """
        reading_header = True
        metadata = {
            "record_seperator":"",
            "column_seperator":" ",
            "columninfo":{},
            "last_column":2,
        }
        for line in lines:
            if reading_header:
                if line.find("#EOH") >= 0:
                    reading_header = False
                else:
                    self._parse_header_line(line, metadata)
            else:
                self._parse_data_line(line, metadata)

    def read(self, filename: str) -> None:
        self.filename = filename
        extension = Path(filename).suffix.lower()
        if extension == ".gef":
            self._read_gef(filename)            
        else:
            raise NotImplementedError(f"Unknown and unhandled file extension {extension}")
        self._merge_layers()
    
    def _read_gef(self, filename: str) -> None:
        """
        Read a GEF file

        Args:
            filename (str): the name of the file to be read

        Returns:
            None
        """
        lines = open(filename, "r", encoding="utf-8", errors="ignore").readlines()

        # remove empty lines
        lines = [line.strip() for line in lines if len(line.strip())>0]

        self.read_from_gef_stringlist(lines)

    def _parse_header_line(self, line: str, metadata: dict) -> None:
        try:
            keyword, argline = line.split("=")
        except Exception as e:
            raise ValueError(f"Error reading headerline '{line}' -> error {e}")

        keyword = keyword.strip().replace("#", "")
        argline = argline.strip()
        args = argline.split(",")

        if keyword == "RECORDSEPARATOR":
            metadata["record_seperator"] = args[0]
        elif keyword == "COLUMN":
            metadata["last_column"] = int(args[0])
        elif keyword == "COLUMNSEPARATOR":
            metadata["column_seperator"] = args[0]
        elif keyword == "COLUMNINFO":
            try:
                column = int(args[0])
                dtype = int(args[3].strip())
                metadata["columninfo"][dtype] = column - 1
            except Exception as e:
                raise ValueError(f"Error reading columninfo '{line}' -> error {e}")
        elif keyword == "XYID":
            try:
                self.x = round(float(args[1].strip()), 2)
                self.y = round(float(args[2].strip()), 2)
            except Exception as e:
                raise ValueError(f"Error reading xyid '{line}' -> error {e}")
        elif keyword == "ZID":
            try:
                assert len(args) == 3 # avoids a situation where #ZID= 0, -1,24, 0.01 leads to a z of -1 due to the erronous comma in 1,24 (should be 1.24)
                self.z_top = float(args[1].strip())
            except Exception as e:
                raise ValueError(f"Error reading zid '{line}' -> error {e}")     
        elif keyword == "TESTID":
            self.name = args[0].strip()    
        elif keyword == "FILEDATE":
            try:
                yyyy = int(args[0].strip())
                mm = int(args[1].strip())
                dd = int(args[2].strip())   

                if yyyy < 1900 or yyyy > 2100 or mm < 1 or mm > 12 or dd < 1 or dd > 31:
                    raise ValueError(f"Invalid date {yyyy}-{mm}-{dd}")            

                self.filedate = f"{yyyy}{mm:02}{dd:02}"
            except:                
                self.filedate = ""
        elif keyword == "STARTDATE":
            try:
                yyyy = int(args[0].strip())
                mm = int(args[1].strip())
                dd = int(args[2].strip())
                self.startdate = f"{yyyy}{mm:02}{dd:02}"
                if yyyy < 1900 or yyyy > 2100 or mm < 1 or mm > 12 or dd < 1 or dd > 31:
                    raise ValueError(f"Invalid date {yyyy}-{mm}-{dd}")
            except:                
                self.startdate = ""
        
    def _parse_data_line(self, line: str, metadata: dict) -> None:
        try:
            if len(line.strip()) == 0: return
            args = line.strip().split(metadata["column_seperator"])
            args = [arg.strip() for arg in args if len(arg.strip()) > 0 and arg.strip() != metadata["record_seperator"]]
            
            z_top_column = metadata["columninfo"][GEF_COLUMN_TOP]
            z_bottom_column = metadata["columninfo"][GEF_COLUMN_BOTTOM]
            soilcode_start_column = metadata["last_column"]

            z_top = float(args[z_top_column])
            z_bottom = float(args[z_bottom_column])

            if (z_bottom > z_top): # sometimes people use positive depth values from z_top in the GEF file.. annoying..
                z_top = self.z_top - z_top
                z_bottom = self.z_top - z_bottom
            
            # no columninfo for the text of the sample, expect all after column GEF_COLUMN_BOTTOM
            soilcode = "_".join(args[soilcode_start_column:]).replace('"','').replace("'", '')
            soilcode = soilcode.replace(" ", "_")

            self.soillayers.append(SoilLayer(
                z_bottom = round(z_bottom,2),
                z_top = round(z_top,2),
                soilcode = soilcode
            ))
        except Exception as e:
            raise ValueError(f"Error reading dataline '{line}' -> error {e}") 

    def _merge_layers(self) -> None:
        # merge layers with same name
        result = []
        for i in range(len(self.soillayers)):
            if i==0:
                result.append(self.soillayers[i])
            else:
                if self.soillayers[i].soilcode == result[-1].soilcode:
                    result[-1].z_bottom = self.soillayers[i].z_bottom
                else:
                    result.append(self.soillayers[i])
        self.soillayers = result