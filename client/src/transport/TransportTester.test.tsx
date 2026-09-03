import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import TransportTester from './TransportTester'

/**
 * These tests drive the panel against a fake WebSocket. They verify the
 * Phase 2 transport client's wiring and its safety labelling - they are not
 * tests of the server protocol, which is covered by the backend suite.
 */

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static readonly OPEN = 1

  url: string
  readyState = 0
  sent: string[] = []
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  open() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }

  receive(payload: unknown) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(payload) }))
  }

  send(data: string) {
    this.sent.push(data)
  }

  close() {
    this.readyState = 3
    this.onclose?.()
  }
}

beforeEach(() => {
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function latestSocket(): FakeWebSocket {
  const socket = FakeWebSocket.instances.at(-1)
  if (socket === undefined) throw new Error('no socket was created')
  return socket
}

describe('TransportTester', () => {
  it('states plainly that it is unauthenticated and unencrypted', () => {
    render(<TransportTester />)
    expect(screen.getByText('Not Authenticated')).toBeInTheDocument()
    expect(screen.getByText('Not End-to-End Encrypted')).toBeInTheDocument()
  })

  it('starts disconnected', () => {
    render(<TransportTester />)
    expect(screen.getByText('disconnected')).toBeInTheDocument()
  })

  it('connects to the versioned endpoint with the chosen client id', async () => {
    const user = userEvent.setup()
    render(<TransportTester />)

    await user.click(screen.getByRole('button', { name: 'Connect' }))
    latestSocket().open()

    expect(latestSocket().url).toContain('/ws/v1')
    expect(latestSocket().url).toContain('client_id=alice')
    expect(await screen.findByText('connected')).toBeInTheDocument()
  })

  it('sends a well-formed message.send envelope', async () => {
    const user = userEvent.setup()
    render(<TransportTester />)

    await user.click(screen.getByRole('button', { name: 'Connect' }))
    latestSocket().open()
    await user.click(await screen.findByRole('button', { name: 'Send test message' }))

    const envelope: unknown = JSON.parse(latestSocket().sent[0])
    expect(envelope).toMatchObject({
      version: '1',
      type: 'message.send',
      sender: 'alice',
      recipient: 'bob',
    })
    expect((envelope as { message_id: string }).message_id).toMatch(/^[0-9a-f-]{36}$/)
  })

  it('renders a delivery acknowledgement', async () => {
    const user = userEvent.setup()
    render(<TransportTester />)

    await user.click(screen.getByRole('button', { name: 'Connect' }))
    latestSocket().open()
    latestSocket().receive({
      type: 'message.delivery_ack',
      message_id: 'abc',
      status: 'delivered',
    })

    expect(await screen.findByText(/message.delivery_ack — delivered/)).toBeInTheDocument()
  })

  it('renders a received transport message', async () => {
    const user = userEvent.setup()
    render(<TransportTester />)

    await user.click(screen.getByRole('button', { name: 'Connect' }))
    latestSocket().open()
    latestSocket().receive({
      type: 'message.receipt',
      message_id: 'abc',
      sender: 'bob',
      recipient: 'alice',
      timestamp: '2026-09-03T10:30:00Z',
      payload: { text: 'hello there' },
    })

    expect(await screen.findByText(/message.receipt — from bob/)).toBeInTheDocument()
  })

  it('renders protocol errors verbatim', async () => {
    const user = userEvent.setup()
    render(<TransportTester />)

    await user.click(screen.getByRole('button', { name: 'Connect' }))
    latestSocket().open()
    latestSocket().receive({
      type: 'protocol.error',
      code: 'WS_1007_SENDER_MISMATCH',
      detail: 'Sender does not match the connection identity.',
      message_id: null,
    })

    expect(await screen.findByText(/WS_1007_SENDER_MISMATCH/)).toBeInTheDocument()
  })

  it('does not send while disconnected', async () => {
    const user = userEvent.setup()
    render(<TransportTester />)

    expect(screen.getByRole('button', { name: 'Send test message' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Connect' }))
    latestSocket().open()
    await user.click(await screen.findByRole('button', { name: 'Disconnect' }))

    expect(screen.getByRole('button', { name: 'Send test message' })).toBeDisabled()
  })
})
