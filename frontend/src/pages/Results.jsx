import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, QUESTION_TYPE_LABELS } from '../api'
import { formatDateTime } from '../player'
import { useDocumentTitle } from '../hooks'

function ChoiceReview({ question, answer }) {
  const selected = new Set(answer?.selected_choice_ids || [])
  return (
    <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {question.choices.map((choice) => {
        const chosen = selected.has(choice.id)
        const marks = []
        if (choice.is_correct) marks.push('correct answer')
        if (chosen) marks.push('your choice')
        return (
          <li key={choice.id}>
            {choice.is_correct ? '✅ ' : chosen ? '❌ ' : '• '}
            {choice.text}
            {marks.length > 0 && (
              <span className="muted"> — {marks.join(', ')}</span>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function AnswerReview({ question, answer }) {
  if (question.type === 'single' || question.type === 'multiple') {
    return <ChoiceReview question={question} answer={answer} />
  }
  if (question.type === 'numerical') {
    return (
      <div className="stack">
        <div>Your answer: <strong>{answer?.numerical_response ?? '—'}</strong></div>
        <div className="muted">
          Correct answer: {question.numerical_answer}
          {Number(question.numerical_tolerance) > 0 &&
            ` (± ${question.numerical_tolerance})`}
        </div>
      </div>
    )
  }
  if (question.type === 'text') {
    return (
      <div className="stack">
        <div>Your answer: <strong>{answer?.text_response || '—'}</strong></div>
        <div className="muted">
          Accepted answer(s): {(question.text_answers || []).join(', ') || '—'}
        </div>
      </div>
    )
  }
  if (question.type === 'image') {
    return (
      <div className="stack answer-preview">
        <div className="muted">Requirement: {question.image_requirement}</div>
        {answer?.image_response ? (
          <img src={answer.image_response} alt="Your uploaded response" />
        ) : (
          <div>No image uploaded.</div>
        )}
        {answer?.needs_review && (
          <div className="alert alert-info" role="note">
            Auto-graded from your upload; an admin may adjust this after manual review.
          </div>
        )}
      </div>
    )
  }
  return null
}

export default function Results() {
  useDocumentTitle('Results')
  const { attemptId } = useParams()
  const navigate = useNavigate()
  const [attempt, setAttempt] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .getAttempt(attemptId)
      .then((data) => {
        if (!data.submitted_at) {
          navigate(`/quiz/${attemptId}`, { replace: true })
          return
        }
        setAttempt(data)
      })
      .catch(() => setError('Could not load these results.'))
  }, [attemptId, navigate])

  if (error) return <div className="alert alert-error" role="alert">{error}</div>
  if (!attempt) return <p>Loading results…</p>

  return (
    <div>
      <div className="card score-hero">
        <h1>Results</h1>
        <p className="muted">{attempt.player} · {formatDateTime(attempt.submitted_at)}</p>
        <div className="score-number" aria-live="polite">
          {attempt.score} / {attempt.total}
        </div>
        <div className="btn-row" style={{ justifyContent: 'center' }}>
          <Link className="btn" to="/">Play again</Link>
          <Link className="btn btn-secondary" to="/history">My attempts</Link>
        </div>
      </div>

      <h2>Review</h2>
      {attempt.questions.map((aq, index) => {
        const correct = aq.answer?.is_correct
        return (
          <section
            className={`card ${correct ? 'result-correct' : 'result-wrong'}`}
            key={aq.id}
            aria-labelledby={`r-${aq.id}-title`}
          >
            <div className="meta">
              <span className="mark" aria-hidden="true">{correct ? '✅' : '❌'}</span>
              <span className="badge">Q{index + 1}</span>
              <span className="badge">{QUESTION_TYPE_LABELS[aq.question.type]}</span>
              <span className="visually-hidden">
                {correct ? 'Correct' : 'Incorrect'}.
              </span>
            </div>
            <h3 id={`r-${aq.id}-title`}>{aq.question.prompt}</h3>
            <AnswerReview question={aq.question} answer={aq.answer} />
          </section>
        )
      })}
    </div>
  )
}
