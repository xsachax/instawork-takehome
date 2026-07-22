import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, beforeEach } from 'vitest'
import Home from '../pages/Home'

describe('Home', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('renders an accessible password-type API key field with guidance', () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    )

    const field = screen.getByLabelText(/AI judge API key/i)
    expect(field).toHaveAttribute('type', 'password')
    // The field explains the with-key / without-key behaviour to the player.
    expect(screen.getByText(/graded by an AI judge/i)).toBeInTheDocument()
    expect(screen.getByText(/only auto/i)).toBeInTheDocument()
  })
})
