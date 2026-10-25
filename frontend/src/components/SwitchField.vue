<script setup lang="ts">
defineProps<{
  label: string
  description?: string
  enabled: boolean
  icon?: unknown
}>()

const emit = defineEmits<{ 'update:enabled': [value: boolean] }>()
</script>

<template>
  <div class="rounded-xl border border-cream-100/12 bg-cream-100/[0.03] p-3.5 transition">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="flex items-center gap-1.5 text-sm text-cream-100">
          <component :is="icon" v-if="icon" class="h-3.5 w-3.5 text-gold-300" />
          {{ label }}
        </p>
        <p v-if="description" class="mt-0.5 text-[11px] leading-relaxed text-ink-300/65">
          {{ description }}
        </p>
      </div>

      <button
        type="button"
        role="switch"
        :aria-checked="enabled"
        :aria-label="label"
        class="relative h-6 w-11 shrink-0 rounded-full border transition-colors duration-200"
        :class="enabled ? 'border-gold-400/60 bg-gold-400/80' : 'border-cream-100/20 bg-felt-950/70'"
        @click="emit('update:enabled', !enabled)"
      >
        <span
          class="absolute top-0.5 h-4.5 w-4.5 rounded-full transition-all duration-200"
          :class="enabled ? 'left-[22px] bg-felt-950' : 'left-0.5 bg-cream-100/60'"
          style="height: 18px; width: 18px"
        />
      </button>
    </div>

    <div
      class="mt-3 overflow-hidden transition-all duration-200"
      :class="enabled ? 'max-h-40 opacity-100' : 'max-h-0 opacity-0'"
    >
      <slot :disabled="!enabled" />
    </div>
  </div>
</template>
