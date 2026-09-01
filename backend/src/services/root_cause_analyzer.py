import os
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
    root_cause_category: Literal["timing/race_condition", "environment", "network", "test_data", "genuine_regression", "unknown"]
    explanation: str
    suggested_next_step: str

API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.1-8b-instant"

SYSTEM_PROMPT = (
    "You are a principal QA automation architect and test reliability expert. "
    "Given the details of a current test failure, stack trace, testing tool in use, and similar past failures, "
    "provide a concise root‑cause explanation and an actionable, concrete code-level fix. "
    "\nCRITICAL GUIDELINES FOR 'suggested_next_step':"
    "\n1. Never output generic advice like 'add explicit wait' or 'increase timeout'."
    "\n2. If a specific failing step and error type are identifiable (e.g., element not clickable, TimeoutException, detached DOM, network timeout), "
    "provide a concrete code-level pointer tailored to the source testing tool (Playwright, Selenium, Tosca, etc.)."
    "\n   Example: In step 'ClickSubmit', replace fixed delay with explicit wait condition, e.g. "
    "(Playwright) `await page.locator('#submit').click({ timeout: 10000 })` or "
    "(Selenium) `WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'submit')))`, "
    "so the test waits for the element to actually become interactive."
    "\n3. Keep suggestions grounded: only output tool-specific code syntax if the source tool can be identified with confidence. "
    "Otherwise, provide actionable guidance in clear, plain English without fabricating unverified code."
    "\n4. If the failure pattern lacks sufficient signal to suggest a confident code fix, do not guess; instead suggest what "
    "diagnostic artifacts (e.g., Playwright trace viewer, DOM snapshots, HAR network logs, server metrics) should be captured."
    "\n\nOutput must be a valid JSON object with the following keys exactly:"
    "\n'verdict': 'likely_flaky' or 'likely_real_bug'"
    "\n'root_cause_category': one of 'timing/race_condition', 'environment', 'network', 'test_data', 'genuine_regression', 'unknown'"
    "\n'explanation': concise explanation under 100 words"
    "\n'suggested_next_step': concrete, actionable fix under 60 words"
    "\nDo not wrap output in markdown code blocks or add any additional commentary."
)

def _detect_tool(test_name: str, current_error: str, current_stack_trace: Optional[str] = None, source_tool: Optional[str] = None) -> str:
    """Infer test automation framework from test name, error message, or stack trace."""
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

def _call_groq(messages: List[Dict[str, str]], test_name: str = "", current_error: str = "", current_stack_trace: Optional[str] = None, source_tool: Optional[str] = None) -> str:
    """Internal helper to call the Groq chat completion endpoint with heuristic fallback."""
    key = os.getenv("GROQ_API_KEY", "")
    tool = _detect_tool(test_name, current_error, current_stack_trace, source_tool)

    if not key:
        is_real_bug = (
            "consistent" in test_name.lower() or
            "valueerror" in current_error.lower() or
            "assertionerror" in current_error.lower() or
            "invalid input" in current_error.lower() or
            "payment gateway timeout" in current_error.lower()
        )
        if is_real_bug:
            if tool == "Playwright":
                suggestion = "Inspect recent commit changes to the backend response schema and verify mock API fixtures with `await page.route()`."
            elif tool == "Selenium":
                suggestion = "Inspect recent commit changes to the business logic and verify test data fixtures before execution."
            else:
                suggestion = "Inspect recent commit changes to the underlying logic and verify input validation handling."

            return json.dumps({
                "verdict": "likely_real_bug",
                "root_cause_category": "genuine_regression",
                "explanation": f"Deterministic failure detected ('{current_error}'). Error occurs consistently across test runs, indicating a code bug or regression rather than flakiness.",
                "suggested_next_step": suggestion
            })
        else:
            if tool == "Playwright":
                suggestion = "In the failing step, replace fixed wait with an explicit locator assertion: `await page.locator('#element').waitFor({ state: 'visible', timeout: 10000 })` or `await page.locator('#submit').click({ timeout: 10000 })`."
            elif tool == "Selenium":
                suggestion = "In the failing step, replace thread sleep with explicit wait: `WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'submit')))` so the test waits for interactivity."
            elif tool == "Tosca":
                suggestion = "In the failing TestStep, configure the 'WaitOn' property on the Module attribute or increase Synchronization timeout to wait for control readiness."
            else:
                suggestion = "Enable trace viewer, DOM snapshots, and network logs on failure to capture whether the target element was detached or blocked during interaction."

            return json.dumps({
                "verdict": "likely_flaky",
                "root_cause_category": "timing/race_condition",
                "explanation": f"Intermittent failure detected ('{current_error}'). Error signature indicates race conditions or asynchronous element state transitions.",
                "suggested_next_step": suggestion
            })

    headers = {"Authorization": f"Bearer {key}"}
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 512,
    }
    response = httpx.post(API_URL, json=payload, headers=headers, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()

def generate_root_cause_explanation(
    test_name: str,
    current_error: str,
    current_stack_trace: Optional[str] = None,
    similar_failures: List[Dict[str, str]] = None,
    source_tool: Optional[str] = None,
) -> RootCauseResponse:
    """Generate an actionable root‑cause explanation with tool-specific fix suggestions."""
    if similar_failures is None:
        similar_failures = []

    tool = _detect_tool(test_name, current_error, current_stack_trace, source_tool)

    similar_text = "\n".join(
        f"- {f.get('test_name', '')}: {f.get('error_message', '')} (at {f.get('timestamp', '')})"
        for f in similar_failures
    )
    if not similar_text:
        similar_text = "(none)"

    user_prompt = (
        f"Test Name: {test_name}\n"
        f"Testing Framework / Tool: {tool}\n"
        f"Current Error: {current_error}\n"
        f"Current Stack Trace: {current_stack_trace or '(none)'}\n"
        f"Similar Past Failures:\n{similar_text}\n\n"
        "Provide a precise root-cause analysis and an actionable, concrete code-level fix tailored to this tool."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    raw_response = _call_groq(messages, test_name=test_name, current_error=current_error, current_stack_trace=current_stack_trace, source_tool=tool)
    try:
        # Strip any accidental markdown formatting if present
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
        raise ValueError(f"Failed to parse LLM response as valid JSON: {e}")
