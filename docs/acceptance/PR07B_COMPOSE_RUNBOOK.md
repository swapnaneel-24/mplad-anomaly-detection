# PR-07B Docker Compose Acceptance Runbook

**Milestone:** PR-07B — Release Candidate Acceptance
**Baseline commit:** `351aded20d4dca1b243f6db6846dcbc22dc6ff33`
**Target environment:** any Docker-equipped environment (Linux with
Docker Engine + Compose v2, or Windows 11 with Docker Desktop)
**Execution owner:** maintainer (the coding AI's sandbox has no
Docker daemon; actual Compose execution is **NOT RUN** by the coding AI).

This runbook is copy-ready and provides **separate** Git Bash and
PowerShell instructions for every shell-specific step. A Bash snippet
does NOT work unchanged in PowerShell and vice versa; the two shells
are clearly distinguished throughout. Every placeholder is either a
safe shell variable (set once at the top of the section and reused) or
an explicit operator-input step marked `[OPERATOR INPUT]`.

---

## 1. Pre-flight checks

### 1.1 Git Bash (Linux, macOS, Windows Git Bash)

```bash
docker version
docker compose version
git status --short
git rev-parse HEAD
```

**Expected:**
- `docker version` → Client + Server sections both present.
- `docker compose version` → Docker Compose v2.x.
- `git status --short` → empty (clean tree).
- `git rev-parse HEAD` → `351aded...` (or the PR-07B verification commit).

### 1.2 PowerShell (Windows 11)

```powershell
docker version
docker compose version
git status --short
git rev-parse HEAD
```

**Expected:** same as §1.1.

If Docker is not available, mark RC-03 NOT RUN and proceed with the
other gates.

---

## 2. Isolated Compose project setup — credential generation

The Compose file (`compose.yaml`) declares `name: peiars` at the top
level. For acceptance, use a uniquely-named disposable project so the
acceptance stack does NOT collide with any existing developer stack.

The `.env.compose` file (gitignored; never committed) supplies
CI-ephemeral credentials. The required secrets (`POSTGRES_PASSWORD`,
`PEIARS_SESSION_SECRET`) use the `:?` substitution form in
`compose.yaml`, so a missing secret fails `docker compose config`
with a clear error rather than silently starting with empty
credentials.

**Important:** the credential generation commands below use shell
command substitution that MUST actually execute at `.env.compose`
write time. Do NOT use a single-quoted heredoc delimiter
(`<<'EOF'`) — that prevents substitution and writes literal
`$(...)` strings into the file.

### 2.1 Git Bash — generate `.env.compose` with random credentials

```bash
# Generate random credentials once; reuse them in the heredoc.
# The unquoted heredoc delimiter (EOF, not 'EOF') allows substitution.
PG_PASS=$(openssl rand -hex 24)
SESSION_SECRET=$(openssl rand -hex 32)
PROJECT_NAME="peiars_pr07b_acceptance_$(date +%s)"

cat > .env.compose <<EOF
# CI-ephemeral values for PR-07B acceptance. NEVER commit this file.
POSTGRES_USER=peiars_app
POSTGRES_PASSWORD=${PG_PASS}
POSTGRES_DB=peiars_review
PEIARS_ENVIRONMENT=development
PEIARS_SESSION_SECRET=${SESSION_SECRET}
PEIARS_SESSION_COOKIE_SECURE=false
PEIARS_DEMONSTRATION_SOURCES=true
PEIARS_CORS_ORIGINS=http://localhost:8080
COMPOSE_PROJECT_NAME=${PROJECT_NAME}
EOF

# Record ONLY the project name (not the secrets) for later use:
echo "Disposable project: ${PROJECT_NAME}"
```

If `openssl` is not available, use `/dev/urandom` directly:

```bash
PG_PASS=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
SESSION_SECRET=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
```

### 2.2 PowerShell — generate `.env.compose` with random credentials

PowerShell does NOT support Bash heredoc syntax. Use the
`Set-Content` cmdlet with an array of strings. Random hex credentials
are generated via `[System.Security.Cryptography.RandomNumberGenerator]`.

