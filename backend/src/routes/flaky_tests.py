from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

try:
    from src.models import FlakyTestSummary
    from src.database import get_db, TestRunORM
    from src.services.flakiness_scorer import rank_flaky_tests
    from src.services.vector_store import search_similar_failures
    from src.services.root_cause_analyzer import generate_root_cause_explanation
except (ImportError, ModuleNotFoundError):
    from ..models import FlakyTestSummary
    from ..database import get_db, TestRunORM
    from ..services.flakiness_scorer import rank_flaky_tests
    from ..services.vector_store import search_similar_failures
    from ..services.root_cause_analyzer import generate_root_cause_explanation

router = APIRouter(prefix="/api/v1/flaky-tests", tags=["flaky-tests"])

@router.get("/", response_model=List[FlakyTestSummary])
def list_flaky_tests(db: Session = Depends(get_db)):
    """Return a ranked list of flaky test summaries."""
    return rank_flaky_tests()

@router.get("/{test_name}/analysis")
def analyze_flaky_test(test_name: str, db: Session = Depends(get_db)):
    """Analyze the most recent failure of a test and provide LLM insight.

    Returns a JSON with similar failures and AI analysis.
    """
    recent_fail = (
        db.query(TestRunORM)
        .filter(TestRunORM.test_name == test_name, TestRunORM.status == "fail")
        .order_by(TestRunORM.timestamp.desc())
        .first()
    )
    if not recent_fail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No failure history found for test '{test_name}'.",
        )
    # Retrieve similar failures from vector store
    similar = search_similar_failures(
        error_message=recent_fail.error_message or "",
        stack_trace=recent_fail.stack_trace or "",
        top_k=5,
    )
    # Generate AI analysis
    analysis = generate_root_cause_explanation(
        test_name=test_name,
        current_error=recent_fail.error_message or "",
        current_stack_trace=recent_fail.stack_trace,
        similar_failures=similar,
    )
    return {
        "similar_failures": similar,
        "analysis": analysis.dict() if hasattr(analysis, "dict") else analysis,
    }
