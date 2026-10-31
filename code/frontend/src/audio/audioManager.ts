/**
 * 08 §3/§4 的播放内核：单例、预加载、解锁、限流、降级。
 *
 * 只用浏览器原生 API（AudioContext + HTMLAudioElement），不引入第三方音频库。
 * 任何异常都走静音降级：不抛未捕获错误，不阻塞对局。
 *
 * v1.1（I11 / S-1）新增「牌面报牌」人声：走**同一套**并发 / 优先级 / 淡出 / 降级内核，
 * 优先级 P3、默认音量 55，另加一条**全局 250ms 最短间隔**（08 §3 规则 6）。
 * 34 个报牌资源**不进** `SOUND_KEYS` 预加载清单（见 `voiceMap.ts`），避免首屏流量失控。
 */
import { reactive } from 'vue'

import { SOUND_KEYS, SOUND_SPECS, sfxUrl, type SoundKey, type SoundPriority } from './soundKeys'
import { VOICE_BASENAME_BY_TILE, voiceBaseFromTarget, voiceUrlOfBase } from './voiceMap'

const MAX_CONCURRENT = 4
const DEDUPE_MS = 150
const P0_SUPPRESS_MS = 200
const RESUME_MUTE_MS = 800
const FADE_OUT_SECONDS = 0.03
const FALLBACK_POOL_SIZE = 4

/** 08 §2.1 / §3：牌面报牌人声 —— P3、默认音量 55（与 `discard` 同档） */
const VOICE_PRIORITY: SoundPriority = 3
const VOICE_VOLUME = 55
/** 08 §3 规则 6：任意两张牌的报牌声之间至少间隔 250ms */
const VOICE_MIN_INTERVAL_MS = 250
/** 08 §4.5：空闲预热每批 4 个（34 个共 9 批） */
const VOICE_PRELOAD_BATCH = 4

export interface AudioRuntimeState {
  /** 用户总开关（关闭后不建音源、不发请求） */
  enabled: boolean
  /** 用户音量 0–100（主增益 = volume / 100） */
  volume: number
  /** 首次用户手势解锁成功 */
  unlocked: boolean
  /** 播放通道：WebAudio 优先，其次 HTMLAudio 池，都不可用则 none */
  mode: 'webaudio' | 'htmlaudio' | 'none'
  /** 已解码可用数量 / 15 */
  loaded: number
  total: number
}

export const audioState = reactive<AudioRuntimeState>({
  enabled: true,
  volume: 70,
  unlocked: false,
  mode: 'webaudio',
  loaded: 0,
  total: SOUND_KEYS.length
})

/** 一次播放的抽象目标：SFX 键与牌面人声共用同一条通道内核 */
interface PlayTarget {
  /** 通道标识：SFX 为 SoundKey，人声为 `voice:<基名>` */
  id: string
  /** 资源 URL */
  url: string
  /** 基础音量 0–100 */
  volume: number
  /** 优先级 P0–P4 */
  priority: SoundPriority
}

interface WebChannel {
  id: string
  priority: SoundPriority
  startedAt: number
  source: AudioBufferSourceNode
  gain: GainNode
}

interface FallbackChannel {
  id: string
  priority: SoundPriority
  startedAt: number
  element: HTMLAudioElement
}

let ctx: AudioContext | null = null
let master: GainNode | null = null
const buffers = new Map<SoundKey, AudioBuffer>()
const loading = new Map<SoundKey, Promise<void>>()
const unavailable = new Set<SoundKey>()
const lastPlayedAt = new Map<SoundKey, number>()

/** 牌面人声：与 15 个 SFX 分开记账，`audioState.loaded/total` 仍只统计 SFX */
const voiceBuffers = new Map<string, AudioBuffer>()
const voiceLoading = new Map<string, Promise<void>>()
const voiceUnavailable = new Set<string>()
const voiceLastPlayedAt = new Map<string, number>()
const voiceLoadRequested = new Set<string>()
let lastVoiceAt = Number.NEGATIVE_INFINITY

const webChannels: WebChannel[] = []
const fallbackChannels: FallbackChannel[] = []
const fallbackPool: HTMLAudioElement[] = []
let fallbackCursor = 0

let suppressUntil = 0
let muteUntil = 0
let gestureBound = false
let visibilityBound = false

