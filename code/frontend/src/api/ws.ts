import { getToken } from './http'

type MessageHandler = (type: string, data: any) => void
type StatusHandler = (connected: boolean, detail?: string) => void

let socket: WebSocket | null = null
let onMessage: MessageHandler | null = null
let onStatus: StatusHandler | null = null
let activeCode = ''
let attempts = 0
let closedByUser = false
let heartbeat: number | undefined
let reconnectTimer: number | undefined

export function setMessageHandler(handler: MessageHandler): void {
  onMessage = handler
}

export function setStatusHandler(handler: StatusHandler): void {
  onStatus = handler
}

function buildUrl(code: string): string {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = encodeURIComponent(getToken())
  return `${protocol}//${location.host}/ws?token=${token}&code=${encodeURIComponent(code)}`
}

function startHeartbeat(): void {
  stopHeartbeat()
  heartbeat = window.setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'ping', data: {} }))
    }
  }, 20000)
}

function stopHeartbeat(): void {
  if (heartbeat !== undefined) {
    window.clearInterval(heartbeat)
    heartbeat = undefined
  }
}

function scheduleReconnect(): void {
  if (closedByUser || !activeCode) return
  const delay = Math.min(1000 * 2 ** attempts, 8000)
  attempts += 1
  onStatus?.(false, `连接断开，${Math.round(delay / 1000)} 秒后重连`)
  reconnectTimer = window.setTimeout(() => openSocket(activeCode), delay)
}

export function openSocket(code: string): void {
  activeCode = code
  closedByUser = false
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    socket.close()
  }
  socket = new WebSocket(buildUrl(code))

  socket.onopen = () => {
    attempts = 0
    onStatus?.(true)
    startHeartbeat()
    sendMessage('state.resync', {})
  }

  socket.onmessage = (event) => {
    const payload = safeParse(event.data)
    if (!payload || !payload.type) return
    onMessage?.(payload.type, payload.data ?? {})
  }

  socket.onclose = (event) => {
    stopHeartbeat()
    onStatus?.(false)
    if (event.code === 4001) {
      closedByUser = true
      onMessage?.('error', { code: 'UNAUTHORIZED', message: '登录已失效，请重新登录' })
      return
    }
    scheduleReconnect()
  }

  socket.onerror = () => {
    onStatus?.(false, '网络异常')
  }
}

function safeParse(raw: string): any {
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function sendMessage(type: string, data: Record<string, unknown> = {}): void {
  if (!socket || socket.readyState !== WebSocket.OPEN) return
  socket.send(JSON.stringify({ type, data }))
}

export function closeSocket(): void {
  closedByUser = true
  activeCode = ''
  if (reconnectTimer !== undefined) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = undefined
  }
  stopHeartbeat()
  if (socket) {
    socket.close()
    socket = null
  }
  onStatus?.(false)
}
