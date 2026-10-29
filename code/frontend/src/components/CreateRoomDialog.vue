<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Check, Loader2, X } from 'lucide-vue-next'

import { api } from '../api/http'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import type { RoomInfo, RuleFamily, RuleTemplate } from '../types'

const emit = defineEmits<{ close: []; created: [room: RoomInfo] }>()
const toast = useToast()
const auth = useAuthStore()
const router = useRouter()

const rules = ref<RuleTemplate[]>([])
const ruleFamilies = ref<RuleFamily[]>([])
const activeFamily = ref('')
const selectedId = ref<number | null>(null)
const name = ref('')
const loading = ref(true)
const saving = ref(false)

const familyQuery = computed(() =>
  auth.currentFamilyCode ? `?family_code=${encodeURIComponent(auth.currentFamilyCode)}` : ''
)

/** 按族分组：先出现的族按 `sort_order` 排，模板按后端顺序 */
const tabs = computed(() =>
  ruleFamilies.value
    .map((family) => ({
      ...family,
      templates: rules.value.filter((item) => item.rule_family_code === family.rule_family_code)
    }))
    .filter((family) => family.templates.length > 0 || family.ready)
    .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
)

const currentTab = computed(() => tabs.value.find((item) => item.rule_family_code === activeFamily.value) || null)
const visibleTemplates = computed(() => currentTab.value?.templates ?? [])
const familyReady = computed(() => currentTab.value?.ready !== false)
const selectedRule = computed(() => rules.value.find((item) => item.id === selectedId.value) || null)

/**
 * 规则摘要卡片的文案。
 *
 * 各族配置形状并不统一（柏氏没有 `ting_hint`、也不保证 `fan_table` 有值），
 * 老库里还可能有缺字段的历史配置；这里一律按「缺就退化」取值，
 * 绝不能在模板里直接 `.ting_hint.enabled`——渲染期抛错会让整个弹窗被 Vue 换成空节点
 * （表现为点「创建牌桌」闪一下就没反应）。
 */
const ruleDetail = computed(() => {
  const config = selectedRule.value?.config as unknown as {
    fan_mode?: string
    fan_table?: unknown
    ting_hint?: { enabled?: boolean }
    rounds_per_game?: number
  }
  if (!config) return null
  return {
    fanMode: config.fan_mode === 'exponential' ? '总番数按 2 的幂放大' : '总番数线性累加',
    fanCount: Array.isArray(config.fan_table) ? config.fan_table.length : 0,
    tingHint: config.ting_hint?.enabled ? '轮到你时能看到听牌提示' : '不给听牌提示',
    rounds: config.rounds_per_game ?? '—'
  }
})

function describe(template: RuleTemplate): string {
  const config = template.config as unknown as {
    base_score?: number
    fan_mode?: string
    fan_cap?: number | null
    allow_chow?: boolean
    turn_timeout?: { enabled: boolean; seconds: number }
    kong_score?: { enabled: boolean }
  }
  const parts = [
    `底分 ${config.base_score ?? '—'}`,
    config.fan_mode === 'exponential' ? '2^N 番' : '线性番',
    config.fan_cap === null || config.fan_cap === undefined ? '不封顶' : `封顶 ${config.fan_cap}`,
    config.allow_chow ? '可吃' : '不可吃',
    config.turn_timeout?.enabled ? `限时 ${config.turn_timeout.seconds}s` : '不限时',
    config.kong_score?.enabled ? '杠计分' : '杠不计分'
  ]
  return parts.join(' · ')
}

onMounted(async () => {
  try {
    const [templateList, familyList] = await Promise.all([
      api.get<RuleTemplate[]>(`/rules${familyQuery.value}`),
      api.get<RuleFamily[]>('/rule-families').catch(() => [] as RuleFamily[])
    ])
    rules.value = templateList
    ruleFamilies.value = familyList

    // 默认选中：家庭默认规则族里第一套可用模板（未就绪的族不自动选）
    const preferred =
      familyList.find((item) => item.rule_family_code === auth.currentFamily?.default_rule_family_code)?.rule_family_code ||
      familyList.find((item) => item.ready)?.rule_family_code ||
      templateList[0]?.rule_family_code ||
      ''
    activeFamily.value = preferred
    const first = templateList.find((item) => item.rule_family_code === preferred) || templateList[0]
    if (first) selectedId.value = first.id
    name.value = `周末家庭局 · ${new Date().toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}`
  } catch (error) {
    toast.error((error as Error).message)
  } finally {
    loading.value = false
  }
})

function pickFamily(code: string): void {
  activeFamily.value = code
  const first = rules.value.find((item) => item.rule_family_code === code)
  selectedId.value = first?.id ?? null
}

function goRules(): void {
  emit('close')
  router.push({ name: 'rules' })
}

