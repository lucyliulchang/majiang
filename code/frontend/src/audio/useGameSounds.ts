/**
 * 08 §2 的事件 → 音效映射。唯一调用点在 stores/game.ts 的
 * handleEvent / handleMessage，组件不直接播音效。
 *
 * 不在本地预播放自己的操作：一律等服务器增量事件，天然避免重复。
 *
 * v1.2（I14 / S-2）：吃 / 碰 / 胡 / 明杠 / 暗杠 / 补杠 改用**女声叫牌人声**
 * （`chow_voice` / `pong_voice` / `hu_voice` / `kong_*_voice`，资源在 `audio/voice/`）；
 * 旧的合成键已从 `SOUND_SPECS` 移除，文件保留在 `audio/sfx/` 但不再触发。
 */
import { audioManager } from './audioManager'
import type { SoundKey } from './soundKeys'
import { soundPrefs } from './soundPrefs'
import { voiceUrlOf } from './voiceMap'

/** 一局只播一次 settled（多赢家不叠加）；round_started 时重置 */
let settledRoundKey = ''

function play(key: SoundKey, gain = 1): void {
  audioManager.play(key, { gain })
}

/**
 * 牌面报牌（人声，08 §2.1 / §4.5）：底噪保留、人声叠加。
 * `tile` 缺失或越界时静默跳过，不报错。
 */
function playVoiceOf(tile: unknown): void {
  const value = Number(tile)
  if (!Number.isInteger(value)) return
  const url = voiceUrlOf(value)
  if (!url) return
  audioManager.playVoice(url)
}

function chatPanelFocused(): boolean {
  if (typeof document === 'undefined') return false
  const active = document.activeElement as HTMLElement | null
  if (!active) return false
  return Boolean(active.closest('[data-chat-panel]'))
}

/** 处理 `event.*` 增量事件；不发声的事件在这里保持沉默 */
export function handleSoundEvent(type: string, data: any, selfSeat: number | null): void {
  switch (type) {
    case 'event.settled': {
      const roundKey = String(data?.round_no ?? '')
      if (roundKey && roundKey === settledRoundKey) return
      settledRoundKey = roundKey
      // 荒庄（有杠）只播 exhausted，不播 hu_voice；多赢家只播一次 hu_voice
      if (data?.is_draw) {
        play('exhausted')
        return
      }
      const winners = Array.isArray(data?.winners) ? data.winners : []
      const hasWinner = winners.length > 0 || (data?.winner_seat ?? null) !== null
      if (hasWinner) play('hu_voice')
      return
    }
    case 'event.kongged': {
      const kind = data?.kind
      if (kind === 'exposed') play('kong_exposed_voice')
      else if (kind === 'hidden') play('kong_hidden_voice')
      else if (kind === 'added') play('kong_added_voice')
      return
    }
    case 'event.claim_open': {
      // 仅当询问窗口包含自己（含抢杠窗口）才提示，避免旁观噪声
      const seats: unknown[] = Array.isArray(data?.seats) ? data.seats : []
      if (selfSeat === null) return
      if (seats.some((seat) => Number(seat) === selfSeat)) play('claim')
      return
    }
    case 'event.claimed':
      if (data?.action === 'pong') play('pong_voice')
      else if (data?.action === 'chow') play('chow_voice')
      return
    case 'event.turn_changed':
      if (selfSeat !== null && Number(data?.seat) === selfSeat && data?.phase === 'discard') play('turn')
      return
    case 'event.discarded':
      // 底噪（discard）保留，人声叠加在其上（08 §2.1）
      play('discard')
      playVoiceOf(data?.tile)
      return
    case 'event.drawn':
      // 自己 100%，他人 40%；观战者（self_seat=null）按他人处理
      play('draw', selfSeat !== null && Number(data?.seat) === selfSeat ? 1 : 0.4)
      return
    case 'event.auto_discard':
    case 'event.claim_timeout':
      play('timeout')
      return
    case 'event.seats_drawn':
      play('dice')
      return
    case 'event.round_started':
      settledRoundKey = ''
      play('deal')
      return
    case 'event.round_restarted':
      // 无杠重发：只播发牌，不播 hu_voice/exhausted
      play('deal')
      return
    default:
      // state.snapshot / room.welcome / pong / error / ready_changed / paused /
      // game_finished / spectate_changed / kong_score / hu_recorded 等不发声
      return
  }
}

/** 处理非事件类消息：目前只有 chat.message 出声 */
export function handleSoundMessage(type: string, data: any): void {
  if (type !== 'chat.message') return
  // 系统播报（login_id=null）不响
  if (!data?.login_id) return
  if (chatPanelFocused()) return
  audioManager.play('chat', { gain: 1, chatAllowed: soundPrefs.chat })
}

/** 进桌/离桌时清空局内去重状态，避免跨房间误丢音 */
export function resetGameSounds(): void {
  settledRoundKey = ''
  audioManager.resetLimits()
}
