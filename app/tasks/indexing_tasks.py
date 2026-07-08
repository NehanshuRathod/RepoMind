from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.metadata.db_models import Project
from app.services.indexing_service import IndexingService


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def refresh_project_task(self, project_id: int, repo_url: str | None = None) -> dict[str, int | str | None]:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} does not exist")
        indexed = IndexingService(db).refresh_github_project(project, repo_url)
        return {"project_id": indexed.id, "status": indexed.status, "commit_hash": indexed.commit_hash}
    finally:
        db.close()
