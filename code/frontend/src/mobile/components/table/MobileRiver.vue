<script setup lang="ts">
import { computed } from 'vue'

import Tile from '../../../components/table/Tile.vue'

/**
 * 中央牌河：自己与对家用 6 列小牌铺开，上家/下家受宽度限制只留最近的 8 张
 * （手机横屏中央区高度有限，宁可少显示历史牌，也不让牌河把牌桌挤爆）。
 */
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

/** 左右两侧只显示最近 8 张 */
function recent(seat: number): number[] {
  return river(seat).slice(-8)
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
      <div class="flex w-[41px] shrink-0 flex-wrap content-center justify-end gap-[1px] overflow-hidden">
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

      <div class="flex w-[41px] shrink-0 flex-wrap content-center justify-start gap-[1px] overflow-hidden">
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
