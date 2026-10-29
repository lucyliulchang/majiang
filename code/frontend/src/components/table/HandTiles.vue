<script setup lang="ts">
import { computed } from 'vue'

import Tile from './Tile.vue'
import { sortHand } from '../../utils/tile'

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

const emit = defineEmits<{
  select: [tile: number]
  discard: [tile: number]
}>()

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
const waitCount = computed(() => {
  const map = props.tenpai || {}
  return Object.keys(map).length
})

function handleClick(tile: number): void {
  if (!props.interactive) return
  if (props.selected === tile) emit('discard', tile)
  else emit('select', tile)
}
</script>

<template>
  <div class="flex items-end gap-3">
    <div class="flex items-end gap-[3px]">
      <button
        v-for="(tile, index) in sorted.rest"
        :key="`${tile}-${index}`"
        type="button"
        class="rounded-[5px] focus:outline-none"
        :class="interactive ? 'cursor-pointer hover:-translate-y-1' : 'cursor-default'"
        @click="handleClick(tile)"
      >
        <Tile
          :tile="tile"
          size="lg"
          eager
          :selected="selected === tile"
          :highlight="showHint && tenpaiSet.has(tile)"
        />
      </button>
    </div>

    <div v-if="sorted.drawn !== null" class="ml-2 flex items-end gap-[3px] border-l border-gold-400/25 pl-3">
      <button
        type="button"
        class="rounded-[5px] focus:outline-none"
        :class="interactive ? 'cursor-pointer hover:-translate-y-1' : 'cursor-default'"
        @click="handleClick(sorted.drawn as number)"
      >
        <Tile
          :tile="sorted.drawn as number"
          size="lg"
          eager
          :selected="selected === (sorted.drawn as number)"
          :highlight="showHint && tenpaiSet.has(sorted.drawn as number)"
        />
      </button>
    </div>

    <span
      v-if="showHint && waitCount > 0"
      class="mb-1 rounded-full border border-gold-400/35 bg-gold-400/10 px-2 py-0.5 text-[11px] text-gold-300"
    >
      {{ waitCount }} 张牌可听
    </span>
  </div>
</template>
