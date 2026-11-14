<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import Tile from '../../../components/table/Tile.vue'

/**
 * 中央牌河：自己与对家用整行小牌铺开；上家/下家是左右两根竖条，
 * 固定 **6 列 × N 行**（每张 micro 20×27 + 1px 缝，六列共 125px，竖条 126px）。
 *
 * 列数取 6 是因为纵向最划算：8/12 张都是 2 行（55px）、18 张才 3 行（83px）；
 * 4 列时 12 张要 3 行、16 张要 4 行（111px），而中间一行常常只有 98–107px。
 * 横向同样宽松：844px 宽的 felt 约 680px，两根 126px 竖条 + 8px 缝 + 54px 牌墙 = 314px，
 * 降到 568px 宽的机型仍余 114px。
 *
 * N 由竖条实测高度算出来（牌高 27 + 缝 1 = 28）：默认 2 行 = 12 张，上限 4 行 = 24 张。
 * 高度预算 = 视口高 − 顶栏41 − pt4 − 自己区87 − 底部槽58 − 牌河内衬10 − 对家行27 − 自己行27 − 两个缝8；
 * 再减去安全区与观战横幅 28。老实现（v1.1.8 及以前）固定 2 列 8 张要 111px，
 * 而 844×390 只剩 107px、观战再降到 79px，最后一行会被 overflow-hidden 切掉半行，
 * 所以改成 6 列（8 张只占 55px）并按实测高度决定行数，既不再裁切，又能在宽裕机型上多显示历史牌。
 */
const SIDE_COLUMNS = 6
const SIDE_ROWS_DEFAULT = 2
const SIDE_ROWS_MAX = 4
/** 一张牌占的高度：27px 牌身 + 1px 行缝 */
const SIDE_TILE_STEP = 28

const props = withDefaults(
  defineProps<{
    discards: number[][]
    selfSeat?: number | null
    lastDiscard?: { seat: number; tile: number } | null
    wallCount?: number
  }>(),
  { selfSeat: null, lastDiscard: null, wallCount: 0 }
)

const order = computed(() => {
  const self = props.selfSeat ?? 0
  return {
    self,
    right: (self + 1) % 4,
    across: (self + 2) % 4,
    left: (self + 3) % 4
  }
})

function river(seat: number): number[] {
  return props.discards[seat] || []
}

/**
 * 竖条能放几行：左右两根竖条在同一 grid 行、高度相同（items-stretch），
 * 只量左侧一根即可。观战横幅出现、横竖屏切换、小屏机都会触发重算。
 */
const leftStrip = ref<HTMLElement | null>(null)
const sideRows = ref(SIDE_ROWS_DEFAULT)
let observer: ResizeObserver | null = null

/** 测量器：n 行恰好占用 n*28-1，所以可用高度加回 1px 再除 */
function measureRows(height: number): number {
  if (!(height > 0)) return SIDE_ROWS_DEFAULT
  return Math.min(SIDE_ROWS_MAX, Math.max(1, Math.floor((height + 1) / SIDE_TILE_STEP)))
}

onMounted(() => {
  if (typeof ResizeObserver === 'undefined') return
  observer = new ResizeObserver((entries) => {
    const box = entries[0]
    if (box) sideRows.value = measureRows(box.contentRect.height)
  })
  if (leftStrip.value) observer.observe(leftStrip.value)
})

onBeforeUnmount(() => observer?.disconnect())

/** 左右两侧显示的最近张数 = 6 列 × 实测行数（默认 12，最多 24） */
const sideVisible = computed(() => sideRows.value * SIDE_COLUMNS)

function recent(seat: number): number[] {
  return river(seat).slice(-sideVisible.value)
}

function isLatest(seat: number, tile: number, index: number, list: number[]): boolean {
  const latest = props.lastDiscard
  if (!latest) return false
  return latest.seat === seat && index === list.length - 1 && latest.tile === tile
}
</script>

<template>
  <div class="grid h-full w-full grid-rows-[auto_1fr_auto] gap-1">
    <!-- 对家 -->
    <div class="mx-auto flex max-w-[80%] flex-wrap content-end justify-center gap-[1px]">
      <Tile
        v-for="(tile, index) in river(order.across)"
        :key="`across-${index}`"
        :tile="tile"
        size="micro"
        :highlight="isLatest(order.across, tile, index, river(order.across))"
      />
    </div>

    <!-- 上家 | 牌墙 | 下家 -->
    <div class="flex min-h-0 items-stretch gap-1">
      <div
        ref="leftStrip"
        class="flex w-[126px] shrink-0 flex-wrap content-center justify-end gap-[1px] overflow-hidden"
      >
        <Tile
          v-for="(tile, index) in recent(order.left)"
          :key="`left-${index}`"
          :tile="tile"
          size="micro"
          :highlight="isLatest(order.left, tile, index, recent(order.left))"
        />
      </div>

      <div class="relative flex min-w-0 flex-1 items-center justify-center">
        <div class="relative flex h-[54px] w-[54px] items-center justify-center">
          <div class="absolute inset-0 rounded-xl border border-gold-400/25 bg-felt-950/40" />
          <div class="absolute inset-[5px] rounded-lg border border-gold-400/10" />
          <div class="relative text-center leading-none">
            <p class="font-num text-[17px] font-bold text-gold-300">{{ wallCount }}</p>
            <p class="mt-0.5 text-[9px] tracking-[0.18em] text-ink-300/65">剩余</p>
          </div>
        </div>
      </div>

      <div class="flex w-[126px] shrink-0 flex-wrap content-center justify-start gap-[1px] overflow-hidden">
        <Tile
          v-for="(tile, index) in recent(order.right)"
          :key="`right-${index}`"
          :tile="tile"
          size="micro"
          :highlight="isLatest(order.right, tile, index, recent(order.right))"
        />
      </div>
    </div>

    <!-- 自己 -->
    <div class="mx-auto flex max-w-[80%] flex-wrap content-start justify-center gap-[1px]">
      <Tile
        v-for="(tile, index) in river(order.self)"
        :key="`self-${index}`"
        :tile="tile"
        size="micro"
        :highlight="isLatest(order.self, tile, index, river(order.self))"
      />
    </div>
  </div>
</template>
