from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.metadata.db_models import User


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register(self, email: str, password: str, full_name: str | None = None) -> User:
        existing = self.db.scalar(select(User).where(User.email == email.lower()))
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

        user = User(email=email.lower(), hashed_password=hash_password(password), full_name=full_name)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> str:
        user = self.db.scalar(select(User).where(User.email == email.lower()))
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
        return create_access_token(str(user.id))
