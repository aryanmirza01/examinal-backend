"""
Authentication service: registration, login, JWT minting.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models.user import User
from app.schemas.user import UserCreate, Token
from app.utils.security import hash_password, verify_password


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    # ── Register ──
    def register(self, payload: UserCreate) -> User:
        email = payload.email.strip()
        username = payload.username.strip()
        if self.db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        if self.db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Username already taken")

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role=payload.role,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ── Authenticate ──
    def authenticate(self, username: str, password: str) -> User | None:
        username = username.strip()
        user = self.db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()
        if not user or not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account deactivated")
        return user

    # ── Tokens ──
    def _create_token(self, data: dict, expires_delta: timedelta) -> str:
        to_encode = data.copy()
        to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def create_tokens(self, user: User) -> Token:
        access = self._create_token(
            {"sub": str(user.id), "role": user.role},
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh = self._create_token(
            {"sub": str(user.id), "type": "refresh"},
            timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        return Token(access_token=access, refresh_token=refresh)

    # ── Refresh ──
    def refresh(self, refresh_token: str) -> Token:
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail="Invalid token type")
            user_id = int(payload["sub"])
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found")
        return self.create_tokens(user)