import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

/**
 * Phase 1 infrastructure tests: these verify that the frontend toolchain
 * (Vitest + jsdom + Testing Library + TypeScript) works. They are not tests
 * of application functionality — none exists yet.
 */
describe('App (Phase 1 scaffold)', () => {
  it('renders without crashing', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: /encrypted chat application/i }))
      .toBeInTheDocument()
  })

  it('states that encrypted messaging is not implemented', () => {
    render(<App />)
    expect(screen.getByText(/no encrypted messaging functionality/i)).toBeInTheDocument()
  })

  it('lists every unimplemented security capability', () => {
    render(<App />)
    // Exact string match so only the status <span> elements match, not their
    // ancestors (whose textContent also contains the phrase).
    expect(screen.getAllByText('NOT IMPLEMENTED')).toHaveLength(7)
  })
})