```powershell
# Generate random hex credentials using the .NET crypto RNG.
function New-HexSecret($Length) {
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ($bytes | ForEach-Object { $_.ToString("x2") }) -join ''
}

$PgPass = New-HexSecret 24
$SessionSecret = New-HexSecret 32
$ProjectName = "peiars_pr07b_acceptance_$([int][double]::Parse((Get-Date -UFormat %s)))"

$lines = @(
    "# CI-ephemeral values for PR-07B acceptance. NEVER commit this file.",
    "POSTGRES_USER=peiars_app",
    "POSTGRES_PASSWORD=$PgPass",
    "POSTGRES_DB=peiars_review",
    "PEIARS_ENVIRONMENT=development",
    "PEIARS_SESSION_SECRET=$SessionSecret",
    "PEIARS_SESSION_COOKIE_SECURE=false",
    "PEIARS_DEMONSTRATION_SOURCES=true",
    "PEIARS_CORS_ORIGINS=http://localhost:8080",
    "COMPOSE_PROJECT_NAME=$ProjectName"
)

Set-Content -Path .env.compose -Value $lines -Encoding ascii

# Record ONLY the project name (not the secrets) for later use:
Write-Host "Disposable project: $ProjectName"
```

**PowerShell note:** `Set-Content -Encoding ascii` produces LF line
endings on Windows (the `.env.compose` parser accepts both LF and
CRLF). Do NOT use `-Encoding UTF8` with PowerShell 5.x — it adds a
BOM that the Compose env-file parser may reject.

### 2.3 Verify configuration WITHOUT exposing secrets

**Do NOT** run `docker compose config` and read its output — that
command renders the full configuration including all `${VAR}`
substitutions, which would display the generated `POSTGRES_PASSWORD`
and `PEIARS_SESSION_SECRET` in plaintext on the terminal.

Instead, verify the configuration validates by checking the exit code
only, and suppress the output:

#### Git Bash

```bash
# Validate WITHOUT printing secrets: redirect stdout+stderr to /dev/null.
docker compose --env-file .env.compose config >/dev/null 2>&1
echo "config exit code: $?"
```

**Expected:** `config exit code: 0`. If the exit code is non-zero, the
required-secret `:?` substitution has failed — inspect the error
(stderr was suppressed to avoid leaking secrets; re-run WITHOUT
redirection ONLY if you are in a private terminal and intend to
debug).

#### PowerShell

```powershell
# Validate WITHOUT printing secrets: redirect output to $null.
docker compose --env-file .env.compose config *> $null
Write-Host "config exit code: $LASTEXITCODE"
```

**Expected:** `config exit code: 0`.

### 2.4 Record the project name for later teardown

Save the project name (NOT the secrets) in a shell variable for the
teardown step in §3.10:

#### Git Bash

```bash
PROJECT_NAME=$(grep '^COMPOSE_PROJECT_NAME=' .env.compose | cut -d= -f2-)
echo "Project: ${PROJECT_NAME}"
```

#### PowerShell

```powershell
$ProjectName = (Select-String -Path .env.compose -Pattern '^COMPOSE_PROJECT_NAME=').Line.Split('=', 2)[1]
Write-Host "Project: $ProjectName"
```

---

## 3. Compose lifecycle — RC-03 mandatory stages

Every step below is shell-specific. Each step that requires operator
interaction (e.g. recording a case UUID, entering a password in the
browser) is marked `[OPERATOR INPUT]`.

### 3.1 Build backend and frontend images

#### Git Bash

```bash
docker compose --env-file .env.compose build
```

#### PowerShell

```powershell
docker compose --env-file .env.compose build
```

**Expected:** both `backend` and `frontend` images build
successfully. The Dockerfiles are `backend/Dockerfile` and
`frontend/Dockerfile`.

**Security invariant:** no application signing secret or PostgreSQL
password is baked into the images. Secrets come from `.env.compose`
at runtime.

### 3.2 Start PostgreSQL

#### Git Bash

```bash
docker compose --env-file .env.compose up --detach db
docker compose --env-file .env.compose ps db
```

#### PowerShell

