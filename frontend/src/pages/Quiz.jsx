import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, QUESTION_TYPE_LABELS } from '../api'
import QuestionInput from '../components/QuestionInput'

export default function Quiz() {
  const { attemptId } = useParams()
  const navigate = useNavigate()
  const [attempt, setAttempt] = useState(null)
  const [answers, setAnswers] = useState({})
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const cached = sessionStorage.getItem(`attempt.${attemptId}`)
    if (cached) {
      setAttempt(JSON.parse(cached))
      setLoading(false)
      return
    }
    // Fall back to the API (returns questions only while unsubmitted).
    api
      .getAttempt(attemptId)
      .then((data) => {
        if (data.submitted_at) {
          navigate(`/results/${attemptId}`, { replace: true })
          return
        }
        setAttempt(data)
      })
      .catch(() => setError('This quiz could not be loaded.'))
      .finally(() => setLoading(false))
  }, [attemptId, navigate])

  function updateAnswer(aqId, value) {
    setAnswers((prev) => ({ ...prev, [aqId]: value }))
  }

  const answeredCount = attempt
    ? attempt.questions.filter((aq) => {
        const a = answers[aq.id] || {}
        return (
          (a.text && a.text.trim()) ||
          a.numerical !== undefined && a.numerical !== '' ||
          (a.selected_choice_ids && a.selected_choice_ids.length) ||
          a.file
        )
      }).length
    : 0

  async function submit(event) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const form = new FormData()
      const answerList = attempt.questions.map((aq) => {
        const a = answers[aq.id] || {}
        if (a.file) form.append(`image_${aq.id}`, a.file)
        return {
          attempt_question_id: aq.id,
          text: a.text || '',
          numerical: a.numerical === '' ? null : a.numerical ?? null,
          selected_choice_ids: a.selected_choice_ids || [],
        }
      })
      form.append('answers', JSON.stringify(answerList))
      await api.submitAttempt(attempt.id, form)
      sessionStorage.removeItem(`attempt.${attempt.id}`)
      navigate(`/results/${attempt.id}`)
    } catch (err) {
      setError(err?.data?.detail || 'Could not submit your answers.')
      setSubmitting(false)
    }
  }

  if (loading) return <p>Loading quiz…</p>
  if (error) return <div className="alert alert-error" role="alert">{error}</div>
  if (!attempt) return null

  const total = attempt.questions.length

  return (
    <div>
      <h1>Quiz in progress</h1>
      <p className="muted" aria-live="polite">
        {answeredCount} of {total} answered
      </p>
      <div className="progress" aria-hidden="true">
        <span style={{ width: `${(answeredCount / total) * 100}%` }} />
      </div>

      <form onSubmit={submit}>
        {attempt.questions.map((aq, index) => (
          <section className="card" key={aq.id} aria-labelledby={`q-${aq.id}-title`}>
            <div className="meta">
              <span className="badge">Q{index + 1}</span>
              <span className="badge">{QUESTION_TYPE_LABELS[aq.question.type]}</span>
              <span className={`badge ${aq.question.difficulty}`}>
                {aq.question.difficulty}
              </span>
              {aq.question.category && (
                <span className="muted">{aq.question.category}</span>
              )}
            </div>
            <h2 id={`q-${aq.id}-title`}>{aq.question.prompt}</h2>
            <QuestionInput
              question={aq.question}
              answer={answers[aq.id]}
              onChange={(value) => updateAnswer(aq.id, value)}
            />
          </section>
        ))}

        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <div className="btn-row">
          <button type="submit" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit answers'}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigate('/')}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
