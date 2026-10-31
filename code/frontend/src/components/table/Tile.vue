<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useSkinsStore } from '../../stores/skins'
import { barCount, dotSlots, localTileArt, tileGlyph, tileKey, tileName, tileRank, tileSuit } from '../../utils/tile'

const props = withDefaults(
  defineProps<{
    tile: number
    /** `micro`/`hand` 是手机牌桌专用档位（牌河小牌 / 自己手牌） */
    size?: 'micro' | 'xs' | 'sm' | 'md' | 'hand' | 'lg' | 'xl'
    faceDown?: boolean
    selected?: boolean
    highlight?: boolean
    dim?: boolean
    idle?: boolean
    /** 标注「这张来自别人打出的牌」（吃/碰/明杠的副露用） */
    mark?: boolean
    /** 标注「这张就是胡牌的那张」（结算页 / 战绩页，金色「胡」角标 + 双层描金，05 §4.5） */
    winTile?: boolean
    /** 首屏手牌用 eager，其余交给浏览器懒加载（05 §6.3） */
    eager?: boolean
    /** 指定皮肤（皮肤管理页的实时预览用；不影响全局当前皮肤） */
    skinCode?: string
  }>(),
  {
    size: 'md',
    faceDown: false,
    selected: false,
    highlight: false,
    dim: false,
    idle: false,
    mark: false,
    winTile: false,
    eager: false,
    skinCode: ''
  }
)

/**
 * 牌身尺寸：宽高比对齐内置矢量牌面的 viewBox 19:26（≈0.73），
 * 这样 `<img>` 用 object-contain 铺满时不会出现上下留白，牌面也不会被拉伸。
 */
const SIZES = {
  micro: { box: 'w-[20px] h-[27px] rounded-[2px]', pad: 'p-[1px]', dot: 'w-[2px] h-[2px]', main: 'text-[10px]', sub: 'text-[6px]', bar: 'w-[1.5px]', gap: 'gap-[0.5px]', badge: 'h-3 w-3 text-[8px] -top-[2px] -right-[2px]' },
  xs: { box: 'w-[17px] h-[23px] rounded-[2px]', pad: 'p-[1px]', dot: 'w-[2px] h-[2px]', main: 'text-[9px]', sub: 'text-[6px]', bar: 'w-[1.5px]', gap: 'gap-[1px]', badge: 'h-2.5 w-2.5 text-[7px] -top-[2px] -right-[2px]' },
  sm: { box: 'w-[24px] h-[33px] rounded-[3px]', pad: 'p-[2px]', dot: 'w-[3px] h-[3px]', main: 'text-[11px]', sub: 'text-[7px]', bar: 'w-[2px]', gap: 'gap-[2px]', badge: 'h-3.5 w-3.5 text-[9px] -top-[4px] -right-[4px]' },
  md: { box: 'w-[32px] h-[44px] rounded-[4px]', pad: 'p-[3px]', dot: 'w-[4px] h-[4px]', main: 'text-[15px]', sub: 'text-[9px]', bar: 'w-[2.5px]', gap: 'gap-[2px]', badge: 'h-3.5 w-3.5 text-[9px] -top-[4px] -right-[4px]' },
  // 手机牌桌专用：38×52 刚好让 14 张排在 iPhone 横屏一屏内
  hand: { box: 'w-[38px] h-[52px] rounded-[4px]', pad: 'p-[3px]', dot: 'w-[5px] h-[5px]', main: 'text-[18px]', sub: 'text-[10px]', bar: 'w-[3px]', gap: 'gap-[2px]', badge: 'h-4 w-4 text-[10px] -top-[5px] -right-[5px]' },
  lg: { box: 'w-[42px] h-[57px] rounded-[5px]', pad: 'p-[4px]', dot: 'w-[6px] h-[6px]', main: 'text-[20px]', sub: 'text-[11px]', bar: 'w-[3px]', gap: 'gap-[3px]', badge: 'h-4 w-4 text-[10px] -top-[5px] -right-[5px]' },
  xl: { box: 'w-[54px] h-[74px] rounded-[6px]', pad: 'p-[5px]', dot: 'w-[8px] h-[8px]', main: 'text-[26px]', sub: 'text-[14px]', bar: 'w-[4px]', gap: 'gap-[4px]', badge: 'h-4 w-4 text-[11px] -top-[6px] -right-[6px]' }
}

