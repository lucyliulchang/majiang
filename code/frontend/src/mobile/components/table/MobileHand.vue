<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import Tile from '../../../components/table/Tile.vue'
import { sortHand } from '../../../utils/tile'

/**
 * 自己的手牌：一整排贴在屏幕底部，摸到的牌用金线隔开。
 *
 * 牌宽按容器宽度自动换档（窄机型降到 md/sm，避免整排横向溢出），
 * 点一张只是「选中」，真正出牌由牌桌下方的「打出」按钮确认——防误触。
 */
const props = withDefaults(
  defineProps<{
    tiles: number[]
    drawn?: number | null
    selected?: number | null
    tenpai?: Record<string, number[]>
    interactive?: boolean
    showHint?: boolean
  }>(),
  { drawn: null, selected: null, tenpai: () => ({}), interactive: true, showHint: false }
)

const emit = defineEmits<{ select: [tile: number] }>()

const wrap = ref<HTMLElement | null>(null)
const width = ref(760)
let observer: ResizeObserver | null = null

onMounted(() => {
  observer = new ResizeObserver((entries) => {
    const box = entries[0]
    if (box) width.value = box.contentRect.width
  })
  if (wrap.value) observer.observe(wrap.value)
})

onBeforeUnmount(() => observer?.disconnect())

/** 13 张手牌 + 摸牌大致需要的宽度：600 以上用 38px，470 以上用 32px，再窄退回 24px */
const size = computed<'sm' | 'md' | 'hand'>(() => {
  if (width.value >= 600) return 'hand'
  if (width.value >= 470) return 'md'
  return 'sm'
})

const sorted = computed(() => {
  const list = sortHand(props.tiles)
  if (props.drawn === null || props.drawn === undefined) return { rest: list, drawn: null as number | null }
  const index = list.indexOf(props.drawn)
  if (index < 0) return { rest: list, drawn: null as number | null }
  const rest = [...list]
  rest.splice(index, 1)
  return { rest, drawn: props.drawn }
})

const tenpaiSet = computed(() => new Set(Object.keys(props.tenpai || {}).map(Number)))

function handleClick(tile: number): void {
  if (!props.interactive) return
  emit('select', tile)
}
</script>

<template>
  <div ref="wrap" class="mj-hscroll relative w-full">
    <div class="mj-hand-row flex w-max min-w-full items-end justify-center gap-[3px] px-1">
      <button
        v-for="(tile, index) in sorted.rest"
        :key="`${tile}-${index}`"
        type="button"
        class="mj-press rounded-[5px] focus:outline-none"
        :class="interactive ? 'cursor-pointer' : 'cursor-default'"
        @click="handleClick(tile)"
      >
        <Tile :tile="tile" :size="size" eager :selected="selected === tile" :highlight="showHint && tenpaiSet.has(tile)" />
      </button>

      <div v-if="sorted.drawn !== null" class="mj-hand-drawn ml-1.5 flex items-end gap-[3px] border-l border-gold-400/30 pl-1.5">
        <button
          type="button"
          class="mj-press rounded-[5px] focus:outline-none"
          :class="interactive ? 'cursor-pointer' : 'cursor-default'"
          @click="handleClick(sorted.drawn as number)"
        >
          <Tile
            :tile="sorted.drawn as number"
            :size="size"
            eager
            :selected="selected === sorted.drawn"
            :highlight="showHint && tenpaiSet.has(sorted.drawn as number)"
          />
        </button>
      </div>
    </div>
  </div>
</template>
