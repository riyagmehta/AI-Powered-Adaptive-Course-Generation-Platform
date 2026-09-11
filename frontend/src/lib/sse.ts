import { authHeaders } from './api'

export interface SSEEvent {
  event: string
  data: Record<string, unknown>
}

export class SSEHttpError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

interface StreamSSEOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
  onEvent: (event: SSEEvent) => void
}

/**
 * Native EventSource can't send an Authorization header or a POST body, and
 * this API needs both (JWT auth, and /doubts takes a question in the body).
 * This reads the same `text/event-stream` wire format by hand over fetch.
 */
export async function streamSSE(url: string, { method = 'GET', body, signal, onEvent }: StreamSSEOptions): Promise<void> {
  const response = await fetch(url, {
    method,
    signal,
    headers: {
      ...authHeaders(),
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok || !response.body) {
    const raw = await response.text().catch(() => response.statusText)
    let detail: string | undefined
    try {
      detail = JSON.parse(raw).detail
    } catch {
      detail = undefined
    }
    throw new SSEHttpError(response.status, detail || raw || `Request failed with status ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''

    for (const block of blocks) {
      if (!block.trim()) continue
      const lines = block.split('\n')
      const eventLine = lines.find((l) => l.startsWith('event: '))
      const dataLine = lines.find((l) => l.startsWith('data: '))
      if (!eventLine || !dataLine) continue

      const event = eventLine.slice('event: '.length)
      const data = JSON.parse(dataLine.slice('data: '.length))
      onEvent({ event, data })
    }
  }
}
