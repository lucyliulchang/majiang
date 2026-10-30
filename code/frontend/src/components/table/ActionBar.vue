<script setup lang="ts">
import { computed } from 'vue'

import Tile from './Tile.vue'
import type { LegalAction } from '../../types'
import { chowRun } from '../../utils/chow'
import { tileName, tilesName } from '../../utils/tile'

const props = withDefaults(
  defineProps<{
    actions: LegalAction[]
    claimTile?: number | null
    reason?: string
    showPass?: boolean
    /**
     * 吃牌选两张（v1.1.0 U-2）：true 时动作条收起，改成候选区 + 确认/取消/过。
     * 选牌本身发生在手牌上（`useHandCursor` 的多选态），这里只负责展示与提交。
     */
    chowOpen?: boolean
    /** 已选的两张手牌（牌面值，不含被吃的那张） */
    chowPicks?: number[]
    /** 服务端下发的候选组合：只是推荐（默认高亮第一组），非唯一解（04 §9.5） */
    chowCandidates?: number[][]
    /** 两张是否已构成合法顺子；false 时「确认吃」置灰 */
    chowValid?: boolean
    /** 选牌提示（还差几张 / 这两张不成顺子） */
    chowHint?: string
  }>(),
  {
    claimTile: null,
    reason: 'discard',
    showPass: true,
    chowOpen: false,
    chowPicks: () => [],
    chowCandidates: () => [],
    chowValid: false,
    chowHint: ''
  }
)

const emit = defineEmits<{
  act: [action: LegalAction]
  pass: []
  openChow: []
  applyChow: [tiles: number[]]
  confirmChow: []
  cancelChow: []
}>()

const hu = computed(() => props.actions.find((item) => item.action === 'hu'))
const pong = computed(() => props.actions.find((item) => item.action === 'pong'))
const kongs = computed(() => props.actions.filter((item) => item.action === 'kong'))
const chows = computed(() => props.actions.filter((item) => item.action === 'chow'))
const hasAny = computed(() => Boolean(hu.value || pong.value || kongs.value.length || chows.value.length))

const isRobKong = computed(() => props.reason === 'rob_kong')

// 两段式询问（05 §「询问·胡优先」）：能胡时先只给「胡」「不胡」，
// 此时这个按钮是"过胡"（只对本张牌生效）；补出吃碰杠之后才是彻底放弃，文案回到「过」。
const passLabel = computed(() => (props.claimTile !== null && hu.value ? '不胡' : '过'))

/** 已选两张的归一化键：用来判断某个候选组合是否就是当前选中的那组 */
const pickedKey = computed(() =>
  [...props.chowPicks]
    .sort((a, b) => a - b)
    .join('-')
)
const pickedCount = computed(() => props.chowPicks.length)

function candidateActive(tiles: number[]): boolean {
  return [...tiles].sort((a, b) => a - b).join('-') === pickedKey.value
}

/** 候选组合的完整三张（含被吃牌），展示成「二万三万四万」 */
function runOf(tiles: number[]): number[] {
  return props.claimTile === null ? [...tiles] : chowRun(props.claimTile, tiles)
}
</script>