```powershell
docker compose --env-file .env.compose up --detach db
docker compose --env-file .env.compose ps db
```

**Expected:** the `db` service (postgres:16-alpine) starts and the
healthcheck (`pg_isready`) transitions to `(healthy)` within ~10
seconds.

### 3.3 Run explicit one-shot Alembic migration

#### Git Bash

```bash
docker compose --env-file .env.compose run --rm migrate
```

#### PowerShell

```powershell
docker compose --env-file .env.compose run --rm migrate
```

**Expected:** Alembic applies all migrations to head (`0001_initial_review_cases`,
`0002_add_event_seq`, `0003_add_users_sessions_auth`). The `migrate`
service is profile-gated so it is NEVER auto-started by
`docker compose up` — it must be invoked explicitly.

### 3.4 Start backend and frontend

#### Git Bash

```bash
docker compose --env-file .env.compose up --detach backend frontend
docker compose --env-file .env.compose ps
```

#### PowerShell

```powershell
docker compose --env-file .env.compose up --detach backend frontend
docker compose --env-file .env.compose ps
```

**Expected:** `db`, `backend`, `frontend` all `(healthy)` (or `Up`
for the frontend, which uses nginx and does not have a healthcheck).

### 3.5 Run the 11-check container smoke test

#### Git Bash

```bash
bash ci/container_smoke_test.sh 8080
```

#### PowerShell

```powershell
# The smoke test is a Bash script; run it via Git Bash or WSL.
bash ci/container_smoke_test.sh 8080
```

**Expected:** all 11 checks pass (exit 0). The script verifies the
documented container contracts through the nginx reverse proxy (the
single browser-visible origin): health endpoints, auth flow, case
creation, case read-back, etc. The script NEVER runs
`docker compose down -v` and NEVER prints the temporary administrator
password.

### 3.6 Create a persisted case through the authenticated application

`[OPERATOR INPUT]` This step requires manual browser interaction.

The temporary administrator password is generated into a shell
variable (NOT printed to the terminal, NOT committed, NOT exposed in
any report). It is copied to the clipboard so the operator can paste
it into the browser login form without it appearing on screen. After
the browser login is complete, the clipboard and the variable are
cleared.

1. Bootstrap an administrator (one-shot, in the running `backend`
   container). Generate a random password, capture it in a shell
   variable, and copy it to the clipboard:

   #### Git Bash

   ```bash
   ADMIN_PASS=$(openssl rand -base64 24)
   docker compose --env-file .env.compose exec backend python -m app.scripts.create_admin \
       --username acceptance-admin \
       --password "${ADMIN_PASS}" \
       --display-name "Acceptance Admin"
   # Copy the password to the clipboard WITHOUT printing it.
   # On Linux Git Bash: use xclip; on Windows Git Bash: use clip.
   if command -v xclip >/dev/null 2>&1; then
     echo -n "${ADMIN_PASS}" | xclip -selection clipboard
   else
     echo -n "${ADMIN_PASS}" | clip
   fi
   echo "Admin username: acceptance-admin (password copied to clipboard — not printed)"
   ```

   #### PowerShell

   ```powershell
   $AdminPass = New-HexSecret 24
   docker compose --env-file .env.compose exec backend python -m app.scripts.create_admin `
       --username acceptance-admin `
       --password $AdminPass `
       --display-name "Acceptance Admin"
   # Copy the password to the clipboard WITHOUT printing it.
   Set-Clipboard -Value $AdminPass
   Write-Host "Admin username: acceptance-admin (password copied to clipboard — not printed)"
   ```

2. Open `http://localhost:8080` in a browser.
3. Log in as `acceptance-admin` — paste the password from the
   clipboard (`Ctrl+V` / `Cmd+V`).
4. Navigate to the Investigation Workspace.
5. Select a synthetic source record (e.g. `synth-001`).
6. Create a review case with title `RC-03 acceptance case`.
7. Add a note `RC-03 persistence note`.
8. `[OPERATOR INPUT]` Record the case UUID from the case detail panel
   (it appears as `Case ID: <uuid>`). Copy it into a shell variable:

   #### Git Bash

   ```bash
   read -p "Paste the case UUID from the browser: " CASE_UUID
   echo "Case UUID: ${CASE_UUID}"
   ```

   #### PowerShell

   ```powershell
   $CaseUuid = Read-Host "Paste the case UUID from the browser"
   Write-Host "Case UUID: $CaseUuid"
   ```

