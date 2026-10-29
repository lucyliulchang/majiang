<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { MessageSquare, Send } from 'lucide-vue-next'

import type { ChatMessage } from '../types'

const props = withDefaults(
  defineProps<{
    messages: ChatMessage[]
    selfLoginId?: string
    connected?: boolean
    title?: string
  }>(),
  { selfLoginId: '', connected: true, title: '牌桌闲聊' }
)

const emit = defineEmits<{ send: [text: string] }>()

const draft = ref('')
const listRef = ref<HTMLElement | null>(null)

const visible = computed(() => props.messages.slice(-120))

function submit(): void {
  const text = draft.value.trim()
  if (!text) return
  emit('send', text.slice(0, 200))
  draft.value = ''
}

function isMine(message: ChatMessage): boolean {
  return Boolean(props.selfLoginId) && message.login_id === props.selfLoginId
}

function timeOf(message: ChatMessage): string {
  const date = new Date(message.created_at)
  if (Number.isNaN(date.getTime())) return ''
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
  },
  { immediate: true }
)
</script>

<template>
  <aside
    data-chat-panel
    class="flex h-full flex-col rounded-2xl border border-gold-400/18 bg-felt-950/55 backdrop-blur"
  >
    <div class="flex items-center gap-2 border-b border-cream-100/10 px-4 py-3">
      <MessageSquare class="h-4 w-4 text-gold-300" />
      <span class="text-sm font-medium text-cream-100">{{ title }}</span>
      <span
        class="ml-auto h-1.5 w-1.5 rounded-full"
        :class="connected ? 'bg-jade-400' : 'bg-vermilion-400'"
      />
    </div>

    <div ref="listRef" class="flex-1 space-y-2.5 overflow-y-auto px-3 py-3">
      <p v-if="!visible.length" class="px-2 py-6 text-center text-xs text-ink-300/60">
        还没有人说话，打个招呼吧
      </p>

      <template v-for="message in visible" :key="message.id">
        <div v-if="message.kind === 'system'" class="flex justify-center">
          <span class="rounded-full border border-jade-500/25 bg-jade-500/10 px-2.5 py-1 text-[11px] text-jade-400">
            {{ message.content }}
          </span>
        </div>

        <div v-else class="flex flex-col" :class="isMine(message) ? 'items-end' : 'items-start'">
          <div class="mb-0.5 flex items-center gap-1.5 px-1 text-[10px] text-ink-300/60">
            <span>{{ isMine(message) ? '我' : message.user_name || '家人' }}</span>
            <span>{{ timeOf(message) }}</span>
          </div>
          <div
            class="max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed"
            :class="
              isMine(message)
                ? 'border border-gold-400/40 bg-gold-400/12 text-cream-100'
                : 'border border-cream-100/10 bg-cream-100/[0.06] text-cream-100/90'
            "
          >
            {{ message.content }}
          </div>
        </div>
      </template>
    </div>

    <div class="border-t border-cream-100/10 p-2.5">
      <div class="flex items-end gap-2">
        <input
          v-model="draft"
          class="field flex-1"
          placeholder="说句话…（回车发送）"
          maxlength="200"
          @keyup.enter="submit"
        />
        <button
          type="button"
          class="btn-gold flex h-[38px] w-[38px] items-center justify-center rounded-lg"
          :disabled="!draft.trim()"
          aria-label="发送"
          @click="submit"
        >
          <Send class="h-4 w-4" />
        </button>
      </div>
    </div>
  </aside>
</template>
