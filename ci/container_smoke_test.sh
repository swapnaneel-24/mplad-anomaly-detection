#!/usr/bin/env bash
# PEIARS container smoke test (PR-06B CI, corrected).
#
# Runs against an already-started Compose stack (db + backend + frontend,
# migrated) and verifies the documented container contracts through the nginx
# reverse proxy (the single browser-visible origin). Designed for the CI
# `container` job: uses a uniquely isolated Compose project name and the same
# .env.compose file every other Compose invocation uses.
#
# Prerequisites:
#   - Docker Engine + Compose v2 available.
#   - .env.compose exists with real (CI-ephemeral) values at the repo root
#     (or at PEIARS_ENV_FILE).
#   - The images are built and the stack is up (db healthy, migrated,
#     backend healthy, frontend up).
#
# Usage (from the repository root):
#   ci/container_smoke_test.sh [FRONTEND_HOST_PORT]
#
# Exit codes:
#   0 — every smoke check passed.
#   1 — one or more checks failed (sanitized details printed).
#
# This script NEVER runs `docker compose down -v` — teardown is the CI
# workflow's responsibility (against the uniquely-named CI project).
# This script NEVER prints the temporary administrator password.
set -euo pipefail

if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1 && python -c 'import sys' >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "ERROR: No working python3 or python interpreter found on PATH." >&2
  exit 1
fi

PORT="${1:-${PEIARS_FRONTEND_PORT:-8080}}"
BASE="http://127.0.0.1:${PORT}"
# Every Compose invocation uses the SAME env file + project name as the
# workflow that started the stack — the exec command needs the substitution
# variables (POSTGRES_PASSWORD etc.) to resolve the Compose config.
ENV_FILE="${PEIARS_ENV_FILE:-.env.compose}"
COMPOSE_PROJECT="${PEIARS_COMPOSE_PROJECT:-peiars}"
COMPOSE="docker compose --env-file ${ENV_FILE} -p ${COMPOSE_PROJECT}"

ADMIN_USER="${PEIARS_SMOKE_USER:-smoke_admin}"
# Ephemeral, run-scoped password. NEVER printed. The create_admin.py CLI
# never displays or logs the password (see its docstring).
ADMIN_PASS="${PEIARS_SMOKE_PASS:-smoke-admin-password-$(date +%s%N)}"

# A real synthetic demonstration record (verified against the synthetic
# source registry). Used for the investigation-write smoke check.
DATASET_ID="synthetic-demonstration"
SNAPSHOT_ID="synthetic-v1"
RECORD_REF="synth-001"

TMP_DIR="$(mktemp -d)"
COOKIE_JAR="${TMP_DIR}/cookies.txt"
PROVISION_LOG="${TMP_DIR}/provision.log"
trap 'rm -rf "${TMP_DIR}"' EXIT

pass=0
fail=0
check() {
  local name="$1" detail="$2" ok="$3"
  if [ "${ok}" = "1" ]; then
    echo "[PASS] ${name}: ${detail}"
    pass=$((pass+1))
  else
    echo "[FAIL] ${name}: ${detail}"
    fail=$((fail+1))
  fi
}

