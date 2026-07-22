import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { getPlayer, setPlayer, formatDateTime } from '../player'
import { useDocumentTitle } from '../hooks'

export default function History() {
  useDocumentTitle('My attempts')
  const [name, setName] = useState(getPlayer())
  const [query, setQuery] = useState(getPlayer())
  const [attempts, setAttempts] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!query) {
      setAttempts([])
      return
    }
    setLoading(true)
    api
      .listAttempts(query)
      .then((data) => setAttempts(data))
      .catch(() => setError('Could not load attempts.'))
      .finally(() => setLoading(false))
  }, [query])

  function load(event) {
    event.preventDefault()
    const trimmed = name.trim()
    setPlayer(trimmed)
    setQuery(trimmed)
  }

  return (
    <div>
      <h1>My attempts</h1>
      <form onSubmit={load} className="card">
        <label htmlFor="history-name">Player name</label>
        <div className="row">
          <input
            id="history-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter your name"
          />
          <button type="submit" style={{ flex: '0 0 auto' }}>View attempts</button>
        </div>
      </form>

      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {loading && <p>Loading…</p>}

      {!loading && query && attempts.length === 0 && (
        <div className="alert alert-info">
          No attempts yet for “{query}”. <Link to="/">Start one?</Link>
        </div>
      )}

      {attempts.length > 0 && (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table>
            <caption className="visually-hidden">
              Previous quiz attempts for {query}
            </caption>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Score</th>
                <th scope="col">Status</th>
                <th scope="col"><span className="visually-hidden">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {attempts.map((a) => (
                <tr key={a.id}>
                  <td>{formatDateTime(a.submitted_at || a.created_at)}</td>
                  <td>{a.submitted_at ? `${a.score} / ${a.total}` : '—'}</td>
                  <td>
                    {a.submitted_at ? (
                      <span className="badge easy">Completed</span>
                    ) : (
                      <span className="badge medium">In progress</span>
                    )}
                  </td>
                  <td>
                    {a.submitted_at ? (
                      <Link to={`/results/${a.id}`}>Review</Link>
                    ) : (
                      <Link to={`/quiz/${a.id}`}>Resume</Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
