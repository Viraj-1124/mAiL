# database/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite DB file (same as before)
DATABASE_URL = "sqlite:///./feedback.db"

# Engine setup
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base for ORM models
Base = declarative_base()


def get_db():
    """Dependency to provide DB session for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
