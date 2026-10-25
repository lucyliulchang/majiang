<script setup lang="ts">
import { computed } from 'vue'

import Tile from './Tile.vue'

const props = withDefaults(
  defineProps<{
    discards: number[][]
    selfSeat?: number | null
    lastDiscard?: { seat: number; tile: number } | null
    wallCount?: number
    turn?: number | null
  }>(),
  { selfSeat: null, lastDiscard: null, wallCount: 0, turn: null }
)

const seatOrder = computed(() => {
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

function isLatest(seat: number, index: number): boolean {
  const latest = props.lastDiscard
  if (!latest) return false
  return latest.seat === seat && index === river(seat).length - 1
}
</script>

<template>
  <div class="grid h-full w-full grid-cols-[1fr_auto_1fr] grid-rows-[1fr_auto_1fr] gap-1">
    <!-- 对家 -->
    <div class="col-start-2 row-start-1 flex flex-wrap content-end items-end justify-center gap-[2px] px-4">
      <Tile
        v-for="(tile, index) in river(seatOrder.across)"
        :key="`across-${index}`"
        :tile="tile"
        size="sm"
        :highlight="isLatest(seatOrder.across, index)"
      />
    </div>

    <!-- 上家（左侧） -->
    <div class="col-start-1 row-start-2 flex flex-wrap content-center items-center justify-end gap-[2px] py-2 pr-2">
      <Tile
        v-for="(tile, index) in river(seatOrder.left)"
        :key="`left-${index}`"
        :tile="tile"
        size="sm"
        :highlight="isLatest(seatOrder.left, index)"
      />
    </div>

    <!-- 牌堆中心 -->
    <div class="col-start-2 row-start-2 flex flex-col items-center justify-center">
      <div class="relative flex h-16 w-16 items-center justify-center">
        <div class="absolute inset-0 rounded-xl border border-gold-400/25 bg-felt-950/40" />
        <div class="absolute inset-[6px] rounded-lg border border-gold-400/15" />
        <div class="relative text-center">
          <p class="font-num text-xl font-bold text-gold-300">{{ wallCount }}</p>
          <p class="text-[10px] tracking-[0.2em] text-ink-300/70">剩餘</p>
        </div>
      </div>
    </div>

    <!-- 下家（右侧） -->
    <div class="col-start-3 row-start-2 flex flex-wrap content-center items-center justify-start gap-[2px] py-2 pl-2">
      <Tile
        v-for="(tile, index) in river(seatOrder.right)"
        :key="`right-${index}`"
        :tile="tile"
        size="sm"
        :highlight="isLatest(seatOrder.right, index)"
      />
    </div>

    <!-- 自己 -->
    <div class="col-start-2 row-start-3 flex flex-wrap content-start items-start justify-center gap-[2px] px-4">
      <Tile
        v-for="(tile, index) in river(seatOrder.self)"
        :key="`self-${index}`"
        :tile="tile"
        size="sm"
        :highlight="isLatest(seatOrder.self, index)"
      />
    </div>
  </div>
</template>
