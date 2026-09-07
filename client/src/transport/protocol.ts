/**
 * Phase 2 WebSocket transport protocol types for the development test client.
 *
 * SCOPE: transport only. Nothing here authenticates anyone and nothing here
 * encrypts anything. See docs/WEBSOCKET_PROTOCOL.md.
 */

export const PROTOCOL_VERSION = '1' as const

export type DeliveryStatus =
  | 'delivered'
  | 'queued'
  | 'recipient_unavailable'
  | 'rejected'

export interface OutboundEnvelope {
  version: typeof PROTOCOL_VERSION
  message_id: string
  type: 'message.send' | 'heartbeat.ping' | 'queue.status'
  sender: string
  recipient?: string
  timestamp: string
  payload: Record<string, unknown>
}

export interface ConnectionReadyMessage {
  type: 'connection.ready'
  connection_id: string
  transport_client_id: string
  authenticated: false
  identity_status: 'TRANSPORT_TEST_IDENTITY'
  protocol_version: string
  heartbeat_interval_seconds: number
  idle_timeout_seconds: number
  max_message_bytes: number
  queued_message_count: number
}

export interface MessageReceiptMessage {
  type: 'message.receipt'
  message_id: string
  sender: string
  recipient: string
  timestamp: string
  payload: Record<string, unknown>
}

export interface DeliveryAckMessage {
  type: 'message.delivery_ack'
  message_id: string
  status: DeliveryStatus
}

export interface HeartbeatPongMessage {
  type: 'heartbeat.pong'
  message_id: string
  server_time: string
}

export interface QueueStatusMessage {
  type: 'queue.status'
  message_id: string
  queued_message_count: number
}

export interface ProtocolErrorMessage {
  type: 'protocol.error'
  code: string
  detail: string
  message_id: string | null
}

export type InboundMessage =
  | ConnectionReadyMessage
  | MessageReceiptMessage
  | DeliveryAckMessage
  | HeartbeatPongMessage
  | QueueStatusMessage
  | ProtocolErrorMessage

/** Narrow an unknown parsed frame to a protocol message. */
export function parseInbound(raw: string): InboundMessage | null {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return null
  }
  if (typeof parsed !== 'object' || parsed === null) return null
  const candidate = parsed as { type?: unknown }
  if (typeof candidate.type !== 'string') return null
  return parsed as InboundMessage
}

/** Build a valid envelope. `sender` is advisory: the server derives its own. */
export function buildEnvelope(
  type: OutboundEnvelope['type'],
  sender: string,
  payload: Record<string, unknown> = {},
  recipient?: string,
): OutboundEnvelope {
  const envelope: OutboundEnvelope = {
    version: PROTOCOL_VERSION,
    message_id: crypto.randomUUID(),
    type,
    sender,
    timestamp: new Date().toISOString(),
    payload,
  }
  if (recipient !== undefined) envelope.recipient = recipient
  return envelope
}

/** WebSocket URL for a transport identity, derived from the API base URL. */
export function transportUrl(clientId: string, apiBaseUrl: string): string {
  const base = new URL(apiBaseUrl)
  base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
  base.pathname = '/ws/v1'
  base.searchParams.set('client_id', clientId)
  return base.toString()
}