async function submit(): Promise<void> {
  if (!familyReady.value) {
    toast.warn('该规则族引擎未就绪，暂时不能开桌')
    return
  }
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
  <div class="fixed inset-0 z-[70] flex items-center justify-center bg-felt-950/85 px-3 backdrop-blur-sm sm:px-4">
    <div class="glass w-full max-w-2xl animate-riseIn overflow-hidden rounded-2xl shadow-table">
      <div class="flex items-center justify-between border-b border-cream-100/10 px-4 py-4 sm:px-6">
        <div class="min-w-0">
          <h2 class="text-lg font-semibold text-cream-100">开一桌</h2>
          <p class="mt-0.5 truncate text-xs text-ink-300/80">
            {{ auth.currentFamilyName }} · 选好规则，开局后本局不再变动
          </p>
        </div>
        <button type="button" class="btn-ghost rounded-lg p-2" @click="emit('close')">
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="max-h-[70vh] space-y-4 overflow-y-auto p-4 sm:p-6">
        <label class="block">
          <span class="mb-1.5 block text-xs text-ink-300/85">牌桌名字</span>
          <input v-model="name" class="field" placeholder="比如 周末家庭局" maxlength="64" />
        </label>

        <div>
          <span class="mb-2 block text-xs text-ink-300/85">规则族</span>
          <p v-if="loading" class="text-sm text-ink-300/70">加载规则…</p>
          <div v-else class="flex flex-wrap gap-1.5">
            <button
              v-for="tab in tabs"
              :key="tab.rule_family_code"
              type="button"
              class="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition"
              :class="
                activeFamily === tab.rule_family_code
                  ? 'border-gold-400/60 bg-gold-400/12 text-cream-100'
                  : 'border-cream-100/12 bg-cream-100/[0.03] text-ink-300/80 hover:border-gold-400/30'
              "
              @click="pickFamily(tab.rule_family_code)"
            >
              {{ tab.rule_family_name }}
              <span v-if="!tab.ready" class="rounded bg-vermilion-500/20 px-1 text-[10px] text-vermilion-400">
                未就绪
              </span>
            </button>
            <span v-if="!tabs.length" class="text-xs text-ink-300/70">还没有可用的规则族</span>
          </div>
        </div>

        <div v-if="!loading">
          <div class="mb-2 flex items-center justify-between gap-2">
            <span class="text-xs text-ink-300/85">选择规则模板</span>
            <button type="button" class="text-[11px] text-gold-300/80 transition hover:text-gold-300" @click="goRules">
              去规则页新建
            </button>
          </div>

          <p
            v-if="!familyReady"
            class="mb-2 rounded-lg border border-vermilion-500/35 bg-vermilion-500/10 px-3 py-2 text-[11px] text-vermilion-400"
          >
            引擎未就绪：该规则族细则尚未配置完成，暂时不能开桌。
          </p>

          <div class="grid gap-2 sm:grid-cols-2">
            <button
              v-for="template in visibleTemplates"
              :key="template.id"
              type="button"
              class="relative rounded-xl border px-3.5 py-3 text-left transition disabled:cursor-not-allowed disabled:opacity-50"
              :class="
                selectedId === template.id
                  ? 'border-gold-400/60 bg-gold-400/10'
                  : 'border-cream-100/12 bg-cream-100/[0.03] hover:border-gold-400/30'
              "
              :disabled="!familyReady"
              @click="selectedId = template.id"
            >
              <div class="flex items-center gap-1.5">
                <span class="truncate text-sm font-medium text-cream-100">{{ template.template_name }}</span>
                <span
                  v-if="template.is_preset"
                  class="shrink-0 rounded bg-jade-500/20 px-1.5 py-0.5 text-[10px] text-jade-400"
                >
                  预置
                </span>
                <Check v-if="selectedId === template.id" class="ml-auto h-4 w-4 shrink-0 text-gold-300" />
              </div>
              <p class="mt-1 line-clamp-2 text-[11px] leading-relaxed text-ink-300/70">
                {{ template.description || describe(template) }}
              </p>
              <p class="mt-1.5 text-[10px] text-gold-400/70">{{ describe(template) }}</p>
            </button>
          </div>

          <div v-if="!visibleTemplates.length" class="rounded-xl border border-cream-100/10 bg-cream-100/[0.03] px-3 py-4 text-center">
            <p class="text-xs text-ink-300/75">这个规则族还没有模板</p>
            <button type="button" class="btn-ghost mt-2 rounded-lg px-3 py-1.5 text-[11px]" @click="goRules">
              去规则页创建
            </button>
          </div>
        </div>

        <div v-if="ruleDetail && familyReady" class="rounded-xl border border-cream-100/10 bg-felt-950/40 p-3 text-[11px] text-ink-300/80">
          <p class="mb-1 text-xs text-gold-300">这套规则会怎么算</p>
          <p class="leading-relaxed">
            {{ ruleDetail.fanMode }}，命中 {{ ruleDetail.fanCount }} 个可选番种；
            {{ ruleDetail.tingHint }}；一场 {{ ruleDetail.rounds }} 局。
          </p>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2 border-t border-cream-100/10 px-4 py-4 sm:px-6">
        <button type="button" class="btn-ghost rounded-lg px-4 py-2 text-sm" @click="emit('close')">取消</button>
        <button
          type="button"
          class="btn-gold flex items-center gap-2 rounded-lg px-5 py-2 text-sm font-semibold"
          :disabled="saving || !familyReady || !selectedId"
          @click="submit"
        >
          <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
          {{ saving ? '创建中…' : '开桌' }}
        </button>
      </div>
    </div>
  </div>
</template>
