# Quiz Platform

A small quiz platform with an **admin question bank**, a **quiz player** that
serves random questions per attempt, **auto‑grading**, a **results/review**
screen, and per‑player **attempt history**.

- **Backend:** Django 5.2 + Django REST Framework (SQLite, file‑backed)
- **Frontend:** React 19 + Vite SPA (React Router)
- **Question types:** Text, Single choice, Multiple choice, Numerical, Image upload
- **Grading:** deterministic types (single/multiple/numerical) are auto‑graded
  exactly; open‑ended types (text/image) can optionally be graded by an **AI
  judge** using a **per‑request API key** the player supplies (see
  [AI judge](#ai-judge-for-open-ended-questions)).

> **Questions per attempt:** the brief mentions both “10” and “5”. The detailed
> requirements and the **0–5 score** use **5**, so 5 is the default. It is
> configurable via the `QUIZ_QUESTION_COUNT` environment variable.

---

## Repository layout

```
.
├── backend/                # Django + DRF API
│   ├── config/             # project settings & URLs
│   ├── quiz/               # app: models, serializers, views, grading, tests
│   │   └── management/commands/seed_questions.py
│   ├── manage.py
│   └── requirements.txt
└── frontend/               # React + Vite SPA
    └── src/
        ├── pages/          # Home, Quiz, Results, History, Admin
        ├── components/     # QuestionInput, QuestionForm
        └── api.js          # API client
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

The suite (42 tests) covers grading rules, per‑type validation, permissions,
the full attempt flow (start → submit → review), scoring, history, answer‑leak
protection, staff score overrides, the auth endpoints, independent
randomization, and the **AI judge** (deterministic‑only pool without a key,
text/image judging with a mocked verdict, and heuristic fallback). The judge's
HTTP boundary is monkeypatched, so the tests never make network calls.

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
1. Go to **Play**, enter your name, and start a quiz. Optionally paste an **AI
   judge API key**: with a key, free‑response and image questions are included
   and graded by an AI judge; without one, only auto‑graded questions appear.
2. Answer the randomly served questions (choices, numerical, text, or image
   upload).
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

| Type | Author provides | Auto‑grading rule |
|------|-----------------|-------------------|
| **Single choice** | ≥2 choices, **exactly one** correct | selected == the one correct choice |
| **Multiple choice** | ≥2 choices, **≥1** correct | selected set **exactly** matches the correct set |
| **Numerical** | a correct answer + optional tolerance | `|answer − expected| ≤ tolerance` |
| **Text** | accepted answers / keywords + match mode | normalized match: exact / contains‑all / contains‑any (**or** AI judge if a key is supplied) |
| **Image upload** | a requirement description | any uploaded image is accepted & flagged for review (**or** AI judge if a key is supplied) |

**Text grading** normalizes input (lowercase, trims, strips punctuation,
collapses whitespace) before matching, and supports multiple accepted answers or
keyword matching.

**Image grading** cannot verify image contents automatically, so an uploaded
image is treated as meeting the requirement (correct) and flagged
`needs_review` so a staff member can adjust the result later via the Django
admin. This keeps the immediate 0–5 results screen intact while acknowledging
the limitation.

Validation is enforced both in the API serializer and surfaced in the admin UI.

---

## AI judge for open-ended questions

Text and image answers can't be graded by fixed rules, so the platform can
delegate them to an **LLM judge** — but only when the player opts in by
providing their **own API key on the request**. There is no server‑side key.

**How it works**

- **Deterministic types** (single, multiple, numerical) are *always* graded by
  the exact rules above — the judge is never involved.
- **Start** (`POST /api/attempts/`) accepts an optional `judge_api_key`:
  - **With a key**, the random question pool may include *every* type, so
    free‑response and image questions can be served.
  - **Without a key**, the pool is restricted to deterministic types only
    (text and image are excluded), so a player is never shown a question that
    can't be graded.
- **Submit** (`POST /api/attempts/{id}/submit/`) accepts an optional
  `judge_api_key` (plus optional `judge_model` / `judge_base_url`). For text and
  image answers:
  - **With a key**, the answer is sent to the judge and `is_correct` is set from
    the verdict, with `needs_review = false`.
  - **Without a key, or if the judge call errors/times out**, grading falls back
    to the existing heuristic with `needs_review = true`.

**Judge design** (`backend/quiz/judge.py`)

- Uses an **OpenAI‑compatible Chat Completions API**. Defaults: base URL
  `https://api.openai.com/v1`, model `gpt-4o-mini` (vision‑capable, so the same
  default serves both judges). Per‑request overrides: `judge_model`,
  `judge_base_url`.
- **Text judge** sends the prompt, the accepted answers/keywords, and the
  player's response, asking for strict JSON: `{"correct": true|false, "reason": "…"}`.
- **Image judge** uses a vision model, passing the uploaded image as a base64
  `data:` URL together with the question's `image_requirement`, and returns the
  same JSON shape.
- The single outbound HTTP request lives in one function
  (`_call_chat_completion`) so tests monkeypatch it and never hit the network.
  All errors are handled gracefully (fall back, never `500`).

**Security**

- The API key is supplied **per request** and is **never persisted or logged**.
  It is not stored on the `Attempt` or anywhere in the database — it is only held
  in memory for the duration of the request.
- In the browser it is kept only in `sessionStorage`, scoped to the active
  attempt, and cleared after submit — never in long‑lived `localStorage`.

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
| `POST` | `/attempts/` | – | Start an attempt (`{"player": "name"}`, optional `judge_api_key`) → random questions (no answers). Without a key the pool is deterministic‑only (no text/image) |
| `POST` | `/attempts/{id}/submit/` | – | Submit answers (`multipart/form-data`) → graded review. Optional `judge_api_key` (+ `judge_model`, `judge_base_url`) AI‑grades text/image |
| `GET` | `/attempts/{id}/` | – | Attempt details (answers hidden until submitted) |
| `GET` | `/attempts/?player=name` | – | A player's attempt history |

**Submit payload** (`multipart/form-data`):
- `answers` — JSON string:
  `[{"attempt_question_id": 1, "text": "...", "numerical": 42, "selected_choice_ids": [3,4]}]`
- image files as separate fields named `image_<attempt_question_id>`.
- optional `judge_api_key` (and optional `judge_model` / `judge_base_url`) to
  AI‑grade text and image answers. The key is never persisted or logged.

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

**AI judge** settings are **not** environment variables — the API key is
supplied per request by the client and never stored server‑side. The judge
provider defaults (used unless the client overrides them per request) are:

| Field | Default | Per‑request override |
|-------|---------|----------------------|
| Base URL | `https://api.openai.com/v1` | `judge_base_url` |
| Model | `gpt-4o-mini` (vision‑capable) | `judge_model` |

---

## Non‑functional notes

- **Accessibility:** semantic landmarks, a skip‑to‑content link, labelled form
  controls, `fieldset`/`legend` for choice groups, visible keyboard focus,
  `aria-live` status updates, descriptive per‑page titles, and focus moved to
  the main region on client‑side navigation.
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
