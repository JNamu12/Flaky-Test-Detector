#!/usr/bin/env bash
# =============================================================================
# tosca_trigger.sh
# =============================================================================
# Triggers a Tosca TestEvent via the Tosca Server Execution API,
# polls for completion, and downloads the JUnit XML results file.
#
# Required environment variables (set these as CI secrets, never hardcode):
#   TOSCA_SERVER_URL      e.g. https://tosca.your-company.com
#   TOSCA_API_TOKEN       Bearer token (Tosca "ToscaCI" API access token)
#   TOSCA_PROJECT_NAME    Tosca project/workspace name
#   TOSCA_EVENT_NAME      Name of the TestEvent to trigger
#
# Optional:
#   TOSCA_POLL_INTERVAL   Seconds between status polls  (default: 15)
#   TOSCA_TIMEOUT         Max seconds to wait           (default: 600)
#   TOSCA_JUNIT_OUT       Output path for JUnit XML     (default: results/tosca_junit.xml)
#
# Exit codes:
#   0  Success – JUnit XML written to TOSCA_JUNIT_OUT
#   1  Missing required environment variable
#   2  Trigger API call failed (network, auth, or TestEvent not found)
#   3  Execution timed out
#   4  Execution completed with status != Passed
# =============================================================================

set -euo pipefail

# ── Helpers ──────────────────────────────────────────────────────────────────

log()  { echo "[tosca] $*" >&2; }
err()  { echo "[tosca][ERROR] $*" >&2; }
die()  { err "$@"; exit "${2:-1}"; }

# ── Validate required env vars ───────────────────────────────────────────────

for var in TOSCA_SERVER_URL TOSCA_API_TOKEN TOSCA_PROJECT_NAME TOSCA_EVENT_NAME; do
  if [[ -z "${!var:-}" ]]; then
    die "Required environment variable '$var' is not set. \
Set it as a repository secret and pass it to this script via the CI environment." 1
  fi
done

POLL_INTERVAL="${TOSCA_POLL_INTERVAL:-15}"
TIMEOUT="${TOSCA_TIMEOUT:-600}"
JUNIT_OUT="${TOSCA_JUNIT_OUT:-results/tosca_junit.xml}"

mkdir -p "$(dirname "$JUNIT_OUT")"

BASE_URL="${TOSCA_SERVER_URL%/}"  # strip trailing slash
AUTH_HEADER="Authorization: Bearer ${TOSCA_API_TOKEN}"
CT_HEADER="Content-Type: application/json"

# ── Step 1: Trigger the TestEvent ────────────────────────────────────────────

log "Triggering TestEvent '${TOSCA_EVENT_NAME}' in project '${TOSCA_PROJECT_NAME}'..."

TRIGGER_URL="${BASE_URL}/rest/toscaci/v1/execution/execute"
TRIGGER_BODY=$(printf '{"projectName":"%s","eventName":"%s"}' \
  "${TOSCA_PROJECT_NAME}" "${TOSCA_EVENT_NAME}")

TRIGGER_RESPONSE=$(curl --silent --show-error --fail-with-body \
  --max-time 30 \
  -X POST \
  -H "${AUTH_HEADER}" \
  -H "${CT_HEADER}" \
  -d "${TRIGGER_BODY}" \
  "${TRIGGER_URL}" 2>&1) || {
  CURL_EXIT=$?
  # Provide targeted error messages for common failure modes
  if echo "${TRIGGER_RESPONSE}" | grep -q "401\|Unauthorized\|Invalid token"; then
    die "Authentication failed. Verify TOSCA_API_TOKEN is a valid ToscaCI API access token." 2
  elif echo "${TRIGGER_RESPONSE}" | grep -q "404\|Not Found\|not found"; then
    die "TestEvent '${TOSCA_EVENT_NAME}' or project '${TOSCA_PROJECT_NAME}' not found. \
Check spelling and confirm the TestEvent is published to the Tosca Server." 2
  elif echo "${TRIGGER_RESPONSE}" | grep -q "403\|Forbidden"; then
    die "Access denied. The token may not have 'Execute' rights on project '${TOSCA_PROJECT_NAME}'." 2
  elif echo "${TRIGGER_RESPONSE}" | grep -q "connection refused\|Could not resolve\|Failed to connect"; then
    die "Cannot reach Tosca Server at '${TOSCA_SERVER_URL}'. Check TOSCA_SERVER_URL and network access." 2
  else
    die "Trigger request failed (curl exit ${CURL_EXIT}). Response: ${TRIGGER_RESPONSE}" 2
  fi
}