const skins = useSkinsStore()

const size = computed(() => SIZES[props.size])
const suit = computed(() => tileSuit(props.tile))
const glyph = computed(() => tileGlyph(props.tile))
const dots = computed(() => (suit.value === 'tong' ? dotSlots(props.tile) : []))
const bars = computed(() => (suit.value === 'tiao' ? barCount(props.tile) : 0))
const isDragonRed = computed(() => props.tile === 31)
const isDragonGreen = computed(() => props.tile === 32)
const isDragonWhite = computed(() => props.tile === 33)
const singleBar = computed(() => suit.value === 'tiao' && tileRank(props.tile) === 0)

/** 牌背用 `back` 键，其余按 0–33 → 1m…white（05 §6.1） */
const assetKey = computed(() => (props.faceDown ? 'back' : tileKey(props.tile)))
/** 预览指定皮肤时不改动全局选中项 */
const previewSkin = computed(() =>
  props.skinCode ? skins.skins.find((item) => item.skin_code === props.skinCode) ?? null : null
)
/** 当前皮肤为这张牌提供的图片（没上传就是空串） */
const skinArt = computed(() =>
  previewSkin.value ? previewSkin.value.assets[assetKey.value] || '' : skins.assetOf(assetKey.value)
)
/**
 * 牌面图三级回退：皮肤图 → 内置矢量牌面（`public/tiles`）→ 纯 CSS。
 * 单张加载失败只影响这一张，不弹错误、不阻塞牌桌（05 §6.3）。
 */
const brokenUrl = ref('')

const imageUrl = computed(() => {
  const local = localTileArt(assetKey.value)
  const candidates = [skinArt.value, local]
  return candidates.find((url) => url && url !== brokenUrl.value) ?? ''
})

watch(assetKey, () => {
  brokenUrl.value = ''
})

const showImage = computed(() => Boolean(imageUrl.value))
const altText = computed(() => (props.faceDown ? '' : tileName(props.tile)))
</script>

