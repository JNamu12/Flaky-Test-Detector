import os
import re
from typing import List, Dict, Optional, Literal
import json

import httpx
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# Load environment variables from .env (project root .env.example is a template)
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


class RootCauseResponse(BaseModel):
    verdict: Literal["likely_flaky", "likely_real_bug"]
    root_cause_category: Literal[
        "timing/race_condition", "environment", "network",
        "test_data", "genuine_regression", "unknown"
    ]
    explanation: str
    suggested_next_step: str


API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.1-8b-instant"

# ---------------------------------------------------------------------------
# SYSTEM PROMPT — instructs Groq Llama 3 to be step-specific and crystal clear
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a senior QA automation engineer reviewing a failing test report for a colleague.
Your job: explain EXACTLY what failed and give a SPECIFIC, COPY-PASTE ready fix.
Write as if you are sitting next to a junior QA engineer and walking them through it step by step.

=== RULES FOR "explanation" (MAX 40 WORDS) ===
- Start with the failing STEP name if in the error (e.g. "In loginStep, ...").
- One sentence: WHY did it fail? Is it FLAKY (intermittent) or a REAL BUG (always fails)?
- No filler words.

=== RULES FOR "suggested_next_step" (MAX 50 WORDS + 1 CODE LINE) ===
- One clear action sentence + one code snippet. Nothing else.
- Use the EXACT tool syntax (Playwright / Selenium / Tosca).
- Reference the EXACT step name and selector/endpoint from the error.
- Example output: "In loginStep, wait for #user-avatar before asserting:\n  await page.locator('#user-avatar').waitFor({ state: 'visible', timeout: 8000 });"
- If no selector visible: say so in one line and suggest enabling trace viewer.

=== OUTPUT FORMAT ===
Output ONLY a valid JSON object. No markdown. No backticks. No extra text. Keys must be exactly:
  "verdict"             : "likely_flaky" or "likely_real_bug"
  "root_cause_category" : one of "timing/race_condition", "environment", "network", "test_data", "genuine_regression", "unknown"
  "explanation"         : string (plain English, max 120 words)
  "suggested_next_step" : string (concrete fix with code, max 150 words)
