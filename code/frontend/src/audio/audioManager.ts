/**
 * 08 §3/§4 的播放内核：单例、预加载、解锁、限流、降级。
 *
 * 只用浏览器原生 API（AudioContext + HTMLAudioElement），不引入第三方音频库。
 * 任何异常都走静音降级：不抛未捕获错误，不阻塞对局。
 */
import { reactive } from 'vue'

import { SOUND_KEYS, SOUND_SPECS, sfxUrl, type SoundKey, type SoundPriority } from './soundKeys'

const MAX_CONCURRENT = 4
const DEDUPE_MS = 150
const P0_SUPPRESS_MS = 200
const RESUME_MUTE_MS = 800
const FADE_OUT_SECONDS = 0.03
const FALLBACK_POOL_SIZE = 4

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

interface WebChannel {
  key: SoundKey
  priority: SoundPriority
  startedAt: number
  source: AudioBufferSourceNode
  gain: GainNode
}

interface FallbackChannel {
  key: SoundKey
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

const webChannels: WebChannel[] = []
const fallbackChannels: FallbackChannel[] = []
const fallbackPool: HTMLAudioElement[] = []
let fallbackCursor = 0

let suppressUntil = 0
let muteUntil = 0
let gestureBound = false
let visibilityBound = false

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
 * 进桌预加载：Promise.allSettled，单个失败不影响其他。
 * 未解锁时先跳过，解锁后会重新调用；saveData 下不预加载，按需拉取。
 */
export async function preloadSounds(): Promise<void> {
  if (!audioState.enabled) return
  if (soundDataSaver()) return
  if (audioState.mode === 'webaudio' && !ctx) return
  if (!audioState.unlocked && audioState.mode === 'webaudio') return
  await Promise.allSettled(SOUND_KEYS.map((key) => loadOne(key)))
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

function playFallback(key: SoundKey, spec: { priority: SoundPriority }, factor: number): void {
  while (fallbackChannels.length >= MAX_CONCURRENT) {
    let victim: FallbackChannel | null = null
    for (const channel of fallbackChannels) {
      if (!victim || channel.priority > victim.priority) victim = channel
    }
    if (!victim || victim.priority < spec.priority) return
    dropFallback(victim)
  }
  const element = fallbackElement()
  if (!element) {
    audioState.mode = 'none'
    return
  }
  const volume = Math.max(0, Math.min(1, (SOUND_SPECS[key].volume / 100) * factor * masterValue()))
  element.src = sfxUrl(key)
  element.volume = volume
  try {
    element.currentTime = 0
  } catch {
    // 新元素可能尚未可写，忽略
  }
  const channel: FallbackChannel = { key, priority: spec.priority, startedAt: nowMs(), element }
  fallbackChannels.push(channel)
  const playing = element.play()
  if (playing && typeof playing.catch === 'function') {
    playing.catch((error) => {
      dropFallback(channel)
      console.debug(`[audio] HTMLAudio 播放 ${key} 被拦截或失败`, error)
    })
  }
  element.onended = () => dropFallback(channel)
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

  if (audioState.mode === 'htmlaudio') {
    lastPlayedAt.set(key, now)
    playFallback(key, spec, factor)
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

  if (!makeRoom(spec.priority, now)) return

  try {
    const source = audioCtx.createBufferSource()
    source.buffer = buffer
    const gain = audioCtx.createGain()
    gain.gain.value = Math.max(0, Math.min(1, (spec.volume / 100) * factor))
    source.connect(gain)
    if (master) gain.connect(master)
    else gain.connect(audioCtx.destination)
    const channel: WebChannel = { key, priority: spec.priority, startedAt: now, source, gain }
    webChannels.push(channel)
    source.onended = () => {
      const index = webChannels.indexOf(channel)
      if (index >= 0) webChannels.splice(index, 1)
    }
    source.start(0)
    lastPlayedAt.set(key, now)
    if (spec.priority === 0) suppressUntil = now + P0_SUPPRESS_MS
  } catch (error) {
    console.debug(`[audio] 播放 ${key} 失败`, error)
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
  suppressUntil = 0
  muteUntil = 0
}

/** 测试/排障辅助：查看当前通道、已解码与已降级的键（不参与业务逻辑） */
export function audioDebug(): {
  channels: SoundKey[]
  fallback: SoundKey[]
  buffers: SoundKey[]
  unavailable: SoundKey[]
  mutedMs: number
  suppressedMs: number
} {
  const now = nowMs()
  return {
    channels: webChannels.map((channel) => channel.key),
    fallback: fallbackChannels.map((channel) => channel.key),
    buffers: [...buffers.keys()],
    unavailable: [...unavailable],
    mutedMs: Math.max(0, Math.round(muteUntil - now)),
    suppressedMs: Math.max(0, Math.round(suppressUntil - now))
  }
}

export const audioManager = {
  state: audioState,
  unlock: unlockAudio,
  preload: preloadSounds,
  play: playSound,
  preview: previewSound,
  stopAll,
  setEnabled: setAudioEnabled,
  setVolume: setAudioVolume,
  notifyConnectionRestored,
  resetLimits: resetAudioLimits,
  debug: audioDebug,
  /** 供调试面板/验收脚本查看已不可用的键 */
  unavailableKeys: (): SoundKey[] => [...unavailable]
}
