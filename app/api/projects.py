import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_owned_project
from app.api.schemas import ProjectCreate, ProjectRead, ProjectStatus
from app.core.config import settings
from app.core.database import get_db
from app.metadata.db_models import Project, User
from app.services.project_service import ProjectService, queue_or_fail
from app.tasks.indexing_tasks import index_github_project_task, index_zip_project_task, refresh_project_task


router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = ProjectService(db).create_project(user.id, payload.project_name, payload.repo_url)
    if payload.repo_url:
        return queue_or_fail(project, lambda: index_github_project_task.delay(project.id, payload.repo_url), db)
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
    return queue_or_fail(project, lambda: index_zip_project_task.delay(project.id, str(temp_zip)), db)


@router.get("", response_model=list[ProjectRead])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ProjectService(db).list_projects(user.id)


@router.get("/{project_id}/status", response_model=ProjectStatus)
def get_project_status(project: Project = Depends(get_owned_project)):
    return ProjectStatus(
        project_id=project.id,
        status=project.status,
        progress=project.indexing_progress,
        task_id=project.indexing_task_id,
        error=project.indexing_error,
        indexed_file_count=project.indexed_file_count,
        indexed_chunk_count=project.indexed_chunk_count,
        last_indexed_at=project.last_indexed_at,
    )


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project: Project = Depends(get_owned_project)):
    return project


@router.post("/{project_id}/refresh", response_model=ProjectRead)
def refresh_project(
    repo_url: str | None = None,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    source_url = repo_url or project.repo_url
    if not source_url:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has no repository URL to refresh")
    return queue_or_fail(project, lambda: refresh_project_task.delay(project.id, repo_url), db)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    ProjectService(db).delete_project(project)


def _persist_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "repo.zip").suffix or ".zip"
    temp_zip = settings.upload_dir / f"{uuid.uuid4().hex}{suffix}"
    with temp_zip.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return temp_zip
