from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.schemas import Token, UserCreate, UserRead
from app.core.database import get_db
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    return AuthService(db).register(payload.email, payload.password, payload.full_name)


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    token = AuthService(db).authenticate(form.username, form.password)
    return Token(access_token=token)
