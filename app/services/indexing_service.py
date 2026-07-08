import hashlib
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.indexing.ast_parser import ASTParser
from app.indexing.chunk_extractor import ChunkExtractor
from app.indexing.file_filter import FileFilter
from app.indexing.file_loader import FileLoader
from app.indexing.models import CodeChunk
from app.indexing.repository_manager import RepositoryManager
from app.metadata.db_models import ChunkMetadata, FileRecord, Project
from app.vectorstore.embedding_service import EmbeddingService
from app.vectorstore.faiss_store import FaissStore


LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
}


class IndexingService:
    def __init__(
        self,
        db: Session,
        repo_manager: RepositoryManager | None = None,
        loader: FileLoader | None = None,
        filterer: FileFilter | None = None,
        parser: ASTParser | None = None,
        extractor: ChunkExtractor | None = None,
        embedder: EmbeddingService | None = None,
    ) -> None:
        self.db = db
        self.repo_manager = repo_manager or RepositoryManager()
        self.loader = loader or FileLoader()
        self.filterer = filterer or FileFilter()
        self.parser = parser or ASTParser()
        self.extractor = extractor or ChunkExtractor()
        self.embedder = embedder or EmbeddingService()

    def index_github_project(self, project: Project, repo_url: str) -> Project:
        workspace: Path | None = None
        try:
            self._mark_status(project, "indexing")
            workspace = self.repo_manager.clone_repo(repo_url)
            commit_hash = self.repo_manager.get_commit_hash(workspace)
            self._index_workspace(project=project, workspace=workspace, repo_url=repo_url, commit_hash=commit_hash)
            return project
        except Exception as exc:
            self._mark_status(project, "failed")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
        finally:
            if workspace is not None:
                self.repo_manager.cleanup(workspace)

    def index_zip_project(self, project: Project, zip_path: Path) -> Project:
        workspace: Path | None = None
        try:
            self._mark_status(project, "indexing")
            workspace = self.repo_manager.extract_zip(zip_path)
            self._index_workspace(project=project, workspace=workspace, repo_url=project.repo_url, commit_hash=None)
            return project
        except Exception as exc:
            self._mark_status(project, "failed")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
        finally:
            if workspace is not None:
                self.repo_manager.cleanup(workspace)
            if zip_path.exists():
                zip_path.unlink()

    def refresh_github_project(self, project: Project, repo_url: str | None = None) -> Project:
        source_url = repo_url or project.repo_url
        if not source_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has no repository URL to refresh")
        return self.index_github_project(project, source_url)

    def _index_workspace(
        self,
        project: Project,
        workspace: Path,
        repo_url: str | None,
        commit_hash: str | None,
    ) -> None:
        chunks, file_records = self._extract_chunks(workspace)
        self.db.execute(delete(ChunkMetadata).where(ChunkMetadata.project_id == project.id))
        self.db.execute(delete(FileRecord).where(FileRecord.project_id == project.id))
        FaissStore.delete(project.vector_index_path)

        project.repo_url = repo_url
        project.commit_hash = commit_hash

        for record in file_records:
            self.db.add(FileRecord(project_id=project.id, **record))

        if chunks:
            vectors = self.embedder.embed_texts([chunk.content for chunk in chunks])
            index_path = settings.vector_store_dir / f"project_{project.id}.faiss"
            store = FaissStore(dim=int(vectors.shape[1]))
            store.add_embeddings(vectors)
            store.save(index_path)
            project.vector_index_path = str(index_path)

            for position, chunk in enumerate(chunks):
                self.db.add(
                    ChunkMetadata(
                        chunk_id=chunk.chunk_id,
                        project_id=project.id,
                        file_path=chunk.file_path,
                        class_name=chunk.class_name,
                        function_name=chunk.function_name,
                        language=chunk.language,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        hash=chunk.content_hash,
                        snippet_preview=self._preview(chunk.content),
                        vector_position=position,
                    )
                )
        else:
            project.vector_index_path = None

        project.status = "indexed"
        project.last_indexed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(project)

    def _extract_chunks(self, workspace: Path) -> tuple[list[CodeChunk], list[dict[str, str]]]:
        files = self.filterer.filter(self.loader.load_files(workspace))
        chunks: list[CodeChunk] = []
        file_records: list[dict[str, str]] = []

        for file_path in files:
            relative_path = file_path.relative_to(workspace).as_posix()
            language = LANGUAGE_BY_EXTENSION.get(file_path.suffix.lower(), "unknown")
            file_records.append(
                {"file_path": relative_path, "language": language, "hash": self._file_hash(file_path)}
            )
            if file_path.suffix.lower() != ".py":
                continue
            try:
                tree, source = self.parser.parse_python(file_path)
            except SyntaxError:
                continue
            chunks.extend(self.extractor.extract_python_chunks(tree, source, relative_path))

        return chunks, file_records

    def _mark_status(self, project: Project, status_value: str) -> None:
        project.status = status_value
        self.db.commit()
        self.db.refresh(project)

    @staticmethod
    def _file_hash(file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _preview(content: str, limit: int = 1200) -> str:
        cleaned = content.strip()
        return cleaned if len(cleaned) <= limit else f"{cleaned[:limit].rstrip()}..."
