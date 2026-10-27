<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, Copy, DoorOpen, ScrollText, Wifi, WifiOff } from 'lucide-vue-next'

import type { RuleBrief } from '../../types'

const props = defineProps<{
  roomName: string
  code: string
  ruleName: string
  ruleBrief: RuleBrief | null
  wallCount: number
  roundNo: number
  totalRounds: number
  connected: boolean
}>()

const emit = defineEmits<{ exit: []; copy: [] }>()

const open = ref(false)

const timeoutText = computed(() => {
  const brief = props.ruleBrief
  if (!brief) return '—'
  return brief.turn_timeout.enabled ? `${brief.turn_timeout.seconds} 秒` : '不限时'
})

const kongText = computed(() => {
  const brief = props.ruleBrief
  if (!brief) return '—'
  const kong = brief.kong_score
  if (!kong.enabled) return '不计分'
  return `明${kong.exposed} / 暗${kong.hidden} / 补${kong.added}`
})

const modeText = computed(() =>
  props.ruleBrief?.fan_mode === 'exponential' ? '2 的 N 次方' : '线性累加'
)
</script>

<template>
  <div class="relative flex flex-wrap items-center gap-3">
    <div class="flex items-center gap-2">
      <span class="text-base font-semibold text-cream-100">{{ roomName }}</span>
      <button
        type="button"
        class="flex items-center gap-1 rounded-md border border-gold-400/30 bg-gold-400/10 px-2 py-0.5 font-mono text-xs tracking-[0.18em] text-gold-300 transition hover:bg-gold-400/20"
        @click="emit('copy')"
      >
        {{ code }}
        <Copy class="h-3 w-3" />
      </button>
    </div>

    <button
      type="button"
      class="flex items-center gap-1.5 rounded-full border border-cream-100/15 bg-cream-100/5 px-3 py-1 text-xs text-cream-100/90 transition hover:border-gold-400/40"
      @click="open = !open"
    >
      <ScrollText class="h-3.5 w-3.5 text-gold-300" />
      {{ ruleName }}
      <span class="text-ink-300/70">· 底分 {{ ruleBrief?.base_score ?? '—' }} · {{ timeoutText }}</span>
      <ChevronDown class="h-3.5 w-3.5 transition" :class="open ? 'rotate-180' : ''" />
    </button>

    <div class="ml-auto flex items-center gap-4 text-xs text-ink-300/80">
      <span>第 <b class="font-num text-cream-100">{{ roundNo }}</b> / {{ totalRounds }} 局</span>
      <span>牌墙 <b class="font-num text-gold-300">{{ wallCount }}</b></span>
      <span class="flex items-center gap-1" :class="connected ? 'text-jade-400' : 'text-vermilion-400'">
        <Wifi v-if="connected" class="h-3.5 w-3.5" />
        <WifiOff v-else class="h-3.5 w-3.5" />
        {{ connected ? '已连接' : '重连中' }}
      </span>
      <button type="button" class="btn-ghost flex items-center gap-1 rounded-lg px-2.5 py-1" @click="emit('exit')">
        <DoorOpen class="h-3.5 w-3.5" />
        离桌
      </button>
    </div>

    <transition name="drop">
      <div
        v-if="open"
        class="absolute left-0 top-full z-30 mt-2 w-[330px] rounded-xl border border-gold-400/25 bg-felt-950/95 p-4 text-xs shadow-table backdrop-blur"
      >
        <p class="mb-2 text-sm font-medium text-gold-300">本局规则</p>
        <dl class="space-y-1.5 text-ink-300/90">
          <div class="flex justify-between"><dt>底分</dt><dd class="text-cream-100">{{ ruleBrief?.base_score }}</dd></div>
          <div class="flex justify-between"><dt>番数算法</dt><dd class="text-cream-100">{{ modeText }}</dd></div>
          <div class="flex justify-between">
            <dt>封顶</dt>
            <dd class="text-cream-100">{{ ruleBrief?.fan_cap === null ? '不封顶' : `${ruleBrief?.fan_cap} 番` }}</dd>
          </div>
          <div class="flex justify-between"><dt>吃牌</dt><dd class="text-cream-100">{{ ruleBrief?.allow_chow ? '允许' : '不允许' }}</dd></div>
          <div class="flex justify-between"><dt>出牌限时</dt><dd class="text-cream-100">{{ timeoutText }}</dd></div>
          <div class="flex justify-between"><dt>杠分</dt><dd class="text-cream-100">{{ kongText }}</dd></div>
          <div class="flex justify-between"><dt>听牌提示</dt><dd class="text-cream-100">{{ ruleBrief?.ting_hint ? '开启' : '关闭' }}</dd></div>
        </dl>
        <div class="mt-2.5 border-t border-cream-100/10 pt-2 text-[11px] text-ink-300/70">
          牌型：{{ (ruleBrief?.patterns || []).join('、') || '—' }}
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.drop-enter-active,
.drop-leave-active {
  transition: all 0.18s ease;
}
.drop-enter-from,
.drop-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
