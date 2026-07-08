from pathlib import Path


ALLOWED_EXTENSIONS = {
    ".py",
    ".java",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
}

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".mypy_cache",
    ".pytest_cache",
}


class FileFilter:
    def filter(self, files: list[Path]) -> list[Path]:
        result: list[Path] = []
        for file_path in files:
            if any(part in IGNORE_DIRS for part in file_path.parts):
                continue
            if file_path.suffix.lower() in ALLOWED_EXTENSIONS:
                result.append(file_path)
        return result
