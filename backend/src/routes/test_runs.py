import os
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, File, UploadFile, Form, status
from sqlalchemy.orm import Session

from ..models import TestRunBatch
from ..database import get_db, TestRunORM
from ..services.vector_store import upsert_failure
from ..services.junit_parser import parse_junit_xml_bytes

router = APIRouter(prefix="/api/v1/test-runs", tags=["test-runs"])

@router.get("/")
def get_all_test_runs(db: Session = Depends(get_db)):
    """Return all raw TestRun records stored in the SQLite database."""
    runs = db.query(TestRunORM).order_by(TestRunORM.timestamp.desc()).all()
    return [
        {
            "id": r.id,
            "test_name": r.test_name,
            "status": r.status,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "duration_ms": r.duration_ms,
            "error_message": r.error_message,
            "stack_trace": r.stack_trace,
            "commit_sha": r.commit_sha,
        }
        for r in runs
    ]

def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    expected_key = os.getenv("API_KEY")
    if expected_key:
        if not x_api_key or x_api_key != expected_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API Key"
            )

@router.post("/ingest")
def ingest_test_runs(batch: TestRunBatch, db: Session = Depends(get_db), _api_key: None = Depends(verify_api_key)):
    """Ingest a batch of TestRun records into the SQLite database.

    Returns the number of records successfully inserted.
    """
    count = 0
    for tr in batch.runs:
        orm_obj = TestRunORM(
            test_name=tr.test_name,
            status=tr.status,
            timestamp=tr.timestamp,
            duration_ms=tr.duration_ms,
            error_message=tr.error_message,
            stack_trace=tr.stack_trace,
            commit_sha=tr.commit_sha,
        )
        db.add(orm_obj)
        if tr.status == "fail" and tr.error_message:
            upsert_failure(
                test_name=tr.test_name,
                error_message=tr.error_message,
                stack_trace=tr.stack_trace,
                timestamp=tr.timestamp,
            )
        count += 1
    db.commit()
    return {"ingested": count}

@router.post("/ingest-junit")
async def ingest_junit_xml(
    file: UploadFile = File(...),
    source_tool: Optional[str] = Form(None),
    commit_sha: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _api_key: None = Depends(verify_api_key),
):
    """Ingest a JUnit XML report file directly via multipart upload."""
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        parsed_runs = parse_junit_xml_bytes(content, commit_sha=commit_sha, source_tool=source_tool)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse JUnit XML file: {str(e)}",
        )

    count = 0
    for tr in parsed_runs:
        orm_obj = TestRunORM(
            test_name=tr["test_name"],
            status=tr["status"],
            timestamp=tr["timestamp"],
            duration_ms=tr["duration_ms"],
            error_message=tr["error_message"],
            stack_trace=tr["stack_trace"],
            commit_sha=tr["commit_sha"],
        )
        db.add(orm_obj)
        if tr["status"] == "fail" and tr["error_message"]:
            upsert_failure(
                test_name=tr["test_name"],
                error_message=tr["error_message"],
                stack_trace=tr["stack_trace"],
                timestamp=tr["timestamp"],
            )
        count += 1
    db.commit()
    return {"ingested": count, "source_tool": source_tool or "junit"}

