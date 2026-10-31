/**
 * 08 §2/§3 的权威映射：音效键 → 文件、目录、基础音量、优先级、是否受聊天开关控制。
 *
 * 只做 SFX：这里没有 BGM、没有牌面报牌的动态键（34 个牌面人声走 `voiceMap.ts` 的
 * `playVoice()` 通道，见 08 §4.5）。新增/替换资源只改本文件，
 * 组件与事件层不直接写文件名。
 *
 * v1.2（I14 / S-2）：吃 / 碰 / 胡 / 明杠 / 暗杠 / 补杠 六个键改指 `voice/` 下的女声素材，
 * 旧合成键（`hu`/`pong`/`chow`/`kong_*`）已从枚举移除 —— **文件仍保留**在 `public/audio/sfx/`，
 * 但不再被引用、不再触发。
 */

/** 15 个音效键：9 个指向 public/audio/sfx/，6 个叫牌键指向 public/audio/voice/ */
export type SoundKey =
  | 'hu_voice'
  | 'exhausted'
  | 'kong_exposed_voice'
  | 'kong_hidden_voice'
  | 'kong_added_voice'
  | 'claim'
  | 'pong_voice'
  | 'chow_voice'
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
  /** 资源文件名（在 `dir` 指定的目录下） */
  file: string
  /**
   * 资源目录：`'sfx'`（默认，自制合成音）或 `'voice'`（女声素材）。
   *
   * 注意：`hu.mp3` / `pong.mp3` / `chow.mp3` / `kong_*.mp3` 在 `sfx/` 与 `voice/`
   * **各有一份同名文件**（旧的合成音保留在磁盘但不再触发），靠本字段区分。
   */
  dir?: 'sfx' | 'voice'
  /** 基础音量 0–100（08 §2「默认音量」） */
  volume: number
  priority: SoundPriority
  /** 受 chatSoundFlag 控制（只有 chat 为 true） */
  chatGated: boolean
}

export const SOUND_SPECS: Record<SoundKey, SoundSpec> = {
  hu_voice: { key: 'hu_voice', file: 'hu.mp3', dir: 'voice', volume: 90, priority: 0, chatGated: false },
  exhausted: { key: 'exhausted', file: 'exhausted.mp3', volume: 55, priority: 1, chatGated: false },
  kong_exposed_voice: { key: 'kong_exposed_voice', file: 'kong_exposed.mp3', dir: 'voice', volume: 75, priority: 1, chatGated: false },
  kong_hidden_voice: { key: 'kong_hidden_voice', file: 'kong_hidden.mp3', dir: 'voice', volume: 75, priority: 1, chatGated: false },
  kong_added_voice: { key: 'kong_added_voice', file: 'kong_added.mp3', dir: 'voice', volume: 75, priority: 1, chatGated: false },
  claim: { key: 'claim', file: 'claim.mp3', volume: 50, priority: 1, chatGated: false },
  pong_voice: { key: 'pong_voice', file: 'pong.mp3', dir: 'voice', volume: 70, priority: 2, chatGated: false },
  chow_voice: { key: 'chow_voice', file: 'chow.mp3', dir: 'voice', volume: 65, priority: 2, chatGated: false },
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
 * 资源 URL：跟随构建 base（生产 `/majiangapp/audio/voice/...`、开发 `/audio/sfx/...`）。
 * 目录由 `SoundSpec.dir` 决定（缺省 `sfx/`）。
 * 末尾带 `?v=` 时即可强制刷新缓存（08 §6）。
 */
export function sfxUrl(key: SoundKey): string {
  const spec = SOUND_SPECS[key]
  return `${import.meta.env.BASE_URL}audio/${spec.dir ?? 'sfx'}/${spec.file}`
}

/** 数字越小越重要 */
export function priorityOf(key: SoundKey): SoundPriority {
  return SOUND_SPECS[key].priority
}
