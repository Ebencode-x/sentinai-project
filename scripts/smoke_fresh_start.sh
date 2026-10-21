#!/bin/sh
# Starts SentinAI exactly as a newcomer would (empty database, no .env, no manual
# steps), then proves that the first-run login works and that the data persists
# across a restart.
#
# Usage: scripts/smoke_fresh_start.sh [path-to-python]   (run from the repo root)
set -eu

PY="${1:-python3}"
# Pick a free port so a leftover process can never answer for us.
PORT="${SMOKE_PORT:-$("$PY" -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')}"
WORK="$(mktemp -d)"
LOG="$WORK/server.log"
PID=""

cleanup() {
  [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

fail() { echo "SMOKE FAIL: $1" >&2; echo "--- server log ---" >&2; tail -25 "$LOG" >&2 || true; exit 1; }

start_server() {
  : > "$LOG"
  env -i PATH="$PATH" HOME="$WORK" \
    DATABASE_URL="sqlite:///$WORK/sentinai.db" LOG_FILE_PATH="$WORK/app.log" \
    "$PY" -m uvicorn src.main:app --port "$PORT" > "$LOG" 2>&1 &
  PID=$!
  i=0
  until curl -fs "http://localhost:$PORT/health/live" >/dev/null 2>&1; do
    i=$((i + 1)); [ "$i" -gt 40 ] && fail "server did not become healthy"
    sleep 0.5
  done
  kill -0 "$PID" 2>/dev/null || fail "server process exited (port clash?)"
}

stop_server() { kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; PID=""; }

login() {
  curl -s -X POST "http://localhost:$PORT/api/auth/login" \
    -H 'content-type: application/json' -d "{\"email\":\"$1\",\"password\":\"$2\"}"
}

# 1. Cold start on an empty database.
start_server
EMAIL="$(sed -n 's/.*FIRST-RUN ADMIN LOGIN  email=\([^ ]*\)  password=\([^ ]*\) .*/\1/p' "$LOG" | head -1)"
PASS="$(sed -n 's/.*FIRST-RUN ADMIN LOGIN  email=\([^ ]*\)  password=\([^ ]*\) .*/\2/p' "$LOG" | head -1)"
[ -n "$EMAIL" ] && [ -n "$PASS" ] || fail "first-run credentials were not printed"

# 2. Wrong password is rejected, right one gets a token.
login "$EMAIL" "wrong-password" | grep -q "Invalid email or password" || fail "wrong password was not rejected"
TOKEN="$(login "$EMAIL" "$PASS" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"
[ -n "$TOKEN" ] || fail "login with the printed password failed"

# 3. Protected routes: refused without a token, allowed with one.
CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT/api/incidents")"
[ "$CODE" = "401" ] || fail "protected route answered $CODE without a token"
CODE="$(curl -s -o /dev/null -w '%{http_code}' -H "X-Session-Token: $TOKEN" "http://localhost:$PORT/api/incidents")"
[ "$CODE" = "200" ] || fail "protected route answered $CODE with a valid token"

# 4. Restart: same database, no new secret printed, old password still works.
stop_server
start_server
grep -q "FIRST-RUN ADMIN LOGIN" "$LOG" && fail "first-run password was printed again after restart"
login "$EMAIL" "$PASS" | grep -q '"token"' || fail "login failed after restart (data not persisted)"

echo "smoke_fresh_start: all checks passed"
