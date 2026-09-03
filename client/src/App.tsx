import './App.css'
import TransportTester from './transport/TransportTester'

/**
 * Phase 2 development placeholder.
 *
 * SCOPE WARNING: this component implements no chat UI, no authentication UI,
 * no contacts, and no cryptographic UX. It hosts the Phase 2 transport test
 * panel, which is a protocol debugging tool - not the chat application.
 */
function App() {
  const notImplemented = [
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
      <p className="phase">Development scaffold — Phase 2 (transport only)</p>

      <section aria-labelledby="status-heading">
        <h2 id="status-heading">Current security status</h2>
        <p>
          This build contains <strong>no encrypted messaging functionality</strong>. The
          WebSocket transport below routes plaintext test payloads and has not been
          security audited.
        </p>
        <ul>
          {notImplemented.map((item) => (
            <li key={item}>
              {item}: <span className="status">NOT IMPLEMENTED</span>
            </li>
          ))}
        </ul>
      </section>

      <TransportTester />
    </main>
  )
}

export default App
