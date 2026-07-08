import json

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.schemas import SearchResponse, SearchResult
from app.metadata.db_models import ChatMessage, ChunkMetadata, Project
from app.vectorstore.embedding_service import EmbeddingService
from app.vectorstore.faiss_store import FaissStore


class SearchService:
    def __init__(self, db: Session, embedder: EmbeddingService | None = None) -> None:
        self.db = db
        self.embedder = embedder or EmbeddingService()

    def search(self, project: Project, query: str, top_k: int) -> SearchResponse:
        if project.status != "indexed" or not project.vector_index_path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is not indexed")

        store = FaissStore.load(project.vector_index_path)
        hits = store.search(self.embedder.embed_query(query), k=top_k)
        if not hits:
            return SearchResponse(project_id=project.id, query=query, results=[])

        positions = [hit.position for hit in hits]
        metadata_rows = self.db.scalars(
            select(ChunkMetadata).where(
                ChunkMetadata.project_id == project.id,
                ChunkMetadata.vector_position.in_(positions),
            )
        ).all()
        metadata_by_position = {row.vector_position: row for row in metadata_rows}

        results: list[SearchResult] = []
        for hit in hits:
            row = metadata_by_position.get(hit.position)
            if row is None:
                continue
            results.append(
                SearchResult(
                    chunk_id=row.chunk_id,
                    project_id=row.project_id,
                    file_path=row.file_path,
                    function_name=row.function_name,
                    class_name=row.class_name,
                    language=row.language,
                    similarity=round(hit.score, 6),
                    start_line=row.start_line,
                    end_line=row.end_line,
                    snippet_preview=row.snippet_preview,
                )
            )

        response = SearchResponse(project_id=project.id, query=query, results=results)
        self._append_chat(project.id, "user", query)
        self._append_chat(project.id, "assistant", response.model_dump_json())
        self.db.commit()
        return response

    def get_history(self, project: Project) -> list[ChatMessage]:
        return list(
            self.db.scalars(
                select(ChatMessage).where(ChatMessage.project_id == project.id).order_by(ChatMessage.created_at.asc())
            ).all()
        )

    def clear_history(self, project: Project) -> None:
        self.db.execute(delete(ChatMessage).where(ChatMessage.project_id == project.id))
        self.db.commit()

    def _append_chat(self, project_id: int, role: str, content: str) -> None:
        if role == "assistant":
            try:
                data = json.loads(content)
                content = json.dumps(data, separators=(",", ":"))
            except json.JSONDecodeError:
                pass
        self.db.add(ChatMessage(project_id=project_id, role=role, content=content))
