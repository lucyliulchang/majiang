/**
 * 吃牌选两张（v1.1.0 U-2）的本地口径。
 *
 * 与服务端 `game/claims.py:is_chow` 一一对应，**只用于界面置灰与提示**：
 * 真正的裁决永远在服务端（非法组合返回 `BAD_CHOW`，04 §9.3）。
 * 前端不得因为"本地算过"就跳过校验，也不得把本地拼出来的组合当成合法解。
 */

/** 两张手牌能否与 `claimTile` 组成顺子（同花色、rank 连续、手里张数够扣） */
export function isLegalChow(claimTile: number | null, picks: number[], hand: number[]): boolean {
  if (claimTile === null || claimTile === undefined) return false
  if (!Number.isInteger(claimTile) || claimTile < 0 || claimTile >= 27) return false
  if (picks.length !== 2) return false
  if (picks.some((tile) => !Number.isInteger(tile) || tile < 0 || tile >= 27)) return false
  const suit = Math.floor(claimTile / 9)
  if (picks.some((tile) => Math.floor(tile / 9) !== suit)) return false

  const ranks = [...new Set([claimTile % 9, ...picks.map((tile) => tile % 9)])].sort((a, b) => a - b)
  if (ranks.length !== 3 || ranks[0] + 1 !== ranks[1] || ranks[1] + 1 !== ranks[2]) return false

  const owned = new Map<number, number>()
  for (const tile of hand) owned.set(tile, (owned.get(tile) ?? 0) + 1)
  const need = new Map<number, number>()
  for (const tile of picks) need.set(tile, (need.get(tile) ?? 0) + 1)
  return [...need].every(([tile, amount]) => (owned.get(tile) ?? 0) >= amount)
}

/** 顺子的三张（含被吃的那张），候选区展示「二万三万四万」用 */
export function chowRun(claimTile: number, picks: number[]): number[] {
  return [...picks, claimTile].sort((a, b) => a - b)
}

/**
 * 牌面值 → 手牌展示顺序里的位置（高亮用）。
 * 手里常有两三张同值的牌，按贪心取"尚未占用"的位置，避免两张选中叠在同一张上。
 */
export function pickIndices(order: number[], picks: number[]): number[] {
  const rest = [...picks]
  const indices: number[] = []
  order.forEach((tile, index) => {
    const at = rest.indexOf(tile)
    if (at < 0) return
    rest.splice(at, 1)
    indices.push(index)
  })
  return indices
}
