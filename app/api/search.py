from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_owned_project
from app.api.schemas import ChatMessageRead, SearchRequest, SearchResponse
from app.core.database import get_db
from app.metadata.db_models import Project
from app.services.search_service import SearchService


router = APIRouter(prefix="/projects/{project_id}", tags=["Search"])


@router.post("/search", response_model=SearchResponse)
def search_project(
    payload: SearchRequest,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    return SearchService(db).search(project, payload.query, payload.top_k)


@router.get("/chat", response_model=list[ChatMessageRead])
def get_chat_history(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    return SearchService(db).get_history(project)


@router.delete("/chat", status_code=status.HTTP_204_NO_CONTENT)
def clear_chat_history(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    SearchService(db).clear_history(project)
