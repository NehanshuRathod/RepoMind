import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

_TMP_DIR = Path(tempfile.mkdtemp(prefix="repomind-test-"))
_TMP_DB = _TMP_DIR / "repomind.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["VECTOR_STORE_DIR"] = str(_TMP_DIR / "vector_indexes")
os.environ["UPLOAD_DIR"] = str(_TMP_DIR / "uploads")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.core.celery_app import celery_app  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.api.dependencies import get_db  # noqa: E402
from app.services.indexing_service import EmbeddingService  # noqa: E402

EMBED_DIM = 384


def _fake_embed(texts):
    vectors = np.zeros((len(texts), EMBED_DIM), dtype="float32")
    for i, text in enumerate(texts):
        for token in "".join(ch if ch.isalnum() else " " for ch in text).split():
            vectors[i, hash(token) % EMBED_DIM] += 1.0
    return vectors


def _fake_query(query):
    return _fake_embed([query])


@pytest.fixture
def client():
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    EmbeddingService.embed_texts = staticmethod(_fake_embed)
    EmbeddingService.embed_query = staticmethod(_fake_query)

    init_db()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
