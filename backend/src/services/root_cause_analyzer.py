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

=== RULES FOR "explanation" (max 120 words) ===
- Start with the failing STEP name if visible in the error (e.g. "In step loginStep, ...").
- Say WHY this specific error occurs — not just what the error type is called.
- State clearly: is it FLAKY (intermittent, non-deterministic) or a REAL BUG (always fails)?
- Be factual. Only mention what is visible in the error message and stack trace.

=== RULES FOR "suggested_next_step" (max 150 words) ===
- MUST be tailored to the EXACT testing tool (Playwright / Selenium / Tosca / Cypress / Pytest).
- MUST reference the EXACT failing step name and the EXACT selector, URL, or API endpoint from the error.
- MUST include a working code snippet in the correct tool syntax. For example:
    Playwright : await page.locator('#user-avatar').waitFor({ state: 'visible', timeout: 10000 });
    Selenium   : WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'user-avatar')))
    Tosca      : On Module 'UserAvatar', set WaitOn=Enabled and SynchronizationTimeout=10000
- If the error is a NETWORK / HTTP error: suggest adding a retry wrapper or page.route() intercept for that specific endpoint.
- If the error is a SESSION / AUTH error: suggest adding a beforeEach hook to refresh the auth token before that step.
- NEVER say "add a wait" or "check the logs" without specifying EXACTLY where and what to wait for.
- If no selector is visible in the error, say so explicitly and suggest enabling Playwright trace viewer or HAR capture for that step.

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
                f"In {step_label}, the request to `{endpoint}` got an intermittent 503. "
                f"Add a response wait before asserting:\n"
                f"  await page.waitForResponse(\n"
                f"    resp => resp.url().includes('{endpoint.split('/')[-1]}') && resp.status() === 200,\n"
                f"    {{ timeout: 15000 }}\n"
                f"  );\n"
                f"Or mock the endpoint to avoid CI dependency:\n"
                f"  await page.route('**{endpoint}', route => route.fulfill({{ status: 200, body: '{{\"ok\":true}}' }}));"
            )
        elif tool == "Selenium":
            fix = (
                f"In {step_label}, wrap the API call to `{endpoint}` in a retry loop:\n"
                f"  for attempt in range(3):\n"
                f"      try:\n"
                f"          response = requests.get('{endpoint}', timeout=10)\n"
                f"          response.raise_for_status(); break\n"
                f"      except: time.sleep(2)"
            )
        else:
            fix = (
                f"In {step_label}, the endpoint `{endpoint}` returned HTTP 503. "
                f"Add a polling retry with exponential backoff (max 3 attempts, 2s apart) before asserting the response."
            )
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
                f"In {step_label}, replace any `time.sleep()` before{sel_label} with:\n"
                f"  element = WebDriverWait(driver, 10).until(\n"
                f"      EC.element_to_be_clickable((By.CSS_SELECTOR, '{sel_css}'))\n"
                f"  )\n"
                f"  element.click()\n"
                f"This waits until the element is both visible AND clickable, not just present in the DOM."
            )
        elif tool == "Tosca":
            fix = (
                f"In {step_label}{sel_label}, open the Module in Tosca Studio and set:\n"
                f"  WaitOn = Enabled\n"
                f"  SynchronizationTimeout = 10000\n"
                f"This tells Tosca to wait for the control to be ready before executing the action, eliminating the timing race."
            )
        else:
            fix = (
                f"In {step_label}{sel_label}, add an explicit wait for the element to be visible before the action. "
                f"Capture a DOM snapshot and HAR network log at the time of failure to confirm the element state."
            )
        return json.dumps({
            "verdict": "likely_flaky",
            "root_cause_category": "timing/race_condition",
            "explanation": (
                f"In {step_label}, the element{sel_label} was not ready within the timeout. "
                f"This is a classic async race condition — the test tried to interact with the element before "
                f"the page/DOM finished rendering or the animation/overlay settled. Happens intermittently on slower CI runners."
            ),
            "suggested_next_step": fix
        })

    # ── SESSION / AUTH errors ──────────────────────────────────────────────
    if "session_expired" in err_lower or ("login" in err_lower and "redirect" in err_lower) or "auth" in err_lower:
        if tool == "Playwright":
            fix = (
                f"In {step_label}, the test was redirected to /login because the auth session expired. Fix options:\n"
                f"Option A — Refresh cookie in beforeEach:\n"
                f"  test.beforeEach(async ({{ page }}) => {{\n"
                f"    await page.context().addCookies([{{\n"
                f"      name: 'auth_token', value: process.env.AUTH_TOKEN,\n"
                f"      domain: 'yourapp.com', path: '/'\n"
                f"    }}]);\n"
                f"  }});\n"
                f"Option B — Use storageState to reuse authenticated session:\n"
                f"  use: {{ storageState: 'auth-state.json' }}"
            )
        else:
            fix = (
                f"In {step_label}, the auth token expired mid-test. "
                f"Add a setUp() hook that re-authenticates and injects a fresh session cookie before this step runs. "
                f"Also increase the session TTL in the CI test environment config to at least 5 minutes."
            )
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
            fix = (
                f"In {step_label}, the assertion consistently fails. Steps to investigate:\n"
                f"1. Run `npx playwright test --debug` to step through the test interactively.\n"
                f"2. Use `await page.route()` to inspect the actual API response shape:\n"
                f"   await page.route('**/api/**', route => {{ console.log(route.request().url()); route.continue(); }});\n"
                f"3. Check recent commits for changes to the backend response schema or frontend assertion logic."
            )
        elif tool == "Selenium":
            fix = (
                f"In {step_label}, the assertion consistently fails. "
                f"Add `print(driver.find_element(By.CSS_SELECTOR, '{selector or '#element'}').text)` "
                f"to log the actual value, then compare with the expected. "
                f"Check recent commits for changes to the business logic or data model."
            )
        else:
            fix = (
                f"In {step_label}, this is a consistent failure indicating a regression. "
                f"Inspect recent commits for changes to the underlying business logic or data schema. "
                f"Log actual vs expected values in the test output to pinpoint the mismatch."
            )
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
        "temperature": 0.2,    # Low = consistent, precise, not creative/generic
        "max_tokens": 700,     # Enough for step-specific explanation + full code snippet
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
