import os
import json
import sys
from pathlib import Path
import httpx

# Paths
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
SAMPLE_DATA_FILE = DATA_DIR / "sample_test_runs.json"
GENERATE_SCRIPT = BASE_DIR / "scripts" / "generate_sample_data.py"

API_BASE = "http://localhost:8000"

def run_generate_data():
    """Execute the sample data generation script."""
    if not GENERATE_SCRIPT.exists():
        print(f"[ERROR] generate_sample_data.py not found at {GENERATE_SCRIPT}")
        sys.exit(1)
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    result = os.system(f"python {GENERATE_SCRIPT}")
    if result != 0:
        print("[ERROR] generate_sample_data.py failed")
        sys.exit(1)
    if not SAMPLE_DATA_FILE.exists():
        print(f"[ERROR] Expected sample data file not found: {SAMPLE_DATA_FILE}")
        sys.exit(1)
    print("[INFO] Sample data generated.")

def ingest_test_runs():
    with open(SAMPLE_DATA_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)
    # The ingest endpoint expects a TestRunBatch structure: {"runs": [...]}
    # Our generator already produces that shape.
    url = f"{API_BASE}/api/v1/test-runs/ingest"
    try:
        resp = httpx.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        print(f"[INFO] Ingest response: {resp.json()}")
    except Exception as e:
        print(f"[ERROR] Ingest request failed: {e}")
        sys.exit(1)

def get_flaky_tests():
    url = f"{API_BASE}/api/v1/flaky-tests"
    try:
        resp = httpx.get(url, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        print("\n=== Ranked Flaky Tests ===")
        for idx, test in enumerate(data, start=1):
            print(f"{idx}. {test['test_name']}: score={test['flakiness_score']:.3f}, total={test['total_runs']}, fails={test['fail_count']}")
        return data
    except Exception as e:
        print(f"[ERROR] Failed to fetch flaky tests: {e}")
        sys.exit(1)

def get_analysis(test_name: str):
    url = f"{API_BASE}/api/v1/flaky-tests/{test_name}/analysis"
    try:
        resp = httpx.get(url, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        analysis = data.get("analysis", {})
        similar = data.get("similar_failures", [])
        print(f"\n=== Analysis for '{test_name}' ===")
        print("Verdict:", analysis.get("verdict"))
        print("Root Cause Category:", analysis.get("root_cause_category"))
        print("Explanation:\n", analysis.get("explanation"))
        print("Suggested Next Step:\n", analysis.get("suggested_next_step"))
        print("\nSimilar Past Failures (most similar first):")
        for idx, entry in enumerate(similar, start=1):
            # entry is expected to contain test_name, error_message, timestamp, score (if vector store returns it)
            print(f"  {idx}. {entry.get('test_name')} @ {entry.get('timestamp')}: {entry.get('error_message')}")
    except Exception as e:
        print(f"[ERROR] Failed to fetch analysis for {test_name}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Step 1: generate sample data
    run_generate_data()
    # Step 2: ingest
    ingest_test_runs()
    # Step 3: list flaky tests
    flaky_tests = get_flaky_tests()
    if not flaky_tests:
        print("[WARN] No flaky tests found.")
        sys.exit(0)
    top_test = flaky_tests[0]["test_name"]
    # Step 4: analysis for top test
    get_analysis(top_test)
