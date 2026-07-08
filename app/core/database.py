from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


is_sqlite = settings.database_url.startswith("sqlite")
is_memory_sqlite = settings.database_url in {"sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}
connect_args = {"check_same_thread": False} if is_sqlite else {}
engine_kwargs: dict[str, object] = {"connect_args": connect_args, "future": True}
if is_memory_sqlite:
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.metadata.db_models import ChatMessage, ChunkMetadata, FileRecord, Project, User

    _ = (ChatMessage, ChunkMetadata, FileRecord, Project, User)
    Base.metadata.create_all(bind=engine)
