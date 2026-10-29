<script setup lang="ts">
import { ChevronLeft } from 'lucide-vue-next'

/**
 * 手机版顶部栏：固定在顶部（含刘海安全区），左侧品牌或返回，右侧由页面自己塞控件
 * （家庭切换、退出登录等）。页面内容用 .mj-nav-hold 让位。
 */
withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    back?: boolean
  }>(),
  { subtitle: '', back: false }
)

const emit = defineEmits<{ back: [] }>()
</script>

<template>
  <header class="mj-safe-t fixed inset-x-0 top-0 z-40 mj-bar-top">
    <div class="flex h-14 items-center gap-2.5 px-3">
      <button
        v-if="back"
        type="button"
        class="mj-press flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-cream-100/10 text-cream-100/85"
        aria-label="返回"
        @click="emit('back')"
      >
        <ChevronLeft class="h-5 w-5" />
      </button>
      <div v-else class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-cream-100 shadow-tile">
        <span class="font-num text-lg font-bold text-vermilion-500">中</span>
      </div>

      <div class="min-w-0 flex-1 leading-tight">
        <p class="truncate text-[15px] font-semibold text-cream-100">{{ title }}</p>
        <p v-if="subtitle" class="mt-0.5 truncate text-[11px] text-ink-300/70">{{ subtitle }}</p>
      </div>

      <slot name="right" />
    </div>
  </header>
</template>
