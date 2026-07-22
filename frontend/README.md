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

## AI judge key

The Play page has an optional password field for a per-request judge API key.
With a key, the backend may serve free-response text and image-upload questions
and will send the key again on submit so those answers can be judged by an
OpenAI-compatible model. Without a key, attempts are limited to auto-graded
single-choice, multiple-choice, and numerical questions.

The key is kept only in component state before the quiz starts and in
`sessionStorage` for the active attempt so it can be reused on submit. It is
removed after submit or cancel and is never stored in `localStorage`.