# Extract a cookie value from the curl Netscape-format jar.
cookie_value() {
  local name="$1"
  awk -v n="${name}" '
    { sub(/^#HttpOnly_/, "") }
    $0 !~ /^#/ && NF >= 7 && $6 == n {
      print $7
      exit
    }
  ' "${COOKIE_JAR}" 2>/dev/null
}

echo "=== PEIARS container smoke test (base=${BASE}, project=${COMPOSE_PROJECT}) ==="

# 1. Frontend HTTP response + static index delivery.
status="$(curl -s -o "${TMP_DIR}/index.html" -w '%{http_code}' "${BASE}/" || echo 000)"
check "frontend root" "status=${status}" \
  "$([ "${status}" = "200" ] && grep -q '<div id="root"' "${TMP_DIR}/index.html" && echo 1 || echo 0)"

# 2. Proxy API routing: /api/v1/health/live through nginx.
status="$(curl -s -o /dev/null -w '%{http_code}' "${BASE}/api/v1/health/live" || echo 000)"
check "proxy /api/v1/health/live" "status=${status}" "$([ "${status}" = "200" ] && echo 1 || echo 0)"

# 3. Readiness after migration: /api/v1/health/ready must be 200 with
#    postgresql + migrations checks ready (CONT-06).
status="$(curl -s -o "${TMP_DIR}/ready.json" -w '%{http_code}' "${BASE}/api/v1/health/ready" || echo 000)"
check "proxy /api/v1/health/ready (migrated)" "status=${status}" \
  "$([ "${status}" = "200" ] && grep -q '"status":"ready"' "${TMP_DIR}/ready.json" && echo 1 || echo 0)"

# 4. CSRF bootstrap: GET /api/v1/auth/csrf sets a readable peiars_csrf cookie.
status="$(curl -s -c "${COOKIE_JAR}" -o "${TMP_DIR}/csrf.json" -w '%{http_code}' "${BASE}/api/v1/auth/csrf" || echo 000)"
csrf_token="$("${PYTHON_BIN}" -c "import sys, json; print(json.load(sys.stdin).get('csrf_token',''))" < "${TMP_DIR}/csrf.json" 2>/dev/null || echo '')"
check "CSRF bootstrap" "status=${status}, token_len=${#csrf_token}" \
  "$([ "${status}" = "200" ] && [ -n "${csrf_token}" ] && [ -n "$(cookie_value peiars_csrf)" ] && echo 1 || echo 0)"

# 5. Provision a dedicated smoke-test admin inside the running backend
#    container. Uses -T (noninteractive; no TTY allocation in CI) and the
#    SAME --env-file + project name as the rest of the stack. Failures are
#    NOT suppressed: a provisioning error fails the smoke test with
#    sanitized diagnostics (the password is never printed — create_admin.py
#    does not echo it, and PROVISION_LOG is only printed on failure after
#    explicit password redaction).
echo "--- provisioning smoke admin '${ADMIN_USER}' ---"
if ! ${COMPOSE} exec -T -e PEIARS_BOOTSTRAP_ADMIN_PASSWORD="${ADMIN_PASS}" \
    backend python scripts/create_admin.py --username "${ADMIN_USER}" --display-name "Smoke Admin" \
    >"${PROVISION_LOG}" 2>&1; then
  # Sanitize: redact any line containing the password (defense in depth —
  # create_admin.py never prints it, but never trust blindly).
  redacted="$(grep -v "${ADMIN_PASS}" "${PROVISION_LOG}" 2>/dev/null | head -20)"
  check "provision smoke admin" "create_admin failed (sanitized log follows)" "0"
  echo "--- sanitized provisioning log (password redacted) ---"
  echo "${redacted}"
  exit 1
fi
check "provision smoke admin" "user='${ADMIN_USER}' created (password not printed)" "1"

# 6. Login as the smoke admin → session cookie + ROTATED CSRF token set.
#    Login rotates the CSRF token (session-fixation prevention, auth.py:119).
status="$(curl -s -b "${COOKIE_JAR}" -c "${COOKIE_JAR}" \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: ${csrf_token}" \
  -X POST "${BASE}/api/v1/auth/login" \
  -d "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}" \
  -o "${TMP_DIR}/login.json" -w '%{http_code}' || echo 000)"
# Read the ROTATED csrf token from the cookie jar for subsequent writes.
csrf_token="$(cookie_value peiars_csrf || echo '')"
session_value="$(cookie_value peiars_session)"
session_ok=0

if [ -n "${session_value}" ]; then
  session_ok=1
fi
check "admin login (CSRF-validated)" "status=${status}, session=${session_ok}, rotated_csrf_len=${#csrf_token}" \
  "$([ "${status}" = "200" ] && [ "${session_ok}" = "1" ] && [ -n "${csrf_token}" ] && echo 1 || echo 0)"

