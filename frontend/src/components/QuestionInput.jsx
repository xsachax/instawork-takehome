// Renders the appropriate answer control for a question type while a player is
// taking a quiz. Choice groups use fieldset/legend for accessibility.
import { QUESTION_TYPE_LABELS } from '../api'

export default function QuestionInput({ question, answer, onChange }) {
  const value = answer || {}

  function setValue(patch) {
    onChange({ ...value, ...patch })
  }

  function toggleChoice(choiceId, isMultiple) {
    if (isMultiple) {
      const current = new Set(value.selected_choice_ids || [])
      if (current.has(choiceId)) {
        current.delete(choiceId)
      } else {
        current.add(choiceId)
      }
      setValue({ selected_choice_ids: [...current] })
    } else {
      setValue({ selected_choice_ids: [choiceId] })
    }
  }

  if (question.type === 'single' || question.type === 'multiple') {
    const isMultiple = question.type === 'multiple'
    const selected = new Set(value.selected_choice_ids || [])
    return (
      <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="visually-hidden">
          {question.prompt} ({QUESTION_TYPE_LABELS[question.type]})
        </legend>
        {question.choices.map((choice) => (
          <label className="option" key={choice.id}>
            <input
              type={isMultiple ? 'checkbox' : 'radio'}
              name={`q-${question.id}`}
              checked={selected.has(choice.id)}
              onChange={() => toggleChoice(choice.id, isMultiple)}
            />
            <span>{choice.text}</span>
          </label>
        ))}
      </fieldset>
    )
  }

  if (question.type === 'numerical') {
    return (
      <div className="field">
        <label htmlFor={`num-${question.id}`}>Your numerical answer</label>
        <input
          id={`num-${question.id}`}
          type="number"
          step="any"
          inputMode="decimal"
          value={value.numerical ?? ''}
          onChange={(e) => setValue({ numerical: e.target.value })}
        />
      </div>
    )
  }

  if (question.type === 'text') {
    return (
      <div className="field">
        <label htmlFor={`text-${question.id}`}>Your answer</label>
        <textarea
          id={`text-${question.id}`}
          value={value.text ?? ''}
          onChange={(e) => setValue({ text: e.target.value })}
        />
      </div>
    )
  }

  if (question.type === 'image') {
    return (
      <div className="field">
        {question.image_requirement && (
          <p className="muted">Requirement: {question.image_requirement}</p>
        )}
        <label htmlFor={`img-${question.id}`}>Upload an image</label>
        <input
          id={`img-${question.id}`}
          type="file"
          accept="image/*"
          onChange={(e) => setValue({ file: e.target.files[0] || null })}
        />
        {value.file && (
          <p className="muted" aria-live="polite">Selected: {value.file.name}</p>
        )}
      </div>
    )
  }

  return null
}
