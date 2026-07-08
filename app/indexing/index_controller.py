from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.metadata.db_models import User
from app.services.indexing_service import IndexingService


router = APIRouter(prefix="/index", tags=["Indexing"])


@router.post("/debug/chunks")
def debug_chunks(repo_url: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project_name = f"debug-{user.id}"
    from app.services.project_service import ProjectService

    project = ProjectService(db).create_project(user.id, project_name, repo_url)
    indexed = IndexingService(db).index_github_project(project, repo_url)
    return {"project_id": indexed.id, "status": indexed.status}
