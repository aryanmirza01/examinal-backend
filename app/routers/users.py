"""
User management endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AdminUser, CurrentUser
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/", response_model=List[UserOut])
def list_users(
    role: str | None = None,
    skip: int = 0,
    limit: int = 50,
    _admin: AdminUser = None,  # type: ignore
    db: Session = Depends(get_db),
):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    return q.offset(skip).limit(limit).all()


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    # Only admins can change role/active status
    if current_user.role != "admin":
        update_data.pop("role", None)
        update_data.pop("is_active", None)

    for k, v in update_data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, _admin: AdminUser, db: Session = Depends(get_db)):  # type: ignore
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()