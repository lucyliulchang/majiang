<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { X } from 'lucide-vue-next'

/**
 * 底部抽屉基座：移动端的「弹窗」一律从底部上滑，
 * 这样拇指够得着、也不像居中弹窗那样把手牌盖死。
 *
 * 打开时锁 body 滚动（多层抽屉用计数避免互相解锁），关闭或卸载时恢复。
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    subtitle?: string
    /** 抽屉最大高度，默认 86vh（留出顶部一条能看到牌桌）；用 vh 不用 dvh，兼容 Chrome 78 */
    maxHeight?: string
    closeOnBackdrop?: boolean
    /** 显示顶部抓握条 */
    grabber?: boolean
  }>(),
  { title: '', subtitle: '', maxHeight: '86vh', closeOnBackdrop: true, grabber: true }
)

const emit = defineEmits<{ close: [] }>()

let lockCount = 0
let savedOverflow = ''

function lockBody(): void {
  if (lockCount === 0) {
    savedOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  lockCount += 1
}

function unlockBody(): void {
  lockCount = Math.max(0, lockCount - 1)
  if (lockCount === 0) document.body.style.overflow = savedOverflow
}

let locked = false

function setLock(next: boolean): void {
  if (next === locked) return
  locked = next
  if (next) lockBody()
  else unlockBody()
}

watch(
  () => props.open,
  (open) => setLock(open),
  { immediate: true }
)

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.open) emit('close')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  setLock(false)
})
</script>

<template>
  <Teleport to="body">
    <transition name="sheet">
      <div
        v-if="open"
        class="fixed inset-0 z-[70] flex items-end justify-center bg-felt-950/80"
        @click.self="closeOnBackdrop && emit('close')"
      >
        <section
          class="mj-sheet flex w-full max-w-[560px] flex-col"
          :style="{ maxHeight }"
          role="dialog"
          aria-modal="true"
        >
          <div v-if="grabber" class="flex justify-center pt-2">
            <span class="mj-grabber" />
          </div>

          <header
            v-if="title || $slots.extra"
            class="flex items-start gap-2 px-4 pb-2"
            :class="grabber ? 'pt-2' : 'pt-4'"
          >
            <div class="min-w-0 flex-1">
              <h2 class="truncate text-base font-semibold text-cream-100">{{ title }}</h2>
              <p v-if="subtitle" class="mt-0.5 text-[11px] leading-relaxed text-ink-300/70">{{ subtitle }}</p>
            </div>
            <slot name="extra" />
            <button
              type="button"
              class="mj-press flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cream-100/10 text-ink-300/80"
              aria-label="关闭"
              @click="emit('close')"
            >
              <X class="h-4 w-4" />
            </button>
          </header>

          <div class="mj-vscroll min-h-0 flex-1 px-4 pb-4">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="border-t border-cream-100/10 px-4 py-3">
            <slot name="footer" />
          </footer>
        </section>
      </div>
    </transition>
  </Teleport>
</template>
