<script setup lang="ts">
import { AlertCircle, CheckCircle2, Info, TriangleAlert } from 'lucide-vue-next'

import { useToast } from '../composables/useToast'

const toast = useToast()

const styles: Record<string, string> = {
  info: 'border-gold-400/35 bg-felt-800/90 text-cream-100',
  success: 'border-jade-400/45 bg-[#0d3a2a]/95 text-cream-100',
  warn: 'border-amber-400/45 bg-[#3a2c10]/95 text-cream-100',
  error: 'border-vermilion-500/50 bg-[#3a1414]/95 text-cream-100'
}

const icons: Record<string, unknown> = {
  info: Info,
  success: CheckCircle2,
  warn: TriangleAlert,
  error: AlertCircle
}
</script>

<template>
  <div class="pointer-events-none fixed inset-x-0 top-4 z-[80] flex flex-col items-center gap-2 px-4">
    <transition-group name="toast">
      <div
        v-for="item in toast.items"
        :key="item.id"
        class="pointer-events-auto flex max-w-md items-center gap-2.5 rounded-xl border px-4 py-2.5 text-sm shadow-lg backdrop-blur"
        :class="styles[item.kind]"
      >
        <component :is="icons[item.kind]" class="h-4 w-4 shrink-0" />
        <span class="leading-relaxed">{{ item.text }}</span>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.24s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(-10px) scale(0.96);
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.98);
}
</style>
