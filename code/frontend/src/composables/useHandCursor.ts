import { computed, onBeforeUnmount, onMounted, ref, watch, type ComputedRef, type Ref } from 'vue'

import { pickIndices } from '../utils/chow'
import { handLayout, tileName } from '../utils/tile'

/**
 * 手牌游标：鼠标点选 + 键盘选牌出牌共用的一套选中状态。
 *
 * 为什么用「索引」而不是「牌面值」：手里常有两三张同值的牌，只有索引才能让 ←/→ 逐张停留；
 * 出牌仍按牌面值下发（服务端同值无差别，`discard(tile)` 只移除一张）。
 *
 * 键位（轮到自己出牌时才响应）：
 * - ← / →：光標左右移一张，到头夹住不循环；未选中时 → 选第一张、← 选最后一张
 * - ↑ / 空格：打出选中的牌；未选中则打刚摸到的那张
 * - ↓ / Esc：取消选中
 *
 * v1.1.0 吃牌选两张（U-2）：`multiActive` 为真时切到**多选**（最多 `multiLimit` 张），
 * 点击是增删、键盘不出牌；出牌路径仍是单选，两套选中互不影响。
 */
export interface HandCursorOptions {
  /** 服务端下发的手牌（含摸牌，升序由本模块统一排） */
  hand: Ref<number[]>
  /** 本回合摸到的牌；不是自己摸牌后出牌时为 null（如碰完直接出牌） */
  drawn: Ref<number | null>
  /** 轮到自己出牌才允许选中与响应键盘 */
  active: Ref<boolean>
  /** 真正出牌，参数为牌面值 */
  discard: (tile: number) => void
  /** 未选中且没有摸牌时按了出牌键（碰/吃后直接出牌的场景），交给调用方提示 */
  onNothingToDiscard?: () => void
  /** 多选模式（吃牌选两张）：true 时点击是增删，不再单选 */
  multiActive?: Ref<boolean>
  /** 多选上限，默认 2 */
  multiLimit?: number
  /** 多选变化后回传牌面值（供 store 校验与提交） */
  onMultiChange?: (tiles: number[]) => void
}

export interface HandCursor {
  /** 当前选中的位置（暗牌升序 + 摸牌末尾），null 表示未选 */
  selectedIndex: Ref<number | null>
  /** 手牌展示顺序，渲染与光标共用 */
  layout: ComputedRef<{ rest: number[]; drawn: number | null }>
  /** 选中的牌面值 */
  selectedTile: ComputedRef<number | null>
  /** 选中的牌名（「五万」），给确认条用 */
  selectedName: ComputedRef<string>
  /** 多选的位置列表（吃牌选两张；出牌不走这里） */
  multiSelected: Ref<number[]>
  /** 点击第 index 张：同一张再点一次取消（多选模式下是增删） */
  select: (index: number) => void
  /** 清空选中（单选 + 多选） */
  clear: () => void
  /** 按牌面值套用一组多选（服务端推荐组合），同值按未占用位置取 */
  setMulti: (tiles: number[]) => void
  /** 只清空多选 */
  clearMulti: () => void
  /** 打出当前选中的牌；未选中时打摸到的牌（与空格/↑ 同义，供「打出」按钮调用） */
  discardSelected: () => void
}

function isTypingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null
  if (!element || !element.tagName) return false
  const tag = element.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  return element.isContentEditable
}

