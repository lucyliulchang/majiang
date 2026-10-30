import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import { api } from '../api/http'
import { closeSocket, openSocket, sendMessage, setMessageHandler, setStatusHandler } from '../api/ws'
import { notifyConnectionRestored, preloadSounds, stopAll } from '../audio/audioManager'
import { handleSoundEvent, handleSoundMessage, resetGameSounds } from '../audio/useGameSounds'
import { useToast } from '../composables/useToast'
import type { ChatMessage, JoinRequest, LegalAction, SeatView, Snapshot, SpectateView } from '../types'
import { isLegalChow } from '../utils/chow'
import { tileName, tilesName } from '../utils/tile'

/** 吃牌最多选两张：`chow-select` 的手牌多选上限 */
export const CHOW_PICK_LIMIT = 2

export interface Banner {
  id: number
  text: string
  kind: 'info' | 'action' | 'win'
}

/** 整场结束（打满局数或房主提前结束）的广播载荷 */
export interface GameFinished {
  scores: { seat: number; name: string; total: number }[]
  /** true = 房主提前收场，未结算的这一局作废 */
  aborted?: boolean
  /** true = 自然打满（本场到此为止，房间随即置 CLOSED） */
  final?: boolean
  ended_by_seat?: number | null
  ended_by_name?: string | null
}

