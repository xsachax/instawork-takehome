# Quiz Platform — Frontend (React + Vite SPA)

Single-page app for the quiz platform. See the [root README](../README.md) for
full setup, architecture, and API docs.

## Commands

```bash
npm install      # install dependencies
npm run dev      # dev server at http://localhost:5173 (proxies /api to Django :8000)
npm run build    # production build into dist/
npm run preview  # preview the production build
npm run lint     # oxlint
```

The dev server proxies `/api` and `/media` to the Django backend on port 8000,
so run the backend (`python manage.py runserver`) alongside `npm run dev`.

## Structure

- `src/pages/` — Home, Quiz, Results, History, Admin
- `src/components/` — `QuestionInput` (player), `QuestionForm` (admin)
- `src/api.js` — API client (session + CSRF handling)

## AI judge API key

The **Home** page has an optional, password‑type **AI judge API key** field.
When a player provides a key:

- the quiz can include free‑response (text) and image questions, and
- those answers are graded by an AI judge (the key is sent with the start and
  submit requests).

Without a key, only auto‑graded question types (single/multiple choice and
numerical) are served. The key is kept only in `sessionStorage`, scoped to the
active attempt, and cleared after submit — it is never written to long‑lived
`localStorage` and never stored on the server. See the
[root README](../README.md#ai-judge-for-open-ended-questions) for the full
design.
