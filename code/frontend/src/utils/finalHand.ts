import type { FinalHand } from '../types'

/** 胡张落点：暗牌下标 / 副露组下标 + 组内下标（三者只会有一个非 null） */
export interface WinTileRef {
  /** 胡张在终局暗牌（`concealed`，已排序）中的下标 */
  concealedIndex: number | null
  /** 胡张所在副露组的下标 */
  meldIndex: number | null
  /** 胡张在副露组内的下标 */
  meldTileIndex: number | null
}

const EMPTY_REF: WinTileRef = { concealedIndex: null, meldIndex: null, meldTileIndex: null }

/**
 * 胡张落点 —— 结算页与战绩页共用的唯一口径（04 §9.5 / 05 §4.5）。
 *
 * 优先用后端落库的 `winning_tile_index`（v1.1.0 新增字段）；
 * 旧局（v1.1.0 之前落库、没有该字段）回退为「`concealed` 中最后一张与 `winning_tile` 同值的牌」，
 * 与后端口径一致（后端也是排序后取最后一次出现），不会指错牌。
 *
 * 暗牌里找不到同值牌时（例如胡张落在副露里），退而查副露，保证**只有一张**牌带「胡」角标。
 */
export function winTileRefOf(finalHand: FinalHand | null | undefined): WinTileRef {
  if (!finalHand) return EMPTY_REF
  const concealed = finalHand.concealed || []
  const winningTile = finalHand.winning_tile
  if (winningTile === null || winningTile === undefined) return EMPTY_REF

  const index = finalHand.winning_tile_index
  if (typeof index === 'number' && Number.isInteger(index) && index >= 0 && index < concealed.length) {
    return { concealedIndex: index, meldIndex: null, meldTileIndex: null }
  }

  // 旧局回退：排序后最后一张同值牌（与后端口径一致）
  for (let i = concealed.length - 1; i >= 0; i -= 1) {
    if (concealed[i] === winningTile) {
      return { concealedIndex: i, meldIndex: null, meldTileIndex: null }
    }
  }

  // 暗牌里没有：胡张落在副露（如抢杠胡的杠上那张）
  const melds = finalHand.melds || []
  for (let m = melds.length - 1; m >= 0; m -= 1) {
    const tiles = melds[m]?.tiles || []
    for (let t = tiles.length - 1; t >= 0; t -= 1) {
      if (tiles[t] === winningTile) {
        return { concealedIndex: null, meldIndex: m, meldTileIndex: t }
      }
    }
  }
  return EMPTY_REF
}

/**
 * 胡张在暗牌（`concealed`，已排序）中的下标；不在暗牌里时为 `null`。
 * 结算页 / 战绩页判断「这张是不是胡张」时用 `winTileRefOf` 更完整。
 */
export function winTileIndexOf(finalHand: FinalHand | null | undefined): number | null {
  return winTileRefOf(finalHand).concealedIndex
}
