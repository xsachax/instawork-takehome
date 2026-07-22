# Quiz Platform

A small quiz platform with an **admin question bank**, a **quiz player** that
serves random questions per attempt, **auto‑grading**, a **results/review**
screen, and per‑player **attempt history**.

- **Backend:** Django 5.2 + Django REST Framework (SQLite, file‑backed)
- **Frontend:** React 19 + Vite SPA (React Router)
- **Question types:** Text, Single choice, Multiple choice, Numerical, Image upload

> **Questions per attempt:** the brief mentions both “10” and “5”. The detailed
> requirements and the **0–5 score** use **5**, so 5 is the default. It is
> configurable via the `QUIZ_QUESTION_COUNT` environment variable.

---

## Quick start

The fastest way to get running (no admin account required):

```bash
./setup.sh
```

`setup.sh` checks prerequisites, creates a Python virtual environment, installs
backend and frontend dependencies, applies migrations, and seeds the question
bank (only if it is empty). Then start the two servers:

```bash
# Terminal 1 — backend
source .venv/bin/activate
cd backend && python manage.py runserver      # http://localhost:8000

# Terminal 2 — frontend
cd frontend && npm run dev                     # http://localhost:5173
```

Open <http://localhost:5173> and choose **Play**. Prefer to set things up by
hand? Follow the [Backend setup](#1-backend-setup) and
[Frontend setup](#2-frontend-setup) steps below.

### Onboarding with an AI agent

Using an AI coding agent? Point it at the onboarding skill at
[`.github/skills/onboarding/SKILL.md`](.github/skills/onboarding/SKILL.md). It
walks the agent through setup, running the app, running the tests, the codebase
map, and the optional AI‑judge feature.

---

## Repository layout

```
.
├── setup.sh                # one-command local setup (non-admin)
├── backend/                # Django + DRF API
│   ├── config/             # project settings & URLs
│   ├── quiz/               # app: models, serializers, views, grading, tests
│   │   ├── grading.py      # deterministic grading
│   │   ├── judge.py        # optional AI judge (text/image)
│   │   └── management/commands/seed_questions.py
│   ├── manage.py
│   └── requirements.txt
├── frontend/               # React + Vite SPA
│   └── src/
│       ├── pages/          # Home, Quiz, Results, History, Admin
│       ├── components/     # QuestionInput, QuestionForm
│       └── api.js          # API client
└── .github/skills/onboarding/SKILL.md   # onboarding skill for AI agents
```

---

## Prerequisites

- **Python 3.11+** (developed on 3.14)
- **Node.js 18+** (developed on Node 22)

---

## 1. Backend setup

From the repository root:

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

cd backend

# Apply migrations (creates db.sqlite3)
python manage.py migrate

# Seed the question bank with 22 sample questions (all 5 types)
python manage.py seed_questions          # add --flush to reset first

# Create a staff account to manage the question bank
python manage.py createsuperuser

# Run the API server (http://localhost:8000)
python manage.py runserver
```

The API is served under `http://localhost:8000/api/`. The Django admin site is
also available at `http://localhost:8000/admin/`.

### Run the backend tests

```bash
cd backend
python manage.py test
```

The suite (35 tests) covers grading rules, per‑type validation, permissions,
the full attempt flow (start → submit → review), scoring, history, answer‑leak
protection, staff score overrides, the auth endpoints, and independent
randomization, including mocked LLM judge flows.

---

## 2. Frontend setup

In a **second terminal**:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The Vite dev server proxies `/api` and `/media` to Django on port 8000, so the
SPA runs same‑origin (session + CSRF cookies work without extra configuration).
Keep **both** the backend (`:8000`) and the frontend (`:5173`) running.

Other frontend commands:

```bash
npm run build      # production build into dist/
npm run preview    # preview the production build
npm run lint       # oxlint
npm test           # Vitest component tests
```

Open **http://localhost:5173** in your browser.

---

## Using the app

### Quiz player (no login)
1. Go to **Play**, enter your name, and optionally enter a judge API key.
   - With a key, the random pool may include all question types, including
     free-response text and image uploads that are graded by an AI judge.
   - Without a key, the quiz serves only deterministic, auto-graded question
     types: single choice, multiple choice, and numerical.
2. Answer the randomly served questions.
3. Submit to see your **score (0–5)**, per‑question ✅/❌ marks, and a full
   **review** showing your answer and the correct answer(s).
4. **My attempts** lists every previous attempt for your name; open any to
   review it again.

### Admin question bank (staff login)
1. Go to **Admin** and sign in with the staff account you created.
2. Create, edit, and delete questions; tag them with **category** and
   **difficulty** (easy/medium/hard); filter/search the bank.

---

## Question types & grading

| Type | Author provides | Grading rule |
|------|-----------------|--------------|
| **Single choice** | ≥2 choices, **exactly one** correct | selected == the one correct choice |
| **Multiple choice** | ≥2 choices, **≥1** correct | selected set **exactly** matches the correct set |
| **Numerical** | a correct answer + optional tolerance | `|answer − expected| ≤ tolerance` |
| **Text** | accepted answers / keywords + match mode | with a judge key: AI verdict; without one or on judge failure: normalized heuristic + `needs_review` |
| **Image upload** | a requirement description | with a judge key: AI vision verdict; without one or on judge failure: uploaded image is accepted + `needs_review` |

**Text grading** normalizes input (lowercase, trims, strips punctuation,
collapses whitespace) before matching, and supports multiple accepted answers or
keyword matching.

**AI judging:** text and image questions are included only when the client sends
a per-request judge API key while starting the attempt. The same key must be sent
again on submit for text/image answers to be judged. The backend uses an
OpenAI-compatible Chat Completions API, sends the question prompt and accepted
answers/keywords or image requirement, asks for strict JSON
`{"correct": true/false, "reason": "..."}`, and sets `needs_review=false` when a
valid verdict is returned.

If no key is sent on submit, or the judge call fails, times out, or returns
malformed JSON, the app falls back to the existing heuristic behavior. Text
answers use normalized matching and are flagged `needs_review`; image uploads
are treated as correct and flagged `needs_review` so staff can adjust them in the
Django admin.

Validation is enforced both in the API serializer and surfaced in the admin UI.

---

## API reference

Base URL: `/api`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/auth/csrf/` | – | Set the CSRF cookie |
| `POST` | `/auth/login/` | – | Staff login (session) |
| `POST` | `/auth/logout/` | – | Log out |
| `GET` | `/auth/me/` | – | Current user info |
| `GET/POST` | `/questions/` | staff | List / create questions (filters: `type`, `category`, `difficulty`, `search`) |
| `GET/PUT/PATCH/DELETE` | `/questions/{id}/` | staff | Retrieve / update / delete a question |
| `POST` | `/attempts/` | – | Start an attempt (`{"player": "name", "judge_api_key": "..."}`; key optional) → returns random questions (no answers) |
| `POST` | `/attempts/{id}/submit/` | – | Submit answers (`multipart/form-data`) → graded review |
| `GET` | `/attempts/{id}/` | – | Attempt details (answers hidden until submitted) |
| `GET` | `/attempts/?player=name` | – | A player's attempt history |

**Submit payload** (`multipart/form-data`):
- `answers` — JSON string:
  `[{"attempt_question_id": 1, "text": "...", "numerical": 42, "selected_choice_ids": [3,4]}]`
- image files as separate fields named `image_<attempt_question_id>`.
- optional judge fields: `judge_api_key`, `judge_model`, `judge_base_url`.

**Judge defaults and overrides:** when a judge key is provided, the backend calls
`https://api.openai.com/v1/chat/completions` using model `gpt-4o-mini` by
default. Clients may override the provider/model per request with
`judge_base_url` and `judge_model`.

---

## Configuration

Backend settings read from environment variables (all optional):

| Variable | Default | Purpose |
|----------|---------|---------|
| `QUIZ_QUESTION_COUNT` | `5` | Questions served per attempt |
| `DJANGO_DEBUG` | `True` | Debug mode |
| `DJANGO_SECRET_KEY` | dev key | Secret key |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | Allowed hosts (comma‑separated) |
| `DJANGO_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed CORS origins |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Trusted CSRF origins |

Judge API keys are provided by the client per request, not via server
environment variables.

---

## Non‑functional notes

- **Accessibility:** semantic landmarks, a skip‑to‑content link, labelled form
  controls, `fieldset`/`legend` for choice groups, visible keyboard focus,
  `aria-live` status updates, descriptive per‑page titles, and focus moved to
  the main region on client‑side navigation.
- **Security:** judge API keys are held only in request memory on the backend.
  They are never stored on attempts, written to the database, logged, or echoed
  back by serializers. The frontend stores a provided key only in `sessionStorage`
  for the active attempt so it can be sent again on submit; it is removed after
  submit or cancel and is never written to long-lived `localStorage`.
- **Responsive:** fluid layout that works on mobile and desktop.
- **Persistence:** all data is stored in SQLite (`backend/db.sqlite3`); uploaded
  images are stored under `backend/media/`.

---

## Quick start (TL;DR)

```bash
# Terminal 1 — backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && python manage.py migrate && python manage.py seed_questions
python manage.py createsuperuser
python manage.py runserver

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
# open http://localhost:5173
```
