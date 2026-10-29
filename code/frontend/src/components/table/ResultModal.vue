<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight, Trophy } from 'lucide-vue-next'

import type { RoundResult, SeatView } from '../../types'
import { tileName } from '../../utils/tile'

const props = withDefaults(
  defineProps<{
    result: RoundResult
    seats: SeatView[]
    selfSeat: number | null
    /** 本局底分（规则快照），用于把「番 → 分」算给家人看 */
    baseScore?: number
    /** 本局庄家座位：庄家倍数只对「庄家那一份」或「庄家胡牌整体」生效 */
    dealerSeat?: number | null
  }>(),
  { baseScore: 1, dealerSeat: null }
)

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

// ---- 分数构成：番分（含自摸/庄家倍数）+ 杠分，避免「13 番自摸怎么不是 26」的困惑 ----
const multipliers = computed(() => props.result.multipliers || { self_draw: 1, dealer: 1 })
const isSelfDraw = computed(() => props.result.win_type === 'self_draw')
/** 一番折算多少分：番合计 × 底分 */
const unitScore = computed(() => props.result.fan_total * (props.baseScore || 1))
/** 自摸倍数只作用于自摸（抢杠胡不走点炮、也不乘自摸倍数） */
const perPayer = computed(() =>
  unitScore.value * (isSelfDraw.value ? Math.max(1, multipliers.value.self_draw) : 1)
)
const dealerPayer = computed(() => perPayer.value * Math.max(1, multipliers.value.dealer))
/** 本局杠分（番分之外另算） */
const kongItems = computed(() => {
  const delta = props.result.kong_delta || []
  return props.seats
    .map((seat) => ({ seat: seat.seat, name: seat.display_name, value: Number(delta[seat.seat] ?? 0) }))
    .filter((item) => item.value !== 0)
})

/** 胡牌的是庄家：三个付款方都要乘庄家倍数 */
const winnerIsDealer = computed(
  () => props.dealerSeat !== null && props.result.winner_seat === props.dealerSeat
)

/** 一家本局收/付的杠分（番分之外的加减分） */
function kongOf(seat: number): number {
  return Number(props.result.kong_delta?.[seat] ?? 0)
}

/** 一家本局收/付的番分 = 总分 − 杠分 */
function fanOf(seat: number): number {
  return (props.result.score_delta[seat] ?? 0) - kongOf(seat)
}

function signed(value: number): string {
  return `${value > 0 ? '+' : ''}${value}`
}
</script>

<template>
  <div class="fixed inset-0 z-[60] flex items-center justify-center bg-felt-950/85 px-4 backdrop-blur-sm">
    <div class="max-h-[92vh] w-full max-w-xl animate-riseIn overflow-y-auto rounded-2xl border border-gold-400/30 bg-gradient-to-b from-felt-800/95 to-felt-950/95 p-6 shadow-table">
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

      <!-- 分数构成：番分与杠分分开算，再相加 -->
      <div
        v-if="result.winner_seat !== null || kongItems.length"
        class="mt-3 space-y-1.5 rounded-xl border border-cream-100/10 bg-felt-950/45 p-3 text-[11px] leading-relaxed text-ink-300/85"
      >
        <p class="text-xs text-gold-300">分数怎么算</p>

        <!-- ① 番分：番 × 底分 × 倍数 -->
        <p v-if="result.winner_seat !== null">
          <span class="mr-1 rounded bg-gold-400/15 px-1 py-0.5 text-gold-200">番分</span>
          {{ result.fan_total }} 番 × 底分 {{ baseScore }} = {{ unitScore }} 分
          <template v-if="isSelfDraw">
            <template v-if="winnerIsDealer">
              ，自摸 ×{{ multipliers.self_draw }}、庄家胡 ×{{ multipliers.dealer }}：三家各付 {{ dealerPayer }} 分
            </template>
            <template v-else>
              ，自摸 ×{{ multipliers.self_draw }}：两家各付 {{ perPayer }} 分<template v-if="multipliers.dealer > 1">，庄家付 {{ dealerPayer }} 分</template>
            </template>
          </template>
          <template v-else>
            <template v-if="winnerIsDealer">
              ，庄家胡 ×{{ multipliers.dealer }}：三家各付 {{ dealerPayer }} 分
            </template>
            <template v-else>
              ，点炮每份 {{ perPayer }} 分<template v-if="multipliers.dealer > 1">，庄家份 {{ dealerPayer }} 分</template>
            </template>
          </template>
        </p>

        <!-- ② 杠分：不占番、不乘倍数，单独加减 -->
        <p v-if="kongItems.length">
          <span class="mr-1 rounded bg-jade-400/15 px-1 py-0.5 text-jade-400">杠分</span>
          本局有杠，杠分单独算、不乘倍数：
          <span v-for="item in kongItems" :key="item.seat" class="mr-2 whitespace-nowrap">
            {{ item.name }} {{ signed(item.value) }}
          </span>
        </p>
        <p v-else class="text-ink-300/70">
          <span class="mr-1 rounded bg-jade-400/15 px-1 py-0.5 text-jade-400">杠分</span>
          本局无杠（开杠才有杠分）
        </p>

        <p class="text-ink-300/55">
          总分 = 番分{{ kongItems.length ? ' + 杠分' : '' }}；每人格子里的数字就是这两项之和
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
            {{ signed(result.score_delta[seat.seat] ?? 0) }}
          </p>
          <!-- 番 / 杠 拆开显示：一眼看出这个数字里有几分是杠 -->
          <p class="text-[10px] text-ink-300/60">
            番 {{ signed(fanOf(seat.seat)) }}
            <template v-if="kongOf(seat.seat) !== 0">
              <span class="text-jade-400/80"> · 杠 {{ signed(kongOf(seat.seat)) }}</span>
            </template>
          </p>
          <p class="text-[10px] text-ink-300/45">累计 {{ seat.total_score }}</p>
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
