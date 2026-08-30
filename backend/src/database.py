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
    """Create tables if they do not exist, and fast auto-seed if empty."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(TestRunORM).first() is None:
            sample_paths = [
                os.path.join(os.path.dirname(__file__), "..", "data", "sample_test_runs.json"),
                os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample_test_runs.json"),
                os.path.abspath(os.path.join(BASE_DIR, "data", "sample_test_runs.json")),
            ]
            sample_path = next((p for p in sample_paths if os.path.exists(p)), None)
            if sample_path:
                with open(sample_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    runs = data.get("runs", data) if isinstance(data, dict) else data
                    orm_objs = []
                    for tr in runs:
                        ts_str = tr.get("timestamp")
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else datetime.now(timezone.utc)
                        orm_objs.append(TestRunORM(
                            test_name=tr["test_name"],
                            status=tr["status"],
                            timestamp=ts,
                            duration_ms=tr.get("duration_ms", 0),
                            error_message=tr.get("error_message"),
                            stack_trace=tr.get("stack_trace"),
                            commit_sha=tr.get("commit_sha"),
                        ))
                    db.bulk_save_objects(orm_objs)
                    db.commit()
    except Exception as e:
        print(f"Auto-seed note: {e}")
    finally:
        db.close()

def get_db():
    """Yield a SQLAlchemy session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

