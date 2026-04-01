from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from app.database import Base

class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    subject = Column(String(1000), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Many replies
    replies = relationship("ContactReply", back_populates="message")

class ContactReply(Base):
    __tablename__ = "contact_replies"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("contact_messages.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("ContactMessage", back_populates="replies")
