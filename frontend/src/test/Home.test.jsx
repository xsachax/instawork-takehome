import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Home from '../pages/Home'

describe('Home', () => {
  it('renders an optional password field for the judge API key', () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    )

    const input = screen.getByLabelText(/openai api key/i)
    expect(input).toHaveAttribute('type', 'password')
    expect(screen.getByText(/free-response\s+and image questions/i)).toBeInTheDocument()
  })
})
