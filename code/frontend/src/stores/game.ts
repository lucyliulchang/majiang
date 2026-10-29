import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { closeSocket, openSocket, sendMessage, setMessageHandler, setStatusHandler } from '../api/ws'
import { notifyConnectionRestored, preloadSounds, stopAll } from '../audio/audioManager'
import { handleSoundEvent, handleSoundMessage, resetGameSounds } from '../audio/useGameSounds'
import { useToast } from '../composables/useToast'
import type { ChatMessage, LegalAction, SeatView, Snapshot, SpectateView } from '../types'
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
  /** 观战视角：在座玩家为 null；观战者未选目标也为 null（只收公共状态） */
  const spectate = computed<SpectateView | null>(() => snapshot.value?.spectate ?? null)
  const spectateSeat = computed(() => spectate.value?.target_seat ?? null)
  const isSpectator = computed(() => selfSeat.value === null)
  /** 观战目标座位视图（未选目标为 null） */
  const spectateSeatView = computed<SeatView | null>(() => {
    const seat = spectateSeat.value
    if (seat === null) return null
    return snapshot.value?.seats?.[seat] ?? null
  })
  /** 每个座位的围观人数（0–10），满员置灰用 */
  const seatViewerCounts = computed<number[]>(() => {
    const counts = [0, 0, 0, 0]
    for (let seat = 0; seat < 4; seat += 1) {
      counts[seat] = snapshot.value?.seats?.[seat]?.spectator_count ?? 0
    }
    return counts
  })
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
      login_id: null,
      kind: 'system',
      content: text,
      created_at: new Date().toISOString()
    })
  }

  function handleEvent(type: string, data: any): void {
    // 08 §2：音效只由增量事件驱动（快照/欢迎包永不发声）
    handleSoundEvent(type, data, selfSeat.value)
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
      case 'event.spectate_changed':
        // 目标离座：横幅消失 + 提示重新选择（快照随后会把视角重置为未选择）
        if (data.target_seat === null && data.target_login_id) {
          const name = snapshot.value?.seats?.find(
            (seat) => seat && seat.login_id === data.target_login_id
          )?.display_name
          if (spectate.value?.target_login_id === data.target_login_id) {
            flash(`${name || '这位家人'} 已离座，请重新选择观战对象`, 'info')
          }
        }
        break
      case 'event.ready_changed':
        break
      default:
        break
    }
  }

  function handleMessage(type: string, data: any): void {
    // chat.message 的提示音在这里判定（系统播报 / 面板聚焦不出声）
    handleSoundMessage(type, data)
    if (type === 'state.snapshot') {
      snapshot.value = data as Snapshot
      if (data.phase !== 'settled') finished.value = finished.value
      return
    }
    if (type === 'room.welcome') {
      roomCode.value = data.room?.room_code || data.room?.code || roomCode.value
      chat.value = (data.chat || []) as ChatMessage[]
      // 进桌即预加载 15 个 SFX（Promise.allSettled，单个失败不影响其他）
      void preloadSounds()
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
    // 进新桌：清空上一桌的 settled 去重与限流状态
    resetGameSounds()
    let everConnected = false
    setMessageHandler(handleMessage)
    setStatusHandler((isUp, detail) => {
      connected.value = isUp
      connectionDetail.value = detail || ''
      if (isUp) {
        // 断线重连：800ms 静音期，吞掉快照恢复与突兀事件，不补播
        if (everConnected) {
          notifyConnectionRestored()
          void preloadSounds()
        }
        everConnected = true
        pushSystem('已连接到牌桌')
      } else if (detail) pushSystem(detail)
    })
    openSocket(code)
  }

  function leaveRoom(): void {
    closeSocket()
    stopAll()
    resetGameSounds()
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

  /** 选择/切换观战目标；null 表示取消跟随（S5b） */
  function followSeat(seat: number | null): void {
    send('spectate.target', { seat })
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
    spectate,
    spectateSeat,
    spectateSeatView,
    isSpectator,
    seatViewerCounts,
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
    sendChat,
    followSeat
  }
})
