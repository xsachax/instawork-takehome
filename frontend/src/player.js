// Small helper to remember the current player's name across pages/reloads.
const KEY = 'quiz.player'

export function getPlayer() {
  return localStorage.getItem(KEY) || ''
}

export function setPlayer(name) {
  if (name) localStorage.setItem(KEY, name)
}

// The judge API key is sensitive, so it is kept only in sessionStorage (cleared
// when the tab closes) and scoped to the active attempt — never in long-lived
// localStorage, and never sent anywhere except the start/submit requests.
function judgeKeyName(attemptId) {
  return `quiz.judgeKey.${attemptId}`
}

export function setJudgeKey(attemptId, key) {
  if (key) sessionStorage.setItem(judgeKeyName(attemptId), key)
}

export function getJudgeKey(attemptId) {
  return sessionStorage.getItem(judgeKeyName(attemptId)) || ''
}

export function clearJudgeKey(attemptId) {
  sessionStorage.removeItem(judgeKeyName(attemptId))
}

export function formatDateTime(value) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}
