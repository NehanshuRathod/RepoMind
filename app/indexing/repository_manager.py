import shutil
import uuid
import zipfile
from pathlib import Path
from git import Repo
import tempfile

BASE_TEMP = Path(tempfile.gettempdir()) / "repomind"
BASE_TEMP.mkdir(parents=True, exist_ok=True)


class RepositoryManager:

    def _create_workspace(self) -> Path:
        folder = BASE_TEMP / str(uuid.uuid4())
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    #GitHub clone
    def clone_repo(self, repo_url: str) -> Path:
        workspace = self._create_workspace()
        Repo.clone_from(repo_url, workspace)
        return workspace

    #Zip extract
    def extract_zip(self, zip_path: Path) -> Path:
        workspace = self._create_workspace()

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(workspace)

        return workspace

    # cleanup (good practice later)
    def cleanup(self, path: Path):
        shutil.rmtree(path, ignore_errors=True)
