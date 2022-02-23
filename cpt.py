from pydantic import BaseModel
from typing import List
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches
from matplotlib.ticker import MultipleLocator
import math

from enum import IntEnum

from pydantic.utils import KeyType

GEF_COLUMN_Z = 1
GEF_COLUMN_QC = 2
GEF_COLUMN_FS = 3
GEF_COLUMN_U = 6
GEF_COLUMN_Z_CORRECTED = 11

class CPT(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z_top: float = 0.0

    z: List[float] = []
    qc: List[float] = []
    fs: List[float] = []
    u: List[float] = []
    Rf: List[float] = []

    name: str = ""
    
    filedate: str = ""
    startdate: str = ""

    filename: str = ""

    pre_excavated_depth: float = 0.0

    @classmethod
    def from_file(self, filename: str) -> 'CPT':
        cpt = CPT()
        cpt.read(filename)
        return cpt

    @property
    def date(self) -> str:
        """Return the date of the CPT in the following order (if available) startdate, filedata, empty string (no date)

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
        Return the lowest point of the CPT

        Args:
            None

        Returns:
            float: deepest point in CPT
        """
        return self.z[-1]

    @property 
    def has_u(self) -> bool:
        """
        Does this CPT has waterpressure

        Args:
            None

        Return:
            bool: true is CPT has waterpressure readings, false otherwise
        """
        return max(self.u) > 0 or min(self.u) < 0

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
            "columnvoids":{}, 
            "columninfo":{}
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
    
    def _read_gef(self, filename: str) -> None:
        """
        Read a GEF file

        Args:
            filename (str): the name of the file to be read

        Returns:
            None
        """
        lines = open(filename, "r", encoding="utf-8", errors="ignore").readlines()

        self.read_from_gef_stringlist(lines)
  
    def _parse_header_line(self, line: str, metadata: dict) -> None:
        try:
            args = line.split("=")
            keyword, argline = args[0], args[1]
        except Exception as e:
            raise ValueError(f"Error reading headerline '{line}' -> error {e}")

        keyword = keyword.strip().replace("#", "")
        argline = argline.strip()
        args = argline.split(",")

        if keyword == "RECORDSEPARATOR":
            metadata["record_seperator"] = args[0]
        elif keyword == "COLUMNSEPARATOR":
            metadata["column_seperator"] = args[0]
        elif keyword == "COLUMNINFO":
            try:
                column = int(args[0])
                dtype = int(args[3].strip())
                if dtype == GEF_COLUMN_Z_CORRECTED:
                    dtype = GEF_COLUMN_Z # use corrected depth instead of depth                
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
                self.z_top = float(args[1].strip())
            except Exception as e:
                raise ValueError(f"Error reading zid '{line}' -> error {e}")     
        elif keyword == "MEASUREMENTVAR":
            if args[0] == '13':
                try:
                    self.pre_excavated_depth = float(args[1])
                except Exception as e:
                    raise ValueError(f"Invalid pre-excavated depth found in line '{line}'. Got error '{e}'")        
        elif keyword == "COLUMNVOID":
            try:
                col = int(args[0].strip())
                metadata["columnvoids"][col - 1] = float(args[1].strip())
            except Exception as e:
                raise ValueError(f"Error reading columnvoid '{line}' -> error {e}")  
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
            if len(line.strip())==0: return
            args = line.replace(metadata["record_seperator"], '').strip().split(metadata["column_seperator"])
            args = [float(arg.strip()) for arg in args if len(arg.strip()) > 0 and arg.strip() != metadata["record_seperator"]]
            
            # skip lines that have a columnvoid
            for col_index, voidvalue in metadata["columnvoids"].items():
                if args[col_index] == voidvalue:
                    return  

            zcolumn = metadata["columninfo"][GEF_COLUMN_Z]
            qccolumn = metadata["columninfo"][GEF_COLUMN_QC]
            fscolumn = metadata["columninfo"][GEF_COLUMN_FS]

            ucolumn = -1
            if GEF_COLUMN_U in metadata["columninfo"].keys():
                ucolumn = metadata["columninfo"][GEF_COLUMN_U]

            dz = self.z_top - abs(args[zcolumn])            
            self.z.append(dz)

            qc = args[qccolumn]
            if qc <= 0:
                qc = 1e-3
            self.qc.append(qc)
            fs = args[fscolumn]
            if fs <= 0:
                fs = 1e-6
            self.fs.append(fs)

            if fs > 0:
                rf = (fs / qc) * 100.0
            else:
                rf = 10.0
            self.Rf.append(rf)

            if ucolumn > -1:
                self.u.append(args[ucolumn])
            else:
                self.u.append(0.0)

        except Exception as e:
            raise ValueError(f"Error reading dataline '{line}' -> error {e}") 

    def as_numpy(self) -> np.array:
        """
        Return the CPT data as a numpy array with;
        
        col     value
        0       z
        1       qc
        2       fs
        3       Rf
        4       u

        Args:
            None

        Returns:
            np.array: the CPT data as a numpy array"""
        return np.transpose(np.array([self.z, self.qc, self.fs, self.Rf, self.u]))
    
    def as_dataframe(self) -> pd.DataFrame:
        """
        Return the CPT data as a dataframe with columns;        
        z, qc, fs, Rf, u

        Args:
            None

        Returns:
            pd.DataFrame: the CPT data as a DataFrame"""
        data = self.as_numpy()
        return pd.DataFrame(data=data, columns=["z", "qc", "fs", "Rf", "u"])