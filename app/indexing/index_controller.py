from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.metadata.db_models import User
from app.services.project_service import ProjectService
from app.tasks.indexing_tasks import index_github_project_task


router = APIRouter(prefix="/index", tags=["Indexing"])


@router.post("/debug/chunks")
def debug_chunks(repo_url: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project_name = f"debug-{user.id}"
    project = ProjectService(db).create_project(user.id, project_name, repo_url)
    task = index_github_project_task.delay(project.id, repo_url)
    return ProjectService(db).queue_indexing_job(project, task.id)
