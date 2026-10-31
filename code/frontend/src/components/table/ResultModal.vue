<script setup lang="ts">
import { computed } from 'vue'
import { ArrowRight, Trophy } from 'lucide-vue-next'

import type { FinalHand, RoundResult, SeatView } from '../../types'
import { winTileRefOf } from '../../utils/finalHand'
import { tileName } from '../../utils/tile'
import Tile from './Tile.vue'

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

/**
 * 是否本局庄家（U-3）：只看快照里的 dealer_seat，荒庄/连庄都成立；
 * 纯渲染判断，不改 FinalHand 类型与后端。
 */
function isDealer(seat: number | null | undefined): boolean {
  return props.dealerSeat !== null && seat !== null && seat !== undefined && seat === props.dealerSeat
}

// ---- 胡牌手牌：赢家暗牌 + 副露，共 14 张（点炮/抢杠的胡张已并入暗牌） ----
const winnerHand = computed<FinalHand | null>(() => {
  const hands = props.result.final_hands || []
  if (!hands.length) return null
  return (
    hands.find((hand) => hand.seat === props.result.winner_seat) ||
    hands.find((hand) => hand.is_winner) ||
    null
  )
})

const winnerTileCount = computed(() => {
  const hand = winnerHand.value
  if (!hand) return 0
  return hand.concealed.length + hand.melds.reduce((sum, meld) => sum + meld.tiles.length, 0)
})

/**
 * 胡张落点（v1.1.0 · 04 §9.5）：优先用后端 `winning_tile_index`，
 * 旧局缺该字段时回退为「暗牌中最后一张与 `winning_tile` 同值的牌」——口径与后端一致。
 */
const winTileRef = computed(() => winTileRefOf(winnerHand.value))

