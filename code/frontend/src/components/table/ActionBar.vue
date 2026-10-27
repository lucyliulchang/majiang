<script setup lang="ts">
import { computed } from 'vue'

import Tile from './Tile.vue'
import type { LegalAction } from '../../types'
import { tileName } from '../../utils/tile'

const props = withDefaults(
  defineProps<{
    actions: LegalAction[]
    claimTile?: number | null
    reason?: string
    showPass?: boolean
  }>(),
  { claimTile: null, reason: 'discard', showPass: true }
)

const emit = defineEmits<{
  act: [action: LegalAction]
  pass: []
}>()

const hu = computed(() => props.actions.find((item) => item.action === 'hu'))
const pong = computed(() => props.actions.find((item) => item.action === 'pong'))
const kongs = computed(() => props.actions.filter((item) => item.action === 'kong'))
const chows = computed(() => props.actions.filter((item) => item.action === 'chow'))
const hasAny = computed(() => Boolean(hu.value || pong.value || kongs.value.length || chows.value.length))

const isRobKong = computed(() => props.reason === 'rob_kong')
</script>

<template>
  <transition name="bar">
    <div
      v-if="hasAny || showPass"
      class="pointer-events-auto flex flex-wrap items-center justify-center gap-2 rounded-2xl border border-gold-400/25 bg-felt-950/80 px-3 py-2.5 shadow-table backdrop-blur-md"
    >
      <div v-if="claimTile !== null" class="mr-1 flex items-center gap-2 pr-2">
        <span class="text-[11px] text-ink-300/80">{{ isRobKong ? '抢杠' : '来牌' }}</span>
        <Tile :tile="claimTile as number" size="sm" highlight />
        <span class="text-xs text-cream-100">{{ tileName(claimTile as number) }}</span>
      </div>

      <button
        v-if="hu"
        type="button"
        class="rounded-xl bg-gradient-to-b from-vermilion-400 to-vermilion-500 px-5 py-2 text-sm font-bold text-cream-50 shadow-[0_10px_24px_-12px_rgba(192,57,43,0.9)] transition hover:brightness-110 animate-pulse"
        @click="emit('act', hu as LegalAction)"
      >
        {{ isRobKong ? '抢杠胡' : '胡' }}
      </button>

      <button
        v-if="pong"
        type="button"
        class="btn-gold rounded-xl px-4 py-2 text-sm font-semibold"
        @click="emit('act', pong as LegalAction)"
      >
        碰
      </button>

      <button
        v-for="(item, index) in kongs"
        :key="`kong-${index}`"
        type="button"
        class="btn-gold rounded-xl px-4 py-2 text-sm font-semibold"
        @click="emit('act', item)"
      >
        {{ item.label || '杠' }}
      </button>

      <button
        v-for="(item, index) in chows"
        :key="`chow-${index}`"
        type="button"
        class="btn-gold rounded-xl px-4 py-2 text-sm font-semibold"
        @click="emit('act', item)"
      >
        {{ item.label || '吃' }}
      </button>

      <button
        v-if="showPass"
        type="button"
        class="btn-ghost rounded-xl px-4 py-2 text-sm"
        @click="emit('pass')"
      >
        过
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
