from pathlib import Path


class FileLoader:
    def load_files(self, repo_path: Path) -> list[Path]:
        return [p for p in repo_path.rglob("*") if p.is_file()]
