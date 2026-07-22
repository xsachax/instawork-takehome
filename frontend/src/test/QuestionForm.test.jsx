import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import QuestionForm from '../components/QuestionForm'

describe('QuestionForm', () => {
  it('builds a choices payload for single-choice questions', async () => {
    const onSave = vi.fn().mockResolvedValue()
    render(<QuestionForm onSave={onSave} onCancel={() => {}} />)

    await userEvent.type(screen.getByLabelText('Prompt'), 'Capital of France?')
    await userEvent.type(screen.getByPlaceholderText('Choice 1'), 'Paris')
    await userEvent.type(screen.getByPlaceholderText('Choice 2'), 'London')
    // Mark the first choice correct (single-choice uses radios).
    await userEvent.click(screen.getAllByRole('radio')[0])
    await userEvent.click(screen.getByRole('button', { name: /save question/i }))

    expect(onSave).toHaveBeenCalledTimes(1)
    const payload = onSave.mock.calls[0][0]
    expect(payload.type).toBe('single')
    expect(payload.choices).toEqual([
      { text: 'Paris', is_correct: true, order: 0 },
      { text: 'London', is_correct: false, order: 1 },
    ])
  })

  it('converts text answers (one per line) into an array', async () => {
    const onSave = vi.fn().mockResolvedValue()
    render(<QuestionForm onSave={onSave} onCancel={() => {}} />)

    await userEvent.selectOptions(screen.getByLabelText('Type'), 'text')
    await userEvent.type(screen.getByLabelText('Prompt'), 'Largest ocean?')
    await userEvent.type(
      screen.getByLabelText(/accepted answers/i),
      'Pacific\nPacific Ocean',
    )
    await userEvent.click(screen.getByRole('button', { name: /save question/i }))

    const payload = onSave.mock.calls[0][0]
    expect(payload.type).toBe('text')
    expect(payload.text_answers).toEqual(['Pacific', 'Pacific Ocean'])
  })
})
