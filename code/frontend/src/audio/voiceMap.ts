/**
 * 08 §4.5：牌面报牌（人声）的唯一映射源 —— tile（0–33）→ 素材基名 → 资源 URL。
 *
 * 为什么不放在 `soundKeys.ts`：
 * - `SoundKey` 是**字面量联合类型**（15 项）。把 34 个牌面音塞进去，预加载会一次拉
 *   49 个文件、首屏流量抬高约 3 倍，`audioState.total` 也随之失控（08 §4.2）。
 * - 牌面音**不进** `SOUND_KEYS` 预加载清单（`preloadSounds()` 仍只拉 15 个 SFX），
 *   改为「按需加载 + 进桌后空闲分批预热」（见 `audioManager.ts`）。
 *
 * 素材基名（`1wan` / `dongfeng` / `bai`）与 `utils/tile.ts` 的 `tileKey()`
 * （`1m` / `east` / `white`）**是两套不同的命名**，必须经本表显式映射，
 * 不得互相替代、也不得复用 `tileKey()` 拼 URL。
 */

/** 34 个牌面素材基名，顺序即 tile 0–33：万 → 筒 → 条 → 东南西北中发白 */
export const VOICE_BASENAME_BY_TILE = [
  '1wan', '2wan', '3wan', '4wan', '5wan', '6wan', '7wan', '8wan', '9wan',
  '1tong', '2tong', '3tong', '4tong', '5tong', '6tong', '7tong', '8tong', '9tong',
  '1tiao', '2tiao', '3tiao', '4tiao', '5tiao', '6tiao', '7tiao', '8tiao', '9tiao',
  'dongfeng', 'nanfeng', 'xifeng', 'beifeng', 'zhong', 'fa', 'bai'
] as const

export type VoiceBasename = (typeof VOICE_BASENAME_BY_TILE)[number]

/** tile（0–33）→ 素材基名；越界或非整数返回 null（调用方静默跳过） */
export function voiceBaseOf(tile: number): VoiceBasename | null {
  if (!Number.isInteger(tile) || tile < 0 || tile > 33) return null
  return VOICE_BASENAME_BY_TILE[tile]
}

/** 素材基名 → 资源 URL（跟随构建 base：生产 `/majiangapp/audio/voice/...`） */
export function voiceUrlOfBase(base: string): string {
  return `${import.meta.env.BASE_URL}audio/voice/${base}.mp3`
}

/** tile（0–33）→ 资源 URL；越界或非整数返回 null */
export function voiceUrlOf(tile: number): string | null {
  const base = voiceBaseOf(tile)
  return base ? voiceUrlOfBase(base) : null
}

/**
 * 把「基名」或「完整 URL」归一化为合法基名；无法识别时返回 null。
 *
 * `audioManager.playVoice()` 同时接受两种写法，这里统一收敛，
 * 并且**只认表内 34 个基名** —— 防止任意 URL 被当成音频资源去拉取。
 */
export function voiceBaseFromTarget(target: string | null | undefined): VoiceBasename | null {
  if (!target) return null
  const raw = String(target).split('?')[0].split('#')[0]
  const name = raw.split('/').pop() ?? ''
  const base = name.replace(/\.mp3$/i, '')
  return (VOICE_BASENAME_BY_TILE as readonly string[]).includes(base)
    ? (base as VoiceBasename)
    : null
}
