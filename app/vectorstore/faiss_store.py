from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class VectorSearchHit:
    position: int
    score: float


class FaissStore:
    def __init__(self, dim: int, index: object | None = None) -> None:
        self.dim = dim
        if index is None:
            faiss = self._faiss()
            self.index = faiss.IndexFlatIP(dim)
        else:
            self.index = index

    @staticmethod
    def _faiss():
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("faiss-cpu is required for vector search") from exc
        return faiss

    @classmethod
    def load(cls, path: Path) -> "FaissStore":
        faiss = cls._faiss()
        index = faiss.read_index(str(path))
        return cls(dim=index.d, index=index)

    def add_embeddings(self, vectors: np.ndarray) -> None:
        if vectors.size == 0:
            return
        normalized = self._normalize(vectors)
        self.index.add(normalized)

    def search(self, query_vector: np.ndarray, k: int = 5) -> list[VectorSearchHit]:
        if self.index.ntotal == 0:
            return []
        normalized = self._normalize(query_vector)
        scores, indices = self.index.search(normalized, min(k, self.index.ntotal))
        hits: list[VectorSearchHit] = []
        for score, index in zip(scores[0], indices[0], strict=False):
            if index >= 0:
                hits.append(VectorSearchHit(position=int(index), score=float(score)))
        return hits

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss = self._faiss()
        faiss.write_index(self.index, str(path))

    @staticmethod
    def delete(path: Path | str | None) -> None:
        if path is None:
            return
        index_path = Path(path)
        if index_path.exists():
            index_path.unlink()

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        arr = np.asarray(vectors, dtype="float32")
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms
