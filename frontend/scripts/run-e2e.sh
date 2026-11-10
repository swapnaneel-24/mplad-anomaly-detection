#!/usr/bin/env bash
# Run the PEIARS PR-05A E2E suite end-to-end:
#   1. Start a disposable pgserver-backed PostgreSQL.
#   2. Apply migrations.
#   3. Create the synthetic reviewer user.
#   4. Start the FastAPI backend on :8000.
#   5. Start the Vite dev server on :5173.
#   6. Run Playwright E2E tests (with screenshots).
#   7. Tear everything down.
#
# All logs go to /tmp/e2e_*.log. The script exits non-zero on any failure.
set -euo pipefail

REPO=/home/z/my-project/pr05a-work/repo
BACKEND="$REPO/backend"
FRONTEND="$REPO/frontend"
E2E_DIR=/tmp/e2e_run
rm -rf "$E2E_DIR"
mkdir -p "$E2E_DIR"

cd "$BACKEND"
pip install -q -r requirements-lock.txt 2>/dev/null || true

# 1. Start pgserver in background; read the URL it prints.
echo "[e2e] starting pgserver..."
python3 "$FRONTEND/scripts/start-pgserver-e2e.py" > "$E2E_DIR/pg.log" 2>&1 &
PG_PID=$!
echo "[e2e] pgserver PID=$PG_PID"

# Wait for the URL line to appear.
PG_URL=""
for i in $(seq 1 30); do
  if grep -q '^postgresql://' "$E2E_DIR/pg.log" 2>/dev/null; then
    PG_URL=$(grep '^postgresql://' "$E2E_DIR/pg.log" | tail -1)
    break
  fi
  sleep 1
done
if [ -z "$PG_URL" ]; then
  echo "[e2e] ERROR: pgserver did not start"
  cat "$E2E_DIR/pg.log"
  kill $PG_PID 2>/dev/null || true
  exit 1
fi
echo "[e2e] pgserver URL: $PG_URL"

# 2. Apply migrations.
echo "[e2e] applying migrations..."
PEIARS_DATABASE_URL="$PG_URL" PEIARS_DATABASE_REQUIRED=true \
  python3 -c "
from alembic.config import Config
from alembic import command
cfg = Config('alembic.ini')
cfg.set_main_option('script_location', 'migrations')
command.upgrade(cfg, 'head')
print('migrations applied')
" > "$E2E_DIR/migrate.log" 2>&1 || { cat "$E2E_DIR/migrate.log"; kill $PG_PID; exit 1; }

# 3. Create synthetic reviewer.
echo "[e2e] creating reviewer user..."
PEIARS_DATABASE_URL="$PG_URL" \
PEIARS_E2E_USERNAME=reviewer_e2e \
PEIARS_E2E_PASSWORD='test-reviewer-password-1234' \
  python3 "$FRONTEND/playwright/setup-reviewer.py" > "$E2E_DIR/reviewer.log" 2>&1 || { cat "$E2E_DIR/reviewer.log"; kill $PG_PID; exit 1; }
cat "$E2E_DIR/reviewer.log"

# 4. Start backend.
echo "[e2e] starting backend..."
PEIARS_DATABASE_URL="$PG_URL" \
PEIARS_DATABASE_REQUIRED=true \
PEIARS_SESSION_SECRET='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' \
PEIARS_SESSION_COOKIE_SECURE=false \
PEIARS_CORS_ORIGINS='["http://127.0.0.1:5173"]' \
  python3 scripts/serve.py --host 127.0.0.1 --port 8000 > "$E2E_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "[e2e] backend PID=$BACKEND_PID"

# Wait for backend health.
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/v1/health/live >/dev/null 2>&1; then
    echo "[e2e] backend ready"
    break
  fi
  sleep 1
done

# 5. Start Vite.
echo "[e2e] starting vite dev server..."
cd "$FRONTEND"
npm run dev > "$E2E_DIR/vite.log" 2>&1 &
VITE_PID=$!
echo "[e2e] vite PID=$VITE_PID"

for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:5173/ >/dev/null 2>&1; then
    echo "[e2e] vite ready"
    break
  fi
  sleep 1
done

# Sanity: CSRF bootstrap through the proxy.
echo "[e2e] sanity: CSRF bootstrap through proxy..."
curl -sI http://127.0.0.1:5173/api/v1/auth/csrf | head -5 || true

# 6. Run Playwright.
echo "[e2e] running playwright..."
mkdir -p "$FRONTEND/screenshots"
set +e
cd "$FRONTEND"
PEIARS_E2E_USERNAME=reviewer_e2e \
PEIARS_E2E_PASSWORD='test-reviewer-password-1234' \
  npx playwright test --reporter=list 2>&1 | tee "$E2E_DIR/playwright.log"
PW_EXIT=$?
set -e

# 7. Tear down.
echo "[e2e] tearing down..."
kill $VITE_PID 2>/dev/null || true
kill $BACKEND_PID 2>/dev/null || true
kill $PG_PID 2>/dev/null || true
sleep 2

echo "[e2e] playwright exit: $PW_EXIT"
exit $PW_EXIT
