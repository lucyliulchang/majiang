<script setup lang="ts">
import { computed } from 'vue'
import { Eye, Users } from 'lucide-vue-next'

import type { SeatView } from '../../types'

const props = withDefaults(
  defineProps<{
    seats: (SeatView | null)[]
    /** 当前跟随的目标；未选目标为 null */
    targetLoginId?: string | null
    limit?: number
  }>(),
  { targetLoginId: null, limit: 10 }
)

const emit = defineEmits<{
  select: [seat: number]
  cancel: []
}>()

interface Card {
  seat: number
  view: SeatView | null
  viewerCount: number
  full: boolean
  followed: boolean
  disabled: boolean
}

const cards = computed<Card[]>(() =>
  [0, 1, 2, 3].map((seat) => {
    const view = props.seats[seat] ?? null
    const viewerCount = view?.spectator_count ?? 0
    const followed = Boolean(view && props.targetLoginId && view.login_id === props.targetLoginId)
    const full = viewerCount >= props.limit && !followed
    return {
      seat,
      view,
      viewerCount,
      full,
      followed,
      disabled: !view || full
    }
  })
)

function pick(card: Card): void {
  if (card.disabled) return
  emit('select', card.seat)
}
</script>

<template>
  <div class="flex flex-col gap-2.5">
    <div class="flex items-center gap-1.5">
      <Eye class="h-3.5 w-3.5 text-gold-300" />
      <p class="text-xs text-cream-100">选一位家人观战，只能看到他的手牌</p>
    </div>

    <div class="grid grid-cols-2 gap-2 lg:grid-cols-4">
      <button
        v-for="card in cards"
        :key="card.seat"
        type="button"
        class="group relative flex min-h-[76px] flex-col justify-between rounded-xl border px-3 py-2.5 text-left transition"
        :class="[
          card.followed
            ? 'border-gold-400/70 bg-gold-400/12'
            : card.disabled
              ? 'cursor-not-allowed border-cream-100/8 bg-cream-100/[0.02] opacity-60'
              : 'border-cream-100/12 bg-cream-100/[0.03] hover:border-gold-400/40 hover:bg-gold-400/[0.06]'
        ]"
        :disabled="card.disabled"
        @click="pick(card)"
      >
        <div class="flex items-center gap-2">
          <span
            v-if="card.view"
            class="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold text-felt-950"
            :style="{ backgroundColor: card.view.color }"
          >
            {{ card.view.display_name.slice(0, 1) }}
          </span>
          <span
            v-else
            class="flex h-7 w-7 items-center justify-center rounded-full border border-dashed border-cream-100/25 text-[10px] text-ink-300/50"
          >
            空
          </span>
          <div class="min-w-0">
            <p class="truncate text-xs text-cream-100">
              {{ card.view ? card.view.display_name : `座位 ${card.seat + 1}` }}
            </p>
            <p class="text-[10px] text-ink-300/60">
              {{ card.view ? (card.view.ready ? '已准备' : '未准备') : '空座' }}
            </p>
          </div>
        </div>

        <div class="mt-1 flex items-center gap-1 text-[10px]">
          <Users class="h-3 w-3 text-gold-400/70" />
          <span v-if="card.full" class="text-vermilion-400">已满 {{ card.viewerCount }}/{{ limit }}</span>
          <span v-else class="text-ink-300/70">围观 {{ card.viewerCount }}/{{ limit }}</span>
          <span v-if="card.followed" class="ml-auto text-gold-300">跟随中</span>
        </div>
      </button>
    </div>

    <button
      v-if="targetLoginId"
      type="button"
      class="btn-ghost mt-1 w-full rounded-lg py-2 text-xs"
      @click="emit('cancel')"
    >
      取消跟随
    </button>
  </div>
</template>
