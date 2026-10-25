<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight, Trophy } from 'lucide-vue-next'

import type { RoundResult, SeatView } from '../../types'
import { tileName } from '../../utils/tile'

const props = defineProps<{
  result: RoundResult
  seats: SeatView[]
  selfSeat: number | null
}>()

const emit = defineEmits<{ next: []; close: [] }>()

const winnerName = computed(() => {
  if (props.result.winner_seat === null) return null
  return props.seats.find((seat) => seat.seat === props.result.winner_seat)?.display_name || '有人'
})

const winTypeText = computed(() => (props.result.win_type === 'self_draw' ? '自摸' : '点炮'))

const myDelta = computed(() => {
  if (props.selfSeat === null) return 0
  return props.result.score_delta[props.selfSeat] ?? 0
})

const isLastRound = computed(() => Boolean(props.result.is_last_round))
</script>

<template>
  <div class="fixed inset-0 z-[60] flex items-center justify-center bg-felt-950/85 px-4 backdrop-blur-sm">
    <div class="w-full max-w-xl animate-riseIn rounded-2xl border border-gold-400/30 bg-gradient-to-b from-felt-800/95 to-felt-950/95 p-6 shadow-table">
      <div class="flex items-start justify-between">
        <div>
          <p class="text-[11px] tracking-[0.28em] text-ink-300/70">第 {{ result.round_no }} 局 · 结算</p>
          <h2 class="mt-1 flex items-center gap-2 text-xl font-semibold text-cream-100">
            <Trophy class="h-5 w-5 text-gold-300" />
            <template v-if="winnerName">
              {{ winnerName }} 胡牌
              <span class="text-sm font-normal text-ink-300/80">
                {{ winTypeText }}
                <template v-if="result.winning_tile !== null">· {{ tileName(result.winning_tile) }}</template>
              </span>
            </template>
            <template v-else>荒庄，本局无人胡牌</template>
          </h2>
        </div>
        <div class="text-right">
          <p class="font-num text-3xl font-bold text-gold-300">{{ result.fan_total }}</p>
          <p class="text-[11px] text-ink-300/70">番</p>
        </div>
      </div>

      <div v-if="result.fan_items.length" class="mt-4 rounded-xl border border-cream-100/10 bg-cream-100/[0.03] p-3">
        <p class="mb-2 text-xs text-ink-300/70">命中番种</p>
        <div class="flex flex-wrap gap-1.5">
          <span
            v-for="item in result.fan_items"
            :key="item.id"
            class="rounded-md border border-gold-400/25 bg-gold-400/10 px-2 py-1 text-xs text-gold-100"
          >
            {{ item.name }}
            <span class="text-gold-300/80">+{{ item.fan * item.count }}</span>
          </span>
        </div>
        <p v-if="result.breakdown?.capped" class="mt-2 text-[11px] text-amber-400">
          已按封顶 {{ result.breakdown.fan_total }} 番计算（原始 {{ result.breakdown.fan_raw }} 番）
        </p>
      </div>

      <div class="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div
          v-for="seat in seats"
          :key="seat.seat"
          class="rounded-xl border px-3 py-2.5"
          :class="
            seat.seat === result.winner_seat
              ? 'border-gold-400/45 bg-gold-400/10'
              : 'border-cream-100/10 bg-felt-900/40'
          "
        >
          <p class="truncate text-xs text-ink-300/80" :style="{ color: seat.color }">{{ seat.display_name }}</p>
          <p
            class="mt-1 font-num text-lg font-bold"
            :class="(result.score_delta[seat.seat] ?? 0) >= 0 ? 'text-jade-400' : 'text-vermilion-400'"
          >
            {{ (result.score_delta[seat.seat] ?? 0) > 0 ? '+' : '' }}{{ result.score_delta[seat.seat] ?? 0 }}
          </p>
          <p class="text-[10px] text-ink-300/60">累计 {{ seat.total_score }}</p>
        </div>
      </div>

      <div class="mt-5 flex items-center justify-between gap-3">
        <p class="text-xs" :class="myDelta >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
          本局你 {{ myDelta > 0 ? '赢' : myDelta < 0 ? '输' : '平' }} {{ Math.abs(myDelta) }} 分
        </p>
        <div class="flex gap-2">
          <button type="button" class="btn-ghost rounded-lg px-3 py-2 text-sm" @click="emit('close')">
            看看牌桌
          </button>
          <button type="button" class="btn-gold flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold" @click="emit('next')">
            {{ isLastRound ? '查看总账' : '下一局' }}
            <ArrowRight class="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
