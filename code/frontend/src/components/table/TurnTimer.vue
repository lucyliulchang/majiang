<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    deadline: number | null
    total?: number
    size?: number
  }>(),
  { total: 15, size: 40 }
)

const now = ref(Date.now() / 1000)
let timer: number | undefined

onMounted(() => {
  timer = window.setInterval(() => {
    now.value = Date.now() / 1000
  }, 250)
})

onBeforeUnmount(() => {
  if (timer !== undefined) window.clearInterval(timer)
})

const remaining = computed(() => {
  if (!props.deadline) return 0
  return Math.max(0, props.deadline - now.value)
})

const ratio = computed(() => {
  if (!props.deadline) return 0
  return Math.min(1, remaining.value / Math.max(1, props.total))
})

const urgent = computed(() => remaining.value <= 5)
</script>

<template>
  <div
    v-if="deadline"
    class="relative flex items-center justify-center rounded-full transition-colors"
    :style="{ width: `${size}px`, height: `${size}px` }"
  >
    <div class="absolute inset-0 rounded-full border border-gold-400/25 bg-felt-950/60" />
    <div
      class="absolute inset-0 rounded-full"
      :style="{
        background: `conic-gradient(${urgent ? '#C0392B' : '#C9A063'} ${ratio * 360}deg, transparent 0deg)`,
        mask: 'radial-gradient(circle, transparent 58%, #000 60%)',
        WebkitMask: 'radial-gradient(circle, transparent 58%, #000 60%)'
      }"
    />
    <span
      class="relative font-num text-sm font-bold"
      :class="urgent ? 'text-vermilion-400' : 'text-gold-300'"
    >
      {{ Math.ceil(remaining) }}
    </span>
  </div>
</template>
