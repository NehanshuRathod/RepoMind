from pathlib import Path
from typing import List

class FileLoader:
    def load_files(self,repo_path:Path)->List[Path]:
        return [p for p in repo_path.rglob("*") if p.is_file()]
    