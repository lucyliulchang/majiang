<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RotateCw, Smartphone } from 'lucide-vue-next'

import { useOrientation } from '../composables/useOrientation'

/**
 * 牌桌的横屏闸门。
 *
 * 手机竖屏时牌桌根本放不下（四家 + 手牌 + 动作条），所以竖屏只留一张引导遮罩：
 * 按一下按钮尽力全屏 + 锁横屏；iOS Safari 两者都不支持，就引导用户手动横过来。
 */
const { landscape, canLock, requestLandscape } = useOrientation()

const dismissed = ref(false)
const trying = ref(false)

/** 手动「先这样看」只在本次竖屏期间有效，转横再竖会重新提示 */
const visible = computed(() => !landscape.value && !dismissed.value)

watch(landscape, (isLandscape) => {
  if (isLandscape) dismissed.value = false
})

function tryLock(): void {
  trying.value = true
  void requestLandscape().finally(() => {
    trying.value = false
  })
}
</script>

<template>
  <Transition name="gate">
    <div v-if="visible" class="fixed inset-0 z-[90] flex flex-col items-center justify-center gap-5 px-8 text-center">
      <div class="absolute inset-0 bg-felt-950/95" aria-hidden="true" />
      <div class="absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gold-400/[0.07] blur-3xl" aria-hidden="true" />

      <div class="relative flex flex-col items-center gap-5">
        <div class="relative flex h-24 w-24 items-center justify-center">
          <Smartphone class="h-12 w-12 text-cream-100/80" />
          <RotateCw class="absolute -right-1 -top-1 h-6 w-6 animate-spin text-gold-300 [animation-duration:3s]" />
        </div>

        <div class="space-y-2">
          <h2 class="text-xl font-semibold text-cream-100">把手机横过来打牌</h2>
          <p class="mx-auto max-w-[280px] text-[13px] leading-relaxed text-ink-300/80">
            牌桌按真实四方位摆放，横屏才放得下你的一整排手牌和吃碰杠胡按钮。
          </p>
        </div>

        <button
          v-if="canLock"
          type="button"
          class="mj-press btn-gold flex min-h-[48px] items-center gap-2 rounded-xl px-6 text-sm font-semibold"
          :disabled="trying"
          @click="tryLock"
        >
          {{ trying ? '正在切换…' : '一键进入横屏' }}
        </button>
        <p v-else class="max-w-[260px] text-[11px] leading-relaxed text-ink-300/60">
          这部手机（如 iPhone 的 Safari）不支持网页锁定方向，请解锁竖屏锁定后把手机横过来。
        </p>

        <button
          type="button"
          class="text-[12px] text-ink-300/60 underline decoration-dotted underline-offset-4"
          @click="dismissed = true"
        >
          先这样看
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.gate-enter-active,
.gate-leave-active {
  transition: opacity 0.2s ease;
}
.gate-enter-from,
.gate-leave-to {
  opacity: 0;
}
</style>
