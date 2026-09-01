from sqlalchemy import Column, Integer, String, DateTime, Text, Float, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# SQLite database path (persistent location when deployed; local project root by default)
# Look for persistent disk paths on Render or container environments
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PERSISTENT_DIR = os.getenv("DATA_DIR") or (
    "/var/data" if os.path.isdir("/var/data") else ("/data" if os.path.isdir("/data") else None)
)
DEFAULT_DB_PATH = (
    os.path.join(PERSISTENT_DIR, "flaky_test_detector.db")
    if PERSISTENT_DIR
    else os.path.join(BASE_DIR, "flaky_test_detector.db")
)
DB_PATH = os.getenv("DB_PATH") or DEFAULT_DB_PATH
DB_DIR = os.path.dirname(DB_PATH) or BASE_DIR
os.makedirs(DB_DIR, exist_ok=True)

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
    """Create tables if they do not exist, and perform one-time auto-seed if empty."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_marker = os.path.join(DB_DIR, ".seeded")
    try:
        # Only seed once ever: check for persistent marker file AND empty table
        if not os.path.exists(seed_marker) and db.query(TestRunORM).first() is None:
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
                # Create persistent marker so seeding never runs again on restart
                try:
                    with open(seed_marker, "w") as mf:
                        mf.write(f"Seeded at {datetime.now(timezone.utc).isoformat()}")
                except Exception as me:
                    print(f"Seed marker notice: {me}")
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