/** 暗牌里胡张的下标（结算页暗牌循环用） */
const winTileIndex = computed(() => winTileRef.value.concealedIndex)

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
    <div class="max-h-[92vh] w-full max-w-2xl animate-riseIn overflow-y-auto rounded-2xl border border-gold-400/30 bg-gradient-to-b from-felt-800/95 to-felt-950/95 p-6 shadow-table sm:p-7">
      <div class="flex items-start justify-between">
        <div>
          <p class="text-[13px] tracking-[0.28em] text-ink-300/70">第 {{ result.round_no }} 局 · 结算</p>
          <h2 class="mt-1 flex items-center gap-2 text-2xl font-semibold text-cream-100">
            <Trophy class="h-6 w-6 text-gold-300" />
            <template v-if="winnerName">
              {{ winnerName }} 胡牌
              <span class="text-base font-normal text-ink-300/80">
                {{ winTypeText }}
                <template v-if="result.winning_tile !== null">· {{ tileName(result.winning_tile) }}</template>
              </span>
            </template>
            <template v-else>荒庄，本局无人胡牌</template>
          </h2>
        </div>
        <div class="text-right">
          <p class="font-num text-4xl font-bold text-gold-300">{{ result.fan_total }}</p>
          <p class="text-[13px] text-ink-300/70">番</p>
        </div>
      </div>

      <!-- 胡牌手牌：赢家暗牌 + 副露，一共 14 张；胡张带金色「胡」角标，副露按组分开 -->
      <div v-if="winnerHand" class="mt-4 rounded-xl border border-gold-400/25 bg-gold-400/[0.06] p-3">
        <div class="mb-2 flex items-center justify-between gap-2">
          <p class="flex min-w-0 items-center gap-1 text-sm text-gold-300">
            <span
              v-if="isDealer(winnerHand.seat)"
              class="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gold-400 text-[10px] font-bold leading-none text-felt-950"
              title="庄家"
            >
              庄
            </span>
            <span class="truncate">胡牌手牌（{{ winnerTileCount }} 张）</span>
          </p>
          <p v-if="winnerHand.melds.length" class="text-xs text-ink-300/60">
            副露 {{ winnerHand.melds.length }} 组
          </p>
        </div>
        <div class="flex flex-wrap items-end gap-1">
          <Tile
            v-for="(tile, index) in winnerHand.concealed"
            :key="`concealed-${index}`"
            :tile="tile"
            size="sm"
            :win-tile="index === winTileIndex"
          />
          <span
            v-for="(meld, meldIndex) in winnerHand.melds"
            :key="`meld-${meldIndex}`"
            class="ml-1 flex items-end gap-0.5 rounded border border-cream-100/10 bg-felt-950/40 px-0.5 py-0.5"
          >
            <Tile
              v-for="(tile, tileIndex) in meld.tiles"
              :key="`meld-tile-${meldIndex}-${tileIndex}`"
              :tile="tile"
              size="sm"
              :mark="meld.claim_tile === tile"
              :win-tile="meldIndex === winTileRef.meldIndex && tileIndex === winTileRef.meldTileIndex"
            />
          </span>
        </div>
        <p class="mt-1.5 text-xs text-ink-300/55">左侧是手里暗牌，右侧分组是吃碰杠；带「胡」角标的是胡张</p>
      </div>

      <div v-if="result.fan_items.length" class="mt-4 rounded-xl border border-cream-100/10 bg-cream-100/[0.03] p-3">
        <p class="mb-2 text-sm text-ink-300/70">命中番种</p>
        <div class="flex flex-wrap gap-1.5">
          <span
            v-for="item in result.fan_items"
            :key="item.id"
            class="rounded-md border border-gold-400/25 bg-gold-400/10 px-2 py-1 text-sm text-gold-100"
          >
            {{ item.name }}
            <span class="text-gold-300/80">+{{ item.fan * item.count }}</span>
          </span>
        </div>
        <p v-if="result.breakdown?.capped" class="mt-2 text-[13px] text-amber-400">
          已按封顶 {{ result.breakdown.fan_total }} 番计算（原始 {{ result.breakdown.fan_raw }} 番）
        </p>
      </div>

      <!-- 分数构成：番分与杠分分开算，再相加 -->
      <div
        v-if="result.winner_seat !== null || kongItems.length"
        class="mt-3 space-y-1.5 rounded-xl border border-cream-100/10 bg-felt-950/45 p-3 text-[13px] leading-relaxed text-ink-300/85"
      >
        <p class="text-sm text-gold-300">分数怎么算</p>

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
          <!-- 名字前「庄」徽标：复用 PlayerSeat 的 isDealer 徽标（金底深字、圆形），8 字昵称靠 truncate 收口 -->
          <p class="flex min-w-0 items-center gap-1 text-sm text-ink-300/80" :style="{ color: seat.color }">
            <span
              v-if="isDealer(seat.seat)"
              class="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gold-400 text-[10px] font-bold leading-none text-felt-950"
              title="庄家"
            >
              庄
            </span>
            <span class="truncate">{{ seat.display_name }}</span>
          </p>
          <p
            class="mt-1 font-num text-xl font-bold"
            :class="(result.score_delta[seat.seat] ?? 0) >= 0 ? 'text-jade-400' : 'text-vermilion-400'"
          >
            {{ signed(result.score_delta[seat.seat] ?? 0) }}
          </p>
          <!-- 番 / 杠 拆开显示：一眼看出这个数字里有几分是杠 -->
          <p class="text-xs text-ink-300/60">
            番 {{ signed(fanOf(seat.seat)) }}
            <template v-if="kongOf(seat.seat) !== 0">
              <span class="text-jade-400/80"> · 杠 {{ signed(kongOf(seat.seat)) }}</span>
            </template>
          </p>
          <p class="text-xs text-ink-300/45">累计 {{ seat.total_score }}</p>
        </div>
      </div>

      <div class="mt-5 flex items-center justify-between gap-3">
        <p class="text-sm" :class="myDelta >= 0 ? 'text-jade-400' : 'text-vermilion-400'">
          本局你 {{ myDelta > 0 ? '赢' : myDelta < 0 ? '输' : '平' }} {{ Math.abs(myDelta) }} 分
        </p>
        <div class="flex gap-2">
          <button type="button" class="btn-ghost rounded-lg px-3.5 py-2 text-base" @click="emit('close')">
            看看牌桌
          </button>
          <button type="button" class="btn-gold flex items-center gap-1.5 rounded-lg px-4 py-2 text-base font-semibold" @click="emit('next')">
            {{ isLastRound ? '查看总账' : '下一局' }}
            <ArrowRight class="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
