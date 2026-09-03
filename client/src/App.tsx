import './App.css'

/**
 * Phase 1 development placeholder.
 *
 * SCOPE WARNING: this component intentionally implements no chat UI, no
 * authentication UI, no contacts, no WebSocket logic, and no cryptographic
 * UX. It exists only to prove that the React + TypeScript + Vite toolchain,
 * ESLint, Vitest, and the production build all work.
 */
function App() {
  const notImplemented = [
    'WebSocket transport',
    'Authentication',
    'Identity verification',
    'Key agreement',
    'End-to-end encryption',
    'Ratcheting',
    'Production hardening',
  ]

  return (
    <main className="app">
      <h1>Encrypted Chat Application</h1>
      <p className="phase">Development scaffold — Phase 1</p>

      <section aria-labelledby="status-heading">
        <h2 id="status-heading">Current security status</h2>
        <p>
          This build contains <strong>no encrypted messaging functionality</strong>. It is a
          development environment scaffold only and has not been security audited.
        </p>
        <ul>
          {notImplemented.map((item) => (
            <li key={item}>
              {item}: <span className="status">NOT IMPLEMENTED</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  )
}

export default App
