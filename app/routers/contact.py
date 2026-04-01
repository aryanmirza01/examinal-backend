from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.contact import ContactCreate, ContactMessage as ContactSchema, ContactReplyCreate
from app.services.contact_service import create_contact_message, get_all_contact_messages, reply_to_message
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/contact", tags=["contact"])

@router.post("/", response_model=ContactSchema)
def submit_contact_form(msg: ContactCreate, db: Session = Depends(get_db)):
    return create_contact_message(db, msg)

@router.get("/", response_model=List[ContactSchema])
def get_contact_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contact messages accessible by admin only"
        )
    return get_all_contact_messages(db)

@router.post("/{message_id}/reply", response_model=ContactSchema)
def reply_to_contact(
    message_id: int,
    reply_data: ContactReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can reply to messages"
        )
    
    msg = reply_to_message(db, message_id, reply_data.reply)
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    return msg
