import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { getPlayer, setPlayer } from '../player'
import { useDocumentTitle } from '../hooks'

export default function Home() {
  useDocumentTitle('Start a quiz')
  const navigate = useNavigate()
  const [name, setName] = useState(getPlayer())
  const [judgeApiKey, setJudgeApiKey] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function start(event) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Please enter your name to start.')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const judgeOptions = { judgeApiKey: judgeApiKey.trim() }
      const attempt = await api.startAttempt(trimmed, judgeOptions)
      setPlayer(trimmed)
      // Cache the served questions so the quiz page renders without a re-fetch
      // (which would otherwise not include the questions for an in-progress attempt).
      sessionStorage.setItem(`attempt.${attempt.id}`, JSON.stringify(attempt))
      if (judgeOptions.judgeApiKey) {
        sessionStorage.setItem(
          `attempt.${attempt.id}.judge`,
          JSON.stringify(judgeOptions),
        )
      } else {
        sessionStorage.removeItem(`attempt.${attempt.id}.judge`)
      }
      navigate(`/quiz/${attempt.id}`)
    } catch (err) {
      setError(
        err?.data?.detail ||
          'Could not start a quiz. Make sure the question bank has been seeded.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="center-narrow">
      <div className="card">
        <h1>Start a quiz</h1>
        <p className="muted">
          You'll get a set of random questions. Answer them, submit, and see your
          score with a full review.
        </p>
        {error && (
          <div className="alert alert-error" role="alert">{error}</div>
        )}
        <form onSubmit={start}>
          <div className="field">
            <label htmlFor="player-name">Your name</label>
            <input
              id="player-name"
              type="text"
              value={name}
              autoComplete="name"
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Alex"
            />
          </div>
          <div className="field">
            <label htmlFor="judge-api-key">OpenAI API key (optional)</label>
            <input
              id="judge-api-key"
              type="password"
              value={judgeApiKey}
              autoComplete="off"
              onChange={(e) => setJudgeApiKey(e.target.value)}
              aria-describedby="judge-api-key-help"
              placeholder="sk-..."
            />
            <p id="judge-api-key-help" className="muted field-hint">
              Provide an OpenAI API key to include and auto-grade free-response
              and image questions (omit it for auto-graded questions only).
            </p>
          </div>
          <button type="submit" disabled={loading}>
            {loading ? 'Starting…' : 'Start quiz'}
          </button>
        </form>
      </div>
    </div>
  )
}
