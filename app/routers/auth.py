"""
Authentication endpoints: register, login, refresh, me.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import CurrentUser
from app.schemas.user import UserCreate, UserOut, Token
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    service = AuthService(db)
    user = service.register(payload)
    return user


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    service = AuthService(db)
    user = service.authenticate(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    tokens = service.create_tokens(user)
    return tokens


@router.post("/refresh", response_model=Token)
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    service = AuthService(db)
    tokens = service.refresh(refresh_token)
    return tokens


@router.get("/me", response_model=UserOut)
def get_me(current_user: CurrentUser):
    return current_user