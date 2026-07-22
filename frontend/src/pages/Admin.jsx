import { useEffect, useState } from 'react'
import { api, QUESTION_TYPE_LABELS } from '../api'
import QuestionForm from '../components/QuestionForm'
import { useDocumentTitle } from '../hooks'

function LoginForm({ onLoggedIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const user = await api.login(username, password)
      onLoggedIn(user)
    } catch (err) {
      setError(err?.data?.detail || 'Login failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="center-narrow">
      <form onSubmit={submit} className="card">
        <h1>Admin sign in</h1>
        <p className="muted">Use a Django staff account to manage the question bank.</p>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <div className="field">
          <label htmlFor="login-user">Username</label>
          <input
            id="login-user"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="login-pass">Password</label>
          <input
            id="login-pass"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}

function QuestionBank({ user, onLogout }) {
  const [questions, setQuestions] = useState([])
  const [filters, setFilters] = useState({ type: '', difficulty: '', search: '' })
  const [editing, setEditing] = useState(null) // null | 'new' | question object
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const data = await api.listQuestions(filters)
      setQuestions(data)
    } catch {
      setError('Could not load questions.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])

  async function handleSave(payload) {
    if (editing && editing !== 'new') {
      await api.updateQuestion(editing.id, payload)
    } else {
      await api.createQuestion(payload)
    }
    setEditing(null)
    load()
  }

  async function handleDelete(question) {
    if (!window.confirm('Delete this question? This cannot be undone.')) return
    await api.deleteQuestion(question.id)
    load()
  }

  if (editing) {
    return (
      <div>
        <div className="btn-row" style={{ justifyContent: 'space-between' }}>
          <h1>Question bank</h1>
        </div>
        <QuestionForm
          question={editing === 'new' ? null : editing}
          onSave={handleSave}
          onCancel={() => setEditing(null)}
        />
      </div>
    )
  }

  return (
    <div>
      <div className="meta" style={{ justifyContent: 'space-between' }}>
        <h1>Question bank</h1>
        <div className="btn-row">
          <span className="muted">Signed in as {user.username}</span>
          <button className="btn-secondary" onClick={onLogout}>Sign out</button>
        </div>
      </div>

      <div className="card">
        <div className="row">
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="f-search">Search prompt</label>
            <input
              id="f-search"
              type="search"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="f-type">Type</label>
            <select
              id="f-type"
              value={filters.type}
              onChange={(e) => setFilters({ ...filters, type: e.target.value })}
            >
              <option value="">All</option>
              <option value="single">Single choice</option>
              <option value="multiple">Multiple choice</option>
              <option value="numerical">Numerical</option>
              <option value="text">Text</option>
              <option value="image">Image upload</option>
            </select>
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label htmlFor="f-diff">Difficulty</label>
            <select
              id="f-diff"
              value={filters.difficulty}
              onChange={(e) => setFilters({ ...filters, difficulty: e.target.value })}
            >
              <option value="">All</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>
        </div>
      </div>

      <div className="btn-row" style={{ marginBottom: '1rem' }}>
        <button onClick={() => setEditing('new')}>+ New question</button>
      </div>

      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {loading ? (
        <p>Loading…</p>
      ) : questions.length === 0 ? (
        <div className="alert alert-info">No questions match your filters.</div>
      ) : (
        <div className="card" style={{ overflowX: 'auto' }}>
          <table>
            <caption className="visually-hidden">Questions in the bank</caption>
            <thead>
              <tr>
                <th scope="col">Prompt</th>
                <th scope="col">Type</th>
                <th scope="col">Category</th>
                <th scope="col">Difficulty</th>
                <th scope="col"><span className="visually-hidden">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {questions.map((q) => (
                <tr key={q.id}>
                  <td>{q.prompt}</td>
                  <td>{QUESTION_TYPE_LABELS[q.type]}</td>
                  <td>{q.category}</td>
                  <td><span className={`badge ${q.difficulty}`}>{q.difficulty}</span></td>
                  <td>
                    <div className="btn-row">
                      <button className="btn-secondary" onClick={() => setEditing(q)}>
                        Edit
                      </button>
                      <button className="btn-danger" onClick={() => handleDelete(q)}>
                        Delete
                      </button>
                    </div>
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

export default function Admin() {
  useDocumentTitle('Admin')
  const [user, setUser] = useState(null)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    api
      .me()
      .then((data) => setUser(data.is_staff ? data : null))
      .finally(() => setChecked(true))
  }, [])

  async function logout() {
    await api.logout()
    setUser(null)
  }

  if (!checked) return <p>Loading…</p>
  if (!user) return <LoginForm onLoggedIn={setUser} />
  return <QuestionBank user={user} onLogout={logout} />
}