9. After the browser login is complete and the case UUID is recorded,
   clear the password variable and the clipboard:

   #### Git Bash

   ```bash
   unset ADMIN_PASS
   echo -n "" | xclip -selection clipboard 2>/dev/null || echo -n "" | clip
   echo "Admin password variable and clipboard cleared."
   ```

   #### PowerShell

   ```powershell
   Remove-Variable -Name AdminPass
   Set-Clipboard -Value ""
   Write-Host "Admin password variable and clipboard cleared."
   ```

   The `create_admin` CLI does NOT print the password in plaintext
   (the existing `ci/container_smoke_test.sh` verifies this). Note that
   passing `--password` on the `docker compose exec` command line
   exposes the temporary password in process arguments while the
   command runs; this is an acceptable documented limitation for a
   disposable local acceptance account, and both the shell variable
   and clipboard are cleared in step 9.

### 3.7 Restart the backend container — confirm case/event persistence

#### Git Bash

```bash
docker compose --env-file .env.compose restart backend
docker compose --env-file .env.compose ps backend
```

#### PowerShell

```powershell
docker compose --env-file .env.compose restart backend
docker compose --env-file .env.compose ps backend
```

**Expected:** `backend` restarts and returns to `(healthy)` within
~10 seconds.

Verify the case persisted through the backend restart. The
authenticated case/history read requires the session cookie from
§3.6. Use the browser to re-open the case, or use `curl` with the
cookie exported from the browser's DevTools:

#### Git Bash

```bash
# [OPERATOR INPUT] Export the session cookie from the browser DevTools
# (Application → Cookies → peiars_session) into CASE_COOKIE:
read -p "Paste the peiars_session cookie value from the browser: " CASE_COOKIE

# Authenticated case detail — verify the case UUID, title, version:
curl -s -o /dev/null -w "case_detail_status: %{http_code}\n" \
    "http://localhost:8080/api/v1/cases/${CASE_UUID}" \
    -H "Cookie: peiars_session=${CASE_COOKIE}"

# Authenticated case history — verify event count:
HISTORY_BODY=$(curl -s "http://localhost:8080/api/v1/cases/${CASE_UUID}/history" \
    -H "Cookie: peiars_session=${CASE_COOKIE}")
echo "history_total: $(echo "${HISTORY_BODY}" | grep -o '"total":[0-9]*' | head -1)"
```

#### PowerShell

```powershell
# [OPERATOR INPUT] Export the session cookie from the browser DevTools.
$CaseCookie = Read-Host "Paste the peiars_session cookie value from the browser"

# Authenticated case detail:
$detailStatus = (Invoke-WebRequest -Uri "http://localhost:8080/api/v1/cases/$CaseUuid" `
    -Headers @{ "Cookie" = "peiars_session=$CaseCookie" } -UseBasicParsing).StatusCode
Write-Host "case_detail_status: $detailStatus"

