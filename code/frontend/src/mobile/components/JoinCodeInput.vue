<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

/**
 * 6 位邀请码输入：6 个格子，数字键盘、整串粘贴、输满自动回调。
 *
 * 手机上逐格按最容易点错，所以「粘贴 / 输满即进」是主路径；
 * 父级拿 complete 事件去校验房间，失败时调 reset() 清空重来。
 */
const props = withDefaults(defineProps<{ disabled?: boolean; error?: string }>(), {
  disabled: false,
  error: ''
})

const emit = defineEmits<{ complete: [code: string] }>()

const digits = ref<string[]>(['', '', '', '', '', ''])
const inputs = ref<HTMLInputElement[]>([])

const code = computed(() => digits.value.join(''))

function setInputRef(element: Element | null, index: number): void {
  if (element) inputs.value[index] = element as HTMLInputElement
}

/** 只保留数字：粘贴、输入法联想、自动填充都可能带进非数字 */
function onlyDigits(text: string): string {
  return (text || '').replace(/\D/g, '')
}

function fillFrom(index: number, raw: string): void {
  const cleaned = onlyDigits(raw)
  if (!cleaned) {
    digits.value[index] = ''
    return
  }
  let cursor = index
  for (const char of cleaned) {
    if (cursor > 5) break
    digits.value[cursor] = char
    cursor += 1
  }
  const focusIndex = Math.min(cursor, 5)
  void nextTick(() => inputs.value[focusIndex]?.focus())
  if (code.value.length === 6) emit('complete', code.value)
}

function onInput(index: number, event: Event): void {
  const target = event.target as HTMLInputElement
  const cleaned = onlyDigits(target.value)
  target.value = ''
  fillFrom(index, cleaned)
}

function onPaste(index: number, event: ClipboardEvent): void {
  const text = event.clipboardData?.getData('text') || ''
  if (!text) return
  event.preventDefault()
  const cleaned = onlyDigits(text)
  // 一次贴 6 位：从第 1 格开始覆盖，符合直觉
  if (cleaned.length > 1) {
    digits.value = ['', '', '', '', '', '']
    fillFrom(0, cleaned)
    return
  }
  fillFrom(index, cleaned)
}

function onKeydown(index: number, event: KeyboardEvent): void {
  if (event.key === 'Backspace' && !digits.value[index] && index > 0) {
    inputs.value[index - 1]?.focus()
  }
}

function reset(): void {
  digits.value = ['', '', '', '', '', '']
  void nextTick(() => inputs.value[0]?.focus())
}

function focus(): void {
  void nextTick(() => inputs.value[0]?.focus())
}

defineExpose({ reset, focus, code })
</script>

<template>
  <div>
    <div class="flex justify-between gap-1.5">
      <input
        v-for="(digit, index) in digits"
        :key="index"
        :ref="(element) => setInputRef(element as Element | null, index)"
        :value="digit"
        class="h-14 w-full rounded-xl border bg-felt-950/60 text-center font-mono text-xl font-bold tracking-widest text-gold-300 outline-none transition"
        :class="
          error
            ? 'border-vermilion-500/60'
            : 'border-cream-100/15 focus:border-gold-400/70 focus:shadow-[0_0_0_3px_rgba(201,160,99,0.15)]'
        "
        maxlength="1"
        inputmode="numeric"
        pattern="[0-9]*"
        autocomplete="one-time-code"
        :disabled="disabled"
        :aria-label="`邀请码第 ${index + 1} 位`"
        @input="onInput(index, $event)"
        @paste="onPaste(index, $event)"
        @keydown="onKeydown(index, $event)"
      />
    </div>
    <p v-if="error" class="mt-2 text-[12px] text-vermilion-400">{{ error }}</p>
  </div>
</template>
