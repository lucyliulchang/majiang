<script setup lang="ts">
import { computed } from 'vue'

import Tile from './Tile.vue'
import { handLayout } from '../../utils/tile'

const props = withDefaults(
  defineProps<{
    tiles: number[]
    drawn?: number | null
    /** 选中的位置（暗牌升序 + 摸牌末尾），null 表示未选；出牌用 */
    selectedIndex?: number | null
    /** 多选位置（吃牌选两张，v1.1.0 U-2）；与 selectedIndex 取并集高亮 */
    selectedIndices?: number[]
    tenpai?: Record<string, number[]>
    interactive?: boolean
    showHint?: boolean
  }>(),
  {
    drawn: null,
    selectedIndex: null,
    selectedIndices: () => [],
    tenpai: () => ({}),
    interactive: true,
    showHint: false
  }
)

const emit = defineEmits<{
  // 只上报「点选第几张」，出牌由牌桌上单独的「打出」按钮/键盘触发
  select: [index: number]
}>()

const sorted = computed(() => handLayout(props.tiles, props.drawn))

const tenpaiSet = computed(() => new Set(Object.keys(props.tenpai || {}).map(Number)))
const waitCount = computed(() => {
  const map = props.tenpai || {}
  return Object.keys(map).length
})
/** 摸牌在整排里的位置：暗牌之后 */
const drawnIndex = computed(() => (sorted.value.drawn === null ? -1 : sorted.value.rest.length))

/** 高亮口径：单选（出牌）+ 多选（吃牌选两张）取并集，互不影响 */
const multiSet = computed(() => new Set(props.selectedIndices))
function isSelected(index: number): boolean {
  return props.selectedIndex === index || multiSet.value.has(index)
}

function handleClick(index: number): void {
  if (!props.interactive) return
  // 依次点选：再点同一张等于取消选中，统一由父级切换；出牌走「打出」按钮，避免误触连打出牌
  emit('select', index)
}
</script>

<template>
  <div class="flex items-end gap-3">
    <div class="flex items-end gap-[4px]">
      <button
        v-for="(tile, index) in sorted.rest"
        :key="`${tile}-${index}`"
        type="button"
        class="rounded-[7px] focus:outline-none"
        :class="interactive ? 'cursor-pointer hover:-translate-y-1.5' : 'cursor-default'"
        @click="handleClick(index)"
      >
        <Tile
          :tile="tile"
          size="xl"
          eager
          :selected="isSelected(index)"
          :highlight="showHint && tenpaiSet.has(tile)"
        />
      </button>
    </div>

    <div v-if="sorted.drawn !== null" class="ml-2 flex items-end gap-[4px] border-l border-gold-400/25 pl-3">
      <button
        type="button"
        class="rounded-[7px] focus:outline-none"
        :class="interactive ? 'cursor-pointer hover:-translate-y-1.5' : 'cursor-default'"
        @click="handleClick(drawnIndex)"
      >
        <Tile
          :tile="sorted.drawn as number"
          size="xl"
          eager
          :selected="isSelected(drawnIndex)"
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
