import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional

def parse_duration(time_str: Optional[str]) -> int:
    """Convert a JUnit 'time' attribute (seconds, float) to milliseconds int."""
    if not time_str:
        return 0
    try:
        return int(float(time_str) * 1000)
    except ValueError:
        return 0

def parse_timestamp(ts_str: Optional[str]) -> datetime:
    """Parse a JUnit 'timestamp' attribute to a datetime object."""
    if not ts_str:
        return datetime.now(timezone.utc)
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)

def build_status(testcase_el: ET.Element) -> Tuple[str, Optional[str], Optional[str]]:
    """Return (status, error_message, stack_trace) for a <testcase> element."""
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
        return "pass", None, None

    return "pass", None, None

def parse_junit_xml_bytes(xml_bytes: bytes, commit_sha: Optional[str] = None, source_tool: Optional[str] = None) -> List[Dict]:
    """Parse raw JUnit XML bytes into a list of TestRun dicts."""
    root = ET.fromstring(xml_bytes)

    if root.tag == "testsuites":
        suites = list(root.iter("testsuite"))
    elif root.tag == "testsuite":
        suites = [root] + list(root.iter("testsuite"))
    else:
        suites = list(root.iter("testsuite"))

    runs = []
    seen_ids = set()

    for suite in suites:
        suite_ts   = suite.get("timestamp")
        suite_name = suite.get("name", "")

        for tc in suite.findall("testcase"):
            classname = tc.get("classname") or suite_name
            name      = tc.get("name", "unknown_test")

            if classname and classname != name and not name.startswith(classname):
                full_name = f"{classname}::{name}"
            else:
                full_name = name

            uid = (full_name, tc.get("time", ""), suite_ts or "")
            if uid in seen_ids:
                continue
            seen_ids.add(uid)

            status, err_msg, stack = build_status(tc)
            tc_ts = tc.get("timestamp") or suite_ts

            runs.append({
                "test_name":     full_name,
                "status":        status,
                "timestamp":     parse_timestamp(tc_ts),
                "duration_ms":   parse_duration(tc.get("time")),
                "error_message": err_msg,
                "stack_trace":   stack,
                "commit_sha":    commit_sha,
                "source_tool":   source_tool,
            })

    return runs
