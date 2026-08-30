"""
junit_xml_to_ingest.py
======================
Convert a JUnit XML report file into the JSON payload expected by
  POST /api/v1/test-runs/ingest

Supports output from:
  - pytest  (--junitxml=report.xml)
  - Playwright/pytest-playwright
  - Playwright Test runner  (--reporter=junit)
  - Selenium + pytest / unittest
  - Any tool producing standard JUnit XML (<testsuite> / <testcase>)

Usage
-----
  python tools/junit_xml_to_ingest.py <path-to-junit.xml> [options]

Options
-------
  --url          Backend ingest URL  (default: http://127.0.0.1:8000/api/v1/test-runs/ingest)
  --commit-sha   Git SHA to attach to every run  (default: current HEAD via git)
  --dry-run      Print the JSON payload but do NOT POST
  --out FILE     Also save the JSON payload to FILE
"""

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def current_git_sha():
    """Return the current HEAD commit SHA, or None if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def parse_duration(time_str):
    """Convert a JUnit 'time' attribute (seconds, float) to milliseconds int."""
    if not time_str:
        return 0
    try:
        return int(float(time_str) * 1000)
    except ValueError:
        return 0


def parse_timestamp(ts_str):
    """
    Parse a JUnit 'timestamp' attribute.
    Falls back to UTC-now if the field is missing or unparseable.
    Returns an ISO-8601 string.
    """
    if not ts_str:
        return datetime.now(timezone.utc).isoformat()
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return datetime.now(timezone.utc).isoformat()


def build_status(testcase_el):
    """
    Return (status, error_message, stack_trace) for a <testcase> element.

    JUnit signals failure with child elements:
      <failure>  - assertion failure
      <error>    - unexpected exception / infrastructure error
      <skipped>  - skipped tests (mapped to pass; adjust if you prefer to omit)
    """
    failure = testcase_el.find("failure")
    error   = testcase_el.find("error")
    skipped = testcase_el.find("skipped")

    if failure is not None:
        msg   = failure.get("message") or failure.text or "Test failure"
        stack = failure.text or None
        return "fail", msg, stack

    if error is not None:
        msg   = error.get("message") or error.text or "Test error"
        stack = error.text or None
        return "fail", msg, stack

    if skipped is not None:
        # Treat skipped as "pass" so ingestion accepts them.
        # Return None, None, None to omit skipped tests entirely.
        return "pass", None, None

    return "pass", None, None


def parse_junit_xml(xml_path, commit_sha):
    """Parse a JUnit XML file and return a list of TestRun dicts."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Handle both <testsuites> (wrapper) and bare <testsuite> roots
    if root.tag == "testsuites":
        suites = list(root.iter("testsuite"))
    elif root.tag == "testsuite":
        suites = [root] + list(root.iter("testsuite"))
    else:
        suites = list(root.iter("testsuite"))

    runs = []
    seen_ids = set()   # deduplicate if nested <testsuite> elements repeat cases

    for suite in suites:
        suite_ts   = suite.get("timestamp")
        suite_name = suite.get("name", "")

        for tc in suite.findall("testcase"):
            classname = tc.get("classname") or suite_name
            name      = tc.get("name", "unknown_test")

            # Build a stable, unique test name: classname::name
            if classname and classname != name and not name.startswith(classname):
                full_name = f"{classname}::{name}"
            else:
                full_name = name

            # Deduplicate
            uid = (full_name, tc.get("time", ""), suite_ts or "")
            if uid in seen_ids:
                continue
            seen_ids.add(uid)

            status, err_msg, stack = build_status(tc)

            # Per-testcase timestamp is rare; fall back to suite timestamp
            tc_ts = tc.get("timestamp") or suite_ts

            runs.append({
                "test_name":     full_name,
                "status":        status,
                "timestamp":     parse_timestamp(tc_ts),
                "duration_ms":   parse_duration(tc.get("time")),
                "error_message": err_msg,
                "stack_trace":   stack,
                "commit_sha":    commit_sha,
            })

    return runs


# ---------------------------------------------------------------------------
# Diagnostics / field-null checker
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["test_name", "status", "timestamp", "duration_ms"]
OPTIONAL_FIELDS = ["error_message", "stack_trace", "commit_sha"]

