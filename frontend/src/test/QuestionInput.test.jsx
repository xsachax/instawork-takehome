import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import QuestionInput from '../components/QuestionInput'

const singleQuestion = {
  id: 1,
  type: 'single',
  prompt: 'Pick one',
  choices: [
    { id: 10, text: 'Alpha' },
    { id: 11, text: 'Beta' },
  ],
}

const multipleQuestion = {
  id: 2,
  type: 'multiple',
  prompt: 'Pick some',
  choices: [
    { id: 20, text: 'One' },
    { id: 21, text: 'Two' },
    { id: 22, text: 'Three' },
  ],
}

describe('QuestionInput', () => {
  it('renders radio buttons for single choice inside a fieldset', () => {
    render(<QuestionInput question={singleQuestion} answer={{}} onChange={() => {}} />)
    const radios = screen.getAllByRole('radio')
    expect(radios).toHaveLength(2)
    expect(screen.getByText('Alpha')).toBeInTheDocument()
  })

  it('reports the selected id when a single choice is picked', async () => {
    const onChange = vi.fn()
    render(<QuestionInput question={singleQuestion} answer={{}} onChange={onChange} />)
    await userEvent.click(screen.getByLabelText('Beta'))
    expect(onChange).toHaveBeenCalledWith({ selected_choice_ids: [11] })
  })

  it('renders checkboxes for multiple choice and accumulates selections', async () => {
    const onChange = vi.fn()
    render(
      <QuestionInput
        question={multipleQuestion}
        answer={{ selected_choice_ids: [20] }}
        onChange={onChange}
      />,
    )
    expect(screen.getAllByRole('checkbox')).toHaveLength(3)
    await userEvent.click(screen.getByLabelText('Two'))
    expect(onChange).toHaveBeenCalledWith({ selected_choice_ids: [20, 21] })
  })

  it('renders a labelled numerical input', async () => {
    const onChange = vi.fn()
    render(
      <QuestionInput
        question={{ id: 3, type: 'numerical', prompt: '2+2' }}
        answer={{}}
        onChange={onChange}
      />,
    )
    const input = screen.getByLabelText(/numerical answer/i)
    expect(input).toHaveAttribute('type', 'number')
    await userEvent.type(input, '4')
    expect(onChange).toHaveBeenCalledWith({ numerical: '4' })
  })

  it('renders a labelled text area', async () => {
    const onChange = vi.fn()
    render(
      <QuestionInput
        question={{ id: 4, type: 'text', prompt: 'name' }}
        answer={{}}
        onChange={onChange}
      />,
    )
    const box = screen.getByLabelText(/your answer/i)
    await userEvent.type(box, 'hi')
    expect(onChange).toHaveBeenCalled()
  })

  it('shows the requirement and a file input for image questions', () => {
    render(
      <QuestionInput
        question={{
          id: 5,
          type: 'image',
          prompt: 'upload',
          image_requirement: 'A blue thing',
        }}
        answer={{}}
        onChange={() => {}}
      />,
    )
    expect(screen.getByText(/A blue thing/)).toBeInTheDocument()
    expect(screen.getByLabelText(/upload an image/i)).toHaveAttribute('type', 'file')
  })
})
