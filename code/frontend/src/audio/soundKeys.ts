/**
 * 08 §2/§3 的权威映射：音效键 → 文件、基础音量、优先级、是否受聊天开关控制。
 *
 * 只做 SFX：这里没有 BGM、没有语音播报。新增/替换资源只改本文件，
 * 组件与事件层不直接写文件名。
 */

/** 15 个音效键，与 public/audio/sfx/ 下的文件名一一对应 */
export type SoundKey =
  | 'hu'
  | 'exhausted'
  | 'kong_exposed'
  | 'kong_hidden'
  | 'kong_added'
  | 'claim'
  | 'pong'
  | 'chow'
  | 'turn'
  | 'discard'
  | 'draw'
  | 'timeout'
  | 'dice'
  | 'deal'
  | 'chat'

/** 0=P0 … 4=P4，数值越小越重要（08 §3） */
export type SoundPriority = 0 | 1 | 2 | 3 | 4

export interface SoundSpec {
  key: SoundKey
  /** public/audio/sfx/ 下的文件名 */
  file: string
  /** 基础音量 0–100（08 §2「默认音量」） */
  volume: number
  priority: SoundPriority
  /** 受 chatSoundFlag 控制（只有 chat 为 true） */
  chatGated: boolean
}

export const SOUND_SPECS: Record<SoundKey, SoundSpec> = {
  hu: { key: 'hu', file: 'hu.mp3', volume: 90, priority: 0, chatGated: false },
  exhausted: { key: 'exhausted', file: 'exhausted.mp3', volume: 55, priority: 1, chatGated: false },
  kong_exposed: { key: 'kong_exposed', file: 'kong_exposed.mp3', volume: 75, priority: 1, chatGated: false },
  kong_hidden: { key: 'kong_hidden', file: 'kong_hidden.mp3', volume: 75, priority: 1, chatGated: false },
  kong_added: { key: 'kong_added', file: 'kong_added.mp3', volume: 75, priority: 1, chatGated: false },
  claim: { key: 'claim', file: 'claim.mp3', volume: 50, priority: 1, chatGated: false },
  pong: { key: 'pong', file: 'pong.mp3', volume: 70, priority: 2, chatGated: false },
  chow: { key: 'chow', file: 'chow.mp3', volume: 65, priority: 2, chatGated: false },
  turn: { key: 'turn', file: 'turn.mp3', volume: 45, priority: 2, chatGated: false },
  discard: { key: 'discard', file: 'discard.mp3', volume: 55, priority: 3, chatGated: false },
  draw: { key: 'draw', file: 'draw.mp3', volume: 35, priority: 3, chatGated: false },
  timeout: { key: 'timeout', file: 'timeout.mp3', volume: 50, priority: 3, chatGated: false },
  dice: { key: 'dice', file: 'dice.mp3', volume: 60, priority: 4, chatGated: false },
  deal: { key: 'deal', file: 'deal.mp3', volume: 50, priority: 4, chatGated: false },
  chat: { key: 'chat', file: 'chat.mp3', volume: 40, priority: 4, chatGated: true }
}

export const SOUND_KEYS = Object.keys(SOUND_SPECS) as SoundKey[]

/** 预加载清单（顺序无关，Promise.allSettled 并发拉取） */
export const SOUND_URLS: Record<SoundKey, string> = SOUND_KEYS.reduce((acc, key) => {
  acc[key] = sfxUrl(key)
  return acc
}, {} as Record<SoundKey, string>)

/**
 * 资源 URL：跟随构建 base（生产 `/majiangapp/audio/sfx/...`、开发 `/audio/sfx/...`）。
 * 末尾带 `?v=` 时即可强制刷新缓存（08 §6）。
 */
export function sfxUrl(key: SoundKey): string {
  return `${import.meta.env.BASE_URL}audio/sfx/${SOUND_SPECS[key].file}`
}

/** 数字越小越重要 */
export function priorityOf(key: SoundKey): SoundPriority {
  return SOUND_SPECS[key].priority
}
