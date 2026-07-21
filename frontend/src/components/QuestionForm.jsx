// Create/edit form for a single question. Adapts its fields to the selected
// question type and surfaces server-side validation errors.
import { useState } from 'react'

const EMPTY = {
  type: 'single',
  prompt: '',
  category: 'General',
  difficulty: 'easy',
  numerical_answer: '',
  numerical_tolerance: '0',
  text_match_mode: 'exact',
  image_requirement: '',
}

function initialState(question) {
  if (!question) {
    return {
      ...EMPTY,
      choices: [
        { text: '', is_correct: false },
        { text: '', is_correct: false },
      ],
      text_answers_raw: '',
    }
  }
  return {
    type: question.type,
    prompt: question.prompt,
    category: question.category || 'General',
    difficulty: question.difficulty,
    numerical_answer: question.numerical_answer ?? '',
    numerical_tolerance: question.numerical_tolerance ?? '0',
    text_match_mode: question.text_match_mode || 'exact',
    image_requirement: question.image_requirement || '',
    choices:
      question.choices && question.choices.length
        ? question.choices.map((c) => ({ text: c.text, is_correct: c.is_correct }))
        : [
            { text: '', is_correct: false },
            { text: '', is_correct: false },
          ],
    text_answers_raw: (question.text_answers || []).join('\n'),
  }
}

export default function QuestionForm({ question, onSave, onCancel }) {
  const [form, setForm] = useState(() => initialState(question))
  const [errors, setErrors] = useState(null)
  const [saving, setSaving] = useState(false)

  const isChoice = form.type === 'single' || form.type === 'multiple'

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function setChoice(index, patch) {
    setForm((prev) => {
      const choices = prev.choices.map((c, i) => {
        if (i !== index) {
          // For single choice, selecting one correct clears the others.
          if (prev.type === 'single' && patch.is_correct) {
            return { ...c, is_correct: false }
          }
          return c
        }
        return { ...c, ...patch }
      })
      return { ...prev, choices }
    })
  }

  function addChoice() {
    setForm((prev) => ({
      ...prev,
      choices: [...prev.choices, { text: '', is_correct: false }],
    }))
  }

  function removeChoice(index) {
    setForm((prev) => ({
      ...prev,
      choices: prev.choices.filter((_, i) => i !== index),
    }))
  }

  function buildPayload() {
    const payload = {
      type: form.type,
      prompt: form.prompt,
      category: form.category,
      difficulty: form.difficulty,
    }
    if (isChoice) {
      payload.choices = form.choices
        .filter((c) => c.text.trim())
        .map((c, order) => ({ text: c.text, is_correct: c.is_correct, order }))
    } else if (form.type === 'numerical') {
      payload.numerical_answer =
        form.numerical_answer === '' ? null : form.numerical_answer
      payload.numerical_tolerance =
        form.numerical_tolerance === '' ? 0 : form.numerical_tolerance
    } else if (form.type === 'text') {
      payload.text_answers = form.text_answers_raw
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
      payload.text_match_mode = form.text_match_mode
    } else if (form.type === 'image') {
      payload.image_requirement = form.image_requirement
    }
    return payload
  }

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setErrors(null)
    try {
      await onSave(buildPayload())
    } catch (err) {
      setErrors(err?.data || { detail: 'Could not save the question.' })
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="card">
      <h2>{question ? 'Edit question' : 'New question'}</h2>

      {errors && (
        <div className="alert alert-error" role="alert">
          {Object.entries(errors).map(([field, msgs]) => (
            <div key={field}>
              <strong>{field}:</strong> {Array.isArray(msgs) ? msgs.join(' ') : String(msgs)}
            </div>
          ))}
        </div>
      )}

      <div className="row">
        <div className="field">
          <label htmlFor="q-type">Type</label>
          <select id="q-type" value={form.type} onChange={(e) => set('type', e.target.value)}>
            <option value="single">Single choice</option>
            <option value="multiple">Multiple choice</option>
            <option value="numerical">Numerical</option>
            <option value="text">Text</option>
            <option value="image">Image upload</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="q-difficulty">Difficulty</label>
          <select
            id="q-difficulty"
            value={form.difficulty}
            onChange={(e) => set('difficulty', e.target.value)}
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="q-category">Category</label>
          <input
            id="q-category"
            type="text"
            value={form.category}
            onChange={(e) => set('category', e.target.value)}
          />
        </div>
      </div>

      <div className="field">
        <label htmlFor="q-prompt">Prompt</label>
        <textarea
          id="q-prompt"
          required
          value={form.prompt}
          onChange={(e) => set('prompt', e.target.value)}
        />
      </div>

      {isChoice && (
        <fieldset style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '1rem' }}>
          <legend>Choices ({form.type === 'single' ? 'exactly one' : 'one or more'} correct)</legend>
          {form.choices.map((choice, index) => (
            <div className="row" key={index} style={{ alignItems: 'center' }}>
              <div className="field" style={{ flex: '3 1 200px', marginBottom: '0.5rem' }}>
                <label className="visually-hidden" htmlFor={`choice-${index}`}>
                  Choice {index + 1} text
                </label>
                <input
                  id={`choice-${index}`}
                  type="text"
                  value={choice.text}
                  placeholder={`Choice ${index + 1}`}
                  onChange={(e) => setChoice(index, { text: e.target.value })}
                />
              </div>
              <label style={{ flex: '0 0 auto', display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                <input
                  type={form.type === 'single' ? 'radio' : 'checkbox'}
                  name="correct-choice"
                  checked={choice.is_correct}
                  onChange={(e) => setChoice(index, { is_correct: e.target.checked })}
                />
                Correct
              </label>
              <button
                type="button"
                className="btn-secondary"
                style={{ flex: '0 0 auto' }}
                onClick={() => removeChoice(index)}
                disabled={form.choices.length <= 2}
              >
                Remove
              </button>
            </div>
          ))}
          <button type="button" className="btn-secondary" onClick={addChoice}>
            + Add choice
          </button>
        </fieldset>
      )}

      {form.type === 'numerical' && (
        <div className="row">
          <div className="field">
            <label htmlFor="q-num">Correct answer</label>
            <input
              id="q-num"
              type="number"
              step="any"
              value={form.numerical_answer}
              onChange={(e) => set('numerical_answer', e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="q-tol">Tolerance (±)</label>
            <input
              id="q-tol"
              type="number"
              step="any"
              value={form.numerical_tolerance}
              onChange={(e) => set('numerical_tolerance', e.target.value)}
            />
          </div>
        </div>
      )}

      {form.type === 'text' && (
        <>
          <div className="field">
            <label htmlFor="q-answers">Accepted answers / keywords (one per line)</label>
            <textarea
              id="q-answers"
              value={form.text_answers_raw}
              onChange={(e) => set('text_answers_raw', e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="q-match">Match mode</label>
            <select
              id="q-match"
              value={form.text_match_mode}
              onChange={(e) => set('text_match_mode', e.target.value)}
            >
              <option value="exact">Exact (normalized) match</option>
              <option value="contains_all">Answer contains all keywords</option>
              <option value="contains_any">Answer contains any keyword</option>
            </select>
          </div>
        </>
      )}

      {form.type === 'image' && (
        <div className="field">
          <label htmlFor="q-req">Image requirement</label>
          <textarea
            id="q-req"
            value={form.image_requirement}
            onChange={(e) => set('image_requirement', e.target.value)}
          />
        </div>
      )}

      <div className="btn-row">
        <button type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save question'}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}
