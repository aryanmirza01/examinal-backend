from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    exam_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submission_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="activity_logs")