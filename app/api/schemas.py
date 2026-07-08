from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProjectCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=255)
    repo_url: str | None = None


class ProjectRead(BaseModel):
    id: int
    user_id: int
    project_name: str
    repo_url: str | None
    commit_hash: str | None
    vector_index_path: str | None
    status: str
    indexing_progress: int
    indexing_error: str | None
    indexing_task_id: str | None
    indexed_file_count: int
    indexed_chunk_count: int
    last_indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectStatus(BaseModel):
    project_id: int
    status: str
    progress: int
    task_id: str | None
    error: str | None
    indexed_file_count: int
    indexed_chunk_count: int
    last_indexed_at: datetime | None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    chunk_id: str
    project_id: int
    file_path: str
    function_name: str | None
    class_name: str | None
    language: str
    similarity: float
    start_line: int
    end_line: int
    snippet_preview: str


class SearchResponse(BaseModel):
    project_id: int
    query: str
    results: list[SearchResult]


class ChatMessageRead(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