<template>
  <div
    :title="faceDown ? '' : tileName(tile)"
    class="relative select-none transition-all duration-150"
    :class="[
      size.box,
      !faceDown && !showImage && 'bg-gradient-to-b from-cream-50 to-cream-200',
      !faceDown && !showImage && !winTile && 'overflow-hidden',
      !faceDown && 'shadow-tile',
      selected
        ? '-translate-y-2 shadow-gold'
        : mark
          ? winTile
            ? '-translate-y-1'
            : '-translate-y-1 ring-1 ring-vermilion-400/85'
          : '',
      highlight && !selected && !winTile ? 'ring-1 ring-gold-400/70' : '',
      winTile ? 'ring-2 ring-gold-400' : '',
      dim ? 'opacity-45' : ''
    ]"
    :style="faceDown && !showImage ? { background: 'linear-gradient(150deg,#1a5c46,#0f3d2e)' } : {}"
  >
    <!-- 副露标记：这一张来自别家打出的牌（吃/碰/明杠）；红点在正上方偏左，与右上角「胡」角标不重叠 -->
    <span
      v-if="mark && !faceDown"
      class="pointer-events-none absolute -top-[3px] left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-vermilion-500 ring-1 ring-cream-50/70"
      aria-hidden="true"
    />

    <!-- 牌面图：皮肤图优先，其次内置矢量牌面（public/tiles）；object-contain 铺满，尺寸仍由 CSS 决定（05 §6.3） -->
    <img
      v-if="showImage"
      :src="imageUrl"
      :alt="altText"
      class="pointer-events-none h-full w-full rounded-[inherit] object-contain"
      :loading="eager ? 'eager' : 'lazy'"
      decoding="async"
      draggable="false"
      @error="brokenUrl = imageUrl"
    />

    <!-- CSS 回退：牌背 -->
    <div
      v-else-if="faceDown"
      class="flex h-full w-full items-center justify-center rounded-[inherit] border border-gold-400/25"
    >
      <div class="h-[70%] w-[62%] rounded-[2px] border border-gold-400/30 bg-[radial-gradient(circle_at_30%_25%,rgba(201,160,99,0.28),transparent_65%)]" />
    </div>

    <!-- CSS 回退：牌面 -->
    <div v-else class="flex h-full w-full flex-col items-center justify-center overflow-hidden rounded-[inherit]" :class="size.pad">
      <div class="absolute inset-[1.5px] rounded-[inherit] border border-gold-400/20" />

      <!-- 万 -->
      <template v-if="suit === 'wan'">
        <span class="font-num font-bold leading-none text-ink-900" :class="size.main">{{ glyph.main }}</span>
        <span class="font-num font-semibold leading-none text-vermilion-500" :class="size.sub">萬</span>
      </template>

      <!-- 筒 -->
      <div v-else-if="suit === 'tong'" class="grid h-full w-full grid-cols-3 grid-rows-3 place-items-center">
        <div v-for="slot in 9" :key="slot" class="flex items-center justify-center">
          <span
            v-if="dots.includes(slot - 1)"
            class="rounded-full border border-jade-500/40 bg-[radial-gradient(circle_at_35%_30%,#5aa9d8,#1f5f8b_70%)]"
            :class="size.dot"
          />
        </div>
      </div>

      <!-- 条 -->
      <div v-else-if="suit === 'tiao'" class="flex h-full w-full items-center justify-center" :class="size.gap">
        <template v-if="singleBar">
          <div class="flex h-[86%] w-[34%] flex-col items-center">
            <span class="h-[26%] w-full rounded-t-full bg-vermilion-500" />
            <span class="h-[74%] w-[52%] rounded-b-sm bg-gradient-to-b from-jade-400 to-jade-500" />
          </div>
        </template>
        <div v-else class="flex h-full w-full flex-wrap items-end justify-center" :class="size.gap">
          <span
            v-for="index in bars"
            :key="index"
            class="rounded-full bg-gradient-to-b from-jade-400 to-jade-500"
            :class="size.bar"
            :style="{ height: bars > 6 ? '28%' : '42%' }"
          />
        </div>
      </div>

      <!-- 字牌 -->
      <span
        v-else
        class="font-num font-bold leading-none"
        :class="[
          size.main,
          isDragonRed ? 'text-vermilion-500' : '',
          isDragonGreen ? 'text-jade-500' : '',
          isDragonWhite ? 'text-ink-600' : '',
          !isDragonRed && !isDragonGreen && !isDragonWhite ? 'text-ink-900' : ''
        ]"
      >
        {{ glyph.main }}
      </span>
    </div>

    <!-- 胡张角标：金色「胡」+ 双层描金（05 §4.5）。
         放在牌面（图片或 CSS 回退）之后、`z-10`，保证皮肤图模式下不被牌面图片吞掉；
         用独立 `v-if`（不参与牌面的 v-if / v-else 链），否则会吞掉 CSS 回退分支。 -->
    <span
      v-if="winTile && !faceDown"
      :class="[
        'pointer-events-none absolute z-10 flex items-center justify-center rounded-full bg-gold-400 font-bold leading-none text-felt-950 ring-1 ring-cream-50/70',
        size.badge
      ]"
      title="胡张"
      aria-hidden="true"
    >
      胡
    </span>
  </div>
</template>