# Extract the execution ID from the response
EXEC_ID=$(echo "${TRIGGER_RESPONSE}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
# Field names vary by Tosca Server version
exec_id = data.get('executionId') or data.get('ExecutionId') or data.get('id')
if not exec_id:
    raise SystemExit('Could not parse executionId from trigger response: ' + repr(data))
print(exec_id)
" 2>&1) || die "Could not parse execution ID from trigger response. Raw: ${TRIGGER_RESPONSE}" 2

log "Execution started. ID: ${EXEC_ID}"

# ── Step 2: Poll for completion ───────────────────────────────────────────────

STATUS_URL="${BASE_URL}/rest/toscaci/v1/execution/${EXEC_ID}/status"
ELAPSED=0

log "Polling for completion (timeout: ${TIMEOUT}s, interval: ${POLL_INTERVAL}s)..."

while true; do
  if [[ $ELAPSED -ge $TIMEOUT ]]; then
    die "Timed out after ${TIMEOUT}s waiting for execution '${EXEC_ID}' to complete." 3
  fi

  STATUS_RESPONSE=$(curl --silent --show-error --fail-with-body \
    --max-time 30 \
    -H "${AUTH_HEADER}" \
    "${STATUS_URL}" 2>&1) || {
    err "Status poll failed after ${ELAPSED}s — will retry. Response: ${STATUS_RESPONSE}"
    sleep "${POLL_INTERVAL}"
    ELAPSED=$(( ELAPSED + POLL_INTERVAL ))
    continue
  }

  STATUS=$(echo "${STATUS_RESPONSE}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
status = data.get('status') or data.get('Status') or data.get('executionStatus') or ''
print(status.strip())
" 2>/dev/null || echo "")

  log "  Status after ${ELAPSED}s: '${STATUS}'"

  case "${STATUS}" in
    Completed|Passed|passed|completed|Finished|finished)
      log "Execution completed successfully."
      break
      ;;
    Failed|failed|Error|error)
      # Do NOT exit here — download the JUnit XML so failures are captured by the detector
      log "WARNING: Execution finished with status '${STATUS}'. Downloading results anyway."
      break
      ;;
    Running|running|Queued|queued|Pending|pending|"")
      sleep "${POLL_INTERVAL}"
      ELAPSED=$(( ELAPSED + POLL_INTERVAL ))
      ;;
    *)
      err "Unexpected status '${STATUS}'. Treating as still running and continuing to poll."
      sleep "${POLL_INTERVAL}"
      ELAPSED=$(( ELAPSED + POLL_INTERVAL ))
      ;;
  esac
done

# ── Step 3: Download JUnit XML results ───────────────────────────────────────

RESULTS_URL="${BASE_URL}/rest/toscaci/v1/execution/${EXEC_ID}/results/junit"

log "Downloading JUnit XML from ${RESULTS_URL} ..."

curl --silent --show-error --fail-with-body \
  --max-time 60 \
  -H "${AUTH_HEADER}" \
  -o "${JUNIT_OUT}" \
  "${RESULTS_URL}" || {
  die "Failed to download JUnit XML results for execution '${EXEC_ID}'." 2
}

# Basic sanity check — the file should contain XML
if ! grep -q "<testsuite\|<testsuites" "${JUNIT_OUT}" 2>/dev/null; then
  err "Downloaded file does not look like valid JUnit XML. First 500 chars:"
  head -c 500 "${JUNIT_OUT}" >&2
  die "JUnit XML validation failed. Check Tosca Server JUnit export configuration." 2
fi

log "JUnit XML saved to '${JUNIT_OUT}'."

# Return non-zero if the execution itself failed, so the CI step is marked failed
# while still allowing the downstream ingest step to run via 'if: always()'.
if [[ "${STATUS}" == Failed || "${STATUS}" == failed || "${STATUS}" == Error || "${STATUS}" == error ]]; then
  err "Execution '${EXEC_ID}' completed with failing status '${STATUS}'."
  exit 4
fi

exit 0
