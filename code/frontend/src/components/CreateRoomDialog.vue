<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Check, Loader2, X } from 'lucide-vue-next'

import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import type { RoomInfo, RuleTemplate } from '../types'

const emit = defineEmits<{ close: []; created: [room: RoomInfo] }>()
const toast = useToast()
const auth = useAuthStore()

const rules = ref<RuleTemplate[]>([])
const selectedId = ref<number | null>(null)
const name = ref('')
const loading = ref(true)
const saving = ref(false)

const selectedRule = computed(() => rules.value.find((item) => item.id === selectedId.value) || null)

function describe(template: RuleTemplate): string {
  const config = template.config
  const parts = [
    `底分 ${config.base_score}`,
    config.fan_mode === 'exponential' ? '2^N 番' : '线性番',
    config.fan_cap === null ? '不封顶' : `封顶 ${config.fan_cap}`,
    config.allow_chow ? '可吃' : '不可吃',
    config.turn_timeout.enabled ? `限时 ${config.turn_timeout.seconds}s` : '不限时',
    config.kong_score.enabled ? '杠计分' : '杠不计分'
  ]
  return parts.join(' · ')
}

onMounted(async () => {
  try {
    rules.value = await api.get<RuleTemplate[]>('/rules')
    if (rules.value.length) {
      selectedId.value = rules.value[0].id
      name.value = `周末家庭局 · ${new Date().toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}`
    }
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
})

async function submit(): Promise<void> {
  if (!selectedId.value) {
    toast.warn('先挑一套规则')
    return
  }
  if (!name.value.trim()) {
    toast.warn('给牌桌起个名字')
    return
  }
  saving.value = true
  try {
    const room = await api.post<RoomInfo>('/rooms', {
      family_code: auth.currentFamilyCode || '',
      room_name: name.value.trim(),
      template_id: selectedId.value
    })
    emit('created', room)
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-[70] flex items-center justify-center bg-felt-950/85 px-4 backdrop-blur-sm">
    <div class="glass w-full max-w-2xl animate-riseIn overflow-hidden rounded-2xl shadow-table">
      <div class="flex items-center justify-between border-b border-cream-100/10 px-6 py-4">
        <div>
          <h2 class="text-lg font-semibold text-cream-100">开一桌</h2>
          <p class="mt-0.5 text-xs text-ink-300/80">选好规则，开局后本局不再变动</p>
        </div>
        <button type="button" class="btn-ghost rounded-lg p-2" @click="emit('close')">
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="max-h-[70vh] space-y-4 overflow-y-auto p-6">
        <label class="block">
          <span class="mb-1.5 block text-xs text-ink-300/85">牌桌名字</span>
          <input v-model="name" class="field" placeholder="比如 周末家庭局" maxlength="64" />
        </label>

        <div>
          <span class="mb-2 block text-xs text-ink-300/85">选择规则模板</span>
          <p v-if="loading" class="text-sm text-ink-300/70">加载规则…</p>
          <div class="grid gap-2 sm:grid-cols-2">
            <button
              v-for="template in rules"
              :key="template.id"
              type="button"
              class="relative rounded-xl border px-3.5 py-3 text-left transition"
              :class="
                selectedId === template.id
                  ? 'border-gold-400/60 bg-gold-400/10'
                  : 'border-cream-100/12 bg-cream-100/[0.03] hover:border-gold-400/30'
              "
              @click="selectedId = template.id"
            >
              <div class="flex items-center gap-1.5">
                <span class="text-sm font-medium text-cream-100">{{ template.template_name }}</span>
                <span
                  v-if="template.is_preset"
                  class="rounded bg-jade-500/20 px-1.5 py-0.5 text-[10px] text-jade-400"
                >
                  预置
                </span>
                <Check v-if="selectedId === template.id" class="ml-auto h-4 w-4 text-gold-300" />
              </div>
              <p class="mt-1 line-clamp-2 text-[11px] leading-relaxed text-ink-300/70">
                {{ template.description || describe(template) }}
              </p>
              <p class="mt-1.5 text-[10px] text-gold-400/70">{{ describe(template) }}</p>
            </button>
          </div>
        </div>

        <div v-if="selectedRule" class="rounded-xl border border-cream-100/10 bg-felt-950/40 p-3 text-[11px] text-ink-300/80">
          <p class="mb-1 text-xs text-gold-300">这套规则会怎么算</p>
          <p class="leading-relaxed">
            {{ selectedRule.config.fan_mode === 'exponential' ? '总番数按 2 的幂放大' : '总番数线性累加' }}，
            命中 {{ selectedRule.config.fan_table.length }} 个可选番种；
            {{ selectedRule.config.ting_hint.enabled ? '轮到你时能看到听牌提示' : '不给听牌提示' }}；
            一场 {{ selectedRule.config.rounds_per_game }} 局。
          </p>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2 border-t border-cream-100/10 px-6 py-4">
        <button type="button" class="btn-ghost rounded-lg px-4 py-2 text-sm" @click="emit('close')">取消</button>
        <button type="button" class="btn-gold flex items-center gap-2 rounded-lg px-5 py-2 text-sm font-semibold" :disabled="saving" @click="submit">
          <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
          {{ saving ? '创建中…' : '开桌' }}
        </button>
      </div>
    </div>
  </div>
</template>
