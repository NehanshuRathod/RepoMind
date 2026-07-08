import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from git import Repo


BASE_TEMP = Path(tempfile.gettempdir()) / "repomind"
BASE_TEMP.mkdir(parents=True, exist_ok=True)


class RepositoryManager:
    def _create_workspace(self) -> Path:
        folder = BASE_TEMP / str(uuid.uuid4())
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def clone_repo(self, repo_url: str) -> Path:
        workspace = self._create_workspace()
        Repo.clone_from(repo_url, workspace)
        return workspace

    def get_commit_hash(self, repo_path: Path) -> str | None:
        try:
            repo = Repo(repo_path)
            return repo.head.commit.hexsha
        except Exception:
            return None

    def extract_zip(self, zip_path: Path) -> Path:
        workspace = self._create_workspace()
        workspace_root = workspace.resolve()

        with zipfile.ZipFile(zip_path, "r") as archive:
            for member in archive.infolist():
                target = (workspace / member.filename).resolve()
                if workspace_root not in target.parents and target != workspace_root:
                    raise ValueError(f"Unsafe ZIP member path: {member.filename}")
            archive.extractall(workspace)

        return workspace

    def cleanup(self, path: Path) -> None:
        shutil.rmtree(path, ignore_errors=True)
