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

class Email(Base):
    """Store fetched and summarized emails."""
    __tablename__ = "emails"

    email_id = Column(String, primary_key=True, index=True)  # Gmail message ID
    user_email = Column(String, nullable=False, index=True)
    sender = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    body = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    priority = Column(String, default="Medium")
    category = Column(String, default="Uncategorized")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

