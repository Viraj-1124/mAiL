# database/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from database.database import Base

class Feedback(Base):
    """ORM model for feedback records."""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