<template>
  <transition name="bar">
    <!-- 吃牌选牌态：点「吃」后展开，不直接提交 -->
    <div
      v-if="chowOpen"
      class="pointer-events-auto flex max-w-[min(94vw,680px)] flex-col gap-1 rounded-2xl border border-gold-400/30 bg-felt-950/90 px-3 py-1.5 shadow-table backdrop-blur-md animate-riseIn"
    >
      <div class="flex flex-wrap items-center justify-center gap-x-2 gap-y-1">
        <div v-if="claimTile !== null" class="flex items-center gap-1.5">
          <span class="text-[13px] text-ink-300/80">来牌</span>
          <Tile :tile="claimTile as number" size="sm" highlight />
        </div>
        <span class="text-[13px] font-medium text-cream-100">
          {{ pickedCount === 2 ? `已选 ${tilesName(chowPicks)}` : '点两张手牌来吃' }}
        </span>
        <span
          v-if="chowHint"
          class="text-[13px]"
          :class="chowValid ? 'text-jade-400' : 'text-vermilion-400'"
        >
          {{ chowHint }}
        </span>
        <span v-else-if="chowValid" class="text-[13px] text-jade-400">可以吃</span>

        <template v-if="chowCandidates.length">
          <span class="ml-1 text-[13px] text-ink-300/80">候选</span>
          <button
            v-for="(tiles, index) in chowCandidates"
            :key="`chow-cand-${index}`"
            type="button"
            class="flex items-center gap-[1px] rounded-lg border px-1.5 py-1 transition"
            :class="
              candidateActive(tiles)
                ? 'border-gold-400 bg-gold-400/20 shadow-gold'
                : 'border-cream-100/15 bg-cream-100/[0.04] hover:border-gold-400/50'
            "
            :title="`套用 ${tilesName(runOf(tiles))}`"
            :aria-label="`套用 ${tilesName(runOf(tiles))}`"
            @click="emit('applyChow', tiles)"
          >
            <Tile v-for="(tile, at) in runOf(tiles)" :key="`${index}-${at}`" :tile="tile" size="sm" />
          </button>
        </template>
      </div>

      <div class="flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          class="rounded-xl px-4 py-1.5 text-base font-semibold transition"
          :class="
            chowValid
              ? 'btn-gold'
              : 'cursor-not-allowed border border-cream-100/15 bg-cream-100/[0.05] text-ink-300/45'
          "
          :disabled="!chowValid"
          @click="emit('confirmChow')"
        >
          确认吃
        </button>
        <button type="button" class="btn-ghost rounded-xl px-4 py-1.5 text-base" @click="emit('cancelChow')">
          取消
        </button>
        <button v-if="showPass" type="button" class="btn-ghost rounded-xl px-4 py-1.5 text-base" @click="emit('pass')">
          过
        </button>
      </div>
    </div>

    <div
      v-else-if="hasAny || showPass"
      class="pointer-events-auto flex flex-wrap items-center justify-center gap-2 rounded-2xl border border-gold-400/25 bg-felt-950/80 px-3 py-2.5 shadow-table backdrop-blur-md"
    >
      <div v-if="claimTile !== null" class="mr-1 flex items-center gap-2 pr-2">
        <span class="text-[13px] text-ink-300/80">{{ isRobKong ? '抢杠' : '来牌' }}</span>
        <Tile :tile="claimTile as number" size="sm" highlight />
        <span class="text-sm text-cream-100">{{ tileName(claimTile as number) }}</span>
      </div>

      <button
        v-if="hu"
        type="button"
        class="rounded-xl bg-gradient-to-b from-vermilion-400 to-vermilion-500 px-5 py-2 text-base font-bold text-cream-50 shadow-[0_10px_24px_-12px_rgba(192,57,43,0.9)] transition hover:brightness-110 animate-pulse"
        @click="emit('act', hu as LegalAction)"
      >
        {{ isRobKong ? '抢杠胡' : '胡' }}
      </button>

      <button
        v-if="pong"
        type="button"
        class="btn-gold rounded-xl px-4 py-2 text-base font-semibold"
        @click="emit('act', pong as LegalAction)"
      >
        碰
      </button>

      <button
        v-for="(item, index) in kongs"
        :key="`kong-${index}`"
        type="button"
        class="btn-gold rounded-xl px-4 py-2 text-base font-semibold"
        @click="emit('act', item)"
      >
        {{ item.label || '杠' }}
      </button>

      <!-- 吃只有一颗按钮：具体用哪两张由玩家点选手牌决定（候选组合在选牌态里展示） -->
      <button
        v-if="chows.length"
        type="button"
        class="btn-gold flex items-center gap-1.5 rounded-xl px-4 py-2 text-base font-semibold"
        @click="emit('openChow')"
      >
        吃
        <span v-if="chowCandidates.length" class="text-[11px] font-normal text-felt-950/60">
          {{ chowCandidates.length }} 种
        </span>
      </button>

      <button
        v-if="showPass"
        type="button"
        class="btn-ghost rounded-xl px-4 py-2 text-base"
        @click="emit('pass')"
      >
        {{ passLabel }}
      </button>
    </div>
  </transition>
</template>

<style scoped>
.bar-enter-active,
.bar-leave-active {
  transition: all 0.22s ease;
}
.bar-enter-from,
.bar-leave-to {
  opacity: 0;
  transform: translateY(18px);
}
</style>
