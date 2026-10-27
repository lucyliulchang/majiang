import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { closeSocket, openSocket, sendMessage, setMessageHandler, setStatusHandler } from '../api/ws'
import { useToast } from '../composables/useToast'
import type { ChatMessage, LegalAction, SeatView, Snapshot } from '../types'
import { tileName, tilesName } from '../utils/tile'

export interface Banner {
  id: number
  text: string
  kind: 'info' | 'action' | 'win'
}

export const useGameStore = defineStore('game', () => {
  const toast = useToast()

  const snapshot = ref<Snapshot | null>(null)
  const chat = ref<ChatMessage[]>([])
  const connected = ref(false)
  const connectionDetail = ref('')
  const roomCode = ref('')
  const banner = ref<Banner | null>(null)
  const finished = ref<{ scores: { seat: number; name: string; total: number }[] } | null>(null)
  const busy = ref(false)

  let bannerSeq = 0
  let bannerTimer: number | undefined

  const seats = computed<SeatView[]>(() => (snapshot.value?.seats || []).filter(Boolean) as SeatView[])
  const selfSeat = computed(() => snapshot.value?.self_seat ?? null)
  const mySeatView = computed(() =>
    selfSeat.value === null ? null : (snapshot.value?.seats?.[selfSeat.value] ?? null)
  )
  const hand = computed(() => snapshot.value?.hand ?? [])
  const drawn = computed(() => snapshot.value?.drawn ?? null)
  const phase = computed(() => snapshot.value?.phase ?? 'waiting')
  const turn = computed(() => snapshot.value?.turn ?? null)
  const legal = computed<LegalAction[]>(() => snapshot.value?.legal?.actions ?? [])
  const ruleBrief = computed(() => snapshot.value?.room?.rule_brief ?? null)
  const result = computed(() => snapshot.value?.result ?? null)
  const isHost = computed(() => Boolean(snapshot.value && mySeatView.value?.is_host))
  const isMyTurn = computed(
    () => selfSeat.value !== null && turn.value === selfSeat.value && phase.value === 'discard'
  )
  const everyoneReady = computed(
    () => seats.value.length === 4 && seats.value.every((seat) => seat.ready)
  )
  const tenpai = computed<Record<string, number[]>>(() => snapshot.value?.tenpai ?? {})

  function hasAction(action: string): boolean {
    return legal.value.some((item) => item.action === action)
  }

  function actionsOf(action: string): LegalAction[] {
    return legal.value.filter((item) => item.action === action)
  }

  function seatName(seat: number | null | undefined): string {
    if (seat === null || seat === undefined) return '牌桌'
    return snapshot.value?.seats?.[seat]?.display_name || `座位${seat + 1}`
  }

  function flash(text: string, kind: Banner['kind'] = 'info'): void {
    banner.value = { id: ++bannerSeq, text, kind }
    if (bannerTimer !== undefined) window.clearTimeout(bannerTimer)
    bannerTimer = window.setTimeout(() => {
      banner.value = null
    }, 2600)
  }

  function pushSystem(text: string): void {
    chat.value.push({
      id: Date.now() + Math.random(),
      user_id: null,
      kind: 'system',
      content: text,
      created_at: new Date().toISOString()
    })
  }

  function handleEvent(type: string, data: any): void {
    switch (type) {
      case 'event.discarded':
        flash(`${seatName(data.seat)} 打出 ${tileName(data.tile)}`, 'action')
        break
      case 'event.claimed': {
        const verb = data.action === 'pong' ? '碰' : '吃'
        const text = data.tiles ? tilesName(data.tiles) : tileName(data.tile)
        flash(`${seatName(data.seat)} ${verb} ${text}`, 'action')
        break
      }
      case 'event.kongged': {
        const kindText = data.kind === 'hidden' ? '暗杠' : data.kind === 'added' ? '补杠' : '明杠'
        flash(`${seatName(data.seat)} ${kindText} ${tileName(data.tile)}`, 'action')
        break
      }
      case 'event.claim_open':
        if (data.reason === 'rob_kong') flash('有人补杠，可抢杠胡', 'win')
        break
      case 'event.auto_discard':
        flash(`${seatName(data.seat)} 超时，系统自动出牌`, 'info')
        break
      case 'event.claim_timeout':
        flash(data.message || '超时未响应，按过处理', 'info')
        break
      case 'event.settled':
        if (data.winner_seat !== null && data.winner_seat !== undefined) {
          flash(`${seatName(data.winner_seat)} 胡牌`, 'win')
        } else {
          flash('荒庄，本局无人胡牌', 'info')
        }
        break
      case 'event.game_finished':
        finished.value = data
        break
      case 'event.ready_changed':
        break
      default:
        break
    }
  }

  function handleMessage(type: string, data: any): void {
    if (type === 'state.snapshot') {
      snapshot.value = data as Snapshot
      if (data.phase !== 'settled') finished.value = finished.value
      return
    }
    if (type === 'room.welcome') {
      roomCode.value = data.room?.code || roomCode.value
      chat.value = (data.chat || []) as ChatMessage[]
      return
    }
    if (type === 'chat.message') {
      chat.value.push(data as ChatMessage)
      if (chat.value.length > 300) chat.value.splice(0, chat.value.length - 300)
      return
    }
    if (type === 'error') {
      toast.error(data.message || '操作失败')
      if (data.code === 'UNAUTHORIZED') {
        window.setTimeout(() => {
          window.location.href = '/login'
        }, 1200)
      }
      return
    }
    if (type.startsWith('event.')) handleEvent(type, data)
  }

  function enterRoom(code: string): void {
    roomCode.value = code
    snapshot.value = null
    chat.value = []
    finished.value = null
    setMessageHandler(handleMessage)
    setStatusHandler((isUp, detail) => {
      connected.value = isUp
      connectionDetail.value = detail || ''
      if (isUp) pushSystem('已连接到牌桌')
      else if (detail) pushSystem(detail)
    })
    openSocket(code)
  }

  function leaveRoom(): void {
    closeSocket()
    snapshot.value = null
    chat.value = []
    roomCode.value = ''
    connected.value = false
  }

  function send(type: string, data: Record<string, unknown> = {}): void {
    sendMessage(type, data)
  }

  function toggleReady(): void {
    send('seat.ready', {})
  }

  function startGame(): void {
    send('game.start', {})
  }

  function nextRound(): void {
    finished.value = null
    send('game.next', {})
  }

  function discard(tile: number): void {
    if (!isMyTurn.value) return
    send('game.action', { action: 'discard', tiles: [tile] })
  }

  function act(action: LegalAction): void {
    send('game.action', {
      action: action.action,
      tiles: action.tiles || [],
      kong_kind: action.kong_kind || null
    })
  }

  function pass(): void {
    send('game.action', { action: 'pass' })
  }

  function sendChat(content: string): void {
    const text = content.trim()
    if (!text) return
    send('chat.send', { content: text })
  }

  return {
    snapshot,
    chat,
    connected,
    connectionDetail,
    roomCode,
    banner,
    finished,
    busy,
    seats,
    selfSeat,
    mySeatView,
    hand,
    drawn,
    phase,
    turn,
    legal,
    ruleBrief,
    result,
    isHost,
    isMyTurn,
    everyoneReady,
    tenpai,
    hasAction,
    actionsOf,
    seatName,
    enterRoom,
    leaveRoom,
    send,
    toggleReady,
    startGame,
    nextRound,
    discard,
    act,
    pass,
    sendChat
  }
})
