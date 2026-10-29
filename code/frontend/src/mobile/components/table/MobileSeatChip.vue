<script setup lang="ts">
import { computed } from 'vue'
import { Crown, Eye, WifiOff } from 'lucide-vue-next'

import Tile from '../../../components/table/Tile.vue'
import type { MeldView, SeatView } from '../../../types'

/**
 * 手机牌桌上的「别家」：只留身份、分数、副露与手牌张数。
 *
 * layout='bar'  → 对家：横放在牌河上方（高度约 30px）
 * layout='side' → 上家/下家：竖在左右两侧（宽度约 62px）
 */
const props = withDefaults(
  defineProps<{
    seat: SeatView
    isTurn?: boolean
    isDealer?: boolean
    layout?: 'bar' | 'side'
    showReady?: boolean
  }>(),
  { isTurn: false, isDealer: false, layout: 'bar', showReady: false }
)

const meldRows = computed(() => props.seat.melds || [])

/** 吃的这副里哪一张是别人打出来的（后端 claim_tile）；碰/杠整组同牌，不标 */
function claimIndex(meld: MeldView): number {
  if (meld.kind !== 'chow') return -1
  const claim = meld.claim_tile
  if (claim === null || claim === undefined) return -1
  return meld.tiles.indexOf(claim)
}

const frameClass = computed(() =>
  props.isTurn ? 'border-gold-400/60 bg-gold-400/[0.08]' : 'border-cream-100/10 bg-felt-950/40'
)

const scoreClass = computed(() => (props.seat.total_score >= 0 ? 'text-jade-400' : 'text-vermilion-400'))
</script>

<template>
  <!-- 对家：一条横带 -->
  <div
    v-if="layout === 'bar'"
    class="flex min-w-0 items-center gap-2 rounded-lg border px-2 py-1 transition-colors"
    :class="[frameClass, isTurn ? 'animate-breathe' : '']"
  >
    <div class="relative shrink-0">
      <span
        class="flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-semibold text-felt-950"
        :style="{ backgroundColor: seat.color }"
      >
        {{ seat.display_name.slice(0, 1) }}
      </span>
      <span
        v-if="isDealer"
        class="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-gold-400 text-[8px] font-bold text-felt-950"
        title="庄家"
      >
        庄
      </span>
    </div>

    <p class="flex min-w-0 items-center gap-1 truncate text-[12px] text-cream-100">
      {{ seat.display_name }}
      <Crown v-if="seat.is_host" class="h-3 w-3 shrink-0 text-gold-300" />
      <WifiOff v-if="!seat.connected" class="h-3 w-3 shrink-0 text-vermilion-400" />
      <Eye v-if="(seat.spectator_count ?? 0) > 0" class="h-3 w-3 shrink-0 text-gold-400/70" />
    </p>

    <span class="shrink-0 text-[11px]" :class="scoreClass">
      {{ seat.total_score > 0 ? '+' : '' }}{{ seat.total_score }}
    </span>
    <span v-if="seat.round_score" class="shrink-0 text-[10px] text-ink-300/60">
      本局 {{ seat.round_score > 0 ? '+' : '' }}{{ seat.round_score }}
    </span>
    <span v-if="showReady && seat.ready" class="shrink-0 text-[10px] text-gold-300">已准备</span>

    <div class="ml-auto flex min-w-0 items-center gap-1 overflow-hidden">
      <div v-for="(meld, index) in meldRows" :key="index" class="flex shrink-0 items-center gap-[1px] rounded border border-gold-400/20 bg-felt-900/60 px-0.5">
        <template v-if="meld.tiles.length">
          <Tile
            v-for="(tile, tileIndex) in meld.tiles"
            :key="tileIndex"
            :tile="tile"
            size="micro"
            :mark="tileIndex === claimIndex(meld)"
          />
        </template>
        <template v-else>
          <Tile v-for="n in meld.count" :key="n" :tile="0" size="micro" face-down />
        </template>
      </div>
      <span class="shrink-0 whitespace-nowrap text-[10px] text-ink-300/65">{{ seat.hand_count }} 张</span>
    </div>
  </div>

  <!-- 上家 / 下家：一列 -->
  <div
    v-else
    class="flex h-full flex-col items-center gap-1 overflow-hidden rounded-lg border px-0.5 py-1.5 transition-colors"
    :class="[frameClass, isTurn ? 'animate-breathe' : '']"
  >
    <div class="relative shrink-0">
      <span
        class="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold text-felt-950"
        :style="{ backgroundColor: seat.color }"
      >
        {{ seat.display_name.slice(0, 1) }}
      </span>
      <span
        v-if="isDealer"
        class="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-gold-400 text-[8px] font-bold text-felt-950"
        title="庄家"
      >
        庄
      </span>
    </div>

    <p class="flex w-full items-center justify-center gap-0.5">
      <span class="truncate text-[10px] leading-tight text-cream-100">{{ seat.display_name }}</span>
      <WifiOff v-if="!seat.connected" class="h-2.5 w-2.5 shrink-0 text-vermilion-400" />
    </p>
    <p class="text-[11px] font-semibold leading-none" :class="scoreClass">
      {{ seat.total_score > 0 ? '+' : '' }}{{ seat.total_score }}
    </p>

    <div class="flex min-h-0 flex-1 flex-col items-center gap-0.5 overflow-hidden pt-0.5">
      <div
        v-for="(meld, index) in meldRows"
        :key="index"
        class="flex shrink-0 items-center gap-[1px] rounded border border-gold-400/20 bg-felt-900/60 px-0.5 py-[1px]"
      >
        <template v-if="meld.tiles.length">
          <Tile
            v-for="(tile, tileIndex) in meld.tiles"
            :key="tileIndex"
            :tile="tile"
            size="micro"
            :mark="tileIndex === claimIndex(meld)"
          />
        </template>
        <template v-else>
          <Tile v-for="n in meld.count" :key="n" :tile="0" size="micro" face-down />
        </template>
      </div>
    </div>

    <span class="shrink-0 text-[9px] leading-none text-ink-300/60">{{ seat.hand_count }} 张</span>
  </div>
</template>
