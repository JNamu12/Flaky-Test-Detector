from collections import defaultdict
from datetime import datetime
from typing import List

from ..models import TestRun, FlakyTestSummary
from ..database import SessionLocal, TestRunORM


def calculate_flakiness_score(runs: List[TestRun]) -> float:
    """Calculate a flakiness score for a list of TestRun objects.

    The score is the number of status transitions (pass↔fail) divided by
    the maximum possible number of transitions (total_runs - 1). If there
    are fewer than three runs the function returns 0.0 because the metric
    would be unreliable.
    """
    if len(runs) < 3:
        return 0.0
    # Ensure runs are sorted chronologically
    runs_sorted = sorted(runs, key=lambda r: r.timestamp)
    transitions = 0
    for previous, current in zip(runs_sorted, runs_sorted[1:]):
        if previous.status != current.status:
            transitions += 1
    return transitions / (len(runs_sorted) - 1)


def rank_flaky_tests() -> List[FlakyTestSummary]:
    """Return a list of FlakyTestSummary objects ordered by flakiness.

    All TestRun records are fetched from the SQLite database, grouped by
    ``test_name`` and scored using :func:`calculate_flakiness_score`. The
    resulting summaries are sorted descending by ``flakiness_score``.
    """
    db = SessionLocal()
    try:
        # Pull all records as ORM objects
        orm_runs = db.query(TestRunORM).all()
    finally:
        db.close()

    # Group ORM rows by test name and convert to Pydantic models
    groups: dict[str, List[TestRun]] = defaultdict(list)
    for orm in orm_runs:
        run = TestRun(
            test_name=orm.test_name,
            status=orm.status,
            timestamp=orm.timestamp,
            duration_ms=orm.duration_ms,
            error_message=orm.error_message,
            stack_trace=orm.stack_trace,
            commit_sha=orm.commit_sha,
        )
        groups[orm.test_name].append(run)

    summaries: List[FlakyTestSummary] = []
    for test_name, runs in groups.items():
        score = calculate_flakiness_score(runs)
        total = len(runs)
        fail_cnt = sum(1 for r in runs if r.status == "fail")
        # Determine last status based on most recent timestamp
        last_status = max(runs, key=lambda r: r.timestamp).status
        summary = FlakyTestSummary(
            test_name=test_name,
            flakiness_score=score,
            total_runs=total,
            fail_count=fail_cnt,
            last_status=last_status,
        )
        summaries.append(summary)

    # Sort by score descending
    summaries.sort(key=lambda s: s.flakiness_score, reverse=True)
    return summaries
