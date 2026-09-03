import { useCallback, useEffect, useRef, useState } from 'react'

import {
  buildEnvelope,
  parseInbound,
  transportUrl,
  type InboundMessage,
} from './protocol'

/**
 * Development transport test client.
 *
 * SCOPE WARNING: this is a protocol debugging tool for Phase 2, not the chat
 * application. It is NOT authenticated and NOT end-to-end encrypted. The
 * polished client is Phase 8's job; encryption is Phase 6's.
 */

type ConnectionState = 'disconnected' | 'connecting' | 'connected'

interface LogEntry {
  id: string
  direction: 'in' | 'out'
  summary: string
}

const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'

function summarize(message: InboundMessage): string {
  switch (message.type) {
    case 'connection.ready':
      return `connection.ready — id ${message.transport_client_id}, ${message.queued_message_count} queued`
    case 'message.receipt':
      return `message.receipt — from ${message.sender}: ${JSON.stringify(message.payload)}`
    case 'message.delivery_ack':
      return `message.delivery_ack — ${message.status}`
    case 'heartbeat.pong':
      return 'heartbeat.pong'
    case 'queue.status':
      return `queue.status — ${message.queued_message_count} queued`
    case 'protocol.error':
      return `protocol.error — ${message.code}: ${message.detail}`
  }
}

export function TransportTester() {
  const [clientId, setClientId] = useState('alice')
  const [recipient, setRecipient] = useState('bob')
  const [text, setText] = useState('transport test message')
  const [state, setState] = useState<ConnectionState>('disconnected')
  const [log, setLog] = useState<LogEntry[]>([])
  const socketRef = useRef<WebSocket | null>(null)

  const append = useCallback((direction: 'in' | 'out', summary: string) => {
    setLog((entries) => [
      ...entries.slice(-49),
      { id: crypto.randomUUID(), direction, summary },
    ])
  }, [])

  const disconnect = useCallback(() => {
    socketRef.current?.close()
    socketRef.current = null
    setState('disconnected')
  }, [])

  const connect = useCallback(() => {
    if (socketRef.current !== null) return
    setState('connecting')
    const socket = new WebSocket(transportUrl(clientId, API_BASE_URL))
    socketRef.current = socket

    socket.onopen = () => {
      setState('connected')
    }
    socket.onclose = () => {
      socketRef.current = null
      setState('disconnected')
      append('in', 'socket closed')
    }
    socket.onerror = () => {
      append('in', 'socket error')
    }
    socket.onmessage = (event: MessageEvent<string>) => {
      const message = parseInbound(event.data)
      append('in', message === null ? 'unparseable frame' : summarize(message))
    }
  }, [append, clientId])

  useEffect(() => () => socketRef.current?.close(), [])

  const send = useCallback(
    (type: 'message.send' | 'heartbeat.ping' | 'queue.status') => {
      const socket = socketRef.current
      if (socket === null || socket.readyState !== WebSocket.OPEN) return

      const envelope =
        type === 'message.send'
          ? buildEnvelope(type, clientId, { text }, recipient)
          : buildEnvelope(type, clientId)

      socket.send(JSON.stringify(envelope))
      append('out', `${type}${type === 'message.send' ? ` -> ${recipient}` : ''}`)
    },
    [append, clientId, recipient, text],
  )

  const connected = state === 'connected'

  return (
    <section className="transport" aria-labelledby="transport-heading">
      <h2 id="transport-heading">Development Transport Test</h2>
      <p className="transport-warning" role="note">
        <strong>Not Authenticated</strong> · <strong>Not End-to-End Encrypted</strong>
        <br />
        This panel exercises the Phase 2 WebSocket transport only. Messages are sent in
        plaintext over the connection and the server does not verify who you are.
      </p>

      <div className="transport-controls">
        <label>
          Transport client ID
          <input
            value={clientId}
            onChange={(event) => setClientId(event.target.value)}
            disabled={connected}
          />
        </label>
        <label>
          Recipient ID
          <input value={recipient} onChange={(event) => setRecipient(event.target.value)} />
        </label>
        <label>
          Test payload text
          <input value={text} onChange={(event) => setText(event.target.value)} />
        </label>
      </div>

      <div className="transport-actions">
        <button type="button" onClick={connect} disabled={state !== 'disconnected'}>
          Connect
        </button>
        <button type="button" onClick={disconnect} disabled={state === 'disconnected'}>
          Disconnect
        </button>
        <button type="button" onClick={() => send('message.send')} disabled={!connected}>
          Send test message
        </button>
        <button type="button" onClick={() => send('heartbeat.ping')} disabled={!connected}>
          Ping
        </button>
        <button type="button" onClick={() => send('queue.status')} disabled={!connected}>
          Queue status
        </button>
      </div>

      <p>
        Status: <span className="status">{state}</span>
      </p>

      <ul className="transport-log">
        {log.map((entry) => (
          <li key={entry.id} data-direction={entry.direction}>
            <span className="status">{entry.direction === 'in' ? '<-' : '->'}</span>{' '}
            {entry.summary}
          </li>
        ))}
      </ul>
    </section>
  )
}

export default TransportTester
