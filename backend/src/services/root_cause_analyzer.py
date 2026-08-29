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
    "You are a senior QA engineer specialized in analyzing flaky test failures. "
    "Given the details of a current test failure and a list of similar past failures, "
    "provide a concise root‑cause explanation and actionable recommendations. "
    "Output must be a JSON object with the following fields exactly: "
    "'verdict' (either 'likely_flaky' or 'likely_real_bug'), "
    "'root_cause_category' (one of 'timing/race_condition', 'environment', 'network', 'test_data', 'genuine_regression', 'unknown'), "
    "'explanation' (a brief explanation under 100 words), "
    "'suggested_next_step' (actionable suggestion under 40 words). "
    "Do not include any additional text or formatting."
)

def _call_groq(messages: List[Dict[str, str]], test_name: str = "", current_error: str = "") -> str:
    """Internal helper to call the Groq chat completion endpoint.

    Returns the assistant's generated content as a string.
    If GROQ_API_KEY is not set, returns a heuristic analysis based on error signature.
    """
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        is_real_bug = (
            "consistent" in test_name.lower() or
            "valueerror" in current_error.lower() or
            "assertionerror" in current_error.lower() or
            "invalid input" in current_error.lower()
        )
        if is_real_bug:
            return json.dumps({
                "verdict": "likely_real_bug",
                "root_cause_category": "genuine_regression",
                "explanation": f"Deterministic failure detected ('{current_error}'). Error occurs consistently across test runs, indicating a code bug or regression rather than flakiness.",
                "suggested_next_step": "Inspect recent commit changes to the underlying logic and verify input validation handling."
            })
        else:
            return json.dumps({
                "verdict": "likely_flaky",
                "root_cause_category": "timing/race_condition",
                "explanation": f"Intermittent failure detected ('{current_error}'). Error signature indicates race conditions or element wait timeouts.",
                "suggested_next_step": "Add explicit element wait conditions or dynamic retry handling to stabilize the test."
            })
    headers = {"Authorization": f"Bearer {key}"}
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
    }
    response = httpx.post(API_URL, json=payload, headers=headers, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    # Groq follows OpenAI schema: choices[0].message.content
    return data["choices"][0]["message"]["content"].strip()

def generate_root_cause_explanation(
    test_name: str,
    current_error: str,
    current_stack_trace: Optional[str] = None,
    similar_failures: List[Dict[str, str]] = None,
) -> RootCauseResponse:
    """Generate a root‑cause explanation for a failing test using Groq LLM.

    Parameters
    ----------
    test_name: str
        Name of the test that failed.
    current_error: str
        The error message of the current failure.
    current_stack_trace: Optional[str]
        Stack trace string of the current failure (if available).
    similar_failures: List[Dict[str, str]]
        A list of dictionaries representing past similar failures. Each dict
        should contain ``test_name``, ``error_message`` and ``timestamp`` keys.

    Returns
    -------
    RootCauseResponse
        Parsed JSON response from the LLM containing verdict, category, explanation, and suggestion.
    """
    if similar_failures is None:
        similar_failures = []

    # Build a human‑readable list of similar failures
    similar_text = "\n".join(
        f"- {f.get('test_name', '')}: {f.get('error_message', '')} (at {f.get('timestamp', '')})"
        for f in similar_failures
    )
    if not similar_text:
        similar_text = "(none)"

    user_prompt = (
        f"Test Name: {test_name}\n"
        f"Current Error: {current_error}\n"
        f"Current Stack Trace: {current_stack_trace or '(none)'}\n"
        f"Similar Past Failures:\n{similar_text}\n"
        "\nProvide a root‑cause analysis and any actionable suggestions."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    raw_response = _call_groq(messages, test_name=test_name, current_error=current_error)
    try:
        parsed = json.loads(raw_response)
        validated = RootCauseResponse(**parsed)
        return validated
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Failed to parse LLM response as valid JSON: {e}")
