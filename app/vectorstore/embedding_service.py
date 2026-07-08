from threading import Lock

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings


class EmbeddingService:
    _model: SentenceTransformer | None = None
    _lock = Lock()

    def __init__(self, model_name: str | None = None, batch_size: int | None = None) -> None:
        self.model_name = model_name or settings.embedding_model_name
        self.batch_size = batch_size or settings.embedding_batch_size

    @property
    def model(self) -> SentenceTransformer:
        if EmbeddingService._model is None:
            with EmbeddingService._lock:
                if EmbeddingService._model is None:
                    EmbeddingService._model = SentenceTransformer(self.model_name)
        return EmbeddingService._model

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype="float32")
        vectors = self.model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.astype("float32")

    def embed_query(self, query: str) -> np.ndarray:
        return self.embed_texts([query])
