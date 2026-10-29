/**
 * 音效偏好（08 §5）：总开关、音量、聊天提示。
 *
 * - localStorage 先读，保证首屏即时生效；服务端 `GET /api/user/pref` 返回后覆盖。
 * - 写请求 500ms 防抖；失败回滚 UI 并 toast。
 * - 只有 SFX 字段，没有 BGM。
 */
import { reactive } from 'vue'

import { api, getToken } from '../api/http'
import { useToast } from '../composables/useToast'
import { audioManager } from './audioManager'

const ENABLED_KEY = 'mj.sound.enabled'
const VOLUME_KEY = 'mj.sound.volume'
const CHAT_KEY = 'mj.sound.chat'
const SAVE_DEBOUNCE_MS = 500
const DEFAULT_ENABLED = true
const DEFAULT_VOLUME = 70
const DEFAULT_CHAT = true

export interface SoundPrefs {
  enabled: boolean
  volume: number
  chat: boolean
}

interface UserPrefResponse {
  last_family_code?: string | null
  skin_code?: string | null
  sound_enabled?: boolean
  sound_volume?: number
  chat_sound?: boolean
  show_tenpai?: boolean
}

export const soundPrefs = reactive<SoundPrefs>({
  enabled: DEFAULT_ENABLED,
  volume: DEFAULT_VOLUME,
  chat: DEFAULT_CHAT
})

const toast = useToast()

let serverSnapshot: SoundPrefs = { enabled: DEFAULT_ENABLED, volume: DEFAULT_VOLUME, chat: DEFAULT_CHAT }
let saveTimer: number | undefined
let pending: Partial<SoundPrefs> = {}
let initialised = false

function clampVolume(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_VOLUME
  return Math.max(0, Math.min(100, Math.round(value)))
}

function readLocal(): void {
  try {
    const enabled = localStorage.getItem(ENABLED_KEY)
    const volume = localStorage.getItem(VOLUME_KEY)
    const chat = localStorage.getItem(CHAT_KEY)
    if (enabled !== null) soundPrefs.enabled = enabled === '1'
    if (volume !== null) soundPrefs.volume = clampVolume(Number(volume))
    if (chat !== null) soundPrefs.chat = chat === '1'
  } catch {
    // 隐私模式等场景直接放弃本地缓存，不影响对局
  }
}

function writeLocal(): void {
  try {
    localStorage.setItem(ENABLED_KEY, soundPrefs.enabled ? '1' : '0')
    localStorage.setItem(VOLUME_KEY, String(soundPrefs.volume))
    localStorage.setItem(CHAT_KEY, soundPrefs.chat ? '1' : '0')
  } catch {
    // 忽略
  }
}

function applyToAudio(): void {
  audioManager.setEnabled(soundPrefs.enabled)
  audioManager.setVolume(soundPrefs.volume)
}

function applyServer(data: UserPrefResponse): void {
  if (typeof data.sound_enabled === 'boolean') soundPrefs.enabled = data.sound_enabled
  if (typeof data.sound_volume === 'number') soundPrefs.volume = clampVolume(data.sound_volume)
  if (typeof data.chat_sound === 'boolean') soundPrefs.chat = data.chat_sound
  applyToAudio()
  writeLocal()
  serverSnapshot = { ...soundPrefs }
}

/**
 * 首屏同步调用：localStorage → 音频内核（首屏即时生效）。
 * 服务端偏好由 App.vue 在拿到 token 后调用 refreshSoundPrefs() 覆盖。
 */
export function initSoundPrefs(): void {
  if (initialised) return
  initialised = true
  readLocal()
  applyToAudio()
}

/** 登录后 / 进桌时拉取服务端偏好（localStorage 已有值，服务端返回后覆盖） */
export async function refreshSoundPrefs(): Promise<void> {
  if (!getToken()) return
  if (saveTimer !== undefined || Object.keys(pending).length) return
  try {
    const data = await api.get<UserPrefResponse>('/user/pref')
    applyServer(data)
  } catch {
    // 离线或接口不可用：继续用本地缓存，不打断对局
  }
}

async function flush(): Promise<void> {
  saveTimer = undefined
  const patch = pending
  pending = {}
  const payload: Record<string, unknown> = {}
  if (patch.enabled !== undefined) payload.sound_enabled = patch.enabled
  if (patch.volume !== undefined) payload.sound_volume = patch.volume
  if (patch.chat !== undefined) payload.chat_sound = patch.chat
  if (!Object.keys(payload).length) return

  const rollback = { ...serverSnapshot }
  try {
    const data = await api.put<UserPrefResponse>('/user/pref', payload)
    applyServer(data)
  } catch {
    soundPrefs.enabled = rollback.enabled
    soundPrefs.volume = rollback.volume
    soundPrefs.chat = rollback.chat
    writeLocal()
    applyToAudio()
    toast.error('音效设置未保存，已恢复原设置')
  }
}

function queueSave(patch: Partial<SoundPrefs>): void {
  pending = { ...pending, ...patch }
  if (saveTimer !== undefined) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => {
    void flush()
  }, SAVE_DEBOUNCE_MS)
}

export function setSoundEnabled(enabled: boolean): void {
  if (soundPrefs.enabled === enabled) return
  soundPrefs.enabled = enabled
  writeLocal()
  applyToAudio()
  queueSave({ enabled })
}

export function setSoundVolume(volume: number): void {
  const next = clampVolume(volume)
  if (soundPrefs.volume === next) return
  soundPrefs.volume = next
  writeLocal()
  // 本地增益即时生效，不发请求
  audioManager.setVolume(next)
  queueSave({ volume: next })
}

export function setChatSound(enabled: boolean): void {
  if (soundPrefs.chat === enabled) return
  soundPrefs.chat = enabled
  writeLocal()
  queueSave({ chat: enabled })
}
