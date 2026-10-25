<script setup lang="ts">
import { computed } from 'vue'

import { barCount, dotSlots, tileGlyph, tileName, tileRank, tileSuit } from '../../utils/tile'

const props = withDefaults(
  defineProps<{
    tile: number
    size?: 'xs' | 'sm' | 'md' | 'lg'
    faceDown?: boolean
    selected?: boolean
    highlight?: boolean
    dim?: boolean
    idle?: boolean
  }>(),
  { size: 'md', faceDown: false, selected: false, highlight: false, dim: false, idle: false }
)

const SIZES = {
  xs: { box: 'w-[17px] h-[25px] rounded-[3px]', pad: 'p-[1px]', dot: 'w-[2px] h-[2px]', main: 'text-[9px]', sub: 'text-[6px]', bar: 'w-[1.5px]', gap: 'gap-[1px]' },
  sm: { box: 'w-[24px] h-[36px] rounded-[4px]', pad: 'p-[2px]', dot: 'w-[3px] h-[3px]', main: 'text-[11px]', sub: 'text-[7px]', bar: 'w-[2px]', gap: 'gap-[2px]' },
  md: { box: 'w-[32px] h-[48px] rounded-[5px]', pad: 'p-[3px]', dot: 'w-[4px] h-[4px]', main: 'text-[15px]', sub: 'text-[9px]', bar: 'w-[2.5px]', gap: 'gap-[2px]' },
  lg: { box: 'w-[42px] h-[62px] rounded-[6px]', pad: 'p-[4px]', dot: 'w-[6px] h-[6px]', main: 'text-[20px]', sub: 'text-[11px]', bar: 'w-[3px]', gap: 'gap-[3px]' }
}

const size = computed(() => SIZES[props.size])
const suit = computed(() => tileSuit(props.tile))
const glyph = computed(() => tileGlyph(props.tile))
const dots = computed(() => (suit.value === 'tong' ? dotSlots(props.tile) : []))
const bars = computed(() => (suit.value === 'tiao' ? barCount(props.tile) : 0))
const isDragonRed = computed(() => props.tile === 31)
const isDragonGreen = computed(() => props.tile === 32)
const isDragonWhite = computed(() => props.tile === 33)
const singleBar = computed(() => suit.value === 'tiao' && tileRank(props.tile) === 0)
</script>

<template>
  <div
    :title="faceDown ? '' : tileName(tile)"
    class="relative select-none transition-all duration-150"
    :class="[
      size.box,
      faceDown ? 'overflow-hidden' : 'bg-gradient-to-b from-cream-50 to-cream-200',
      !faceDown && 'shadow-tile',
      selected ? '-translate-y-2 shadow-gold' : '',
      highlight && !selected ? 'ring-1 ring-gold-400/70' : '',
      dim ? 'opacity-45' : ''
    ]"
    :style="faceDown ? { background: 'linear-gradient(150deg,#1a5c46,#0f3d2e)' } : {}"
  >
    <!-- 牌背 -->
    <div v-if="faceDown" class="flex h-full w-full items-center justify-center rounded-[inherit] border border-gold-400/25">
      <div class="h-[70%] w-[62%] rounded-[2px] border border-gold-400/30 bg-[radial-gradient(circle_at_30%_25%,rgba(201,160,99,0.28),transparent_65%)]" />
    </div>

    <!-- 牌面 -->
    <div v-else class="flex h-full w-full flex-col items-center justify-center overflow-hidden rounded-[inherit]" :class="size.pad">
      <div class="absolute inset-[1.5px] rounded-[inherit] border border-gold-400/20" />

      <!-- 万 -->
      <template v-if="suit === 'wan'">
        <span class="font-num font-bold leading-none text-ink-900" :class="size.main">{{ glyph.main }}</span>
        <span class="font-num font-semibold leading-none text-vermilion-500" :class="size.sub">萬</span>
      </template>

      <!-- 筒 -->
      <div v-else-if="suit === 'tong'" class="grid h-full w-full grid-cols-3 grid-rows-3 place-items-center">
        <div v-for="slot in 9" :key="slot" class="flex items-center justify-center">
          <span
            v-if="dots.includes(slot - 1)"
            class="rounded-full border border-jade-500/40 bg-[radial-gradient(circle_at_35%_30%,#5aa9d8,#1f5f8b_70%)]"
            :class="size.dot"
          />
        </div>
      </div>

      <!-- 条 -->
      <div v-else-if="suit === 'tiao'" class="flex h-full w-full items-center justify-center" :class="size.gap">
        <template v-if="singleBar">
          <div class="flex h-[86%] w-[34%] flex-col items-center">
            <span class="h-[26%] w-full rounded-t-full bg-vermilion-500" />
            <span class="h-[74%] w-[52%] rounded-b-sm bg-gradient-to-b from-jade-400 to-jade-500" />
          </div>
        </template>
        <div v-else class="flex h-full w-full flex-wrap items-end justify-center" :class="size.gap">
          <span
            v-for="index in bars"
            :key="index"
            class="rounded-full bg-gradient-to-b from-jade-400 to-jade-500"
            :class="size.bar"
            :style="{ height: bars > 6 ? '28%' : '42%' }"
          />
        </div>
      </div>

      <!-- 字牌 -->
      <span
        v-else
        class="font-num font-bold leading-none"
        :class="[
          size.main,
          isDragonRed ? 'text-vermilion-500' : '',
          isDragonGreen ? 'text-jade-500' : '',
          isDragonWhite ? 'text-ink-600' : '',
          !isDragonRed && !isDragonGreen && !isDragonWhite ? 'text-ink-900' : ''
        ]"
      >
        {{ glyph.main }}
      </span>
    </div>
  </div>
</template>
