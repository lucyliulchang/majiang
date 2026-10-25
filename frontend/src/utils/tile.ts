export type TileSuit = 'wan' | 'tong' | 'tiao' | 'honor'

export const NUM_CN = ['一', '二', '三', '四', '五', '六', '七', '八', '九']
export const HONOR_CN = ['東', '南', '西', '北', '中', '發', '白']

export function tileSuit(tile: number): TileSuit {
  if (tile < 0 || tile > 33) return 'honor'
  if (tile < 9) return 'wan'
  if (tile < 18) return 'tong'
  if (tile < 27) return 'tiao'
  return 'honor'
}

/** 数牌返回 0-8（一到九），字牌返回 0-6（东南西北中发白） */
export function tileRank(tile: number): number {
  return tile < 27 ? tile % 9 : tile - 27
}

export function tileName(tile: number): string {
  if (tile < 0 || tile > 33) return '?'
  const suit = tileSuit(tile)
  const rank = tileRank(tile)
  if (suit === 'honor') return HONOR_CN[rank]
  const suffix = suit === 'wan' ? '万' : suit === 'tong' ? '筒' : '条'
  return `${NUM_CN[rank]}${suffix}`
}

export function tilesName(tiles: number[]): string {
  return tiles.map(tileName).join(' ')
}

/** 筒子圆点排布：返回 0-8 的格子序号（3x3 网格） */
const DOT_LAYOUT: number[][] = [
  [4],
  [1, 7],
  [2, 4, 6],
  [0, 2, 6, 8],
  [0, 2, 4, 6, 8],
  [0, 1, 2, 6, 7, 8],
  [0, 1, 2, 4, 6, 7, 8],
  [0, 1, 2, 3, 5, 6, 7, 8],
  [0, 1, 2, 3, 4, 5, 6, 7, 8]
]

export function dotSlots(tile: number): number[] {
  return DOT_LAYOUT[tileRank(tile)] ?? []
}

/** 条子竖条数量 */
export function barCount(tile: number): number {
  return tileRank(tile) + 1
}

export function sortHand(tiles: number[]): number[] {
  return [...tiles].sort((a, b) => a - b)
}

/** 万用汉字数字，筒用圆点，条用竖条，字用汉字 —— 牌面渲染的元信息 */
export function tileGlyph(tile: number): { main: string; sub: string; suit: TileSuit } {
  const suit = tileSuit(tile)
  const rank = tileRank(tile)
  if (suit === 'honor') return { main: HONOR_CN[rank], sub: '', suit }
  if (suit === 'wan') return { main: NUM_CN[rank], sub: '萬', suit }
  return { main: NUM_CN[rank], sub: '', suit }
}