export const useGameStore = defineStore('game', () => {
  const toast = useToast()

  const snapshot = ref<Snapshot | null>(null)
  const chat = ref<ChatMessage[]>([])
  const connected = ref(false)
  const connectionDetail = ref('')
  const roomCode = ref('')
  const banner = ref<Banner | null>(null)
  const finished = ref<GameFinished | null>(null)
  /** 房主收摊：房间已在服务端关闭，前端不再重连、也不再显示牌桌 */
  const roomClosed = ref(false)
  const busy = ref(false)
  /** 正在关房（结束牌局）：防重复点击，也用来判断 3s 兜底是否还有效 */
  const closing = ref(false)
  /** S10：非本家庭成员凭码进桌 —— 已申请、等房主在牌桌上确认 */
  const joinPending = ref(false)
  const joinPendingInfo = ref<{ room_name?: string; family_name?: string; message?: string } | null>(null)
  /** 房主没同意（或被关房）：显示原因，玩家自己回大厅 */
  const joinDenied = ref('')
  /** 房主专属：待确认的进桌申请 */
  const joinRequests = ref<JoinRequest[]>([])

  let bannerSeq = 0
  let bannerTimer: number | undefined
  /** 结束牌局的 3s 兜底：WS 没回执就改走 REST 关房（B-1） */
  let endTimer: number | undefined
  const END_FALLBACK_MS = 3000

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

  // ---- 吃牌选两张（v1.1.0 U-2）：点「吃」不提交，先进 chow-select ----
  /** 选牌态：true 时动作条收起、手牌可多选（最多两张） */
  const chowSelecting = ref(false)
  /** 已选的两张手牌（牌面值；同值可重复一次，代表手里确实有两张） */
  const chowPicks = ref<number[]>([])
  const chowClaimTile = computed(() => snapshot.value?.legal?.claim_tile ?? null)
  /**
   * 服务端下发的候选组合（`legal.actions[].tiles`）。
   * 按 04 §9.5 它们只是**推荐**（默认高亮第一组），不是唯一解——玩家可以自己点手牌。
   */
  const chowCandidates = computed<number[][]>(() => {
    const seen = new Set<string>()
    const list: number[][] = []
    for (const item of legal.value) {
      if (item.action !== 'chow') continue
      const tiles = item.tiles ?? []
      if (tiles.length !== 2) continue
      const key = [...tiles].sort((a, b) => a - b).join('-')
      if (seen.has(key)) continue
      seen.add(key)
      list.push(tiles)
    }
    return list
  })
  const chowRecommended = computed<number[]>(() => chowCandidates.value[0] ?? [])
  /** 本地镜像服务端顺子校验，只用来置灰「确认吃」；裁决仍在服务端 */
  const chowValid = computed(() => isLegalChow(chowClaimTile.value, chowPicks.value, hand.value))
  const chowHint = computed(() => {
    if (!chowSelecting.value) return ''
    if (chowPicks.value.length < CHOW_PICK_LIMIT) {
      return `再点 ${CHOW_PICK_LIMIT - chowPicks.value.length} 张手牌`
    }
    return chowValid.value ? '' : '这两张不能和被吃的牌组成顺子'
  })

  /** 进入选牌态：默认套用服务端推荐组合，玩家可改选 */
  function beginChow(): void {
    if (!chowCandidates.value.length) return
    chowSelecting.value = true
    chowPicks.value = [...chowRecommended.value]
  }

  function setChowPicks(tiles: number[]): void {
    chowPicks.value = tiles.slice(0, CHOW_PICK_LIMIT)
  }

  /** 取消只退出选牌态（可再次进入），不提交；真放弃请点「过」 */
  function cancelChow(): void {
    chowSelecting.value = false
    chowPicks.value = []
  }

  /** 提交吃牌：两张**手牌**（不含被吃的那张），由服务端严格校验（04 §9.3） */
  function chow(tiles: number[]): void {
    if (tiles.length !== 2) return
    if (send('game.action', { action: 'chow', tiles: [...tiles] })) cancelChow()
  }

  function confirmChow(): void {
    if (!chowValid.value) return
    chow([...chowPicks.value])
  }

  // 窗口一关（收口 / 超时 / 换牌 / 换局）立刻清空选牌态，避免污染下一张牌
  watch(
    () => `${snapshot.value?.legal?.claim_tile ?? ''}|${legal.value.some((i) => i.action === 'chow')}|${phase.value}`,
    () => {
      if (!chowSelecting.value && !chowPicks.value.length) return
      cancelChow()
    }
  )

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
        finished.value = data as GameFinished
        // 收到整场结算即视为结束牌局已生效，撤掉 3s 兜底
        closing.value = false
        clearEndFallback()
        break
      case 'event.seats_drawn':
        // 新一场开桌：收起上一场的整场结算层
        finished.value = null
        break
      case 'event.room_closed':
        // 房主结束了牌局并关房：断掉连接（不重连），停在结算层由玩家自己回大厅
        closing.value = false
        clearEndFallback()
        roomClosed.value = true
        closeSocket()
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
      joinRequests.value = (data.join_requests || []) as JoinRequest[]
      if (data.phase !== 'settled') finished.value = finished.value
      return
    }
    if (type === 'room.welcome') {
      roomCode.value = data.room?.room_code || data.room?.code || roomCode.value
      chat.value = (data.chat || []) as ChatMessage[]
      // 房主同意后服务端补发 welcome：收起等待遮罩
      joinPending.value = false
      joinPendingInfo.value = null
      joinDenied.value = ''
      // 进桌即预加载 15 个 SFX（Promise.allSettled，单个失败不影响其他）
      void preloadSounds()
      return
    }
    if (type === 'room.join_pending') {
      // 非本家庭成员凭码进桌：先等着，房主在牌桌上点「同意」后才收 welcome
      joinPending.value = true
      joinPendingInfo.value = data
      return
    }
    if (type === 'room.join_denied') {
      joinPending.value = false
      joinPendingInfo.value = null
      joinRequests.value = []
      joinDenied.value = data?.message || '房主没有同意这次进桌'
      // 服务端不再推房态，客户端主动断开避免无限重连
      closeSocket()
      return
    }
    if (type === 'chat.message') {
      chat.value.push(data as ChatMessage)
      if (chat.value.length > 300) chat.value.splice(0, chat.value.length - 300)
      return
    }
    if (type === 'error') {
      toast.error(data.message || '操作失败')
      if (data.code === 'CLOSE_FAILED') {
        // 关房没落库：房间还开着，别跳转，让房主原地重试或回大厅关桌
        closing.value = false
        clearEndFallback()
      }
      if (data.code === 'BAD_CHOW') {
        // 服务端独立拒绝（前端置灰被绕过 / 手牌已变）：退出选牌态，让玩家重来
        cancelChow()
      }
      if (data.code === 'UNAUTHORIZED') {
        window.setTimeout(() => {
          // 按构建 base 跳登录：手机版在 /mjmobile/ 下，写死 /login 会 404
          window.location.href = `${import.meta.env.BASE_URL}login`
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
    roomClosed.value = false
    joinPending.value = false
    joinPendingInfo.value = null
    joinDenied.value = ''
    joinRequests.value = []
    cancelChow()
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
    clearEndFallback()
    closing.value = false
    closeSocket()
    stopAll()
    resetGameSounds()
    snapshot.value = null
    chat.value = []
    roomCode.value = ''
    connected.value = false
    joinPending.value = false
    joinPendingInfo.value = null
    joinDenied.value = ''
    joinRequests.value = []
    cancelChow()
  }

  /** 房主确认/拒绝「非本家庭成员凭码进桌」的申请（S10） */
  function approveJoin(loginId: string, allow: boolean): void {
    send('room.approve', { login_id: loginId, allow })
  }

  function dismissJoinDenied(): void {
    joinDenied.value = ''
  }

  /** 发 WS 消息；连接不在 OPEN 时明确提示（旧版静默丢弃，用户以为点了就生效） */
  function send(type: string, data: Record<string, unknown> = {}): boolean {
    const ok = sendMessage(type, data)
    if (!ok) toast.warn('连接已断开，正在重连…')
    return ok
  }

  function clearEndFallback(): void {
    if (endTimer !== undefined) {
      window.clearTimeout(endTimer)
      endTimer = undefined
    }
  }

  /** 房间主键（快照 `room.room_id`）：REST 关房兜底要用它拼 `/rooms/{id}/close` */
  function roomId(): number | null {
    const id = snapshot.value?.room?.room_id
    return typeof id === 'number' && id > 0 ? id : null
  }

  /**
   * REST 关房兜底：`POST /api/rooms/{id}/close`（房主/家庭管理员；重复调用幂等）。
   *
   * WS 断开、或 3s 内既没收到 `game_finished` 也没收到 `room_closed` 时用它，
   * 成功后置 `roomClosed` 并断开连接（不重连，停在"这桌已经结束了"遮罩）。
   * `silent=true` 用于"回大厅"顺手关房：失败不打扰用户，交给大厅重试。
   */
  async function closeRoomByApi(silent = false): Promise<boolean> {
    const id = roomId()
    if (id === null) {
      if (!silent) toast.error('关房失败，请在大厅关闭牌桌')
      return false
    }
    try {
      await api.post(`/rooms/${id}/close`, {})
    } catch (error) {
      if (!silent) {
        toast.error(`${(error as Error).message || '关房失败'}，请在大厅关闭牌桌`)
      }
      return false
    }
    roomClosed.value = true
    closeSocket()
    if (!silent) toast.success('已通过大厅接口关闭牌桌')
    return true
  }

  /**
   * 开桌的人结束本场（已打完的局保留，未结算的一局作废，房间随即关闭）。
   *
   * WS 只是快路径：发出去后起 3s 定时器，若既没等到 `event.game_finished`
   * 也没等到 `event.room_closed`（断网/服务端没回执），改走 REST 关房兜底；
   * 两条路都失败才提示"请在大厅关闭牌桌"。
   */
  function endGame(): void {
    if (closing.value) return
    closing.value = true
    clearEndFallback()
    endTimer = window.setTimeout(() => {
      endTimer = undefined
      if (!closing.value) return
      void closeRoomByApi().finally(() => {
        closing.value = false
      })
    }, END_FALLBACK_MS)
    if (sendMessage('game.finish', {})) return
    // 连接不在 OPEN：不必等 3s，立刻兜底
    clearEndFallback()
    void closeRoomByApi().finally(() => {
      closing.value = false
    })
  }

  /**
   * 回大厅：房主在房间还没关掉时先幂等调一次关房接口（已 CLOSED 就是 0 行更新），
   * 其他人直接退——他们没关房权限，别弹 FORBIDDEN。
   */
  async function exitToLobby(): Promise<void> {
    if (!roomClosed.value && isHost.value) await closeRoomByApi(true)
    leaveRoom()
  }

  function toggleReady(): void {
    send('seat.ready', {})
  }

  /** 开局：房主可顺带定本场出牌限时（0 秒 = 不限时） */
  function startGame(turnTimeout?: { enabled: boolean; seconds: number } | null): void {
    send('game.start', turnTimeout ? { turn_timeout: turnTimeout } : {})
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
    roomClosed,
    busy,
    closing,
    joinPending,
    joinPendingInfo,
    joinDenied,
    joinRequests,
    approveJoin,
    dismissJoinDenied,
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
    chowSelecting,
    chowPicks,
    chowClaimTile,
    chowCandidates,
    chowRecommended,
    chowValid,
    chowHint,
    beginChow,
    setChowPicks,
    cancelChow,
    chow,
    confirmChow,
    enterRoom,
    leaveRoom,
    send,
    toggleReady,
    startGame,
    nextRound,
    endGame,
    closeRoomByApi,
    exitToLobby,
    discard,
    act,
    pass,
    sendChat,
    followSeat
  }
})
