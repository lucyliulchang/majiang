<script setup lang="ts">
import Tile from '../../components/table/Tile.vue'

/**
 * 竖屏认证页外壳：飘浮的大牌做背景，中间一张卡。
 * 键盘弹起时靠 dvh + 可滚动容器保证提交按钮仍然够得着。
 */
withDefaults(defineProps<{ title: string; subtitle?: string }>(), { subtitle: '' })

defineEmits<{ submit: [] }>()

const floating = [
  { tile: 31, className: 'left-[-6%] top-[12%]', tilt: '-12deg', delay: '0s' },
  { tile: 4, className: 'left-[6%] bottom-[16%]', tilt: '9deg', delay: '1.4s' },
  { tile: 13, className: 'right-[-8%] top-[22%]', tilt: '14deg', delay: '0.7s' },
  { tile: 22, className: 'right-[4%] bottom-[10%]', tilt: '-7deg', delay: '2.1s' }
]
</script>

<template>
  <div class="mj-app mj-safe-t relative overflow-hidden">
    <div class="pointer-events-none absolute inset-0" aria-hidden="true">
      <div
        v-for="item in floating"
        :key="item.tile"
        class="mj-float absolute opacity-[0.12]"
        :class="item.className"
        :style="{ '--mj-tilt': item.tilt, animationDelay: item.delay }"
      >
        <Tile :tile="item.tile" size="lg" class="scale-[2.2]" />
      </div>
      <div class="absolute left-1/2 top-[14%] h-[320px] w-[320px] -translate-x-1/2 rounded-full bg-gold-400/[0.07] blur-3xl" />
    </div>

    <div class="relative mx-auto flex min-h-full w-full max-w-[430px] flex-col justify-center px-5 py-8">
      <div class="mb-6 flex items-center gap-2">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-cream-100 shadow-tile">
          <span class="font-num text-xl font-bold text-vermilion-500">中</span>
        </div>
        <div class="leading-tight">
          <p class="text-[15px] font-semibold tracking-[0.16em] text-cream-100">家庭麻将</p>
          <p class="text-[10px] tracking-[0.28em] text-gold-400/70">FAMILY TABLE · MOBILE</p>
        </div>
      </div>

      <slot name="alerts" />

      <form class="mj-card p-5 shadow-table" @submit.prevent="$emit('submit')">
        <div class="mb-5">
          <h1 class="text-[22px] font-semibold leading-tight text-cream-100">{{ title }}</h1>
          <p v-if="subtitle" class="mt-1.5 text-[12px] leading-relaxed text-ink-300/75">{{ subtitle }}</p>
        </div>
        <slot />
      </form>

      <div class="mt-4 flex items-center justify-between px-1 text-[11px] text-ink-300/60">
        <slot name="footer">
          <span class="flex items-center gap-1.5">
            <span class="h-1.5 w-1.5 rounded-full bg-jade-400" />
            服务正常
          </span>
        </slot>
      </div>
    </div>
  </div>
</template>
