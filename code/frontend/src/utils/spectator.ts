/**
 * v1.2.0 围观点名（04 §9.5）：后端每座最多下发 2 位围观者昵称。
 *
 * 牌桌只点前两位、每位名字最多 4 个字，其余一律忽略（总数只放进 hover 的 title）；
 * 老后端不下发 `spectator_names` 时返回空串，调用方回退成原来的「围观 N」。
 */

/** 每座最多显示几位（与后端 `DEFAULT_SPECTATE_NAME_LIMIT` 对齐） */
export const SPECTATOR_NAME_LIMIT = 2
/** 单个名字最多显示几个字符 */
export const SPECTATOR_NAME_CHARS = 4

export function shortSpectatorName(name?: string | null): string {
  const text = (name || '').trim()
  if (!text) return ''
  // 按码点切，避免把 emoji / 代理对截成半个字
  return [...text].slice(0, SPECTATOR_NAME_CHARS).join('')
}

/** 「韩建、柏向」：最多两位、每位最多 4 字；没有点名时返回空串 */
export function spectatorLine(names?: string[] | null): string {
  return (names || [])
    .slice(0, SPECTATOR_NAME_LIMIT)
    .map(shortSpectatorName)
    .filter(Boolean)
    .join('、')
}

/** 悬停提示：全名 + 真实总数，不占布局（`韩建、柏向平 等 3 人正在围观`） */
export function spectatorTitle(names: string[] | null | undefined, count = 0): string {
  const full = (names || []).filter(Boolean)
  if (!full.length) return count > 0 ? `${count} 人正在围观` : '暂无围观'
  const head = full.join('、')
  return count > full.length ? `${head} 等 ${count} 人正在围观` : `${head} 正在围观`
}
