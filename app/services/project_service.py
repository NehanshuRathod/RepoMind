from celery.exceptions import CeleryError
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.metadata.db_models import Project
from app.vectorstore.faiss_store import FaissStore


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_project(self, user_id: int, project_name: str, repo_url: str | None = None) -> Project:
        existing = self.db.scalar(
            select(Project).where(Project.user_id == user_id, Project.project_name == project_name)
        )
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project name already exists")
        project = Project(user_id=user_id, project_name=project_name, repo_url=repo_url, status="created")
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list_projects(self, user_id: int) -> list[Project]:
        return list(
            self.db.scalars(select(Project).where(Project.user_id == user_id).order_by(Project.updated_at.desc())).all()
        )

    def queue_indexing_job(self, project: Project, task_id: str | None = None) -> Project:
        project.status = "queued"
        project.indexing_progress = 0
        project.indexing_error = None
        project.indexing_task_id = task_id
        self.db.commit()
        self.db.refresh(project)
        return project

    def mark_queue_error(self, project: Project, error: str) -> Project:
        project.status = "failed"
        project.indexing_error = error
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete_project(self, project: Project) -> None:
        FaissStore.delete(project.vector_index_path)
        self.db.delete(project)
        self.db.commit()


def queue_or_fail(project: Project, enqueue_call, db: Session) -> Project:
    service = ProjectService(db)
    service.queue_indexing_job(project)
    try:
        async_result = enqueue_call()
    except CeleryError as exc:
        service.mark_queue_error(project, str(exc))
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Indexing queue is unavailable") from exc
    project.indexing_task_id = async_result.id
    db.commit()
    db.refresh(project)
    return project