# 7. Authenticated read: GET /api/v1/sources (synthetic records, CONT-14).
status="$(curl -s -b "${COOKIE_JAR}" -o "${TMP_DIR}/sources.json" -w '%{http_code}' "${BASE}/api/v1/sources" || echo 000)"
sources_count="$("${PYTHON_BIN}" -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('sources',[])))" < "${TMP_DIR}/sources.json" 2>/dev/null || echo '?')"
check "authenticated GET /api/v1/sources" "status=${status}, sources=${sources_count}" \
  "$([ "${status}" = "200" ] && [ "${sources_count}" != "0" ] && [ "${sources_count}" != "?" ] && echo 1 || echo 0)"

# 8. Authenticated PostgreSQL-backed WRITE: POST /api/v1/cases (real DB
#    write — not just a source listing). Uses a real synthetic record_ref.
status="$(curl -s -b "${COOKIE_JAR}" -o "${TMP_DIR}/case.json" -w '%{http_code}' \
  -H "Content-Type: application/json" -H "X-CSRF-Token: ${csrf_token}" \
  -X POST "${BASE}/api/v1/cases" \
  -d "{\"dataset_id\":\"${DATASET_ID}\",\"snapshot_id\":\"${SNAPSHOT_ID}\",\"record_ref\":\"${RECORD_REF}\",\"title\":\"Smoke audit case\",\"created_by\":\"${ADMIN_USER}\"}" \
  || echo 000)"
case_id="$("${PYTHON_BIN}" -c "import sys, json; print(json.load(sys.stdin).get('id',''))" < "${TMP_DIR}/case.json" 2>/dev/null || echo '')"
check "authenticated POST /cases (DB write)" "status=${status}, case_id=${case_id}" \
  "$([ "${status}" = "201" ] && [ -n "${case_id}" ] && echo 1 || echo 0)"

# 9. Authenticated READ of the written record: GET /api/v1/cases/{id}.
if [ -n "${case_id}" ]; then
  status="$(curl -s -b "${COOKIE_JAR}" -o "${TMP_DIR}/case_read.json" -w '%{http_code}' "${BASE}/api/v1/cases/${case_id}" || echo 000)"
  read_title="$("${PYTHON_BIN}" -c "import sys, json; print(json.load(sys.stdin).get('title',''))" < "${TMP_DIR}/case_read.json" 2>/dev/null || echo '')"
  check "authenticated GET /cases/{id} (read-back)" "status=${status}, title='${read_title}'" \
    "$([ "${status}" = "200" ] && [ "${read_title}" = "Smoke audit case" ] && echo 1 || echo 0)"
else
  check "authenticated GET /cases/{id} (read-back)" "skipped (no case_id)" "0"
fi

# 10. CSRF-invalid write rejected (CONT-15): POST /api/v1/auth/logout with a
#     bogus CSRF token must be 403 (not 200).
status="$(curl -s -b "${COOKIE_JAR}" -H 'Content-Type: application/json' -H 'X-CSRF-Token: INVALID' \
  -X POST "${BASE}/api/v1/auth/logout" -o /dev/null -w '%{http_code}' || echo 000)"
check "CSRF-invalid write rejected" "status=${status} (expect 403)" \
  "$([ "${status}" = "403" ] && echo 1 || echo 0)"

# 11. Logout (valid CSRF).
status="$(curl -s -b "${COOKIE_JAR}" -H 'Content-Type: application/json' -H "X-CSRF-Token: ${csrf_token}" \
  -X POST "${BASE}/api/v1/auth/logout" -o /dev/null -w '%{http_code}' || echo 000)"
check "logout (valid CSRF)" "status=${status} (expect 200 or 204)" \
  "$([ "${status}" = "200" ] || [ "${status}" = "204" ] && echo 1 || echo 0)"

echo
echo "=== smoke summary: ${pass} passed, ${fail} failed ==="
exit $([ "${fail}" = "0" ] && echo 0 || echo 1)
