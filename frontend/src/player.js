// Small helper to remember the current player's name across pages/reloads.
const KEY = 'quiz.player'

export function getPlayer() {
  return localStorage.getItem(KEY) || ''
}

export function setPlayer(name) {
  if (name) localStorage.setItem(KEY, name)
}

export function formatDateTime(value) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}
