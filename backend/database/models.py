# database/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
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
    thread_id = Column(String)
    smart_thread_id = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    attachments = relationship("EmailAttachment", back_populates="email")



class EmailAttachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(String, ForeignKey("emails.email_id"))
    filename = Column(String)
    mime_type = Column(String)
    size = Column(Integer)
    attachment_id = Column(String)  # Gmail internal attachment ID

    email = relationship("Email", back_populates="attachments")