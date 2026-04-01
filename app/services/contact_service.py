from sqlalchemy.orm import Session, joinedload
from app.models.contact import ContactMessage, ContactReply
from app.schemas.contact import ContactCreate
from app.utils.email import send_reply_email

def create_contact_message(db: Session, msg: ContactCreate):
    new_msg = ContactMessage(
        name=msg.name,
        email=msg.email,
        subject=msg.subject,
        message=msg.message
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    return new_msg

def get_all_contact_messages(db: Session):
    return db.query(ContactMessage).options(joinedload(ContactMessage.replies)).order_by(ContactMessage.created_at.desc()).all()

def reply_to_message(db: Session, message_id: int, reply_text: str):
    msg = db.query(ContactMessage).filter(ContactMessage.id == message_id).first()
    if not msg:
        return None
    
    # Create DB record for the reply
    new_reply = ContactReply(
        message_id = message_id,
        content = reply_text
    )
    db.add(new_reply)
    db.commit()
    db.refresh(new_reply)

    # Attempt to send real email
    send_reply_email(msg.email, msg.subject, reply_text)
    
    # Refresh msg to get the new replies list
    db.refresh(msg)
    return msg
