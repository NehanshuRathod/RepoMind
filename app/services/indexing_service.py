import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.indexing.ast_parser import ASTParser
from app.indexing.chunk_extractor import ChunkExtractor
from app.indexing.file_filter import FileFilter
from app.indexing.file_loader import FileLoader
from app.indexing.models import CodeChunk
from app.indexing.repository_manager import RepositoryManager
from app.indexing.tree_sitter_parser import MultiLanguageChunker
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


@dataclass(frozen=True)
class ScannedFile:
    relative_path: str
    absolute_path: Path
    language: str
    file_hash: str


@dataclass(frozen=True)
class ChunkVectorRecord:
    chunk_id: str
    file_path: str
    class_name: str | None
    function_name: str | None
    language: str
    start_line: int
    end_line: int
    content_hash: str
    snippet_preview: str
    vector: np.ndarray


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
        self.multilang = MultiLanguageChunker()
        self.embedder = embedder or EmbeddingService()

    def index_github_project(self, project: Project, repo_url: str) -> Project:
        workspace: Path | None = None
        try:
            self._mark_status(project, "indexing", progress=5)
            workspace = self.repo_manager.clone_repo(repo_url)
            self._mark_status(project, "indexing", progress=15)
            commit_hash = self.repo_manager.get_commit_hash(workspace)
            self._index_workspace(project=project, workspace=workspace, repo_url=repo_url, commit_hash=commit_hash)
            return project
        except Exception as exc:
            self._mark_status(project, "failed", progress=project.indexing_progress, error=str(exc))
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
        finally:
            if workspace is not None:
                self.repo_manager.cleanup(workspace)

    def index_zip_project(self, project: Project, zip_path: Path) -> Project:
        workspace: Path | None = None
        try:
            self._mark_status(project, "indexing", progress=5)
            workspace = self.repo_manager.extract_zip(zip_path)
            self._mark_status(project, "indexing", progress=15)
            self._index_workspace(project=project, workspace=workspace, repo_url=project.repo_url, commit_hash=None)
            return project
        except Exception as exc:
            self._mark_status(project, "failed", progress=project.indexing_progress, error=str(exc))
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
        scanned_files = self._scan_files(workspace)
        self._mark_status(project, "indexing", progress=25)

        old_file_hashes = {
            row.file_path: row.hash
            for row in self.db.scalars(select(FileRecord).where(FileRecord.project_id == project.id)).all()
        }
        old_chunks_by_file = self._load_reusable_chunks(project.id)

        reusable_files = {
            scanned.relative_path
            for scanned in scanned_files
            if old_file_hashes.get(scanned.relative_path) == scanned.file_hash
            and all(chunk.vector is not None for chunk in old_chunks_by_file.get(scanned.relative_path, []))
        }
        changed_files = {scanned.relative_path for scanned in scanned_files} - reusable_files

        reusable_records = [
            self._record_from_metadata(chunk)
            for file_path in sorted(reusable_files)
            for chunk in old_chunks_by_file.get(file_path, [])
        ]
        self._mark_status(project, "indexing", progress=40)

        changed_chunks = self._extract_chunks(workspace, scanned_files, changed_files)
        self._mark_status(project, "indexing", progress=55)

        new_records = self._embed_chunks(changed_chunks)
        all_records = reusable_records + new_records
        all_records.sort(key=lambda record: (record.file_path, record.start_line, record.end_line, record.chunk_id))
        self._mark_status(project, "indexing", progress=75)

        self._replace_project_index(project=project, records=all_records)
        self._replace_metadata(project=project, scanned_files=scanned_files, records=all_records)

        project.repo_url = repo_url
        project.commit_hash = commit_hash
        project.status = "indexed"
        project.indexing_progress = 100
        project.indexing_error = None
        project.indexed_file_count = len(scanned_files)
        project.indexed_chunk_count = len(all_records)
        project.last_indexed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(project)

    def _scan_files(self, workspace: Path) -> list[ScannedFile]:
        files = self.filterer.filter(self.loader.load_files(workspace))
        scanned_files: list[ScannedFile] = []
        for file_path in files:
            relative_path = file_path.relative_to(workspace).as_posix()
            scanned_files.append(
                ScannedFile(
                    relative_path=relative_path,
                    absolute_path=file_path,
                    language=LANGUAGE_BY_EXTENSION.get(file_path.suffix.lower(), "unknown"),
                    file_hash=self._file_hash(file_path),
                )
            )
        return sorted(scanned_files, key=lambda item: item.relative_path)

    def _load_reusable_chunks(self, project_id: int) -> dict[str, list[ChunkMetadata]]:
        chunks_by_file: dict[str, list[ChunkMetadata]] = defaultdict(list)
        rows = self.db.scalars(select(ChunkMetadata).where(ChunkMetadata.project_id == project_id)).all()
        for row in rows:
            chunks_by_file[row.file_path].append(row)
        return chunks_by_file

    def _extract_chunks(self, workspace: Path, scanned_files: list[ScannedFile], changed_files: set[str]) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        for scanned in scanned_files:
            if scanned.relative_path not in changed_files:
                continue
            if scanned.absolute_path.suffix.lower() == ".py":
                try:
                    tree, source = self.parser.parse_python(scanned.absolute_path)
                except SyntaxError:
                    continue
                chunks.extend(self.extractor.extract_python_chunks(tree, source, scanned.relative_path))
            else:
                chunks.extend(self.multilang.extract(scanned.absolute_path, scanned.language))
        return chunks

    def _embed_chunks(self, chunks: list[CodeChunk]) -> list[ChunkVectorRecord]:
        if not chunks:
            return []
        unique_chunks: dict[str, CodeChunk] = {}
        order: list[str] = []
        for chunk in chunks:
            if chunk.content_hash not in unique_chunks:
                unique_chunks[chunk.content_hash] = chunk
                order.append(chunk.content_hash)

        vectors = self.embedder.embed_texts([unique_chunks[content_hash].content for content_hash in order])
        vector_by_hash = dict(zip(order, vectors, strict=True))

        records: list[ChunkVectorRecord] = []
        for chunk in chunks:
            records.append(
                ChunkVectorRecord(
                    chunk_id=chunk.chunk_id,
                    file_path=chunk.file_path,
                    class_name=chunk.class_name,
                    function_name=chunk.function_name,
                    language=chunk.language,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content_hash=chunk.content_hash,
                    snippet_preview=self._preview(chunk.content),
                    vector=np.asarray(vector_by_hash[chunk.content_hash], dtype="float32"),
                )
            )
        return records

    def _record_from_metadata(self, chunk: ChunkMetadata) -> ChunkVectorRecord:
        return ChunkVectorRecord(
            chunk_id=chunk.chunk_id,
            file_path=chunk.file_path,
            class_name=chunk.class_name,
            function_name=chunk.function_name,
            language=chunk.language,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            content_hash=chunk.hash,
            snippet_preview=chunk.snippet_preview,
            vector=np.frombuffer(chunk.vector, dtype="float32").copy(),
        )

    def _replace_project_index(self, project: Project, records: list[ChunkVectorRecord]) -> None:
        FaissStore.delete(project.vector_index_path)
        if not records:
            project.vector_index_path = None
            return
        vectors = np.vstack([record.vector for record in records]).astype("float32")
        index_path = settings.vector_store_dir / f"project_{project.id}.faiss"
        store = FaissStore(dim=int(vectors.shape[1]))
        store.add_embeddings(vectors)
        store.save(index_path)
        project.vector_index_path = str(index_path)

    def _replace_metadata(self, project: Project, scanned_files: list[ScannedFile], records: list[ChunkVectorRecord]) -> None:
        self.db.execute(delete(ChunkMetadata).where(ChunkMetadata.project_id == project.id))
        self.db.execute(delete(FileRecord).where(FileRecord.project_id == project.id))

        for scanned in scanned_files:
            self.db.add(
                FileRecord(
                    project_id=project.id,
                    file_path=scanned.relative_path,
                    language=scanned.language,
                    hash=scanned.file_hash,
                )
            )

        for position, record in enumerate(records):
            self.db.add(
                ChunkMetadata(
                    chunk_id=record.chunk_id,
                    project_id=project.id,
                    file_path=record.file_path,
                    class_name=record.class_name,
                    function_name=record.function_name,
                    language=record.language,
                    start_line=record.start_line,
                    end_line=record.end_line,
                    hash=record.content_hash,
                    snippet_preview=record.snippet_preview,
                    vector_position=position,
                    vector=np.asarray(record.vector, dtype="float32").tobytes(),
                )
            )

    def _mark_status(self, project: Project, status_value: str, progress: int, error: str | None = None) -> None:
        project.status = status_value
        project.indexing_progress = max(0, min(100, progress))
        project.indexing_error = error
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