"""


# ---------------------------------------------------------------------------
# Helper: extract failing step name from error message / stack trace
# ---------------------------------------------------------------------------
def _extract_step_name(error_msg: str, stack_trace: Optional[str]) -> str:
    combined = f"{error_msg} {stack_trace or ''}"
    # Match "(step: loginStep)" pattern from our demo tests
    m = re.search(r'\(step:\s*([\w]+)\)', combined)
    if m:
        return m.group(1)
    # Match "at FunctionName (tests/..."
    m2 = re.search(r'\bat\s+([\w][\w_]+)\s+\(', combined)
    if m2:
        return m2.group(1)
    return ""


# ---------------------------------------------------------------------------
# Helper: extract element selector or HTTP endpoint from error message
# ---------------------------------------------------------------------------
def _extract_selector(error_msg: str) -> str:
    # HTTP endpoint e.g. "POST /api/v1/payments/submit"
    ep = re.search(r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[\w/\-\.]+)', error_msg)
    if ep:
        return ep.group(0)[:100]
    # CSS / locator patterns
    sel = re.search(r'(?:Selector:\s*|locator\(["\'])([\w#.\[\]=\-\'"@ ]+)', error_msg)
    if sel:
        return sel.group(1).strip()[:100]
    # Quoted ID-like selector
    sel2 = re.search(r'["\']([#.][^"\']+)["\']', error_msg)
    if sel2:
        return sel2.group(1)[:100]
    return ""


# ---------------------------------------------------------------------------
# Helper: detect testing framework
# ---------------------------------------------------------------------------
def _detect_tool(
    test_name: str,
    current_error: str,
    current_stack_trace: Optional[str] = None,
    source_tool: Optional[str] = None,
) -> str:
    if source_tool and source_tool.lower() not in ("unknown", "none", ""):
        return source_tool
    combined = f"{test_name} {current_error} {current_stack_trace or ''}".lower()
    if "playwright" in combined or ".spec." in combined or "locator" in combined or "page." in combined:
        return "Playwright"
    if "selenium" in combined or "webdriver" in combined or "staleelement" in combined or "nosuchelement" in combined:
        return "Selenium"
    if "tosca" in combined or "tbox" in combined or "executionentry" in combined:
        return "Tosca"
    if "cypress" in combined or "cy." in combined:
        return "Cypress"
    if "pytest" in combined or "assert" in combined or "test_" in combined:
        return "Pytest / Python"
    return "Generic"


# ---------------------------------------------------------------------------
# Heuristic fallback — step-aware and error-type-aware (used when no API key)
# ---------------------------------------------------------------------------
def _heuristic_fallback(
    test_name: str,
    current_error: str,
    current_stack_trace: Optional[str],
    tool: str,
) -> str:
    step = _extract_step_name(current_error, current_stack_trace)
    selector = _extract_selector(current_error)
    step_label = f"step '{step}'" if step else "the failing step"
    sel_label = f" on `{selector}`" if selector else ""

    err_lower = current_error.lower()

    # ── NETWORK errors ─────────────────────────────────────────────────────
    if "503" in current_error or "econnreset" in err_lower or "networkError" in current_error:
        endpoint = selector or "/api/v1/..."
        if tool == "Playwright":
            fix = (
                f"In {step_label}, mock the flaky endpoint to avoid CI dependency:\n"
                f"  await page.route('**{selector or '/api/v1/...'}', route => route.fulfill({{ status: 200, body: '{{\"ok\":true}}' }}));"
            )
        elif tool == "Selenium":
            fix = (
                f"In {step_label}, retry the call to `{selector or endpoint}` up to 3 times with 2s backoff before asserting."
            )
        else:
            fix = f"In {step_label}, add a retry (max 3, 2s delay) for `{selector or 'the endpoint'}` before asserting."
        return json.dumps({
            "verdict": "likely_flaky",
            "root_cause_category": "network",
            "explanation": (
                f"In {step_label}, a transient HTTP 503 or connection reset occurred{sel_label}. "
                f"The backend service was temporarily overloaded on this CI run. "
                f"This is NOT a code bug — it is an environment/infrastructure flakiness issue that disappears on retry."
            ),
            "suggested_next_step": fix
        })

    # ── TIMEOUT / DETACHED DOM ─────────────────────────────────────────────
    if "timeout" in err_lower or "not visible" in err_lower or "detached" in err_lower:
        if tool == "Playwright":
            loc = f"page.locator('{selector}')" if selector else "page.locator('#target-element')"
            fix = (
                f"In {step_label}, before interacting{sel_label}, add an explicit visibility wait:\n"
                f"  await {loc}.waitFor({{ state: 'visible', timeout: 10000 }});\n"
                f"If the element detaches due to a React re-render, assert it is stable first:\n"
                f"  await expect({loc}).toBeVisible();\n"
                f"  await {loc}.click();\n"
                f"Enable `--trace on` in CI to capture a DOM snapshot and network waterfall at the point of failure."
            )
        elif tool == "Selenium":
            sel_css = selector or '#target-element'
            fix = (
                f"In {step_label}, replace sleep with:\n"
                f"  WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '{sel_css}')))"
            )
        elif tool == "Tosca":
            fix = f"In {step_label}{sel_label}, set WaitOn=Enabled and SynchronizationTimeout=10000 in Tosca Studio."
        else:
            fix = f"In {step_label}, add an explicit wait for {selector or 'the element'} to be visible, then run with --trace on."
        return json.dumps({
            "verdict": "likely_flaky",
            "root_cause_category": "timing/race_condition",
            "explanation": (
                f"In {step_label}, {selector or 'the element'} was not ready within the timeout — "
                f"async race condition. Happens intermittently on CI runners."
            ),
            "suggested_next_step": fix
        })

    # ── SESSION / AUTH errors ──────────────────────────────────────────────
    if "session_expired" in err_lower or ("login" in err_lower and "redirect" in err_lower) or "auth" in err_lower:
        if tool == "Playwright":
            fix = (
                f"In {step_label}, refresh auth before this step:\n"
                f"  test.beforeEach(async ({{ page }}) => {{ await page.context().addCookies([{{ name: 'auth_token', value: process.env.AUTH_TOKEN, domain: 'yourapp.com', path: '/' }}]); }});"
            )
        else:
            fix = f"In {step_label}, re-authenticate in setUp() before this step or extend session TTL in CI config."
        return json.dumps({
            "verdict": "likely_flaky",
            "root_cause_category": "environment",
            "explanation": (
                f"In {step_label}, the test was redirected to /login with reason=session_expired. "
                f"The CI runner was slow to start, causing the auth token to expire before the assertion was reached. "
                f"This is environment-level flakiness — not a code bug."
            ),
            "suggested_next_step": fix
        })

    # ── REAL BUG (consistent assertion failure) ───────────────────────────
    is_real_bug = (
        "assertionerror" in err_lower and
        "session_expired" not in err_lower and
        "http 503" not in err_lower and
        "timeout" not in err_lower
    )
    if is_real_bug:
        if tool == "Playwright":
            fix = f"Run with --debug to step through. Check recent commits for schema changes around {step_label}."
        elif tool == "Selenium":
            fix = f"Log actual value: print(driver.find_element(By.CSS_SELECTOR, '{selector or '#element'}').text). Check recent commits."
        else:
            fix = f"In {step_label}, compare actual vs expected in logs. Check recent commits for logic or data model changes."
        return json.dumps({
            "verdict": "likely_real_bug",
            "root_cause_category": "genuine_regression",
            "explanation": (
                f"In {step_label}, the assertion consistently fails — the actual value does not match the expected value. "
                f"This is a deterministic failure, meaning a real code regression was introduced, not an intermittent environment issue."
            ),
            "suggested_next_step": fix
        })

    # ── GENERIC fallback ───────────────────────────────────────────────────
    return json.dumps({
        "verdict": "likely_flaky",
        "root_cause_category": "unknown",
        "explanation": (
            f"In {step_label}, the test failed with an unclassified error. "
            f"There is insufficient signal from a single run to pinpoint the root cause."
        ),
        "suggested_next_step": (
            f"In {step_label}, enable full diagnostics on the next run:\n"
            f"  npx playwright test --trace on\n"
            f"This captures a DOM snapshot, console logs, and network HAR at the exact point of failure, "
            f"making root cause identification much faster."
        )
    })


# ---------------------------------------------------------------------------
# Call Groq Cloud API
# ---------------------------------------------------------------------------
def _call_groq(
    messages: List[Dict[str, str]],
    test_name: str = "",
    current_error: str = "",
    current_stack_trace: Optional[str] = None,
    source_tool: Optional[str] = None,
) -> str:
    key = os.getenv("GROQ_API_KEY", "")
    tool = _detect_tool(test_name, current_error, current_stack_trace, source_tool)

    if not key:
        return _heuristic_fallback(test_name, current_error, current_stack_trace, tool)

    headers = {"Authorization": f"Bearer {key}"}
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.1,    # Very low = consistent, deterministic, no fluff
        "max_tokens": 300,     # Short & sharp — one explanation + one code line
    }
    response = httpx.post(API_URL, json=payload, headers=headers, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def generate_root_cause_explanation(
    test_name: str,
    current_error: str,
    current_stack_trace: Optional[str] = None,
    similar_failures: List[Dict[str, str]] = None,
    source_tool: Optional[str] = None,
) -> RootCauseResponse:
    """Generate a step-specific, actionable root-cause explanation with tool-tailored code fix."""
    if similar_failures is None:
        similar_failures = []

    tool = _detect_tool(test_name, current_error, current_stack_trace, source_tool)
    step = _extract_step_name(current_error, current_stack_trace)
    selector = _extract_selector(current_error)

    similar_text = "\n".join(
        f"- {f.get('test_name', '')}: {f.get('error_message', '')} (at {f.get('timestamp', '')})"
        for f in similar_failures
    )
    if not similar_text:
        similar_text = "(none — first occurrence of this failure)"

    user_prompt = (
        f"Test Name: {test_name}\n"
        f"Testing Framework / Tool: {tool}\n"
        f"Failing Step (extracted from error): {step or '(step name not explicitly in error)'}\n"
        f"Element / Endpoint Involved: {selector or '(not explicitly mentioned in error)'}\n"
        f"Current Error Message: {current_error}\n"
        f"Current Stack Trace:\n{current_stack_trace or '(none provided)'}\n\n"
        f"Similar Past Failures in This Test (from vector search):\n{similar_text}\n\n"
        "Instructions:\n"
        "1. Identify the EXACT step, the EXACT element or endpoint, and the EXACT error type from the error message above.\n"
        "2. In 'explanation': state in plain English what went wrong in that specific step and WHY it is flaky or a real bug.\n"
        "3. In 'suggested_next_step': give a CONCRETE, copy-paste ready fix using the correct syntax for this tool. "
        "Reference the exact step name and selector/endpoint. Never give generic advice.\n"
        "4. If similar past failures exist, mention whether the error pattern is repeating at the same step or changing.\n"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw_response = _call_groq(
        messages,
        test_name=test_name,
        current_error=current_error,
        current_stack_trace=current_stack_trace,
        source_tool=tool,
    )

    try:
        clean_json = raw_response.strip()
        if clean_json.startswith("```"):
            clean_json = clean_json.split("```")[1]
            if clean_json.startswith("json"):
                clean_json = clean_json[4:]
            clean_json = clean_json.strip()
        parsed = json.loads(clean_json)
        validated = RootCauseResponse(**parsed)
        return validated
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(
            f"Failed to parse LLM response as valid JSON: {e}. "
            f"Raw response (first 400 chars): {raw_response[:400]}"
        )
