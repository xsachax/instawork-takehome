#!/usr/bin/env bash
#
# Run the whole Quiz Platform with ONE command.
#
# This is the friendly, non-technical entrypoint. It will, in order:
#   1. Set things up the first time (dependencies, database, sample questions).
#   2. Start the backend (API) and the frontend (website) together.
#   3. Open the app in your web browser.
#   4. Shut everything down cleanly when you press Ctrl+C.
#
# Usage:
#   ./start.sh
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
LOG_DIR="$ROOT/.run-logs"
BACKEND_PORT="8000"
FRONTEND_PORT="5173"
BACKEND_URL="http://localhost:$BACKEND_PORT"
FRONTEND_URL="http://localhost:$FRONTEND_PORT"

# ---- pretty output -------------------------------------------------------
if [ -t 1 ]; then
  BOLD="$(printf '\033[1m')"; GREEN="$(printf '\033[32m')"
  YELLOW="$(printf '\033[33m')"; RED="$(printf '\033[31m')"; RESET="$(printf '\033[0m')"
else
  BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi
info()  { printf '%s==>%s %s\n' "$GREEN$BOLD" "$RESET" "$*"; }
warn()  { printf '%s==>%s %s\n' "$YELLOW$BOLD" "$RESET" "$*"; }
error() { printf '%s==>%s %s\n' "$RED$BOLD" "$RESET" "$*" >&2; }

# ---- helpers -------------------------------------------------------------
# Wait until a TCP port is accepting connections (portable, no curl needed).
# Tries both IPv4 and IPv6 loopback, since dev servers may bind either one.
wait_for_port() {
  port="$1"; tries="${2:-60}"
  i=0
  while [ "$i" -lt "$tries" ]; do
    for h in 127.0.0.1 ::1; do
      if (exec 3<>"/dev/tcp/$h/$port") 2>/dev/null; then
        exec 3>&- 3<&- 2>/dev/null || true
        return 0
      fi
    done
    sleep 1
    i=$((i + 1))
  done
  return 1
}

# Is something already listening on this port?
port_in_use() {
  (exec 3<>"/dev/tcp/$1/$2") 2>/dev/null && { exec 3>&- 3<&- 2>/dev/null || true; return 0; }
  return 1
}

open_url() {
  url="$1"
  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  elif command -v wslview >/dev/null 2>&1; then
    wslview "$url" >/dev/null 2>&1 || true
  else
    info "Open your web browser to: $BOLD$url$RESET"
  fi
}

BACK_PID=""
FRONT_PID=""
CLEANED=0
cleanup() {
  [ "$CLEANED" = "1" ] && return 0
  CLEANED=1
  printf '\n'
  info "Stopping the app…"
  [ -n "$FRONT_PID" ] && kill "$FRONT_PID" 2>/dev/null || true
  [ -n "$BACK_PID" ]  && kill "$BACK_PID"  2>/dev/null || true
  wait 2>/dev/null || true
  info "Stopped. See you next time!"
}
trap cleanup INT TERM

# ---- 0. friendly port check ----------------------------------------------
for pp in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if port_in_use "127.0.0.1" "$pp"; then
    error "Port $pp is already in use. Is the app (or something else) already running?"
    error "Close whatever is using port $pp and try again."
    exit 1
  fi
done

# ---- 1. first-run setup ---------------------------------------------------
FIRST_RUN=0
if [ ! -d "$VENV" ] || [ ! -d "$ROOT/frontend/node_modules" ]; then
  FIRST_RUN=1
  info "First run detected — setting things up. This can take a few minutes…"
  if ! bash "$ROOT/setup.sh"; then
    error "Setup did not finish. Please read the messages above and try again."
    exit 1
  fi
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

# Safety net: make sure the database is ready and has questions, even if the
# virtualenv already existed from a previous partial setup.
( cd "$ROOT/backend" && python manage.py migrate >/dev/null 2>&1 ) || true
question_count="$(
  cd "$ROOT/backend" && python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from quiz.models import Question; print(Question.objects.count())" 2>/dev/null || echo 0
)"
if [ "${question_count:-0}" = "0" ]; then
  info "Adding sample questions…"
  ( cd "$ROOT/backend" && python manage.py seed_questions >/dev/null 2>&1 ) || true
fi

# ---- first-run only: offer to create an admin account --------------------
# Admin accounts live in the local database (never in the repo), so a fresh
# clone has none. Offer to create one on the very first run only; afterwards
# use `cd backend && python manage.py createsuperuser`.
if [ "$FIRST_RUN" = "1" ]; then
  has_superuser="$(
    cd "$ROOT/backend" && python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(is_superuser=True).exists())" 2>/dev/null || echo False
  )"
  if [ "$has_superuser" != "True" ]; then
    if [ -t 0 ]; then
      printf '\n'
      info "Optional: create an admin account to manage the question bank."
      printf '%s==>%s Create an admin now? [y/N] ' "$GREEN$BOLD" "$RESET"
      reply=""
      read -r reply || true
      case "$reply" in
        [yY]|[yY][eE][sS])
          ( cd "$ROOT/backend" && python manage.py createsuperuser ) \
            || warn "Admin not created. You can run 'cd backend && python manage.py createsuperuser' later."
          ;;
        *)
          info "Skipped. Create one later with: (cd backend && python manage.py createsuperuser)"
          ;;
      esac
    else
      info "No admin account yet — create one with: (cd backend && python manage.py createsuperuser)"
    fi
  fi
fi

# ---- 2. start both servers ------------------------------------------------
mkdir -p "$LOG_DIR"

info "Starting the backend (API)…"
( cd "$ROOT/backend" && exec python manage.py runserver "$BACKEND_PORT" ) \
  >"$LOG_DIR/backend.log" 2>&1 &
BACK_PID=$!

info "Starting the frontend (website)…"
( cd "$ROOT/frontend" && exec npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort ) \
  >"$LOG_DIR/frontend.log" 2>&1 &
FRONT_PID=$!

# ---- 3. wait until ready, then open the browser --------------------------
info "Waiting for the app to be ready…"
if ! wait_for_port "$BACKEND_PORT" 60; then
  error "The backend did not start. Last lines of $LOG_DIR/backend.log:"
  tail -n 20 "$LOG_DIR/backend.log" >&2 || true
  cleanup
  exit 1
fi
if ! wait_for_port "$FRONTEND_PORT" 60; then
  error "The frontend did not start. Last lines of $LOG_DIR/frontend.log:"
  tail -n 20 "$LOG_DIR/frontend.log" >&2 || true
  cleanup
  exit 1
fi

printf '\n'
info "${BOLD}The Quiz Platform is running!${RESET}"
info "  Website : ${BOLD}$FRONTEND_URL${RESET}   (this is the one to use)"
info "  API     : $BACKEND_URL"
info "Logs are in ${BOLD}.run-logs/${RESET}. Press ${BOLD}Ctrl+C${RESET} to stop."
printf '\n'
open_url "$FRONTEND_URL"

# ---- 4. keep running until Ctrl+C or a server exits ----------------------
while kill -0 "$BACK_PID" 2>/dev/null && kill -0 "$FRONT_PID" 2>/dev/null; do
  sleep 1
done

# If we get here without Ctrl+C, one of the servers stopped on its own.
if [ "$CLEANED" = "0" ]; then
  warn "One of the servers stopped unexpectedly. Check the logs in .run-logs/."
fi
cleanup
