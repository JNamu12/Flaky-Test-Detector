from sqlalchemy import Column, Integer, String, DateTime, Text, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# SQLite database path (in project root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "flaky_test_detector.db"))
SQLALCHEMY_DATABASE_URL = f"sqlite+pysqlite:///{DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class TestRunORM(Base):
    __tablename__ = "testruns"
    id = Column(Integer, primary_key=True, index=True)
    test_name = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False)  # "pass" or "fail"
    timestamp = Column(DateTime, nullable=False)
    duration_ms = Column(Integer, nullable=False)
    error_message = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    commit_sha = Column(String, nullable=True)

import json
from datetime import datetime, timezone

def init_db():
    """Create tables if they do not exist."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Yield a SQLAlchemy session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

