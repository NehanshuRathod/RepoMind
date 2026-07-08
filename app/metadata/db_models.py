from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    projects: Mapped[list["Project"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    commit_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    vector_index_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="created", nullable=False)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner: Mapped[User] = relationship(back_populates="projects")
    chunks: Mapped[list["ChunkMetadata"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    files: Mapped[list["FileRecord"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("user_id", "project_name", name="uq_project_user_name"),)


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(80), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="files")

    __table_args__ = (UniqueConstraint("project_id", "file_path", name="uq_file_project_path"),)


class ChunkMetadata(Base):
    __tablename__ = "embeddings_metadata"

    chunk_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    class_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    function_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(80), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    snippet_preview: Mapped[str] = mapped_column(Text, nullable=False)
    vector_position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="chunks")


class ChatMessage(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="chat_messages")