export function useHandCursor(options: HandCursorOptions): HandCursor {
  const selectedIndex = ref<number | null>(null)
  const multiSelected = ref<number[]>([])
  const layout = computed(() => handLayout(options.hand.value, options.drawn.value))
  /** 屏幕上的顺序：暗牌在前，摸牌在最右 */
  const order = computed(() => {
    const list = [...layout.value.rest]
    if (layout.value.drawn !== null) list.push(layout.value.drawn)
    return list
  })
  const selectedTile = computed(() => {
    const index = selectedIndex.value
    if (index === null) return null
    return order.value[index] ?? null
  })
  const selectedName = computed(() => (selectedTile.value === null ? '' : tileName(selectedTile.value)))

  const multiActive = computed(() => Boolean(options.multiActive?.value))
  const multiLimit = computed(() => options.multiLimit ?? 2)

  // 手牌变了（出牌、碰杠、换局）索引可能越界：夹回最后一张，没牌就清空
  watch(order, (list) => {
    if (multiSelected.value.length) {
      multiSelected.value = multiSelected.value.filter((index) => index < list.length)
    }
    if (selectedIndex.value === null) return
    if (!list.length) {
      selectedIndex.value = null
      return
    }
    if (selectedIndex.value > list.length - 1) selectedIndex.value = list.length - 1
  })

  // 进/出多选态时把单选清掉：出牌的「已选」不能带到吃牌里，反之亦然
  watch(multiActive, (active) => {
    if (active) selectedIndex.value = null
  })

  function multiTiles(): number[] {
    return multiSelected.value
      .map((index) => order.value[index])
      .filter((tile): tile is number => tile !== undefined)
  }

  function emitMulti(): void {
    options.onMultiChange?.(multiTiles())
  }

  function toggleMulti(index: number): void {
    if (order.value[index] === undefined) return
    const at = multiSelected.value.indexOf(index)
    if (at >= 0) {
      multiSelected.value.splice(at, 1)
    } else if (multiSelected.value.length >= multiLimit.value) {
      // 已选满还点第三张：挤掉最早选的那张，避免"点了没反应"
      multiSelected.value.shift()
      multiSelected.value.push(index)
    } else {
      multiSelected.value.push(index)
    }
    emitMulti()
  }

  function setMulti(tiles: number[]): void {
    multiSelected.value = pickIndices(order.value, tiles.slice(0, multiLimit.value))
    emitMulti()
  }

  function clearMulti(): void {
    if (!multiSelected.value.length) return
    multiSelected.value = []
    emitMulti()
  }

  function select(index: number): void {
    if (!options.active.value) return
    if (multiActive.value) {
      toggleMulti(index)
      return
    }
    selectedIndex.value = selectedIndex.value === index ? null : index
  }

  function clear(): void {
    selectedIndex.value = null
    clearMulti()
  }

  function move(step: number): void {
    const total = order.value.length
    if (!total) return
    const current = selectedIndex.value
    if (current === null) {
      selectedIndex.value = step > 0 ? 0 : total - 1
      return
    }
    // 不循环：到头夹住，避免误跳回另一端
    selectedIndex.value = Math.min(total - 1, Math.max(0, current + step))
  }

  function discardActive(): void {
    if (multiActive.value) return
    const tile = selectedTile.value
    if (tile !== null) {
      options.discard(tile)
      selectedIndex.value = null
      return
    }
    const drawnTile = layout.value.drawn
    if (drawnTile !== null) {
      options.discard(drawnTile)
      return
    }
    options.onNothingToDiscard?.()
  }

  function onKeydown(event: KeyboardEvent): void {
    if (!options.active.value) return
    // 组合键留给浏览器/系统；输入框里的按键不能当作出牌
    if (event.altKey || event.ctrlKey || event.metaKey) return
    if (isTypingTarget(event.target)) return
    // 吃牌选牌态只认 Esc / ↓：方向键与空格留给页面滚动与「确认吃」按钮
    if (multiActive.value) {
      if (event.key === 'ArrowDown' || event.key === 'Escape') {
        event.preventDefault()
        clearMulti()
      }
      return
    }
    switch (event.key) {
      case 'ArrowLeft':
        event.preventDefault()
        move(-1)
        break
      case 'ArrowRight':
        event.preventDefault()
        move(1)
        break
      case 'ArrowUp':
      case ' ':
      case 'Spacebar':
        event.preventDefault()
        if (!event.repeat) discardActive()
        break
      case 'ArrowDown':
      case 'Escape':
        event.preventDefault()
        clear()
        break
      default:
        break
    }
  }

  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))

  return {
    selectedIndex,
    layout,
    selectedTile,
    selectedName,
    multiSelected,
    select,
    clear,
    setMulti,
    clearMulti,
    discardSelected: discardActive
  }
}
