<script setup lang="ts">
import { computed } from 'vue'
import { ArrowUpRight, Copy, Monitor } from 'lucide-vue-next'

import MobileSheet from './MobileSheet.vue'
import { useToast } from '../../composables/useToast'

/**
 * 「这个功能请用电脑」的提示。
 *
 * 手机版第一版只做打牌闭环；规则模板编辑、皮肤上传、成员管理这些
 * 「表格 + 批量上传」的活在小屏上体验极差，统一指回 PC 版。
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    /** 被点击的功能名，例如「规则模板」 */
    feature?: string
    title?: string
    desc?: string
  }>(),
  {
    feature: '这个功能',
    title: '',
    desc: '需要勾选、填表或批量上传，在电脑上操作更快也不容易点错。'
  }
)

const emit = defineEmits<{ close: [] }>()
const toast = useToast()

/** PC 版固定挂在同域 /majiangapp/ 下（与手机版 /mjmobile/ 并存） */
const pcUrl = computed(() => `${window.location.origin}/majiangapp/`)
const heading = computed(() => props.title || `${props.feature}请用电脑打开`)

function copyUrl(): void {
  navigator.clipboard?.writeText(pcUrl.value).then(
    () => toast.success('电脑版地址已复制'),
    () => toast.warn(`电脑版地址：${pcUrl.value}`)
  )
}
</script>

<template>
  <MobileSheet :open="open" :title="heading" :subtitle="`牌局、战绩、家庭切换在手机上都能用；${feature}留给了电脑版。`" @close="emit('close')">
    <div class="mt-1 space-y-3">
      <div class="mj-card-flat flex items-start gap-3 p-3.5">
        <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gold-400/10 text-gold-300">
          <Monitor class="h-5 w-5" />
        </span>
        <div class="min-w-0">
          <p class="text-sm text-cream-100">在电脑浏览器里打开</p>
          <p class="mt-1 break-all font-mono text-[12px] text-gold-300/90">{{ pcUrl }}</p>
          <p class="mt-2 text-[11px] leading-relaxed text-ink-300/70">{{ desc }}</p>
        </div>
      </div>

      <div class="flex gap-2">
        <button
          type="button"
          class="mj-press btn-ghost flex min-h-[46px] flex-1 items-center justify-center gap-1.5 rounded-xl text-sm"
          @click="copyUrl"
        >
          <Copy class="h-4 w-4" />
          复制地址
        </button>
        <a
          :href="pcUrl"
          target="_blank"
          rel="noopener"
          class="mj-press btn-gold flex min-h-[46px] flex-1 items-center justify-center gap-1.5 rounded-xl text-sm font-semibold"
        >
          直接打开
          <ArrowUpRight class="h-4 w-4" />
        </a>
      </div>
    </div>
  </MobileSheet>
</template>