# Authenticated case history:
$history = (Invoke-WebRequest -Uri "http://localhost:8080/api/v1/cases/$CaseUuid/history" `
    -Headers @{ "Cookie" = "peiars_session=$CaseCookie" } -UseBasicParsing).Content
Write-Host "history_total: $($history | Select-String -Pattern '"total":(\d+)' | ForEach-Object { $_.Matches[0].Value })"
```

**Expected:** `case_detail_status: 200` and `history_total` ≥ 2
(created + note_added). The case UUID, title, version, status,
record_ref, dataset_id, snapshot_id match what was created in §3.6.

### 3.8 Database outage and recovery — linear sequence

This section exercises the full outage-and-recovery cycle in a single
linear, safe sequence:

1. **Stop** the disposable DB container.
2. **Assert** readiness returns 503 and liveness returns 200 while the
   DB is down.
3. **Start** the DB container.
4. **Bounded-poll** readiness until it returns 200 (or the deadline
   is exceeded, in which case FAIL with a recovery instruction).
5. **Verify** the authenticated case/history from §3.6 are still
   readable after recovery.

Every failure path has an explicit recovery/cleanup instruction. On
explicit assertion failures, the script makes a best-effort attempt
to restart the DB before exiting (note that abrupt shell termination
can still bypass cleanup, in which case run `docker compose --env-file .env.compose start db` manually).

#### Git Bash

```bash
# --- Step 1: stop the disposable DB ---
docker compose --env-file .env.compose stop db

# --- Step 2: assert readiness 503 + liveness 200 while DB is down ---
sleep 1
DOWN_READY=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/api/v1/health/ready")
DOWN_LIVE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/api/v1/health/live")
echo "ready_while_down: ${DOWN_READY}"
echo "live_while_down: ${DOWN_LIVE}"

if [ "${DOWN_READY}" != "503" ]; then
  echo "FAIL: readiness did not return 503 while DB was down (got ${DOWN_READY})"
  echo "RECOVERY: docker compose --env-file .env.compose start db"
  docker compose --env-file .env.compose start db
  exit 1
fi
if [ "${DOWN_LIVE}" != "200" ]; then
  echo "FAIL: liveness was not 200 while DB was down (got ${DOWN_LIVE})"
  echo "RECOVERY: docker compose --env-file .env.compose start db"
  docker compose --env-file .env.compose start db
  exit 1
fi

# --- Step 3: start the DB ---
docker compose --env-file .env.compose start db

# --- Step 4: bounded-poll readiness to 200 (60s deadline, 2s interval) ---
START=$SECONDS
DEADLINE=$((SECONDS + 60))
READY_STATUS=""
while [ "$SECONDS" -lt "$DEADLINE" ]; do
  READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/api/v1/health/ready")
  ELAPSED=$((SECONDS - START))
  echo "ready=${READY_STATUS} (elapsed: ${ELAPSED}s)"
  [ "$READY_STATUS" = "200" ] && break
  sleep 2
done

if [ "$READY_STATUS" != "200" ]; then
  echo "FAIL: readiness did not return 200 within 60s (last status: ${READY_STATUS})"
  echo "RECOVERY: inspect 'docker compose --env-file .env.compose logs db' and 'logs backend';"
  echo "  the DB container is running but readiness did not recover. Do NOT proceed to §3.9."
  exit 1
fi
echo "PASS: readiness recovered to 200"

# --- Step 5: verify authenticated case/history persistence ---
curl -s -o /dev/null -w "case_after_db_restart: %{http_code}\n" \
    "http://localhost:8080/api/v1/cases/${CASE_UUID}" \
    -H "Cookie: peiars_session=${CASE_COOKIE}"

HISTORY_BODY=$(curl -s "http://localhost:8080/api/v1/cases/${CASE_UUID}/history" \
    -H "Cookie: peiars_session=${CASE_COOKIE}")
echo "history_total_after_db_restart: $(echo "${HISTORY_BODY}" | grep -o '"total":[0-9]*' | head -1)"
```

**Expected:** `ready_while_down: 503`, `live_while_down: 200`,
`PASS: readiness recovered to 200`, `case_after_db_restart: 200`,
`history_total_after_db_restart` ≥ 2. No stale `200` is served while
the DB is down.

#### PowerShell

PowerShell's `Invoke-WebRequest` throws a terminating error on HTTP
4xx/5xx by default. The script below uses a helper function
(`Get-HttpStatus`) that catches the error and returns the status code
(e.g. 503) without an uncaught terminating error. Unexpected responses
(e.g. a connection failure that produces no HTTP status) are returned
as `000` and fail the assertion.

```powershell
# Helper: get the HTTP status code without throwing on 4xx/5xx.
function Get-HttpStatus {
    param(
        [string]$Url,
        [hashtable]$Headers = @{}
    )

    try {
        $resp = Invoke-WebRequest -Uri $Url `
            -Headers $Headers `
            -UseBasicParsing `
            -ErrorAction Stop
        return [int]$resp.StatusCode
    } catch [System.Net.Http.HttpRequestException] {
        # Connection failure (no HTTP response at all).
        return 0
    } catch {
        # PowerShell throws on 4xx/5xx; the status code is in the exception.
        if ($_.Exception.Response) {
            return [int]$_.Exception.Response.StatusCode
        }
        return 0
    }
}

