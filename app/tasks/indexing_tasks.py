from pathlib import Path

from app.core.logger import log_event
from app.core.metrics import Timer, metrics
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.metadata.db_models import Project
from app.services.indexing_service import IndexingService


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def index_github_project_task(self, project_id: int, repo_url: str) -> dict[str, int | str | None]:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} does not exist")
        project.indexing_task_id = self.request.id
        db.commit()
        with Timer("indexing_duration_seconds"):
            indexed = IndexingService(db).index_github_project(project, repo_url)
        metrics.incr("indexing_total")
        metrics.incr("indexed_files_total", indexed.indexed_file_count)
        metrics.incr("indexed_chunks_total", indexed.indexed_chunk_count)
        log_event(
            "indexing_completed",
            project_id=indexed.id,
            source="github",
            files=indexed.indexed_file_count,
            chunks=indexed.indexed_chunk_count,
            commit_hash=indexed.commit_hash,
        )
        return {"project_id": indexed.id, "status": indexed.status, "commit_hash": indexed.commit_hash}
    except Exception:
        metrics.incr("indexing_errors_total")
        log_event("indexing_failed", project_id=project_id, source="github")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def index_zip_project_task(self, project_id: int, zip_path: str) -> dict[str, int | str | None]:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} does not exist")
        project.indexing_task_id = self.request.id
        db.commit()
        with Timer("indexing_duration_seconds"):
            indexed = IndexingService(db).index_zip_project(project, Path(zip_path))
        metrics.incr("indexing_total")
        metrics.incr("indexed_files_total", indexed.indexed_file_count)
        metrics.incr("indexed_chunks_total", indexed.indexed_chunk_count)
        log_event(
            "indexing_completed",
            project_id=indexed.id,
            source="zip",
            files=indexed.indexed_file_count,
            chunks=indexed.indexed_chunk_count,
        )
        return {"project_id": indexed.id, "status": indexed.status, "commit_hash": indexed.commit_hash}
    except Exception:
        metrics.incr("indexing_errors_total")
        log_event("indexing_failed", project_id=project_id, source="zip")
        raise
    finally:
        db.close()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def refresh_project_task(self, project_id: int, repo_url: str | None = None) -> dict[str, int | str | None]:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} does not exist")
        project.indexing_task_id = self.request.id
        db.commit()
        with Timer("indexing_duration_seconds"):
            indexed = IndexingService(db).refresh_github_project(project, repo_url)
        metrics.incr("refresh_total")
        metrics.incr("indexed_files_total", indexed.indexed_file_count)
        metrics.incr("indexed_chunks_total", indexed.indexed_chunk_count)
        log_event(
            "indexing_completed",
            project_id=indexed.id,
            source="refresh",
            files=indexed.indexed_file_count,
            chunks=indexed.indexed_chunk_count,
        )
        return {"project_id": indexed.id, "status": indexed.status, "commit_hash": indexed.commit_hash}
    except Exception:
        metrics.incr("indexing_errors_total")
        log_event("indexing_failed", project_id=project_id, source="refresh")
        raise
    finally:
        db.close()
