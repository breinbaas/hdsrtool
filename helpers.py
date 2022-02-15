from typing import List
from pathlib import Path

def case_insensitive_glob(filepath: str, fileextension: str) -> List[Path]:
    p = Path(filepath)
    result = []
    for filename in p.glob('**/*'):
        if str(filename.suffix).lower() == fileextension.lower():
            result.append(filename.absolute())
    return result