# --- Step 1: stop the disposable DB ---
docker compose --env-file .env.compose stop db

# --- Step 2: assert readiness 503 + liveness 200 while DB is down ---
Start-Sleep -Seconds 1
$DownReady = Get-HttpStatus "http://localhost:8080/api/v1/health/ready"
$DownLive = Get-HttpStatus "http://localhost:8080/api/v1/health/live"
Write-Host "ready_while_down: $DownReady"
Write-Host "live_while_down: $DownLive"

if ($DownReady -ne 503) {
    Write-Host "FAIL: readiness did not return 503 while DB was down (got $DownReady)"
    Write-Host "RECOVERY: docker compose --env-file .env.compose start db"
    docker compose --env-file .env.compose start db
    exit 1
}
if ($DownLive -ne 200) {
    Write-Host "FAIL: liveness was not 200 while DB was down (got $DownLive)"
    Write-Host "RECOVERY: docker compose --env-file .env.compose start db"
    docker compose --env-file .env.compose start db
    exit 1
}

# --- Step 3: start the DB ---
docker compose --env-file .env.compose start db

# --- Step 4: bounded-poll readiness to 200 (60s deadline, 2s interval) ---
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$Deadline = $Stopwatch.Elapsed.Add([TimeSpan]::FromSeconds(60))
$ReadyStatus = 0
while ($Stopwatch.Elapsed -lt $Deadline) {
    $ReadyStatus = Get-HttpStatus "http://localhost:8080/api/v1/health/ready"
    $ElapsedSec = [int]$Stopwatch.Elapsed.TotalSeconds
    Write-Host "ready=$ReadyStatus (elapsed: ${ElapsedSec}s)"
    if ($ReadyStatus -eq 200) { break }
    Start-Sleep -Seconds 2
}
$Stopwatch.Stop()

if ($ReadyStatus -ne 200) {
    Write-Host "FAIL: readiness did not return 200 within 60s (last status: $ReadyStatus)"
    Write-Host "RECOVERY: inspect 'docker compose --env-file .env.compose logs db' and 'logs backend';"
    Write-Host "  the DB container is running but readiness did not recover. Do NOT proceed to §3.9."
    exit 1
}
Write-Host "PASS: readiness recovered to 200"

# --- Step 5: verify authenticated case/history persistence ---
$CaseStatus = Get-HttpStatus `
    -Url "http://localhost:8080/api/v1/cases/$CaseUuid" `
    -Headers @{ Cookie = "peiars_session=$CaseCookie" }
Write-Host "case_after_db_restart: $CaseStatus"
if ($CaseStatus -ne 200) {
    throw "Case persistence verification failed: HTTP $CaseStatus"
}

$HistoryResp = Invoke-WebRequest -Uri "http://localhost:8080/api/v1/cases/$CaseUuid/history" `
    -Headers @{ "Cookie" = "peiars_session=$CaseCookie" } -UseBasicParsing
$HistoryTotal = ($HistoryResp.Content | Select-String -Pattern '"total":(\d+)' |
    ForEach-Object { $_.Matches[0].Value })
Write-Host "history_total_after_db_restart: $HistoryTotal"
```

**Expected:** `ready_while_down: 503`, `live_while_down: 200`,
`PASS: readiness recovered to 200`, `case_after_db_restart: 200`,
`history_total_after_db_restart` ≥ 2. No stale `200` is served while
the DB is down.

**Failure recovery summary (both shells):**

