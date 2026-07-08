from pathlib import Path

import numpy as np
import pytest

from app.vectorstore.faiss_store import FaissStore


faiss = pytest.importorskip("faiss")


def test_faiss_store_saves_loads_and_searches():
    index_path = Path("storage/faiss_test_index.faiss")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    store = FaissStore(dim=3)
    store.add_embeddings(np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype="float32"))
    store.save(index_path)

    loaded = FaissStore.load(index_path)
    hits = loaded.search(np.array([[0.9, 0.1, 0.0]], dtype="float32"), k=2)

    assert [hit.position for hit in hits] == [0, 1]
    assert hits[0].score > hits[1].score
