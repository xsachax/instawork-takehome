#!/usr/bin/env bash
#
# One-command setup for the Quiz Platform (non-admin).
#
# Sets up everything a regular user needs to run the app locally:
#   - a Python virtual environment + backend dependencies
#   - database migrations
#   - a seeded question bank (only if empty)
#   - frontend dependencies
#
# It does NOT create a Django admin/superuser account (that is optional and
# only needed to manage the question bank). See the printed next steps.
#
# Usage:
#   ./setup.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"

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

# ---- prerequisites -------------------------------------------------------
missing=0
need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    error "Missing required tool: $1 ($2)"
    missing=1
  fi
}
info "Checking prerequisites…"
need python3 "https://www.python.org/downloads/ (3.11+)"
need node    "https://nodejs.org/ (18+)"
need npm     "ships with Node.js"
if [ "$missing" -ne 0 ]; then
  error "Please install the missing tool(s) above and re-run ./setup.sh"
  exit 1
fi

# ---- backend: virtualenv + dependencies ----------------------------------
if [ ! -d "$VENV" ]; then
  info "Creating virtual environment at .venv"
  python3 -m venv "$VENV"
else
  info "Reusing existing virtual environment at .venv"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

info "Upgrading pip"
python -m pip install --upgrade pip >/dev/null

info "Installing backend dependencies"
pip install -r "$ROOT/backend/requirements.txt"

# ---- database: migrate + seed (idempotent) -------------------------------
info "Applying database migrations"
( cd "$ROOT/backend" && python manage.py migrate )

question_count="$(
  cd "$ROOT/backend" && python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from quiz.models import Question; print(Question.objects.count())"
)"
if [ "$question_count" -eq 0 ]; then
  info "Seeding the question bank with sample questions"
  ( cd "$ROOT/backend" && python manage.py seed_questions )
else
  warn "Question bank already has $question_count questions — skipping seed."
  warn "To reset it, run: (cd backend && python manage.py seed_questions --flush)"
fi

# ---- frontend: dependencies ----------------------------------------------
info "Installing frontend dependencies (npm install)"
( cd "$ROOT/frontend" && npm install )

# ---- done ----------------------------------------------------------------
cat <<EOF

${GREEN}${BOLD}Setup complete!${RESET} Start the app with two terminals:

  ${BOLD}Terminal 1 (backend)${RESET}
    source .venv/bin/activate
    cd backend && python manage.py runserver      # http://localhost:8000

  ${BOLD}Terminal 2 (frontend)${RESET}
    cd frontend && npm run dev                     # http://localhost:5173

Then open ${BOLD}http://localhost:5173${RESET} and go to "Play".

Optional — manage the question bank as an admin:
    source .venv/bin/activate
    cd backend && python manage.py createsuperuser
  then sign in on the Admin page (or at http://localhost:8000/admin/).

Run the tests:
    (cd backend && source ../.venv/bin/activate && python manage.py test)
    (cd frontend && npm test)
EOF
