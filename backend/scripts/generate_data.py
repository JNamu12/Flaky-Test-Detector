import os
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
import uuid

# Set reproducible seed
random.seed(42)

# Base directory for output
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "generated_test_runs.json"

# ---------------------------------------------------------------------------
# Helper to create timestamps
# ---------------------------------------------------------------------------
def rand_time(base: datetime, i: int) -> str:
    """Return an ISO‑8601 timestamp offset by ~i*3 hours from *base*.
    Adds a random jitter of up to ±30 minutes to make the series look
    more realistic.
    """
    jitter_minutes = random.randint(-30, 30)
    delta = timedelta(hours=3 * i, minutes=jitter_minutes)
    ts = base + delta
    return ts.isoformat()

# ---------------------------------------------------------------------------
# Test name groups
# ---------------------------------------------------------------------------
flaky_tests = {
    "test_login_flaky": [
        "TimeoutException: element not clickable at point (100, 200)",
        "StaleElementReferenceException: element is not attached to the page document",
    ],
    "test_search_flaky": [
        "TimeoutError: waiting for selector \"#search\" failed: timeout 5000ms exceeded",
        "ElementClickInterceptedException: element click intercepted by overlay",
    ],
    "test_payment_flaky": [
        "TimeoutException: element not clickable at point (300, 400)",
        "StaleElementReferenceException: element is not attached to the page document",
    ],
    "test_profile_update_flaky": [
        "TimeoutError: waiting for selector \"#save\" failed: timeout 5000ms exceeded",
        "ElementClickInterceptedException: element click intercepted by overlay",
    ],
}

stable_pass_tests = [
    f"test_stable_pass_{i}" for i in range(1, 13)
]

real_bug_tests = {
    "test_data_corruption": "AssertionError: Expected non‑null data but got None",
    "test_api_contract": "AssertionError: Response JSON mismatches contract",
}

# ---------------------------------------------------------------------------
# Generate runs
# ---------------------------------------------------------------------------
runs = []
base_time = datetime.utcnow()
run_index = 0

# Flaky tests – alternate pass/fail, use random template when failing
for test_name, error_templates in flaky_tests.items():
    # generate 9‑12 runs per flaky test
    num_runs = random.randint(9, 12)
    for _ in range(num_runs):
        # weighted status: ~55% pass, 45% fail
        status = "pass" if random.random() < 0.55 else "fail"
        error_msg = None
        stack_trace = None
        if status == "fail":
            error_msg = random.choice(error_templates)
            # fake stack trace referencing the test name and a random line number
            line_no = random.randint(10, 250)
            stack_trace = f"File \"{test_name}.py\", line {line_no}, in {test_name}\n    {error_msg}"
        run = {
            "id": run_index,
            "test_name": test_name,
            "status": status,
            "timestamp": rand_time(base_time, run_index),
            "duration_ms": random.randint(800, 4200),
            "error_message": error_msg,
            "stack_trace": stack_trace,
            "commit_sha": ''.join(random.choices('0123456789abcdef', k=7)),
        }
        runs.append(run)
        run_index += 1

# Stable pass tests – always pass
for test_name in stable_pass_tests:
    # generate 8‑11 runs with ~95% pass / 5% fail
    num_runs = random.randint(8, 11)
    for _ in range(num_runs):
        if random.random() < 0.95:
            status = "pass"
            error_msg = None
            stack = None
        else:
            status = "fail"
            error_msg = "unexpected value in one‑off environment hiccup"
            stack = f"File \"{test_name}.py\", line {random.randint(10,250)}, in {test_name}\n    {error_msg}"
        run = {
            "id": run_index,
            "test_name": test_name,
            "status": status,
            "timestamp": rand_time(base_time, run_index),
            "duration_ms": random.randint(800, 4200),
            "error_message": error_msg,
            "stack_trace": stack,
            "commit_sha": ''.join(random.choices('0123456789abcdef', k=7)),
        }
        runs.append(run)
        run_index += 1

# Real‑bug tests – always fail with the fixed assertion message
for test_name, fixed_msg in real_bug_tests.items():
    # generate 8‑10 runs, all failures with the fixed message
    num_runs = random.randint(8, 10)
    for _ in range(num_runs):
        run = {
            "id": run_index,
            "test_name": test_name,
            "status": "fail",
            "timestamp": rand_time(base_time, run_index),
            "duration_ms": random.randint(800, 4200),
            "error_message": fixed_msg,
            "stack_trace": f"File \"{test_name}.py\", line {random.randint(10,250)}, in {test_name}\n    {fixed_msg}",
            "commit_sha": ''.join(random.choices('0123456789abcdef', k=7)),
        }
        runs.append(run)
        run_index += 1

# ---------------------------------------------------------------------------
# Write output – structure matches the expected TestRunBatch schema
# ---------------------------------------------------------------------------
sorted_runs = sorted(runs, key=lambda r: r["timestamp"])

# Prepare output matching the TestRunBatch schema
output = {"runs": sorted_runs}

# Write to the sample file used by other scripts
SAMPLE_OUTPUT = DATA_DIR / "sample_test_runs.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)
with open(SAMPLE_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

# Summary table
summary = {}
for run in sorted_runs:
    name = run["test_name"]
    status = run["status"]
    if name not in summary:
        summary[name] = {"pass": 0, "fail": 0}
    summary[name]["pass" if status == "pass" else "fail"] += 1

print("\n=== Test Run Summary ===")
print(f"{'Test Name':<30} {'Pass':>6} {'Fail':>6}")
print('-' * 44)
for name, counts in sorted(summary.items()):
    print(f"{name:<30} {counts['pass']:>6} {counts['fail']:>6}")

print(f"\nGenerated {len(sorted_runs)} synthetic test‑run records → {SAMPLE_OUTPUT}")