| Failure | Recovery |
|---|---|
| Readiness did NOT return 503 while DB was down | The DB may not have stopped fully; wait longer and re-assert. If readiness returns 200 while the DB is stopped, investigate the readiness probe configuration (`backend/app/services/db_readiness.py`). The script auto-starts the DB before exiting so the stack is recoverable. |
| Liveness did NOT return 200 while DB was down | Liveness probes process health only (not DB); if it fails, the backend process may have crashed. Inspect `docker compose --env-file .env.compose logs backend`. The script auto-starts the DB before exiting. |
| Readiness did NOT recover to 200 within 60s | The DB container is running but not accepting connections or migrations are stale. Inspect `docker compose --env-file .env.compose logs db` and `logs backend`. Do NOT proceed to §3.9 until readiness is verified. |
| Case/history not readable after recovery | The volume may have been accidentally removed. Inspect `docker volume ls` for the project's volume; if missing, re-execute from §3.6 (re-create the case). |

### 3.9 Restart the frontend container — confirm browser-facing routes still work

#### Git Bash

```bash
docker compose --env-file .env.compose restart frontend
curl -s -o /dev/null -w "frontend_root: %{http_code}\n" "http://localhost:8080/"
```

#### PowerShell

```powershell
docker compose --env-file .env.compose restart frontend
$status = (Invoke-WebRequest -Uri "http://localhost:8080/" -UseBasicParsing).StatusCode
Write-Host "frontend_root: $status"
```

**Expected:** `frontend_root: 200` (nginx served `index.html`). The
backend API remains reachable through the nginx proxy at
`/api/v1/...`.

### 3.10 Explicit teardown of the disposable project

**Project ownership verification BEFORE any volume removal.** The
script below verifies that the volume it is about to remove belongs
to the disposable project recorded in §2.4 — it does NOT assume a
hardcoded volume name.

#### Git Bash

```bash
# Stop and remove containers + networks (NOT volumes):
docker compose --env-file .env.compose down

# List volumes owned by this project:
PROJECT_VOLUMES=$(docker volume ls --filter "label=com.docker.compose.project=${PROJECT_NAME}" --format '{{.Name}}')
echo "Volumes owned by ${PROJECT_NAME}:"
echo "${PROJECT_VOLUMES}"

# Safety gate: refuse to remove if no volumes match the project label.
if [ -z "${PROJECT_VOLUMES}" ]; then
  echo "FAIL: no volumes found for project '${PROJECT_NAME}' — refuse to remove anything."
  exit 1
fi

# Confirm each volume's project label BEFORE removing:
for vol in ${PROJECT_VOLUMES}; do
  LABEL=$(docker volume inspect "${vol}" --format '{{index .Labels "com.docker.compose.project"}}')
  if [ "${LABEL}" = "${PROJECT_NAME}" ]; then
    echo "Removing volume ${vol} (project: ${LABEL}) — matches disposable project"
    docker volume rm "${vol}"
  else
    echo "SKIP volume ${vol} (project: ${LABEL}) — does NOT match disposable project"
  fi
done
```

#### PowerShell

