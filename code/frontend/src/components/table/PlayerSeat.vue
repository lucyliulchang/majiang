<script setup lang="ts">
import { computed } from 'vue'
import { Crown, Eye, WifiOff } from 'lucide-vue-next'

import Tile from './Tile.vue'
import type { MeldView, SeatView } from '../../types'

const props = withDefaults(
  defineProps<{
    seat: SeatView
    isTurn?: boolean
    isDealer?: boolean
    compact?: boolean
    showReady?: boolean
  }>(),
  { isTurn: false, isDealer: false, compact: false, showReady: true }
)

const total = computed(() => props.seat.total_score)
const roundScore = computed(() => props.seat.round_score)
const hiddenCount = computed(() => props.seat.hand_count)
const backs = computed(() => Math.min(hiddenCount.value, 14))

/** 吃的这副里哪一张是别人打出来的（后端 claim_tile）；其余副露整组同牌，不标 */
function claimIndex(meld: MeldView): number {
  if (meld.kind !== 'chow') return -1
  const claim = meld.claim_tile
  if (claim === null || claim === undefined) return -1
  return meld.tiles.indexOf(claim)
}
</script>

<template>
  <div
    class="relative flex items-center rounded-xl border transition-all duration-300"
    :class="[
      compact ? 'gap-2 px-2.5 py-1.5' : 'gap-3 px-3 py-2',
      isTurn ? 'border-gold-400/60 bg-gold-400/[0.07] animate-breathe' : 'border-cream-100/10 bg-felt-950/35'
    ]"
  >
    <div class="relative">
      <span
        class="flex items-center justify-center rounded-full font-semibold text-felt-950"
        :class="compact ? 'h-8 w-8 text-xs' : 'h-10 w-10 text-sm'"
        :style="{ backgroundColor: seat.color }"
      >
        {{ seat.display_name.slice(0, 1) }}
      </span>
      <span
        v-if="isDealer"
        class="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-gold-400 text-[9px] font-bold text-felt-950"
        title="庄家"
      >
        庄
      </span>
    </div>

    <div class="min-w-0">
      <p class="flex items-center gap-1 truncate text-cream-100" :class="compact ? 'text-xs' : 'text-sm'">
        {{ seat.display_name }}
        <Crown v-if="seat.is_host" class="h-3 w-3 text-gold-300" />
        <WifiOff v-if="!seat.connected" class="h-3 w-3 text-vermilion-400" />
      </p>
      <!-- 被围观人数（全房可见，不暴露观战者身份） -->
      <span
        v-if="(seat.spectator_count ?? 0) > 0"
        class="mt-0.5 inline-flex items-center gap-0.5 text-[10px] text-gold-400/80"
        :title="`${seat.spectator_count} 人正在围观`"
      >
        <Eye class="h-3 w-3" />
        围观 {{ seat.spectator_count }}
      </span>
      <div class="mt-0.5 flex items-center gap-2 text-[11px]">
        <span :class="total >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
          {{ total > 0 ? '+' : '' }}{{ total }}
        </span>
        <span v-if="roundScore !== 0" class="text-ink-300/70">
          本局 {{ roundScore > 0 ? '+' : '' }}{{ roundScore }}
        </span>
        <span v-if="showReady && seat.ready" class="text-gold-300">已准备</span>
      </div>
    </div>

    <div class="ml-auto flex items-center gap-2">
      <!-- 副露 -->
      <div v-if="seat.melds.length" class="flex flex-wrap items-center gap-1">
        <div
          v-for="(meld, index) in seat.melds"
          :key="index"
          class="flex items-center gap-[1px] rounded border border-gold-400/20 bg-felt-900/60 px-1 py-0.5"
        >
          <template v-if="meld.tiles.length">
            <Tile
              v-for="(tile, tileIndex) in meld.tiles"
              :key="tileIndex"
              :tile="tile"
              size="xs"
              :mark="tileIndex === claimIndex(meld)"
            />
          </template>
          <template v-else>
            <Tile :tile="0" size="xs" face-down />
            <Tile :tile="0" size="xs" face-down />
            <Tile :tile="0" size="xs" face-down />
            <Tile v-if="meld.count === 4" :tile="0" size="xs" face-down />
          </template>
        </div>
      </div>

      <!-- 手牌背面 -->
      <div v-if="!compact" class="flex items-end gap-[1px]">
        <Tile v-for="index in backs" :key="index" :tile="0" size="xs" face-down />
      </div>
      <span v-else class="text-[11px] text-ink-300/70">{{ hiddenCount }} 张</span>
    </div>
  </div>
</template>
