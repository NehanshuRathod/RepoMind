import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_owned_project
from app.api.schemas import ProjectCreate, ProjectRead
from app.core.config import settings
from app.core.database import get_db
from app.metadata.db_models import Project, User
from app.services.indexing_service import IndexingService
from app.services.project_service import ProjectService


router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ProjectService(db)
    project = service.create_project(user.id, payload.project_name, payload.repo_url)
    if payload.repo_url:
        project = IndexingService(db).index_github_project(project, payload.repo_url)
    return project


@router.post("/upload", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def upload_project(
    project_name: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = ProjectService(db).create_project(user.id, project_name)
    temp_zip = _persist_upload(file)
    return IndexingService(db).index_zip_project(project, temp_zip)


@router.get("", response_model=list[ProjectRead])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ProjectService(db).list_projects(user.id)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project: Project = Depends(get_owned_project)):
    return project


@router.post("/{project_id}/refresh", response_model=ProjectRead)
def refresh_project(
    repo_url: str | None = None,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    return IndexingService(db).refresh_github_project(project, repo_url)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    ProjectService(db).delete_project(project)


def _persist_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "repo.zip").suffix or ".zip"
    temp_zip = settings.upload_dir / f"{uuid.uuid4().hex}{suffix}"
    with temp_zip.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return temp_zip