```powershell
# Stop and remove containers + networks (NOT volumes):
docker compose --env-file .env.compose down

# List volumes owned by this project:
$ProjectVolumes = (docker volume ls --filter "label=com.docker.compose.project=$ProjectName" --format '{{.Name}}')
Write-Host "Volumes owned by $ProjectName:"
Write-Host $ProjectVolumes

# Safety gate: refuse to remove if no volumes match the project label.
if (-not $ProjectVolumes) {
    Write-Host "FAIL: no volumes found for project '$ProjectName' — refuse to remove anything."
    exit 1
}

# Confirm each volume's project label BEFORE removing:
foreach ($vol in ($ProjectVolumes -split "`n")) {
    $vol = $vol.Trim()
    if (-not $vol) { continue }
    $Label = (docker volume inspect $vol --format '{{index .Labels "com.docker.compose.project"}}')
    if ($Label -eq $ProjectName) {
        Write-Host "Removing volume $vol (project: $Label) — matches disposable project"
        docker volume rm $vol
    } else {
        Write-Host "SKIP volume $vol (project: $Label) — does NOT match disposable project"
    }
}
```

**Security invariant:** `docker compose down` (without `-v`) removes
containers and networks but NOT volumes. The explicit
`docker volume rm` above is gated by a project-label check — it only
removes volumes whose `com.docker.compose.project` label matches the
disposable project name from §2.4. An unrelated developer stack's
volume (labelled with a different project name) is NEVER removed.

**NEVER** run `docker compose down -v` against the ordinary
developer stack (`name: peiars`) — that would destroy persisted
investigation data.

### 3.11 Verify no unrelated project/volume was affected

#### Git Bash

```bash
docker volume ls | grep peiars
```

#### PowerShell

```powershell
docker volume ls | Select-String peiars
```

**Expected:** only the disposable `${PROJECT_NAME}_*` volume was
created and removed by this run. Any other `peiars_*` volume belongs
to a separate developer stack and must be untouched.

`[OPERATOR INPUT]` Manually confirm that no unrelated volume (e.g.
`peiars_peiars_pgdata` from the ordinary developer stack) was
removed. If an unrelated volume is missing, STOP and investigate —
do NOT proceed.

---

## 4. Security invariants (per contract §8)

| Invariant | Verification |
|---|---|
| No application signing secret baked into images | PASS — `PEIARS_SESSION_SECRET` comes from `.env.compose` at runtime; the Dockerfiles do not `ENV` any secret |
| No PostgreSQL password baked into images | PASS — `POSTGRES_PASSWORD` comes from `.env.compose` at runtime; `compose.yaml` uses the `:?` substitution form |
| No accidental publication of the database to external interfaces | PASS — the `db` service has no published port by default; only `frontend` publishes host port 8080 |
| Documented loopback binding of the frontend | PASS — `frontend` publishes `127.0.0.1:8080:80` (or `0.0.0.0:8080:80` per the maintainer's `.env.compose`) |
| Same-origin reverse-proxy behavior | PASS — nginx proxies `/api/` to `http://backend:8000` with full header preservation (`frontend/nginx/default.conf`) |
| Browser-visible Host and port when required by Origin validation | PASS — nginx preserves `$http_host` (PR-06B verification) |
| Explicit migration service | PASS — `migrate` is profile-gated; never auto-started by `docker compose up` |
| Project-scoped PostgreSQL storage | PASS — `peiars_pgdata` volume is scoped to the `COMPOSE_PROJECT_NAME` |
| No automatic destructive volume operations | PASS — `docker compose down` (without `-v`) is the default; volume removal is an explicit, project-label-gated action (§3.10) |
| Secrets not displayed through `docker compose config` | PASS — §2.3 redirects config output to `/dev/null` / `$null`; only the exit code is inspected |

---

## 5. Data persistence invariants (per contract §8)

A routine container restart MUST NOT destroy persisted investigation
data. The `peiars_pgdata` volume is a named Docker volume scoped to
the `COMPOSE_PROJECT_NAME`; it survives `docker compose down`,
`docker compose restart`, and host reboots. It is destroyed ONLY by
an explicit, project-label-gated `docker volume rm` (§3.10) or
`docker compose down -v`.

**Acceptance rule:** NEVER use `docker compose down -v` against
persistent developer data. For destructive cleanup, require a clearly
identified disposable project (§2.1/§2.2) and explicit project-label
ownership verification (§3.10) BEFORE the volume removal.

---

## 6. Recording results

For each executed command, record in `PR07B_EVIDENCE_REGISTER.md`:

- The exact command (including `--env-file .env.compose`).
- The shell used (Git Bash or PowerShell).
- The observed stdout / exit code.
- The wall-clock duration.
- The execution timestamp.
- The Docker Engine and Compose versions (`docker version`,
  `docker compose version`).
- The `COMPOSE_PROJECT_NAME` used (must be uniquely identified as
  disposable — record the project name, NOT the secrets).
- The bounded-poll readiness result (PASS/FAIL with the last status
  code and elapsed time).
- The authenticated case/history persistence result (HTTP status +
  event count for each restart scenario).

Mark RC-03 as PASS / FAIL / PARTIAL / NOT RUN in
`PR07B_TEST_MATRIX.md` based on the observed results. The 11-check
container smoke test (`ci/container_smoke_test.sh`) is the primary
gate; the lifecycle stages in §3.1-§3.11 are the supplementary
evidence. Each sub-stage may be marked independently if the
maintainer executes only some of them.
