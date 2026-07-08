import hashlib
import json

from fastapi import HTTPException, status
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.schemas import SearchResponse, SearchResult
from app.core.logger import log_event
from app.core.metrics import Timer, metrics
from app.core.config import settings
from app.metadata.db_models import ChatMessage, ChunkMetadata, Project
from app.vectorstore.embedding_service import EmbeddingService
from app.vectorstore.faiss_store import FaissStore


class SearchService:
    def __init__(self, db: Session, embedder: EmbeddingService | None = None, cache: Redis | None = None) -> None:
        self.db = db
        self.embedder = embedder or EmbeddingService()
        self.cache = cache or Redis.from_url(settings.redis_url, decode_responses=True)

    def search(self, project: Project, query: str, top_k: int) -> SearchResponse:
        if project.status != "indexed" or not project.vector_index_path:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is not indexed")

        cache_key = self._cache_key(project, query, top_k)
        cached = self._get_cached(cache_key)
        if cached is not None:
            metrics.incr("search_cache_hits_total")
            self._append_chat(project.id, "user", query)
            self._append_chat(project.id, "assistant", cached.model_dump_json())
            self.db.commit()
            return cached

        metrics.incr("search_total")
        with Timer("search_duration_seconds"):
            store = FaissStore.load(project.vector_index_path)
            hits = store.search(self.embedder.embed_query(query), k=top_k)
        if not hits:
            response = SearchResponse(project_id=project.id, query=query, results=[])
            self._set_cached(cache_key, response)
            log_event("search_completed", project_id=project.id, results=0, cached=False)
            return response

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
        self._set_cached(cache_key, response)
        self._append_chat(project.id, "user", query)
        self._append_chat(project.id, "assistant", response.model_dump_json())
        self.db.commit()
        log_event("search_completed", project_id=project.id, results=len(results), cached=False)
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

    def _get_cached(self, cache_key: str) -> SearchResponse | None:
        try:
            payload = self.cache.get(cache_key)
        except RedisError:
            return None
        if not payload:
            return None
        return SearchResponse.model_validate_json(payload)

    def _set_cached(self, cache_key: str, response: SearchResponse) -> None:
        try:
            self.cache.setex(cache_key, settings.query_cache_ttl_seconds, response.model_dump_json())
        except RedisError:
            return

    def _cache_key(self, project: Project, query: str, top_k: int) -> str:
        version = project.last_indexed_at.isoformat() if project.last_indexed_at else "not-indexed"
        raw = json.dumps(
            {"project_id": project.id, "query": query.strip().lower(), "top_k": top_k, "version": version},
            sort_keys=True,
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"repomind:search:{digest}"

    def _append_chat(self, project_id: int, role: str, content: str) -> None:
        if role == "assistant":
            try:
                data = json.loads(content)
                content = json.dumps(data, separators=(",", ":"))
            except json.JSONDecodeError:
                pass
        self.db.add(ChatMessage(project_id=project_id, role=role, content=content))