/** 牌面人声空闲预热状态 */
let voicePreloadStarted = false
let voicePreloadPending = false

function nowMs(): number {
  return typeof performance !== 'undefined' ? performance.now() : Date.now()
}

function masterValue(): number {
  return Math.max(0, Math.min(1, audioState.volume / 100))
}

function soundDataSaver(): boolean {
  const connection = (navigator as any)?.connection
  return Boolean(connection?.saveData)
}

function ensureContext(): AudioContext | null {
  if (ctx) return ctx
  if (!audioState.enabled) return null
  const Ctor = (window as any).AudioContext || (window as any).webkitAudioContext
  if (!Ctor) {
    audioState.mode = 'htmlaudio'
    return null
  }
  try {
    ctx = new Ctor() as AudioContext
    master = ctx.createGain()
    master.gain.value = masterValue()
    master.connect(ctx.destination)
    audioState.mode = 'webaudio'
    bindVisibility()
    return ctx
  } catch (error) {
    // 08 §4.4：AudioContext 构造失败 → 切 HTMLAudio 池
    console.debug('[audio] AudioContext 不可用，回退 HTMLAudio', error)
    ctx = null
    master = null
    audioState.mode = 'htmlaudio'
    bindVisibility()
    return null
  }
}

/**
 * 首次用户手势中创建/恢复 AudioContext。失败不打断交互，等下一次手势重试。
 */
export function unlockAudio(): void {
  if (!audioState.enabled) return
  const audioCtx = ensureContext()
  if (!audioCtx) {
    // 没有 WebAudio：用一次静音 HTMLAudio 播放探针判断是否可播
    if (audioState.mode === 'htmlaudio') markUnlocked()
    return
  }
  if (audioCtx.state === 'running') {
    markUnlocked()
    return
  }
  // iOS 需要在手势内先播一个静音 buffer
  try {
    const silent = audioCtx.createBuffer(1, 1, 22050)
    const source = audioCtx.createBufferSource()
    source.buffer = silent
    source.connect(audioCtx.destination)
    source.start(0)
  } catch (error) {
    console.debug('[audio] 静音探针失败', error)
  }
  audioCtx
    .resume()
    .then(() => {
      if (audioCtx.state === 'running') markUnlocked()
    })
    .catch((error) => {
      console.debug('[audio] resume 失败，等待下一次手势', error)
    })
}

function markUnlocked(): void {
  if (audioState.unlocked) return
  audioState.unlocked = true
  unbindGestures()
  void preloadSounds()
  // 进桌早于解锁时挂起的牌面人声预热，此刻补跑
  if (voicePreloadPending) {
    voicePreloadPending = false
    preloadVoices()
  }
}

const gestureHandler = (): void => unlockAudio()

export function bindAudioGestures(): void {
  if (gestureBound || typeof window === 'undefined') return
  gestureBound = true
  bindVisibility()
  window.addEventListener('pointerdown', gestureHandler, { capture: true, passive: true })
  window.addEventListener('keydown', gestureHandler, { capture: true })
  window.addEventListener('touchstart', gestureHandler, { capture: true, passive: true })
}

function unbindGestures(): void {
  if (!gestureBound) return
  gestureBound = false
  window.removeEventListener('pointerdown', gestureHandler, { capture: true })
  window.removeEventListener('keydown', gestureHandler, { capture: true })
  window.removeEventListener('touchstart', gestureHandler, { capture: true })
}

function bindVisibility(): void {
  if (visibilityBound || typeof document === 'undefined') return
  visibilityBound = true
  document.addEventListener('visibilitychange', handleVisibilityChange)
}

function handleVisibilityChange(): void {
  if (document.visibilityState === 'hidden') {
    // 切后台：停掉正在播的（不累积队列），并挂起上下文
    stopAll(0.01)
    if (ctx && ctx.state === 'running') {
      ctx.suspend().catch(() => {})
    }
    return
  }
  // 回前台：800ms 静音期，不补播
  muteUntil = nowMs() + RESUME_MUTE_MS
  suppressUntil = 0
  if (ctx && audioState.unlocked) {
    ctx.resume().catch(() => {})
  }
}

/** 重连成功 / 快照恢复后调用：吞掉恢复期间与随后的突兀事件 */
export function notifyConnectionRestored(): void {
  muteUntil = nowMs() + RESUME_MUTE_MS
}

