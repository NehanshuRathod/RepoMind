from pathlib import Path
from typing import List


ALLOWED_EXTENSIONS = {
    ".py", ".java", ".js", ".ts", ".cpp", ".c", ".go", ".rs"
}

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", "dist", "build"
}


class FileFilter:
    def filter(self, files: List[Path]) -> List[Path]:
        result = []

        for f in files:
            if any(part in IGNORE_DIRS for part in f.parts):
                continue

            if f.suffix.lower() in ALLOWED_EXTENSIONS:
                result.append(f)

        return result
