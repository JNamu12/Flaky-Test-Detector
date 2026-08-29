import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

# Fixed seed for reproducibility
random.seed(42)

# Configuration
NUM_FLaky = 4
NUM_STABLE_PASS = 12
NUM_CONSISTENT_FAIL = 2
RUNS_PER_FLAKY = 7
RUNS_PER_STABLE = 7
RUNS_PER_FAIL = 4

# Generate test names
flaky_tests = [f"test_flaky_{i+1}" for i in range(NUM_FLaky)]
stable_tests = [f"test_stable_pass_{i+1}" for i in range(NUM_STABLE_PASS)]
fail_tests = [f"test_consistent_fail_{i+1}" for i in range(NUM_CONSISTENT_FAIL)]

# Error patterns for flaky tests (two distinct messages)
flaky_errors = [
    "TimeoutException: element not clickable",
    "StaleElementReferenceException",
    "AssertionError: expected True but got False",
    "ConnectionError: failed to connect to server",
]

# Error message for consistently failing tests
consistent_error = "ValueError: invalid input data"

records = []
current_time = datetime.utcnow()

# Helper to create a single run dict
def make_run(test_name, status, error_msg=None):
    global current_time
    # Increment time a bit for each record
    current_time += timedelta(seconds=random.randint(5, 30))
    return {
        "test_name": test_name,
        "status": status,
        "timestamp": current_time.isoformat() + "Z",
        "duration_ms": random.randint(50, 5000),
        "error_message": error_msg,
        "stack_trace": None,
        "commit_sha": f"{random.getrandbits(160):040x}",
    }

# Generate flaky test runs (alternating pass/fail with recurring errors)
for idx, test_name in enumerate(flaky_tests):
    error_msg = flaky_errors[idx % len(flaky_errors)]
    for i in range(RUNS_PER_FLAKY):
        if i % 2 == 0:  # even index -> pass
            records.append(make_run(test_name, "pass"))
        else:  # odd -> fail with recurring error
            records.append(make_run(test_name, "fail", error_msg))

# Generate stable passing test runs
for test_name in stable_tests:
    for _ in range(RUNS_PER_STABLE):
        records.append(make_run(test_name, "pass"))

# Generate consistently failing test runs
for test_name in fail_tests:
    for _ in range(RUNS_PER_FAIL):
        records.append(make_run(test_name, "fail", consistent_error))

# Shuffle records to simulate realistic ordering
random.shuffle(records)

# Output directory
output_dir = Path(__file__).resolve().parent.parent.parent / "data"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "sample_test_runs.json"

# Write JSON file
with output_path.open("w", encoding="utf-8") as f:
    json.dump(records, f, indent=2)

# Print summary table
summary = Counter((rec["test_name"], rec["status"]) for rec in records)
print("Test Name -> Pass/Fail Counts")
for test_name in sorted({rec["test_name"] for rec in records}):
    passes = summary.get((test_name, "pass"), 0)
    fails = summary.get((test_name, "fail"), 0)
    print(f"{test_name}: {passes} pass / {fails} fail")
