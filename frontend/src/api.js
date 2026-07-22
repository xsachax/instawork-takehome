// Thin API client for the quiz backend.
//
// All requests are same-origin (Vite proxies /api to Django), so the session
// cookie flows automatically. Mutating requests include the CSRF token that
// Django sets via the /api/auth/csrf/ endpoint.

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? decodeURIComponent(match[2]) : null
}

export async function ensureCsrf() {
  if (!getCookie('csrftoken')) {
    await fetch('/api/auth/csrf/', { credentials: 'include' })
  }
}

async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const headers = {}
  const opts = { method, credentials: 'include', headers }

  if (method !== 'GET' && method !== 'HEAD') {
    await ensureCsrf()
    headers['X-CSRFToken'] = getCookie('csrftoken') || ''
  }

  if (body !== undefined) {
    if (isForm) {
      opts.body = body // FormData; browser sets the multipart boundary.
    } else {
      headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    }
  }

  const res = await fetch(`/api${path}`, opts)
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const error = new Error('Request failed')
    error.status = res.status
    error.data = data
    throw error
  }
  return data
}

function readJudgeOption(options, camelName, apiName) {
  return options?.[camelName] ?? options?.[apiName] ?? ''
}

function appendJudgeOptions(target, options = {}) {
  const fields = {
    judge_api_key: readJudgeOption(options, 'judgeApiKey', 'judge_api_key'),
    judge_model: readJudgeOption(options, 'judgeModel', 'judge_model'),
    judge_base_url: readJudgeOption(options, 'judgeBaseUrl', 'judge_base_url'),
  }
  Object.entries(fields).forEach(([name, value]) => {
    const trimmed = typeof value === 'string' ? value.trim() : value
    if (!trimmed) return
    if (target instanceof FormData) {
      target.append(name, trimmed)
    } else {
      target[name] = trimmed
    }
  })
  return target
}

export const api = {
  // Auth
  me: () => request('/auth/me/'),
  login: (username, password) =>
    request('/auth/login/', { method: 'POST', body: { username, password } }),
  logout: () => request('/auth/logout/', { method: 'POST' }),

  // Question bank (staff)
  listQuestions: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== '' && v != null),
    ).toString()
    return request(`/questions/${qs ? `?${qs}` : ''}`)
  },
  createQuestion: (payload) =>
    request('/questions/', { method: 'POST', body: payload }),
  updateQuestion: (id, payload) =>
    request(`/questions/${id}/`, { method: 'PUT', body: payload }),
  deleteQuestion: (id) => request(`/questions/${id}/`, { method: 'DELETE' }),

  // Quiz player
  startAttempt: (player, judgeOptions = {}) =>
    request('/attempts/', {
      method: 'POST',
      body: appendJudgeOptions({ player }, judgeOptions),
    }),
  getAttempt: (id) => request(`/attempts/${id}/`),
  submitAttempt: (id, formData, judgeOptions = {}) =>
    request(`/attempts/${id}/submit/`, {
      method: 'POST',
      body: appendJudgeOptions(formData, judgeOptions),
      isForm: true,
    }),
  listAttempts: (player) =>
    request(`/attempts/${player ? `?player=${encodeURIComponent(player)}` : ''}`),
}

export const QUESTION_TYPE_LABELS = {
  text: 'Text',
  single: 'Single choice',
  multiple: 'Multiple choice',
  numerical: 'Numerical',
  image: 'Image upload',
}
