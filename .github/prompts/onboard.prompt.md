---
mode: agent
description: Onboard to the Quiz Platform — set up, run, and test the app from a fresh checkout.
---

# Onboard to the Quiz Platform

Get me (or yourself, as an agent) from a fresh checkout of this repository to a
running, tested app. This repo has a companion agent skill at
`.github/skills/onboarding/SKILL.md` — read it first and follow it as the source
of truth; the steps below mirror it for convenience.

## What this project is

A small quiz platform:

- **Backend:** Django 5.2 + Django REST Framework, SQLite (file-backed), in `backend/`.
- **Frontend:** React 19 + Vite single-page app (React Router), in `frontend/`.
- **Question types:** Text, Single choice, Multiple choice, Numerical, Image upload.
- Each attempt serves **5 random** questions and is scored **0–5**.

## Do this, in order

1. **Check prerequisites:** Python 3.11+ and Node.js 18+ with npm.
   Run `python3 --version`, `node --version`, `npm --version` and report anything missing.
2. **Run one-command setup** from the repo root: `./setup.sh`
   (creates `.venv`, installs backend + frontend deps, migrates, seeds the
   question bank only if empty; does not create an admin). If `setup.sh` fails on
   a missing tool, install it and re-run. If the script is unavailable, fall back
   to the manual steps in `README.md`.
3. **Start both servers** (two terminals):
   - Backend: `source .venv/bin/activate && cd backend && python manage.py runserver` → http://localhost:8000
   - Frontend: `cd frontend && npm run dev` → http://localhost:5173
4. **Verify it works:**
   - `curl -s -X POST http://localhost:8000/api/attempts/ -H 'Content-Type: application/json' -d '{"player":"tester"}'` returns an attempt with 5 questions.
   - http://localhost:5173 loads and lets you start a quiz.
5. **Run the tests and report results:**
   - Backend: `(cd backend && source ../.venv/bin/activate && python manage.py test)`
   - Frontend: `(cd frontend && npm test && npm run lint && npm run build)`

## Then explain

Give me a short tour: the codebase map (`backend/quiz/models.py`,
`grading.py`, `judge.py`, `views.py`; `frontend/src/pages` and `components`), how
grading works per question type, and the optional per-request AI-judge for
text/image questions (deterministic types only when no API key is supplied). For
full detail, defer to `.github/skills/onboarding/SKILL.md`.