async function loadOne(key: SoundKey): Promise<void> {
  if (buffers.has(key) || unavailable.has(key)) return
  const running = loading.get(key)
  if (running) return running

  const task = (async () => {
    try {
      if (audioState.mode === 'htmlaudio') {
        // 无 WebAudio：只预热 HTTP 缓存，播放交给 HTMLAudio 池
        const response = await fetch(sfxUrl(key), { cache: 'force-cache' })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return
      }
      const response = await fetch(sfxUrl(key), { cache: 'force-cache' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.arrayBuffer()
      const audioCtx = ensureContext()
      if (!audioCtx) throw new Error('AudioContext unavailable')
      const buffer = await audioCtx.decodeAudioData(data)
      buffers.set(key, buffer)
    } catch (error) {
      // 08 §4.4：单键失败只静音该键，debug 一次，其余照常
      unavailable.add(key)
      console.debug(`[audio] 音效 ${key} 加载/解码失败，已跳过`, error)
    } finally {
      loading.delete(key)
      audioState.loaded = buffers.size
    }
  })()

  loading.set(key, task)
  return task
}

/**
 * 按需加载一个牌面人声资源。
 * 失败只标记该基名 `unavailable`（该牌面静音），其余 33 个照常（08 §4.5 降级表）。
 */
async function loadVoice(base: string): Promise<void> {
  if (voiceBuffers.has(base) || voiceUnavailable.has(base)) return
  const running = voiceLoading.get(base)
  if (running) return running

  const task = (async () => {
    try {
      const url = voiceUrlOfBase(base)
      if (audioState.mode === 'htmlaudio') {
        // 无 WebAudio：只预热 HTTP 缓存，播放交给 HTMLAudio 池
        const response = await fetch(url, { cache: 'force-cache' })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return
      }
      const response = await fetch(url, { cache: 'force-cache' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.arrayBuffer()
      const audioCtx = ensureContext()
      if (!audioCtx) throw new Error('AudioContext unavailable')
      const buffer = await audioCtx.decodeAudioData(data)
      voiceBuffers.set(base, buffer)
    } catch (error) {
      voiceUnavailable.add(base)
      console.debug(`[audio] 报牌 ${base} 加载/解码失败，已跳过`, error)
    } finally {
      voiceLoading.delete(base)
    }
  })()

  voiceLoading.set(base, task)
  return task
}

/**
 * 进桌预加载：Promise.allSettled，单个失败不影响其他。
 * 未解锁时先跳过，解锁后会重新调用；saveData 下不预加载，按需拉取。
 * **仍然只拉 15 个 SFX** —— 牌面人声不在此列（08 §4.5）。
 */
export async function preloadSounds(): Promise<void> {
  if (!audioState.enabled) return
  if (soundDataSaver()) return
  if (audioState.mode === 'webaudio' && !ctx) return
  if (!audioState.unlocked && audioState.mode === 'webaudio') return
  await Promise.allSettled(SOUND_KEYS.map((key) => loadOne(key)))
}

/** 空闲调度：`requestIdleCallback` 优先，缺失时退回 `setTimeout` */
function scheduleIdle(fn: () => void): void {
  if (typeof window === 'undefined') return
  const ric = (window as any).requestIdleCallback
  if (typeof ric === 'function') {
    ric(fn, { timeout: 3000 })
    return
  }
  setTimeout(fn, 300)
}

/**
 * 牌面人声空闲预热（08 §4.5）：进桌后分批拉取 34 个 mp3，每批 4 个，共 9 批。
 * - 不进 `SOUND_KEYS` 预加载清单 → 首屏仍是 15 个 SFX 的请求量；
 * - `navigator.connection.saveData` 为真时**不预热**，全部按需加载；
 * - 解锁前调用则挂起，解锁后补跑。
 */
export function preloadVoices(): void {
  if (!audioState.enabled) return
  if (soundDataSaver()) return
  if (!audioState.unlocked) {
    voicePreloadPending = true
    return
  }
  if (voicePreloadStarted) return
  voicePreloadStarted = true

  let index = 0
  const runBatch = (): void => {
    const batch = VOICE_BASENAME_BY_TILE.slice(index, index + VOICE_PRELOAD_BATCH)
    index += batch.length
    void Promise.allSettled(batch.map((base) => loadVoice(base)))
    if (index < VOICE_BASENAME_BY_TILE.length) scheduleIdle(runBatch)
  }
  scheduleIdle(runBatch)
}

function lowestPriorityChannel(): WebChannel | null {
  let victim: WebChannel | null = null
  for (const channel of webChannels) {
    if (!victim) {
      victim = channel
      continue
    }
    if (channel.priority > victim.priority) victim = channel
    else if (channel.priority === victim.priority && channel.startedAt < victim.startedAt) victim = channel
  }
  return victim
}

function dropChannel(channel: WebChannel): void {
  const index = webChannels.indexOf(channel)
  if (index >= 0) webChannels.splice(index, 1)
  try {
    const audioCtx = ctx
    if (audioCtx && master) {
      const at = audioCtx.currentTime
      channel.gain.gain.cancelScheduledValues(at)
      channel.gain.gain.setValueAtTime(channel.gain.gain.value, at)
      channel.gain.gain.linearRampToValueAtTime(0, at + FADE_OUT_SECONDS)
      channel.source.stop(at + FADE_OUT_SECONDS + 0.01)
    }
  } catch {
    // 已结束的 source 再次 stop 会抛，忽略
  }
}

function makeRoom(priority: SoundPriority, startedAt: number): boolean {
  while (webChannels.length >= MAX_CONCURRENT) {
    const victim = lowestPriorityChannel()
    if (!victim) break
    // 同级别丢更早的；若在播的比新来的更重要，则丢新来的
    if (victim.priority > priority || victim.priority === priority) {
      dropChannel(victim)
    } else {
      return false
    }
  }
  return webChannels.length < MAX_CONCURRENT
}

function dropFallback(channel: FallbackChannel): void {
  const index = fallbackChannels.indexOf(channel)
  if (index >= 0) fallbackChannels.splice(index, 1)
  try {
    channel.element.pause()
    channel.element.currentTime = 0
  } catch {
    // 忽略
  }
}

function fallbackElement(): HTMLAudioElement | null {
  if (typeof Audio === 'undefined') return null
  if (fallbackPool.length < FALLBACK_POOL_SIZE) {
    try {
      const element = new Audio()
      element.preload = 'auto'
      fallbackPool.push(element)
    } catch (error) {
      console.debug('[audio] HTMLAudio 不可用', error)
      return null
    }
  }
  const element = fallbackPool[fallbackCursor % fallbackPool.length]
  fallbackCursor += 1
  return element
}

function playFallback(target: PlayTarget, factor: number): void {
  while (fallbackChannels.length >= MAX_CONCURRENT) {
    let victim: FallbackChannel | null = null
    for (const channel of fallbackChannels) {
      if (!victim || channel.priority > victim.priority) victim = channel
    }
    if (!victim || victim.priority < target.priority) return
    dropFallback(victim)
  }
  const element = fallbackElement()
  if (!element) {
    audioState.mode = 'none'
    return
  }
  const volume = Math.max(0, Math.min(1, (target.volume / 100) * factor * masterValue()))
  element.src = target.url
  element.volume = volume
  try {
    element.currentTime = 0
  } catch {
    // 新元素可能尚未可写，忽略
  }
  const channel: FallbackChannel = { id: target.id, priority: target.priority, startedAt: nowMs(), element }
  fallbackChannels.push(channel)
  const playing = element.play()
  if (playing && typeof playing.catch === 'function') {
    playing.catch((error) => {
      dropFallback(channel)
      console.debug(`[audio] HTMLAudio 播放 ${target.id} 被拦截或失败`, error)
    })
  }
  element.onended = () => dropFallback(channel)
}

/**
 * WebAudio 播放：SFX 与牌面人声共用的通道内核（并发上限、优先级抢占、30ms 淡出）。
 * 成功返回 true（调用方据此记去重时间戳）。
 */
function playDecoded(target: PlayTarget, buffer: AudioBuffer, factor: number): boolean {
  const audioCtx = ctx
  if (!audioCtx) return false
  const now = nowMs()
  if (!makeRoom(target.priority, now)) return false
  try {
    const source = audioCtx.createBufferSource()
    source.buffer = buffer
    const gain = audioCtx.createGain()
    gain.gain.value = Math.max(0, Math.min(1, (target.volume / 100) * factor))
    source.connect(gain)
    if (master) gain.connect(master)
    else gain.connect(audioCtx.destination)
    const channel: WebChannel = { id: target.id, priority: target.priority, startedAt: now, source, gain }
    webChannels.push(channel)
    source.onended = () => {
      const index = webChannels.indexOf(channel)
      if (index >= 0) webChannels.splice(index, 1)
    }
    source.start(0)
    if (target.priority === 0) suppressUntil = now + P0_SUPPRESS_MS
    return true
  } catch (error) {
    console.debug(`[audio] 播放 ${target.id} 失败`, error)
    return false
  }
}

export interface PlayOptions {
  /** 额外增益系数（08 §2：他人摸牌 40%） */
  gain?: number
  /** 聊天音效：需 chatSoundFlag=1 */
  chatAllowed?: boolean
}

/**
 * 播放一个音效键。所有限流/降级都在这里，调用方不需要判断。
 */
export function playSound(key: SoundKey, options: PlayOptions = {}): void {
  if (!audioState.enabled || audioState.mode === 'none') return
  const spec = SOUND_SPECS[key]
  if (key === 'chat' && options.chatAllowed === false) return
  if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return

  const now = nowMs()
  if (now < muteUntil) return
  // P0 后 200ms 内到达的 P3/P4 直接丢弃，不排队
  if (spec.priority >= 3 && now < suppressUntil) return
  const last = lastPlayedAt.get(key)
  if (last !== undefined && now - last < DEDUPE_MS) return
  if (unavailable.has(key)) return

  const factor = Math.max(0, options.gain ?? 1)
  const target: PlayTarget = { id: key, url: sfxUrl(key), volume: spec.volume, priority: spec.priority }

  if (audioState.mode === 'htmlaudio') {
    lastPlayedAt.set(key, now)
    playFallback(target, factor)
    return
  }

  const audioCtx = ctx
  if (!audioCtx || audioCtx.state !== 'running') return

  const buffer = buffers.get(key)
  if (!buffer) {
    // saveData 或尚未加载：按需拉取一次，本次静音
    void loadOne(key)
    return
  }

  if (playDecoded(target, buffer, factor)) lastPlayedAt.set(key, now)
}

export interface VoicePlayOptions {
  /** 额外增益系数（默认 1） */
  gain?: number
}

/** 当前是否有 P0（如 `hu`）正在播放：人声不得盖过它 */
function hasPlayingP0(): boolean {
  for (const channel of webChannels) if (channel.priority === 0) return true
  for (const channel of fallbackChannels) if (channel.priority === 0) return true
  return false
}

/**
 * 播放牌面人声报牌（08 §2.1 / §4.5）。
 *
 * `target` 可以是素材基名（`1wan`）或完整 URL（`voiceUrlOf(tile)` 的返回值），
 * 内部统一归一化为基名；无法识别时**静默跳过**，不报错。
 *
 * 限流：**同键 150ms 去重** 与 **全局 250ms 最短间隔** 两条同时生效；
 * 优先级 P3，受 `MAX_CONCURRENT = 4` 约束；`hu`（P0）在播时不与其叠响。
 */
export function playVoice(target: string | null | undefined, options: VoicePlayOptions = {}): void {
  if (!audioState.enabled || audioState.mode === 'none') return
  const base = voiceBaseFromTarget(target)
  if (!base) return
  if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return

  const now = nowMs()
  if (now < muteUntil) return
  // P0（hu）后 200ms 内到达的报牌直接丢弃（08 §3 规则 3）
  if (now < suppressUntil) return
  // 同一张牌 150ms 内连出 → 同键去重
  const last = voiceLastPlayedAt.get(base)
  if (last !== undefined && now - last < DEDUPE_MS) return
  // 任意两张牌的报牌之间至少间隔 250ms（08 §3 规则 6）
  if (now - lastVoiceAt < VOICE_MIN_INTERVAL_MS) return
  if (voiceUnavailable.has(base)) return
  // 人声不得盖过 hu（P0）：结算音在播时不叠响
  if (hasPlayingP0()) return

  const factor = Math.max(0, options.gain ?? 1)
  const spec: PlayTarget = {
    id: `voice:${base}`,
    url: voiceUrlOfBase(base),
    volume: VOICE_VOLUME,
    priority: VOICE_PRIORITY
  }

  if (audioState.mode === 'htmlaudio') {
    voiceLastPlayedAt.set(base, now)
    lastVoiceAt = now
    playFallback(spec, factor)
    return
  }

  const audioCtx = ctx
  if (!audioCtx || audioCtx.state !== 'running') return

  const buffer = voiceBuffers.get(base)
  if (!buffer) {
    // 尚未加载：按需拉取一次，**本次静音**（沿用既有降级语义）
    if (!voiceLoadRequested.has(base)) {
      voiceLoadRequested.add(base)
      console.debug(`[audio] 报牌 ${base} 尚未加载，按需拉取（本次静音）`)
    }
    void loadVoice(base)
    return
  }

  if (playDecoded(spec, buffer, factor)) {
    voiceLastPlayedAt.set(base, now)
    lastVoiceAt = now
  }
}

/** 停止所有通道（禁止硬切爆音：给 30ms 淡出） */
export function stopAll(fadeSeconds = FADE_OUT_SECONDS): void {
  for (const channel of [...webChannels]) {
    const audioCtx = ctx
    if (audioCtx && fadeSeconds > 0) {
      try {
        const at = audioCtx.currentTime
        channel.gain.gain.cancelScheduledValues(at)
        channel.gain.gain.setValueAtTime(channel.gain.gain.value, at)
        channel.gain.gain.linearRampToValueAtTime(0, at + fadeSeconds)
        channel.source.stop(at + fadeSeconds + 0.01)
      } catch {
        // 忽略
      }
    } else {
      try {
        channel.source.stop()
      } catch {
        // 忽略
      }
    }
    const index = webChannels.indexOf(channel)
    if (index >= 0) webChannels.splice(index, 1)
  }
  for (const channel of [...fallbackChannels]) dropFallback(channel)
}

export function setAudioEnabled(enabled: boolean): void {
  audioState.enabled = enabled
  if (!enabled) {
    // 08 §4.4：关闭后不创建音源、不再请求音频
    stopAll(0.01)
    if (master) master.gain.value = 0
    return
  }
  if (master) master.gain.value = masterValue()
  if (audioState.unlocked) void preloadSounds()
}

export function setAudioVolume(volume: number): void {
  const next = Math.max(0, Math.min(100, Math.round(Number.isFinite(volume) ? volume : 70)))
  audioState.volume = next
  if (master) master.gain.value = masterValue()
}

/** 试听：不受 150ms 去重与静音期影响，但仍尊重总开关/解锁状态 */
export function previewSound(key: SoundKey): void {
  if (!audioState.enabled) return
  lastPlayedAt.delete(key)
  muteUntil = 0
  suppressUntil = 0
  playSound(key, { gain: 1 })
}

/** 测试/排障辅助：清空限流状态 */
export function resetAudioLimits(): void {
  lastPlayedAt.clear()
  voiceLastPlayedAt.clear()
  lastVoiceAt = Number.NEGATIVE_INFINITY
  suppressUntil = 0
  muteUntil = 0
}

/** 测试/排障辅助：查看当前通道、已解码与已降级的键（不参与业务逻辑） */
export function audioDebug(): {
  channels: string[]
  fallback: string[]
  buffers: string[]
  unavailable: string[]
  voiceBuffers: string[]
  voiceUnavailable: string[]
  mutedMs: number
  suppressedMs: number
} {
  const now = nowMs()
  return {
    channels: webChannels.map((channel) => channel.id),
    fallback: fallbackChannels.map((channel) => channel.id),
    buffers: [...buffers.keys()],
    unavailable: [...unavailable],
    voiceBuffers: [...voiceBuffers.keys()],
    voiceUnavailable: [...voiceUnavailable],
    mutedMs: Math.max(0, Math.round(muteUntil - now)),
    suppressedMs: Math.max(0, Math.round(suppressUntil - now))
  }
}

export const audioManager = {
  state: audioState,
  unlock: unlockAudio,
  preload: preloadSounds,
  preloadVoices,
  play: playSound,
  playVoice,
  preview: previewSound,
  stopAll,
  setEnabled: setAudioEnabled,
  setVolume: setAudioVolume,
  notifyConnectionRestored,
  resetLimits: resetAudioLimits,
  debug: audioDebug,
  /** 供调试面板/验收脚本查看已不可用的键 */
  unavailableKeys: (): SoundKey[] => [...unavailable],
  /** 牌面人声已降级（加载失败）的基名 */
  voiceUnavailableKeys: (): string[] => [...voiceUnavailable]
}
