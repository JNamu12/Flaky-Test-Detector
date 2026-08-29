from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel

class TestRun(BaseModel):
    test_name: str
    status: Literal["pass", "fail"]
    timestamp: datetime
    duration_ms: int
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    commit_sha: Optional[str] = None

class TestRunBatch(BaseModel):
    runs: List[TestRun]

class FlakyTestSummary(BaseModel):
    test_name: str
    flakiness_score: float
    total_runs: int
    fail_count: int
    last_status: str