def diagnose(runs):
    """Print a field-quality report so the user can spot null/malformed values."""
    print("\n" + "=" * 60)
    print(f"  FIELD QUALITY REPORT  ({len(runs)} test run(s) parsed)")
    print("=" * 60)

    issues = []

    for i, r in enumerate(runs):
        label = f"[{i}] {r.get('test_name', '??')}"

        # Required fields must not be None / empty
        for f in REQUIRED_FIELDS:
            v = r.get(f)
            if v is None or v == "":
                issues.append(f"{label}: REQUIRED field '{f}' is null/empty")

        # duration_ms should be a non-negative integer
        dm = r.get("duration_ms")
        if isinstance(dm, int) and dm < 0:
            issues.append(f"{label}: 'duration_ms' is negative ({dm})")

        # status must be exactly 'pass' or 'fail'
        st = r.get("status")
        if st not in ("pass", "fail"):
            issues.append(f"{label}: 'status' is '{st}' -- must be 'pass' or 'fail'")

        # timestamp must be parseable as ISO-8601
        ts = r.get("timestamp", "")
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            issues.append(f"{label}: 'timestamp' is malformed ('{ts}')")

        # fail runs should have error_message
        if st == "fail" and not r.get("error_message"):
            issues.append(f"{label}: status=fail but 'error_message' is null -- "
                          "categorization will be limited")

    # Summary per optional field
    null_counts = {f: sum(1 for r in runs if not r.get(f)) for f in OPTIONAL_FIELDS}
    for f, cnt in null_counts.items():
        pct = (100 * cnt // len(runs)) if runs else 0
        flag = "WARNING" if cnt == len(runs) else "OK"
        print(f"  {flag}  {f:15s}  null in {cnt}/{len(runs)} runs  ({pct}%)")

    if issues:
        print(f"\n  {len(issues)} issue(s) found:\n")
        for msg in issues:
            print(f"     - {msg}")
    else:
        print("\n  OK  No issues found -- all required fields present & valid.")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# HTTP POST
import time

def post_payload(url, payload, api_key=None, max_retries=3):
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            print(f"Posting to {url} (Attempt {attempt}/{max_retries})...")
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read().decode()
                print(f"HTTP {resp.status} -- Response: {body}")
                return
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"HTTP {e.code} -- Error: {body}", file=sys.stderr)
            sys.exit(1)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"Attempt {attempt} failed: {e}. Server may be waking up from sleep.", file=sys.stderr)
            if attempt < max_retries:
                time.sleep(10)
            else:
                print("Max retries reached. Exiting.", file=sys.stderr)
                sys.exit(1)



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Parse a JUnit XML report and POST it to the Flaky Test Detector ingestion endpoint."
    )
    parser.add_argument("xml_file", help="Path to the JUnit XML report file")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/api/v1/test-runs/ingest",
        help="Ingestion endpoint URL (default: %(default)s)",
    )
    parser.add_argument(
        "--commit-sha",
        default=None,
        help="Git commit SHA to attach. Defaults to current HEAD.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the JSON payload but do NOT POST to the server.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to save the generated JSON payload to a file.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API Key for the ingestion endpoint (falls back to API_KEY env var).",
    )
    args = parser.parse_args()

    xml_path = Path(args.xml_file).resolve()
    if not xml_path.exists():
        print(f"File not found: {xml_path}", file=sys.stderr)
        sys.exit(1)

    commit_sha = args.commit_sha or current_git_sha()
    if not commit_sha:
        print("No git repo found and --commit-sha not provided; commit_sha will be null.")

    print(f"Parsing:     {xml_path}")
    print(f"Commit SHA:  {commit_sha or '(null)'}")
    print(f"Endpoint:    {args.url}")

    runs    = parse_junit_xml(xml_path, commit_sha)
    payload = {"runs": runs}

    print(f"Parsed {len(runs)} test run(s).")

    # Always show the field quality report
    diagnose(runs)

    # Pretty-print a sample (first 3)
    sample = runs[:3]
    print("Sample (first 3 runs):")
    print(json.dumps(sample, indent=2, default=str))

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nPayload saved to {out_path}")

    if args.dry_run:
        print("\n[dry-run] Skipping POST.")
        return

    api_key = args.api_key or os.environ.get("API_KEY")

    print(f"\nPOSTing to {args.url} ...")
    post_payload(url=args.url, payload=payload, api_key=api_key)


if __name__ == "__main__":
    main()
