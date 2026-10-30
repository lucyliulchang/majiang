<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import Tile from '../../../components/table/Tile.vue'
import { handLayout } from '../../../utils/tile'

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

const emit = defineEmits<{ select: [index: number] }>()

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

const sorted = computed(() => handLayout(props.tiles, props.drawn))
/** 摸牌在整排里的位置：暗牌之后 */
const drawnIndex = computed(() => (sorted.value.drawn === null ? -1 : sorted.value.rest.length))

const tenpaiSet = computed(() => new Set(Object.keys(props.tenpai || {}).map(Number)))

/** 高亮口径：单选（出牌）+ 多选（吃牌选两张）取并集，互不影响 */
const multiSet = computed(() => new Set(props.selectedIndices))
function isSelected(index: number): boolean {
  return props.selectedIndex === index || multiSet.value.has(index)
}

function handleClick(index: number): void {
  if (!props.interactive) return
  emit('select', index)
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
        @click="handleClick(index)"
      >
        <Tile
          :tile="tile"
          :size="size"
          eager
          :selected="isSelected(index)"
          :highlight="showHint && tenpaiSet.has(tile)"
        />
      </button>

      <div v-if="sorted.drawn !== null" class="mj-hand-drawn ml-1.5 flex items-end gap-[3px] border-l border-gold-400/30 pl-1.5">
        <button
          type="button"
          class="mj-press rounded-[5px] focus:outline-none"
          :class="interactive ? 'cursor-pointer' : 'cursor-default'"
          @click="handleClick(drawnIndex)"
        >
          <Tile
            :tile="sorted.drawn as number"
            :size="size"
            eager
            :selected="isSelected(drawnIndex)"
            :highlight="showHint && tenpaiSet.has(sorted.drawn as number)"
          />
        </button>
      </div>
    </div>
  </div>
</template>
