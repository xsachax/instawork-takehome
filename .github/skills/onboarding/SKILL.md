---
name: quiz-platform-onboarding
description: >-
  Onboard to the Quiz Platform repository (Django + DRF backend, React + Vite
  SPA). Use this when a developer or AI agent needs to set up, run, test, or
  understand this project for the first time. Covers one-command setup, running
  both servers, running the test suites, the codebase map, and the AI-judge
  feature.
---

# Quiz Platform — Onboarding

You are getting a person (or yourself, as an agent) from a fresh checkout to a
running, tested app. Follow these steps in order. Prefer running the provided
script over doing steps by hand.

## 1. What this project is

A small quiz platform:

- **Backend:** Django 5.2 + Django REST Framework, SQLite (file-backed). Code in
  `backend/`.
- **Frontend:** React 19 + Vite single-page app (React Router). Code in
  `frontend/`.
- **Question types:** Text, Single choice, Multiple choice, Numerical, Image
  upload.
- Each attempt serves **5 random** questions and is scored **0–5**.

## 2. Prerequisites

- **Python 3.11+** (developed on 3.14)
- **Node.js 18+** and **npm** (developed on Node 22)

Verify: `python3 --version`, `node --version`, `npm --version`.

## 3. Easiest path: one command

From the repository root:

```bash
./start.sh
```

`start.sh` does everything: on first run it sets up dependencies, the database,
and sample questions, and offers to create an admin account; then it starts the
backend and frontend together, waits until they're ready, opens the app in the
browser, and stops both cleanly on Ctrl+C. Server logs are written to
`.run-logs/`. If you use this, you can skip sections 4–5 below (they explain the
manual equivalent).

## 4. Manual setup (do this if not using `./start.sh`)

From the repository root:

```bash
./setup.sh
```

This creates a `.venv`, installs backend + frontend dependencies, runs
migrations, and seeds the question bank (only if empty). It does **not** create
an admin account (not needed to play). If `setup.sh` is unavailable, follow the
manual steps in `README.md`.

## 5. Run the app manually (two terminals)

```bash
# Terminal 1 — backend API on http://localhost:8000
source .venv/bin/activate
cd backend && python manage.py runserver

# Terminal 2 — frontend SPA on http://localhost:5173
cd frontend && npm run dev
```

Open **http://localhost:5173** and choose **Play**. The Vite dev server proxies
`/api` and `/media` to Django, so cookies/CSRF work with no extra config.

### Verify it works

- `curl -s -X POST http://localhost:8000/api/attempts/ -H 'Content-Type: application/json' -d '{"player":"tester"}'`
  should return an attempt with 5 questions.
- The browser home page should load and let you start a quiz.

## 6. Run the tests

```bash
# Backend (Django test runner)
(cd backend && source ../.venv/bin/activate && python manage.py test)

# Frontend (Vitest) + lint + build
(cd frontend && npm test && npm run lint && npm run build)
```

All suites should pass. The frontend tests never hit the network; backend judge
tests mock the LLM HTTP call.

## 7. Codebase map

```
backend/
  config/settings.py      # settings; QUIZ_QUESTION_COUNT controls questions/attempt
  quiz/models.py          # Question, Choice, Attempt, AttemptQuestion, Answer
  quiz/grading.py         # deterministic grading (single/multiple/numerical/text/image)
  quiz/judge.py           # optional AI judge for text/image (OpenAI-compatible)
  quiz/views.py           # AttemptViewSet (start/submit/list/retrieve), auth, QuestionViewSet
  quiz/serializers.py     # per-type validation
  quiz/tests.py           # backend test suite
  quiz/management/commands/seed_questions.py   # sample question bank
frontend/src/
  pages/                  # Home, Quiz, Results, History, Admin
  components/             # QuestionInput, QuestionForm
  api.js                  # fetch-based API client
```

## 8. Grading & the optional AI judge

- **Single / Multiple / Numerical** are auto-graded deterministically.
- **Text / Image** are non-deterministic. By default they use a heuristic and
  are flagged for review. If the player supplies a **per-request API key** when
  starting a quiz, those questions are included and graded by an
  OpenAI-compatible judge (default model `gpt-4o-mini`, vision for images). The
  key is held only for the request — never stored or logged. With no key, only
  the deterministic question types are served. See `backend/quiz/judge.py` and
  the README for details.

## 9. Become an admin (optional)

To create/edit/delete questions:

```bash
source .venv/bin/activate
cd backend && python manage.py createsuperuser
```

Then sign in on the **Admin** page in the SPA, or at
`http://localhost:8000/admin/`.

## 10. Troubleshooting

- **`./start.sh` says a port is already in use:** something is already listening
  on 8000 or 5173 (maybe a previous run). Stop it, then re-run `./start.sh`. To
  see why a server didn't start, check `.run-logs/backend.log` and
  `.run-logs/frontend.log`.
- **`./setup.sh` fails on a missing tool:** install the tool it names and re-run.
- **Empty quiz / "question bank is empty":** run
  `(cd backend && python manage.py seed_questions)`.
- **Frontend can't reach the API:** make sure the backend is running on port
  8000 and start the frontend with `npm run dev` (its proxy targets 8000).
