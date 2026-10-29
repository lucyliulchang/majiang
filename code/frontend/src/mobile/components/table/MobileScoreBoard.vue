<script setup lang="ts">
import { computed } from 'vue'
import { Copy, MessageSquare, MoreHorizontal, Wifi, WifiOff } from 'lucide-vue-next'

import type { RuleBrief } from '../../../types'

/**
 * 横屏牌桌顶栏（≈40px）：一条信息带，不换行、不撑高。
 * 房间名、邀请码、局风/局数、牌墙余量、连接状态，其余都收进「更多」抽屉。
 */
const props = defineProps<{
  roomName: string
  code: string
  ruleName: string
  ruleBrief: RuleBrief | null
  wallCount: number
  roundNo: number
  totalRounds: number
  roundWind?: number | null
  dealerName?: string | null
  connected: boolean
  familyName?: string
}>()

const emit = defineEmits<{ copy: []; more: []; chat: [] }>()

const WIND_TEXT = ['东', '南', '西', '北']

const roundText = computed(() => {
  const wind = props.roundWind
  const prefix = wind === null || wind === undefined ? '' : `${WIND_TEXT[wind] || ''}风 · `
  if (props.roundNo > props.totalRounds) return `${prefix}第 ${props.roundNo} 局（连庄）`
  return `${prefix}第 ${props.roundNo} / ${props.totalRounds} 局`
})
</script>

<template>
  <div class="flex w-full min-w-0 items-center gap-2">
    <button
      type="button"
      class="mj-press flex shrink-0 items-center gap-1 rounded-md border border-gold-400/30 bg-gold-400/10 px-1.5 py-0.5 font-mono text-[11px] tracking-[0.14em] text-gold-300"
      :aria-label="`复制邀请码 ${code}`"
      @click="emit('copy')"
    >
      {{ code }}
      <Copy class="h-3 w-3" />
    </button>

    <div class="flex min-w-0 items-center gap-1.5">
      <span class="truncate text-[13px] font-semibold text-cream-100">{{ roomName }}</span>
      <span class="hidden shrink-0 whitespace-nowrap text-[11px] text-ink-300/70 min-[560px]:inline">
        {{ roundText }}
      </span>
    </div>

    <div class="ml-auto flex shrink-0 items-center gap-2">
      <span class="whitespace-nowrap text-[11px] text-ink-300/75">
        牌墙 <b class="font-num text-[12px] text-gold-300">{{ wallCount }}</b>
      </span>
      <span class="flex items-center gap-1 text-[11px]" :class="connected ? 'text-jade-400' : 'text-vermilion-400'">
        <Wifi v-if="connected" class="h-3.5 w-3.5" />
        <WifiOff v-else class="h-3.5 w-3.5" />
      </span>
      <button
        type="button"
        class="mj-press flex h-8 w-8 items-center justify-center rounded-lg border border-cream-100/15 bg-cream-100/5 text-cream-100/85"
        aria-label="打开牌桌聊天"
        @click="emit('chat')"
      >
        <MessageSquare class="h-4 w-4" />
      </button>
      <button
        type="button"
        class="mj-press flex h-8 items-center gap-1 rounded-lg border border-cream-100/15 bg-cream-100/5 px-2 text-[11px] text-cream-100/85"
        aria-label="更多：规则、皮肤、音效、离桌"
        @click="emit('more')"
      >
        <MoreHorizontal class="h-4 w-4" />
      </button>
    </div>
  </div>
</template>
