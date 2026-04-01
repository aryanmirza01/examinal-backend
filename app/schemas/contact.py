from pydantic import EmailStr, BaseModel
from datetime import datetime
from typing import Optional, List

class ContactCreate(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str

class ContactReplyCreate(BaseModel):
    reply: str

class ContactReply(BaseModel):
    id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ContactMessage(BaseModel):
    id: int
    name: str
    email: str
    subject: str
    message: str
    created_at: datetime
    replies: List[ContactReply] = []

    class Config:
        from_attributes = True
