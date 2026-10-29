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

/**
 * 05 §6.1 的 35 个资源键：34 张牌 + 牌背。
 * 顺序即皮肤管理页 35 格网格的展示顺序（万 → 筒 → 条 → 字 → 牌背）。
 */
export const TILE_KEYS = [
  '1m', '2m', '3m', '4m', '5m', '6m', '7m', '8m', '9m',
  '1p', '2p', '3p', '4p', '5p', '6p', '7p', '8p', '9p',
  '1s', '2s', '3s', '4s', '5s', '6s', '7s', '8s', '9s',
  'east', 'south', 'west', 'north', 'red', 'green', 'white',
  'back'
] as const

export type TileKey = (typeof TILE_KEYS)[number]

const HONOR_KEYS: TileKey[] = ['east', 'south', 'west', 'north', 'red', 'green', 'white']

/** 牌编码（0–33）→ tile_key：0–8 万、9–17 筒、18–26 条、27–33 东南西北中发白（04 §9.3） */
export function tileKey(tile: number): TileKey {
  if (!Number.isInteger(tile) || tile < 0 || tile > 33) return 'back'
  if (tile < 9) return `${tile + 1}m` as TileKey
  if (tile < 18) return `${tile - 8}p` as TileKey
  if (tile < 27) return `${tile - 17}s` as TileKey
  return HONOR_KEYS[tile - 27]
}

/** tile_key → 中文名（图片 alt、皮肤管理页标签） */
export function tileKeyName(key: string): string {
  if (key === 'back') return '牌背'
  if (key === 'preview') return '预览图'
  const match = /^([1-9])([mps])$/.exec(key)
  if (match) {
    const rank = Number(match[1]) - 1
    const suffix = match[2] === 'm' ? '万' : match[2] === 'p' ? '筒' : '条'
    return `${NUM_CN[rank]}${suffix}`
  }
  const honorIndex = HONOR_KEYS.indexOf(key as TileKey)
  if (honorIndex >= 0) return tileName(27 + honorIndex)
  return key
}

/** 牌背资源键（05 §6.1） */
export const BACK_KEY: TileKey = 'back'

/** 万用汉字数字，筒用圆点，条用竖条，字用汉字 —— 牌面渲染的元信息 */
export function tileGlyph(tile: number): { main: string; sub: string; suit: TileSuit } {
  const suit = tileSuit(tile)
  const rank = tileRank(tile)
  if (suit === 'honor') return { main: HONOR_CN[rank], sub: '', suit }
  if (suit === 'wan') return { main: NUM_CN[rank], sub: '萬', suit }
  return { main: NUM_CN[rank], sub: '', suit }
}
